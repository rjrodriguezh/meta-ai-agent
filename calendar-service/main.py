"""
google-calendar-service
Gestiona disponibilidad y eventos en Google Calendar para la clínica de Felipe.

Endpoints:
  GET  /health
  GET  /disponibilidad?fecha=YYYY-MM-DD          → slots libres del día
  GET  /disponibilidad/proximos?dias=7            → slots libres próximos N días
  POST /eventos                                   → crear evento (retorna event_id)
  DELETE /eventos/{event_id}                      → eliminar evento
"""

import os
import json
from datetime import date, datetime, timedelta, time
from typing import Optional

from fastapi import FastAPI, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from dotenv import load_dotenv

from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

load_dotenv("../.env")

app = FastAPI(title="google-calendar-service", version="1.0")

# ── Configuración ────────────────────────────────────────────────────────────

CALENDAR_ID    = os.getenv("GOOGLE_CALENDAR_ID", "primary")
SA_JSON        = os.getenv("GOOGLE_SERVICE_ACCOUNT_JSON")   # JSON completo como string
SA_FILE        = os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE")   # o ruta al archivo

# Horario de atención: Lunes a viernes, 9:00 a 18:00. Sábado y domingo cerrado.
DURACION_MIN   = 50          # duración de cada sesión en minutos
BUFFER_MIN     = 10          # buffer entre sesiones
HORARIOS_POR_DIA = {
    0: (time(9, 0), time(18, 0)),   # lunes
    1: (time(9, 0), time(18, 0)),   # martes
    2: (time(9, 0), time(18, 0)),   # miércoles
    3: (time(9, 0), time(18, 0)),   # jueves
    4: (time(9, 0), time(18, 0)),   # viernes
    # 5 = sábado, 6 = domingo: no están en el dict → cerrado
}

SCOPES = ["https://www.googleapis.com/auth/calendar"]


def get_credentials():
    if SA_JSON:
        info = json.loads(SA_JSON)
        return service_account.Credentials.from_service_account_info(info, scopes=SCOPES)
    if SA_FILE:
        return service_account.Credentials.from_service_account_file(SA_FILE, scopes=SCOPES)
    raise RuntimeError("Configura GOOGLE_SERVICE_ACCOUNT_JSON o GOOGLE_SERVICE_ACCOUNT_FILE en .env")


def get_service():
    creds = get_credentials()
    return build("calendar", "v3", credentials=creds, cache_discovery=False)


# ── Helpers ──────────────────────────────────────────────────────────────────

def slots_del_dia(fecha: date) -> list[str]:
    """Genera todos los slots posibles para un día (sin considerar ocupados)."""
    horario = HORARIOS_POR_DIA.get(fecha.weekday())
    if not horario:
        return []
    hora_inicio, hora_fin = horario

    slots = []
    cursor = datetime.combine(fecha, hora_inicio)
    fin    = datetime.combine(fecha, hora_fin)
    delta  = timedelta(minutes=DURACION_MIN + BUFFER_MIN)
    while cursor + timedelta(minutes=DURACION_MIN) <= fin:
        slots.append(cursor.strftime("%H:%M"))
        cursor += delta
    return slots


def eventos_del_dia(service, fecha: date) -> list[dict]:
    """Retorna los eventos de Google Calendar para la fecha dada."""
    tz      = "America/Santiago"
    inicio  = datetime.combine(fecha, time(0, 0)).isoformat() + "-04:00"
    fin_dia = datetime.combine(fecha + timedelta(days=1), time(0, 0)).isoformat() + "-04:00"
    try:
        result = service.events().list(
            calendarId=CALENDAR_ID,
            timeMin=inicio,
            timeMax=fin_dia,
            singleEvents=True,
            orderBy="startTime",
        ).execute()
        return result.get("items", [])
    except HttpError as e:
        raise HTTPException(status_code=502, detail=f"Google Calendar error: {e}")


def slots_libres(service, fecha: date) -> list[str]:
    """Slots del día que no están ocupados en Google Calendar."""
    if fecha.weekday() not in HORARIOS_POR_DIA:
        return []

    eventos = eventos_del_dia(service, fecha)
    ocupados = set()

    for ev in eventos:
        start_str = ev.get("start", {}).get("dateTime", "")
        end_str   = ev.get("end",   {}).get("dateTime", "")
        if not start_str:
            continue
        ev_start = datetime.fromisoformat(start_str)
        ev_end   = datetime.fromisoformat(end_str) if end_str else ev_start + timedelta(minutes=DURACION_MIN)
        # Marcar todos los slots que se superponen con este evento
        for slot_str in slots_del_dia(fecha):
            slot_dt  = datetime.combine(fecha, datetime.strptime(slot_str, "%H:%M").time())
            slot_end = slot_dt + timedelta(minutes=DURACION_MIN)
            if slot_dt < ev_end and slot_end > ev_start:
                ocupados.add(slot_str)

    return [s for s in slots_del_dia(fecha) if s not in ocupados]


# ── Modelos ──────────────────────────────────────────────────────────────────

class CrearEventoRequest(BaseModel):
    titulo:      str
    fecha:       str          # YYYY-MM-DD
    hora:        str          # HH:MM
    descripcion: Optional[str] = ""
    ubicacion:   Optional[str] = ""
    duracion:    Optional[int] = DURACION_MIN   # minutos


class EventoResponse(BaseModel):
    event_id:  str
    titulo:    str
    fecha:     str
    hora:      str
    link:      Optional[str] = None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok", "service": "google-calendar-service"}


@app.get("/disponibilidad")
def disponibilidad(fecha: str = Query(..., description="YYYY-MM-DD")):
    """Retorna los slots libres para la fecha indicada."""
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida. Formato: YYYY-MM-DD")

    service = get_service()
    libres  = slots_libres(service, d)

    return {
        "fecha":          fecha,
        "dia_semana":     d.strftime("%A"),
        "slots_libres":   libres,
        "total_libres":   len(libres),
        "disponible":     len(libres) > 0,
    }


@app.get("/disponibilidad/proximos")
def disponibilidad_proximos(dias: int = Query(7, ge=1, le=30)):
    """Retorna slots libres para los próximos N días laborales."""
    service  = get_service()
    hoy      = date.today()
    resultado = []

    for i in range(1, dias + 15):   # iterar más días para cubrir fines de semana
        d = hoy + timedelta(days=i)
        if d.weekday() not in HORARIOS_POR_DIA:
            continue
        libres = slots_libres(service, d)
        if libres:
            resultado.append({
                "fecha":        d.isoformat(),
                "dia_semana":   d.strftime("%A"),
                "slots_libres": libres,
            })
        if len(resultado) >= dias:
            break

    return {"dias": resultado, "total_dias": len(resultado)}


@app.post("/eventos", response_model=EventoResponse)
def crear_evento(req: CrearEventoRequest):
    """Crea un evento en Google Calendar y retorna el event_id."""
    try:
        d   = date.fromisoformat(req.fecha)
        h   = datetime.strptime(req.hora, "%H:%M").time()
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha u hora inválida")

    start_dt = datetime.combine(d, h)
    end_dt   = start_dt + timedelta(minutes=req.duracion)
    tz       = "America/Santiago"

    evento = {
        "summary":     req.titulo,
        "description": req.descripcion,
        "location":    req.ubicacion or "",
        "start":       {"dateTime": start_dt.isoformat(), "timeZone": tz},
        "end":         {"dateTime": end_dt.isoformat(),   "timeZone": tz},
        "colorId":     "2",   # verde
    }

    service = get_service()
    try:
        result = service.events().insert(calendarId=CALENDAR_ID, body=evento).execute()
    except HttpError as e:
        import traceback
        detail = f"Google Calendar error {e.resp.status}: {e.content.decode('utf-8', errors='replace')}"
        print(f"[GCal ERROR] {detail}")
        traceback.print_exc()
        raise HTTPException(status_code=502, detail=detail)

    return EventoResponse(
        event_id = result["id"],
        titulo   = result.get("summary", req.titulo),
        fecha    = req.fecha,
        hora     = req.hora,
        link     = result.get("htmlLink"),
    )


@app.delete("/eventos/{event_id}")
def eliminar_evento(event_id: str):
    """Elimina un evento de Google Calendar por su ID."""
    service = get_service()
    try:
        service.events().delete(calendarId=CALENDAR_ID, eventId=event_id).execute()
    except HttpError as e:
        if e.resp.status == 404:
            raise HTTPException(status_code=404, detail="Evento no encontrado")
        raise HTTPException(status_code=502, detail=f"Google Calendar error: {e}")

    return {"status": "ok", "event_id": event_id, "message": "Evento eliminado"}


@app.get("/eventos")
def listar_eventos(fecha: str = Query(..., description="YYYY-MM-DD")):
    """Lista los eventos del día (útil para debug/dashboard)."""
    try:
        d = date.fromisoformat(fecha)
    except ValueError:
        raise HTTPException(status_code=400, detail="Fecha inválida")

    service = get_service()
    eventos = eventos_del_dia(service, d)

    items = []
    for ev in eventos:
        start = ev.get("start", {}).get("dateTime", ev.get("start", {}).get("date", ""))
        end   = ev.get("end",   {}).get("dateTime", ev.get("end",   {}).get("date", ""))
        items.append({
            "event_id": ev.get("id"),
            "titulo":   ev.get("summary", "(sin título)"),
            "inicio":   start,
            "fin":      end,
        })

    return {"fecha": fecha, "eventos": items, "total": len(items)}
