import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import date, timedelta, datetime
from urllib.parse import quote

import requests
from fastapi import FastAPI, Form, Query
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from pydantic import BaseModel

SMTP_HOST = os.getenv("SMTP_HOST", "")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASS = os.getenv("SMTP_PASS", "")
FROM_EMAIL = os.getenv("FROM_EMAIL", SMTP_USER)

# ── Poner en False para deshabilitar el envío real de emails ──────────────
EMAIL_ENABLED = os.getenv("EMAIL_ENABLED", "false").lower() == "true"

app = FastAPI(title="Dashboard Agenda IA")

PATIENTS_URL    = os.getenv("PATIENTS_SERVICE_URL",    "http://localhost:8083")
AGENDA_URL      = os.getenv("AGENDA_SERVICE_URL",      "http://localhost:8082")
AI_URL          = os.getenv("AI_SERVICE_URL",          "http://localhost:8081")
ACTIVITIES_URL  = os.getenv("ACTIVITIES_SERVICE_URL",  "http://localhost:8084")
CALENDAR_URL    = os.getenv("CALENDAR_SERVICE_URL",    "http://localhost:8085")
CLINIC_LOCATION = os.getenv("CLINIC_LOCATION", "Clínica de Kinesiología Felipe Castillo")


def _gcal_build_desc(agen_id: int, pac_id: int, extra: str = "") -> tuple[str, str]:
    """Retorna (titulo, descripcion) enriquecidos para el evento GCal."""
    try:
        paciente = requests.get(f"{PATIENTS_URL}/patients/{pac_id}", timeout=3).json()
        nombre   = paciente.get("pac_nombre_corto", "Paciente")
        telefono = paciente.get("pac_telefono", "")
        maps_url = "https://maps.google.com/?q=San+Antonio+418,+Santiago,+Chile"
        diag = ""
        try:
            ficha = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas/activa", timeout=3).json()
            diag  = ficha.get("fic_diagnostico", "")
            total = ficha.get("fic_cantidad_sesiones", 0)
            real  = ficha.get("fic_sesiones_realizadas", 0)
            fid   = ficha.get("fic_id", "")
            pendientes = total - real
        except Exception:
            ficha, total, real, fid, pendientes = None, 0, 0, "", 0

        titulo = f"{diag} — Cita #{agen_id} — {nombre}" if diag else f"Cita #{agen_id} — {nombre}"

        lines = [
            f"👤 Paciente: {nombre}",
            f"📞 Teléfono: {telefono}",
        ]
        if ficha and diag:
            lines += [
                "",
                f"📋 Ficha #{fid}: {diag}",
                f"✅ Sesiones: {real} realizadas de {total} totales — {pendientes} pendientes",
            ]
        lines += [
            "",
            "📌 Instrucciones:",
            "• Llevar ropa cómoda y zapatillas",
            "• No aplicar cremas en la zona afectada",
            "• FONASA: traer bonos y orden médica el día de la cita",
            "",
            "🩺 Felipe Castillo y Tomas Sepúlveda",
            f"📍 {CLINIC_LOCATION}",
            f"🗺 {maps_url}",
        ]

        if extra:
            lines += ["", extra]

        return titulo, "\n".join(lines)
    except Exception:
        return f"Cita #{agen_id}", extra or "Agendado desde dashboard"


def gcal_eliminar(agen_id: int):
    """Obtiene el cal_event_id de la cita y lo elimina de Google Calendar."""
    try:
        cita = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json()
        event_id = cita.get("agen_cal_event_id", "")
        if event_id:
            requests.delete(f"{CALENDAR_URL}/eventos/{event_id}", timeout=5)
    except Exception:
        pass


def gcal_reagendar(agen_id: int, pac_id: int, nueva_fecha: str, nueva_hora: str, fecha_original: str = "", hora_original: str = ""):
    """Elimina el evento viejo de GCal y crea uno nuevo con la nueva fecha/hora."""
    try:
        cita = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json()
        event_id = cita.get("agen_cal_event_id", "")
        if event_id:
            requests.delete(f"{CALENDAR_URL}/eventos/{event_id}", timeout=5)
        extra = f"📅 Reagendado desde {fecha_original} {hora_original}" if fecha_original else "Reagendado desde dashboard"
        titulo, desc = _gcal_build_desc(agen_id, pac_id, extra=extra)
        titulo += " (reagendada)"
        body = {"titulo": titulo, "fecha": nueva_fecha, "hora": nueva_hora,
                "descripcion": desc, "ubicacion": CLINIC_LOCATION}
        resp = requests.post(f"{CALENDAR_URL}/eventos", json=body, timeout=5)
        if resp.ok:
            new_event_id = resp.json().get("event_id", "")
            if new_event_id:
                requests.patch(f"{AGENDA_URL}/agenda/{agen_id}/cal_event",
                               json={"cal_event_id": new_event_id}, timeout=3)
    except Exception:
        pass

# ── email de estado de cita ────────────────────────────────────────────────

def send_email_cita(pac_id: int, evento: str, fecha: str, hora: str,
                    agen_id: int = 0, fecha_orig: str = "", hora_orig: str = "") -> str:
    """
    evento: "agendada" | "reagendada" | "cancelada"
    Retorna un mensaje de notificación para mostrar en pantalla.
    Si EMAIL_ENABLED=False, no envía pero igual retorna el mensaje.
    """
    VERBO = {"agendada": "agendamiento", "reagendada": "reagendamiento",
             "cancelada": "cancelacion", "realizada": "sesion realizada"}
    verbo = VERBO.get(evento, evento)
    cita_ref = f"Cita #{agen_id}" if agen_id else f"cita del {fecha}"

    nombre, email = f"paciente #{pac_id}", ""
    try:
        pac    = requests.get(f"{PATIENTS_URL}/patients/{pac_id}", timeout=3).json()
        nombre = pac.get("pac_nombre_corto") or nombre
        email  = (pac.get("pac_email") or "").strip()
    except Exception:
        return f"Sin info del paciente #{pac_id} — no se pudo notificar ({verbo})"

    if not email:
        return f"Sin email registrado para {nombre} — no se envio notificacion de {verbo}"

    if not EMAIL_ENABLED:
        return f"[Email deshabilitado] Se notificaria a {nombre} ({email}) sobre {cita_ref} ({verbo})"

    hora_fmt = hora[:5] if hora else ""
    maps_url = "https://maps.google.com/?q=San+Antonio+418,+Santiago,+Chile"

    TEMAS = {
        "agendada":   ("✅ Cita confirmada",       "#16a34a", "#f0fdf4"),
        "reagendada": ("📅 Cita reagendada",        "#d97706", "#fffbeb"),
        "cancelada":  ("❌ Cita cancelada",          "#dc2626", "#fff1f2"),
        "realizada":  ("✔️ Sesión registrada",      "#3b82f6", "#eff6ff"),
    }
    asunto_pfx, color, bg = TEMAS.get(evento, ("Cita", "#075e54", "#f9fafb"))

    if evento == "agendada":
        titulo_body = "Tu cita ha sido confirmada"
        detalle = f"""
        <div style="background:{bg};border-left:4px solid {color};padding:16px;border-radius:4px;margin:16px 0">
            <b>📅 Fecha:</b> {fecha}<br>
            <b>⏰ Hora:</b> {hora_fmt}<br>
            <b>📍 Lugar:</b> {CLINIC_LOCATION}
        </div>
        <p>Recuerda:</p>
        <ul style="color:#555;font-size:14px">
            <li>Llevar ropa cómoda y zapatillas</li>
            <li>No aplicar cremas en la zona afectada</li>
            <li>FONASA: traer bonos y orden médica</li>
        </ul>
        <p><a href="{maps_url}" style="color:#075e54">📍 Ver ubicación en Google Maps</a></p>"""

    elif evento == "reagendada":
        titulo_body = "Tu cita ha sido reagendada"
        orig_str = f"<br><b>Fecha anterior:</b> {fecha_orig} {hora_orig[:5]}" if fecha_orig else ""
        detalle = f"""
        <div style="background:{bg};border-left:4px solid {color};padding:16px;border-radius:4px;margin:16px 0">
            <b>📅 Nueva fecha:</b> {fecha}<br>
            <b>⏰ Nueva hora:</b> {hora_fmt}{orig_str}<br>
            <b>📍 Lugar:</b> {CLINIC_LOCATION}
        </div>
        <p>Recuerda:</p>
        <ul style="color:#555;font-size:14px">
            <li>Llevar ropa cómoda y zapatillas</li>
            <li>No aplicar cremas en la zona afectada</li>
            <li>FONASA: traer bonos y orden médica</li>
        </ul>
        <p><a href="{maps_url}" style="color:#075e54">📍 Ver ubicación en Google Maps</a></p>"""

    elif evento == "realizada":
        titulo_body = "Tu sesión ha sido registrada"
        detalle = f"""
        <div style="background:{bg};border-left:4px solid {color};padding:16px;border-radius:4px;margin:16px 0">
            <b>📅 Fecha:</b> {fecha}<br>
            <b>⏰ Hora:</b> {hora_fmt}
        </div>
        <p style="color:#555">Gracias por asistir a tu sesión. Si tienes dudas sobre los ejercicios indicados, escríbenos por WhatsApp.</p>"""

    else:  # cancelada
        titulo_body = "Tu cita ha sido cancelada"
        detalle = f"""
        <div style="background:{bg};border-left:4px solid {color};padding:16px;border-radius:4px;margin:16px 0">
            <b>📅 Fecha cancelada:</b> {fecha}<br>
            <b>⏰ Hora:</b> {hora_fmt}
        </div>
        <p style="color:#555">Si deseas reagendar, comunícate con nosotros por WhatsApp o llámanos directamente.</p>"""

    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:auto">
        <div style="background:#075e54;padding:20px 24px;border-radius:8px 8px 0 0">
            <h1 style="color:white;margin:0;font-size:20px">{asunto_pfx}</h1>
        </div>
        <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
            <p>Hola <b>{nombre}</b>,</p>
            <p>{titulo_body}:</p>
            {detalle}
            <hr style="border:none;border-top:1px solid #e5e7eb;margin:20px 0">
            <p style="color:#9ca3af;font-size:12px">
                Felipe Castillo &amp; Tomás Sepúlveda — Kinesiología<br>
                {CLINIC_LOCATION}
            </p>
        </div>
    </div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"{asunto_pfx} — {fecha} {hora_fmt}"
    msg["From"]    = FROM_EMAIL
    msg["To"]      = email
    msg.attach(MIMEText(html, "html"))

    if not SMTP_HOST or not SMTP_USER or not SMTP_PASS:
        return f"⚠️ SMTP no configurado — no se envió notificación a {nombre}"

    try:
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.sendmail(FROM_EMAIL, email, msg.as_string())
        print(f"[email] {evento} enviado a {email} (pac_id={pac_id})", flush=True)
        return f"📧 Se notificó a {nombre} ({email}) sobre {cita_ref} ({verbo})"
    except Exception as e:
        print(f"[email] Error enviando {evento} a {email}: {e}", flush=True)
        return f"❌ Error al notificar a {nombre}: {e}"


# ── helpers ────────────────────────────────────────────────────────────────

def _notif_banner(msg: str) -> str:
    """Genera un banner de notificacion que se auto-cierra a los 10s."""
    if not msg:
        return ""
    # Detectar tipo por palabras clave (sin emojis para evitar issues de encoding)
    ml = msg.lower()
    if "deshabilitado" in ml or "desactivado" in ml:
        bg, border = "#fefce8", "#d97706"
        icono = "&#128276;"        # 🔕
    elif "sin email" in ml or "sin info" in ml:
        bg, border = "#fffbeb", "#f59e0b"
        icono = "&#9888;&#65039;"  # ⚠️
    elif "error" in ml:
        bg, border = "#fff1f2", "#f87171"
        icono = "&#10060;"         # ❌
    elif "notificaria" in ml or "notificó" in ml or "notifico" in ml:
        bg, border = "#f0fdf4", "#16a34a"
        icono = "&#128231;"        # 📧
    else:
        bg, border = "#eff6ff", "#3b82f6"
        icono = "&#128231;"        # 📧
    safe = msg.replace('"', '&quot;').replace('<', '&lt;').replace('>', '&gt;')
    return (
        f'<div id="notif-banner" style="background:{bg};border:1px solid {border};border-radius:10px;'
        f'padding:12px 18px;margin-bottom:16px;display:flex;align-items:center;'
        f'justify-content:space-between;font-size:13px;gap:12px">'
        f'<span>{icono}&nbsp; {safe}</span>'
        f'<button onclick="document.getElementById(\'notif-banner\').style.display=\'none\'"'
        f' style="background:none;border:none;cursor:pointer;color:#9ca3af;font-size:18px;'
        f'padding:0 4px;line-height:1">&#x2715;</button>'
        f'</div>'
        f'<script>setTimeout(function(){{var b=document.getElementById("notif-banner");'
        f'if(b)b.style.display="none";}},10000);</script>'
    )

def nav():
    return """
    <nav style="background:#075e54;padding:0;position:sticky;top:0;z-index:500;box-shadow:0 2px 8px rgba(0,0,0,.2)">
        <div style="display:flex;align-items:stretch;padding:0 24px;gap:0">

            <!-- Logo -->
            <a href="/dashboard" style="color:white;text-decoration:none;font-weight:800;font-size:17px;
                letter-spacing:.5px;padding:14px 20px 14px 0;margin-right:8px;border-right:1px solid rgba(255,255,255,.2)">
                🩺 KineApp
            </a>

            <!-- Dashboard directo -->
            <a href="/dashboard" class="nav-direct">Dashboard</a>

            <!-- Agenda grupo -->
            <div class="nav-group">
                <button class="nav-btn" onclick="toggleDrop('drop-agenda')">
                    Agenda <span style="font-size:10px">▼</span>
                </button>
                <div id="drop-agenda" class="nav-drop">
                    <a href="/calendario" class="drop-item">📅 Calendario semanal</a>
                    <a href="/agenda" class="drop-item">📋 Agenda diaria</a>
                </div>
            </div>

            <!-- Clínica grupo -->
            <div class="nav-group">
                <button class="nav-btn" onclick="toggleDrop('drop-clinica')">
                    Clínica <span style="font-size:10px">▼</span>
                </button>
                <div id="drop-clinica" class="nav-drop">
                    <div class="drop-label">👤 Pacientes</div>
                    <a href="/pacientes" class="drop-item">Lista de pacientes</a>
                    <a href="/pacientes/nuevo" class="drop-item">+ Nuevo paciente</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">📁 Fichas</div>
                    <a href="/fichas" class="drop-item">Fichas activas</a>
                    <a href="/buscar?tipo=fichas" class="drop-item">Buscar por diagnóstico</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">✅ Sesiones</div>
                    <a href="/sesiones?periodo=hoy" class="drop-item">Realizadas hoy</a>
                    <a href="/sesiones?periodo=semana" class="drop-item">Realizadas esta semana</a>
                    <a href="/sesiones?periodo=mes" class="drop-item">Realizadas este mes</a>
                    <a href="/sesiones?periodo=canceladas" class="drop-item">Canceladas</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">🏋 Ejercicios</div>
                    <a href="/ejercicios" class="drop-item">Biblioteca de ejercicios</a>
                    <a href="/ejercicios/nuevo" class="drop-item">+ Nuevo ejercicio</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">🩺 Diagnósticos</div>
                    <a href="/diagnosticos" class="drop-item">Lista de diagnósticos</a>
                    <a href="/diagnosticos/nuevo" class="drop-item">+ Nuevo diagnóstico</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">🤖 Bot WhatsApp</div>
                    <a href="/configuracion/bot" class="drop-item">⚙ Configurar personalidad</a>
                    <div class="drop-divider"></div>
                    <div class="drop-label">⚙ Administración</div>
                    <a href="/admin" class="drop-item">🗑 Resetear datos de prueba</a>
                </div>
            </div>

            <!-- Buscador central -->
            <div style="flex:1;display:flex;align-items:center;justify-content:center;padding:8px 24px">
                <div style="position:relative;width:100%;max-width:480px">
                    <form action="/buscar" method="get">
                        <input name="q" id="nav-search" type="text" autocomplete="off"
                            placeholder="🔍  Buscar paciente, ficha, diagnóstico..."
                            style="width:100%;padding:9px 16px;border-radius:24px;border:none;
                                font-size:14px;background:rgba(255,255,255,.15);color:white;
                                outline:none;margin:0"
                            oninput="buscarLive(this.value)"
                            onfocus="this.style.background='rgba(255,255,255,.25)'"
                            onblur="this.style.background='rgba(255,255,255,.15)';
                                    setTimeout(()=>document.getElementById('live-results').style.display='none',200)"
                        >
                    </form>
                    <div id="live-results" style="display:none;position:absolute;top:calc(100% + 6px);left:0;right:0;
                        background:white;border-radius:12px;box-shadow:0 8px 24px rgba(0,0,0,.2);
                        max-height:360px;overflow-y:auto;z-index:9999"></div>
                </div>
            </div>

            <!-- Agenda IA -->
            <a href="/agenda-ia" style="color:rgba(255,255,255,.8);text-decoration:none;font-size:13px;
                padding:14px 12px;display:flex;align-items:center;gap:5px;white-space:nowrap;
                border-left:1px solid rgba(255,255,255,.2);margin-left:8px">
                🤖 Agenda IA
            </a>
        </div>
    </nav>

    <style>
        .nav-group { position:relative; }
        .nav-direct {
            color:white;text-decoration:none;font-size:14px;font-weight:600;
            padding:14px 16px;display:flex;align-items:center;
            transition:background .15s;
        }
        .nav-direct:hover { background:rgba(255,255,255,.1); }
        .nav-btn {
            background:none;border:none;color:white;font-size:14px;font-weight:600;
            padding:14px 16px;cursor:pointer;height:100%;
            transition:background .15s;
        }
        .nav-btn:hover { background:rgba(255,255,255,.1); }
        .nav-drop {
            display:none;position:absolute;top:100%;left:0;
            background:white;border-radius:10px;min-width:210px;
            box-shadow:0 8px 24px rgba(0,0,0,.15);padding:8px 0;z-index:9999;
        }
        .nav-drop.open { display:block; }
        .drop-item {
            display:block;padding:9px 18px;color:#1f2937;text-decoration:none;
            font-size:13px;transition:background .1s;
        }
        .drop-item:hover { background:#f0fdf4;color:#075e54; }
        .drop-label {
            padding:8px 18px 4px;font-size:11px;font-weight:700;color:#9ca3af;
            text-transform:uppercase;letter-spacing:.6px;
        }
        .drop-divider { border-top:1px solid #f3f4f6;margin:6px 0; }
        input::placeholder { color:rgba(255,255,255,.6); }
    </style>

    <script>
    function toggleDrop(id) {
        const all = document.querySelectorAll('.nav-drop');
        all.forEach(d => { if (d.id !== id) d.classList.remove('open'); });
        document.getElementById(id).classList.toggle('open');
    }
    document.addEventListener('click', function(e) {
        if (!e.target.closest('.nav-group')) {
            document.querySelectorAll('.nav-drop').forEach(d => d.classList.remove('open'));
        }
    });

    let searchTimeout;
    async function buscarLive(q) {
        const box = document.getElementById('live-results');
        if (!q || q.length < 2) { box.style.display='none'; return; }
        clearTimeout(searchTimeout);
        searchTimeout = setTimeout(async () => {
            const res = await fetch('/api/buscar?q=' + encodeURIComponent(q));
            const data = await res.json();
            if (!data.length) { box.style.display='none'; return; }
            box.innerHTML = data.map(r => {
                const icon = r.tipo === 'paciente' ? '👤' : '📁';
                return `<a href="${r.url}" style="display:flex;align-items:center;gap:10px;
                    padding:10px 14px;text-decoration:none;color:#1f2937;border-bottom:1px solid #f3f4f6">
                    <span style="font-size:18px">${icon}</span>
                    <div>
                        <div style="font-weight:600;font-size:13px">${r.titulo}</div>
                        <div style="font-size:12px;color:#6b7280">${r.subtitulo}</div>
                    </div>
                </a>`;
            }).join('');
            box.style.display = 'block';
        }, 250);
    }
    </script>
    """

def layout(titulo: str, contenido: str) -> str:
    return f"""
    <!DOCTYPE html>
    <html>
    <head>
        <meta charset="UTF-8">
        <title>{titulo}</title>
        <style>
            * {{ box-sizing: border-box; }}
            body {{ font-family: Arial, sans-serif; background:#f4f6f8; margin:0; padding:0; }}
            nav a {{ color:white; text-decoration:none; }}
            .container {{ padding:30px; }}
            h1 {{ color:#075e54; }}
            .cards {{ display:grid; grid-template-columns:repeat(4,1fr); gap:20px; margin-top:20px; }}
            .card {{ background:white; border-radius:12px; padding:25px; box-shadow:0 2px 8px rgba(0,0,0,.08); }}
            .number {{ font-size:40px; font-weight:bold; color:#075e54; }}
            .label {{ margin-top:8px; color:#555; font-size:16px; }}
            table {{ width:100%; border-collapse:collapse; background:white; border-radius:8px; overflow:hidden; }}
            th, td {{ padding:12px; border-bottom:1px solid #eee; text-align:left; }}
            th {{ background:#075e54; color:white; }}
            tr:hover {{ background:#f9f9f9; }}
            a {{ color:#075e54; }}
            .btn {{ background:#075e54; color:white; border:none; padding:10px 18px; border-radius:8px; cursor:pointer; text-decoration:none; font-size:14px; }}
            .btn:hover {{ background:#064e46; }}
            .btn-danger {{ background:#b91c1c; }}
            input, textarea, select {{ width:100%; padding:10px; margin:6px 0 16px; border:1px solid #ccc; border-radius:8px; font-size:14px; }}
            label {{ font-weight:bold; color:#333; }}
            .form-card {{ background:white; padding:28px; border-radius:12px; box-shadow:0 2px 8px rgba(0,0,0,.08); max-width:500px; }}
            .badge {{ padding:4px 10px; border-radius:20px; font-size:12px; font-weight:bold; }}
            .badge-verde {{ background:#dcf8c6; color:#1a6e1a; }}
            .badge-amarillo {{ background:#fef9c3; color:#92400e; }}
            .badge-rojo {{ background:#fee2e2; color:#991b1b; }}
            .hora-libre {{ color:#aaa; }}
            .hora-ocupada {{ background:#dcf8c6; font-weight:bold; }}
        </style>
    </head>
    <body>
        {nav()}
        <div class="container">
            {contenido}
        </div>
    </body>
    </html>
    """

ESTADOS_ACTIVOS = {"agendada", "reagendada"}

BADGE_STYLES = {
    "agendada":  "background:#16a34a;color:white",
    "reagendada": "background:#84cc16;color:#1a2e05",
    "realizada":  "background:#3b82f6;color:white",
    "cancelada":  "background:#ef4444;color:white",
}

def badge_estado(estado: str) -> str:
    e = (estado or "").lower()
    style = BADGE_STYLES.get(e, "background:#9ca3af;color:white")
    return f'<span style="display:inline-block;padding:2px 10px;border-radius:12px;font-size:12px;font-weight:600;letter-spacing:.4px;{style}">{(estado or "").upper()}</span>'

def es_activa(cita: dict) -> bool:
    return (cita.get("agen_estado") or "").lower() in ESTADOS_ACTIVOS

# ── dashboard ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
def home():
    return RedirectResponse(url="/dashboard")

@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    hoy_d = date.today()
    hoy   = hoy_d.strftime("%Y-%m-%d")

    # Inicio de semana (lunes) e inicio de mes
    inicio_semana = (hoy_d - timedelta(days=hoy_d.weekday())).strftime("%Y-%m-%d")
    inicio_mes    = hoy_d.replace(day=1).strftime("%Y-%m-%d")

    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        pacientes = []

    pac_map = {p["pac_id"]: p for p in pacientes}

    # Cargar citas de los últimos 30 días + hoy (para stats)
    todas_citas = []
    for i in range(-30, 15):
        d = (hoy_d + timedelta(days=i)).strftime("%Y-%m-%d")
        try:
            todas_citas.extend(requests.get(f"{AGENDA_URL}/agenda/fecha/{d}", timeout=2).json())
        except Exception:
            pass

    agenda_hoy = [c for c in todas_citas if c.get("agen_fecha","") == hoy]

    # Stats
    realizadas_hoy    = [c for c in todas_citas if c.get("agen_fecha","") == hoy and (c.get("agen_estado","")).upper() == "REALIZADA"]
    realizadas_semana = [c for c in todas_citas if inicio_semana <= c.get("agen_fecha","") <= hoy and (c.get("agen_estado","")).upper() == "REALIZADA"]
    realizadas_mes    = [c for c in todas_citas if inicio_mes <= c.get("agen_fecha","") <= hoy and (c.get("agen_estado","")).upper() == "REALIZADA"]
    canceladas_mes    = [c for c in todas_citas if inicio_mes <= c.get("agen_fecha","") <= hoy and (c.get("agen_estado","")).upper() == "CANCELADA"]
    pendientes_hoy    = [c for c in agenda_hoy if es_activa(c)]

    fichas_activas = 0
    for p in pacientes:
        try:
            f = requests.get(f"{PATIENTS_URL}/patients/{p['pac_id']}/fichas/activa", timeout=2).json()
            if f and f.get("fic_id"):
                fichas_activas += 1
        except Exception:
            pass

    def stat_card(numero, label, link, color="#075e54", bg="white", icon=""):
        return f"""
        <a href="{link}" style="text-decoration:none">
        <div style="background:{bg};border-left:3px solid {color};border-radius:8px;
            padding:12px 16px;box-shadow:0 1px 4px rgba(0,0,0,.07);
            cursor:pointer;transition:transform .15s,box-shadow .15s"
            onmouseover="this.style.transform='translateY(-2px)';this.style.boxShadow='0 4px 12px rgba(0,0,0,.12)'"
            onmouseout="this.style.transform='';this.style.boxShadow='0 1px 4px rgba(0,0,0,.07)'">
            <div style="font-size:24px;font-weight:800;color:{color};line-height:1">{numero}</div>
            <div style="color:#555;font-size:12px;margin-top:4px">{icon} {label}</div>
            <div style="font-size:10px;color:{color};margin-top:4px;font-weight:600">Ver detalle →</div>
        </div>
        </a>"""

    # Tabla citas de hoy
    rows_hoy = ""
    for a in sorted(agenda_hoy, key=lambda x: x.get("agen_hora","")):
        pac = pac_map.get(a.get("pac_id"), {})
        rows_hoy += f"""<tr>
            <td>{a.get('agen_hora','')[:5]}</td>
            <td><a href="/pacientes/{a.get('pac_id')}">{pac.get('pac_nombre_corto','—')}</a></td>
            <td>{badge_estado(a.get('agen_estado',''))}</td>
            <td>{pac.get('pac_telefono','—')}</td>
        </tr>"""

    contenido = f"""
    <h1 style="margin-bottom:4px">Dashboard</h1>
    <p style="color:#6b7280;margin-top:0;margin-bottom:24px">{hoy_d.strftime('%A %d de %B %Y')}</p>

    <div style="display:grid;grid-template-columns:repeat(7,1fr);gap:10px;margin-bottom:28px">
        {stat_card(len(pacientes), "Pacientes activos", "/pacientes", "#075e54", "white", "👤")}
        {stat_card(fichas_activas, "Fichas activas", "/fichas", "#7c3aed", "white", "📁")}
        {stat_card(len(pendientes_hoy), "Pendientes hoy", "/sesiones?periodo=pendientes_hoy", "#d97706", "white", "⏳")}
        {stat_card(len(realizadas_hoy), "Realizadas hoy", "/sesiones?periodo=hoy", "#16a34a", "#f0fdf4", "✅")}
        {stat_card(len(realizadas_semana), "Esta semana", "/sesiones?periodo=semana", "#2563eb", "#eff6ff", "📆")}
        {stat_card(len(realizadas_mes), "Este mes", "/sesiones?periodo=mes", "#0891b2", "#ecfeff", "📊")}
        {stat_card(len(canceladas_mes), "Canceladas mes", "/sesiones?periodo=canceladas", "#dc2626", "#fff1f2", "❌")}
    </div>

    <h2 style="color:#374151;font-size:16px;margin-bottom:12px">Agenda de hoy — {hoy}</h2>
    <table>
        <thead><tr><th>Hora</th><th>Paciente</th><th>Estado</th><th>Teléfono</th></tr></thead>
        <tbody>{rows_hoy if rows_hoy else '<tr><td colspan="4" style="color:#aaa;padding:16px">Sin citas hoy</td></tr>'}</tbody>
    </table>
    """
    return layout("Dashboard", contenido)


# ── fichas activas ──────────────────────────────────────────────────────────

@app.get("/fichas", response_class=HTMLResponse)
def fichas_page(estado: str = Query(""), q: str = Query("")):
    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        pacientes = []

    # Recopilar todas las fichas con su paciente
    todas = []
    for p in pacientes:
        try:
            fichas = requests.get(f"{PATIENTS_URL}/patients/{p['pac_id']}/fichas", timeout=2).json()
        except Exception:
            fichas = []
        for f in fichas:
            todas.append((p, f))

    # Aplicar filtros
    filtradas = todas
    if estado:
        filtradas = [(p,f) for p,f in filtradas if f.get("fic_estado","").upper() == estado.upper()]
    if q:
        ql = q.lower()
        filtradas = [(p,f) for p,f in filtradas
                     if ql in p.get("pac_nombre_corto","").lower()
                     or ql in p.get("pac_nombres","").lower()
                     or ql in p.get("pac_apellidos","").lower()
                     or ql in f.get("fic_diagnostico","").lower()]

    # Conteos para badges de filtro
    total     = len(todas)
    n_activas = sum(1 for _,f in todas if f.get("fic_estado","").upper() == "ACTIVA")
    n_fin     = sum(1 for _,f in todas if f.get("fic_estado","").upper() == "FINALIZADA")

    def tab(label, val, count, color, bg):
        activo = estado == val
        return (f'<a href="/fichas?estado={val}&q={q}" '
                f'style="display:inline-flex;align-items:center;gap:6px;padding:7px 16px;border-radius:20px;'
                f'text-decoration:none;font-size:13px;font-weight:600;border:2px solid {color};'
                f'{"background:"+color+";color:white" if activo else "background:"+bg+";color:"+color}">'
                f'{label}'
                f'<span style="background:{"rgba(255,255,255,.3)" if activo else color};color:{"white" if activo else "white"};'
                f'border-radius:10px;padding:1px 7px;font-size:11px">{count}</span>'
                f'</a>')

    tabs_html = (
        tab("Todas", "", total, "#374151", "#f3f4f6") +
        tab("Activas", "ACTIVA", n_activas, "#16a34a", "#f0fdf4") +
        tab("Finalizadas", "FINALIZADA", n_fin, "#6b7280", "#f9fafb")
    )

    rows = ""
    for p, f in filtradas:
        estado_f = (f.get("fic_estado","")).upper()
        if estado_f == "ACTIVA":
            badge = '<span style="background:#16a34a;color:white;padding:2px 10px;border-radius:10px;font-size:12px">ACTIVA</span>'
        else:
            badge = '<span style="background:#9ca3af;color:white;padding:2px 10px;border-radius:10px;font-size:12px">FINALIZADA</span>'

        diag_txt = f.get('fic_diagnostico','')
        rows += f"""<tr>
            <td><a href="/pacientes/{p['pac_id']}" style="color:#075e54;font-weight:600">{p.get('pac_nombre_corto') or p.get('pac_nombres','—')}</a></td>
            <td>{diag_txt or '—'}</td>
            <td>{badge}</td>
            <td style="text-align:center">{f.get('fic_cantidad_sesiones',0)}</td>
            <td style="font-size:12px;color:#6b7280">{f.get('fic_observacion','') or '—'}</td>
            <td style="white-space:nowrap">
                <a href="/pacientes/{p['pac_id']}" class="btn" style="font-size:12px;padding:4px 10px">Ver</a>
                <a href="/ejercicios/por-diagnostico?texto={quote(diag_txt)}" class="btn" style="font-size:12px;padding:4px 10px;background:#7c3aed">🏋 Ejercicios</a>
            </td>
        </tr>"""

    contenido = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h1 style="margin:0">Fichas clínicas</h1>
    </div>

    <!-- Filtros de estado -->
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
        {tabs_html}
    </div>

    <!-- Búsqueda por nombre / diagnóstico -->
    <form method="get" action="/fichas" style="margin-bottom:20px">
        <input type="hidden" name="estado" value="{estado}">
        <div style="display:flex;gap:8px;max-width:480px">
            <input name="q" value="{q}" placeholder="Buscar por paciente o diagnóstico..."
                style="flex:1;margin:0;padding:9px 14px">
            <button class="btn" type="submit">Buscar</button>
            {'<a href="/fichas?estado='+estado+'" class="btn" style="background:#6b7280">✕</a>' if q else ''}
        </div>
    </form>

    <!-- Tabla -->
    <table>
        <thead><tr><th>Paciente</th><th>Diagnóstico</th><th>Estado</th><th style="text-align:center">Sesiones</th><th>Observación</th><th></th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="6" style="color:#aaa;padding:20px;text-align:center">Sin fichas</td></tr>'}</tbody>
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:8px">{len(filtradas)} fichas mostradas</p>
    """
    return layout("Fichas", contenido)


# ── sesiones por período ────────────────────────────────────────────────────

@app.get("/sesiones", response_class=HTMLResponse)
def sesiones_page(periodo: str = Query("mes")):
    hoy_d = date.today()
    hoy   = hoy_d.strftime("%Y-%m-%d")

    if periodo == "hoy":
        fechas = [hoy]
        titulo = f"Sesiones realizadas hoy — {hoy}"
        estado_filtro = {"REALIZADA"}
    elif periodo == "semana":
        inicio = hoy_d - timedelta(days=hoy_d.weekday())
        fechas = [(inicio + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
        titulo = f"Sesiones realizadas esta semana"
        estado_filtro = {"REALIZADA"}
    elif periodo == "canceladas":
        inicio = hoy_d.replace(day=1)
        dias_mes = (hoy_d - inicio).days + 1
        fechas = [(inicio + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_mes)]
        titulo = "Sesiones canceladas este mes"
        estado_filtro = {"CANCELADA"}
    elif periodo == "pendientes_hoy":
        fechas = [hoy]
        titulo = f"Pendientes hoy — {hoy}"
        estado_filtro = {"AGENDADA", "REAGENDADA"}
    else:  # mes
        inicio = hoy_d.replace(day=1)
        dias_mes = (hoy_d - inicio).days + 1
        fechas = [(inicio + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(dias_mes)]
        titulo = "Sesiones realizadas este mes"
        estado_filtro = {"REALIZADA"}

    citas = []
    for f in fechas:
        try:
            dia = requests.get(f"{AGENDA_URL}/agenda/fecha/{f}", timeout=2).json()
            citas.extend([c for c in dia if (c.get("agen_estado","")).upper() in estado_filtro])
        except Exception:
            pass
    citas.sort(key=lambda x: (x.get("agen_fecha",""), x.get("agen_hora","")))

    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
        pac_map = {p["pac_id"]: p for p in pacientes}
    except Exception:
        pac_map = {}

    rows = ""
    for c in citas:
        pac = pac_map.get(c.get("pac_id"), {})
        rows += f"""<tr>
            <td>{c.get('agen_fecha','')}</td>
            <td>{c.get('agen_hora','')[:5]}</td>
            <td><a href="/pacientes/{c.get('pac_id')}">{pac.get('pac_nombre_corto','—')}</a></td>
            <td>{badge_estado(c.get('agen_estado',''))}</td>
            <td style="font-size:12px;color:#6b7280">{c.get('agen_observacion','') or '—'}</td>
        </tr>"""

    # Links a otros períodos
    tabs = ""
    for p, label in [("hoy","Hoy"),("semana","Esta semana"),("mes","Este mes"),("canceladas","Canceladas")]:
        activo = p == periodo
        tabs += f'<a href="/sesiones?periodo={p}" style="padding:8px 16px;border-radius:20px;text-decoration:none;font-size:13px;font-weight:600;{"background:#075e54;color:white" if activo else "background:white;color:#374151;border:1px solid #e5e7eb"}">{label}</a>'

    contenido = f"""
    <h1 style="margin-bottom:16px">{titulo}</h1>
    <div style="display:flex;gap:8px;margin-bottom:24px">{tabs}</div>
    <table>
        <thead><tr><th>Fecha</th><th>Hora</th><th>Paciente</th><th>Estado</th><th>Observación</th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="5" style="color:#aaa;padding:16px">Sin sesiones en este período</td></tr>'}</tbody>
    </table>
    <p style="color:#9ca3af;font-size:13px;margin-top:12px">Total: <b>{len(citas)}</b> sesiones</p>"""
    return layout("Sesiones", contenido)

# ── calendario ─────────────────────────────────────────────────────────────

@app.get("/calendario", response_class=HTMLResponse)
def calendario(semana: int = 0, notif: str = Query("")):
    hoy = date.today()
    # semana=0 → semana actual, semana=1 → próxima, semana=-1 → anterior
    inicio = hoy - timedelta(days=hoy.weekday()) + timedelta(weeks=semana)
    dias = [inicio + timedelta(days=i) for i in range(7)]

    citas_por_dia = {}
    for d in dias:
        fecha = d.strftime("%Y-%m-%d")
        try:
            citas_por_dia[fecha] = requests.get(f"{AGENDA_URL}/agenda/fecha/{fecha}", timeout=3).json()
        except Exception:
            citas_por_dia[fecha] = []

    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        pacientes = []

    pac_map  = {p["pac_id"]: p["pac_nombre_corto"] for p in pacientes}
    pac_list = sorted(pacientes, key=lambda p: p.get("pac_nombre_corto",""))

    todas_citas = [c for citas in citas_por_dia.values() for c in citas]
    horas = sorted(set(c.get("agen_hora","")[:5] for c in todas_citas if c.get("agen_hora")))
    if not horas:
        horas = ["09:00"]

    # Colores por estado (igual que en fichas)
    COLOR_CAL = {
        "AGENDADA":   ("background:#f0fdf4;border-left:3px solid #16a34a", "#16a34a"),
        "REAGENDADA": ("background:#f7fee7;border-left:3px solid #84cc16", "#84cc16"),
        "REALIZADA":  ("background:#eff6ff;border-left:3px solid #3b82f6", "#3b82f6"),
        "CANCELADA":  ("background:#fff1f2;border-left:3px solid #f87171", "#f87171"),
    }

    header = "".join(
        f'<th style="min-width:130px">{d.strftime("%a")}<br><small>{d.strftime("%d/%m")}</small></th>'
        for d in dias
    )

    filas = ""
    for h in horas:
        filas += f'<tr><td style="white-space:nowrap;padding:6px 10px;color:#555;font-size:13px"><b>{h}</b></td>'
        for d in dias:
            fecha = d.strftime("%Y-%m-%d")
            cita = next(
                (c for c in citas_por_dia[fecha] if c.get("agen_hora","")[:5] == h),
                None
            )
            if cita:
                estado = (cita.get("agen_estado") or "").upper()
                nombre = pac_map.get(cita.get("pac_id"), "—")
                style, color = COLOR_CAL.get(estado, ("background:#f3f4f6", "#374151"))
                agen_id = cita.get("agen_id")
                pac_id  = cita.get("pac_id")
                filas += (
                    f'<td data-cita="1" data-estado="{estado}" data-pac="{pac_id}" '
                    f'style="{style};padding:6px 8px;cursor:pointer;font-size:12px" '
                    f'onclick="abrirCita({agen_id},{pac_id},\'{fecha}\',\'{h}\',\'{estado}\',\'{nombre}\')">'
                    f'<b style="color:{color}">{nombre}</b><br>'
                    f'<span style="color:{color};font-size:11px">{estado}</span>'
                    f'</td>'
                )
            else:
                filas += (
                    f'<td style="color:#d1d5db;text-align:center;cursor:pointer;font-size:18px" '
                    f'onclick="abrirNueva(\'{fecha}\',\'{h}\')">+</td>'
                )
        filas += "</tr>"

    # Opciones de pacientes para el select
    pac_options = "".join(
        f'<option value="{p["pac_id"]}">{p.get("pac_nombre_corto","")} — {p.get("pac_telefono","")}</option>'
        for p in pac_list
    )

    sem_anterior = semana - 1
    sem_siguiente = semana + 1
    rango = f'{dias[0].strftime("%d/%m")} — {dias[6].strftime("%d/%m/%Y")}'

    pac_options_filtro = "".join(
        f'<option value="{p["pac_id"]}">{p.get("pac_nombre_corto","")}</option>'
        for p in pac_list
    )

    notif_html = _notif_banner(notif)

    contenido = f"""
    {notif_html}
    <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px">
        <h1 style="margin:0">Calendario semanal</h1>
        <div style="display:flex;align-items:center;gap:12px">
            <a href="/calendario?semana={sem_anterior}" class="btn" style="padding:6px 14px">◀ Anterior</a>
            <span style="font-weight:600;color:#075e54">{rango}</span>
            <a href="/calendario?semana={sem_siguiente}" class="btn" style="padding:6px 14px">Siguiente ▶</a>
            <a href="/calendario?semana=0" class="btn" style="padding:6px 14px;background:#6b7280">Hoy</a>
        </div>
    </div>

    <!-- Filtros -->
    <div style="display:flex;gap:14px;align-items:center;flex-wrap:wrap;margin-bottom:14px;
                background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:10px 16px">
        <span style="font-weight:600;color:#374151;font-size:13px">Estado:</span>
        <div style="display:flex;gap:6px;flex-wrap:wrap">
            <button id="fb-todos" onclick="filtrarEstado('')"
                style="padding:4px 12px;border-radius:20px;border:1px solid #075e54;
                       background:#075e54;color:white;cursor:pointer;font-size:12px">Todos</button>
            <button id="fb-AGENDADA" onclick="filtrarEstado('AGENDADA')"
                style="padding:4px 12px;border-radius:20px;border:1px solid #16a34a;
                       background:white;color:#16a34a;cursor:pointer;font-size:12px">● Agendada</button>
            <button id="fb-REAGENDADA" onclick="filtrarEstado('REAGENDADA')"
                style="padding:4px 12px;border-radius:20px;border:1px solid #84cc16;
                       background:white;color:#65a30d;cursor:pointer;font-size:12px">● Reagendada</button>
            <button id="fb-REALIZADA" onclick="filtrarEstado('REALIZADA')"
                style="padding:4px 12px;border-radius:20px;border:1px solid #3b82f6;
                       background:white;color:#3b82f6;cursor:pointer;font-size:12px">● Realizada</button>
            <button id="fb-CANCELADA" onclick="filtrarEstado('CANCELADA')"
                style="padding:4px 12px;border-radius:20px;border:1px solid #f87171;
                       background:white;color:#f87171;cursor:pointer;font-size:12px">● Cancelada</button>
        </div>
        <span style="font-weight:600;color:#374151;font-size:13px;margin-left:8px">Paciente:</span>
        <select id="filt-pac" onchange="filtrarPaciente(this.value)"
            style="padding:4px 10px;border:1px solid #d1d5db;border-radius:8px;font-size:13px;
                   background:white;color:#374151;min-width:180px">
            <option value="">— Todos —</option>
            {pac_options_filtro}
        </select>
        <button onclick="limpiarFiltros()"
            style="padding:4px 10px;border-radius:8px;border:1px solid #d1d5db;
                   background:white;color:#6b7280;cursor:pointer;font-size:12px;margin-left:4px">✕ Limpiar</button>
    </div>

    <div style="overflow-x:auto">
    <table style="min-width:900px">
        <thead><tr><th style="width:60px">Hora</th>{header}</tr></thead>
        <tbody>{filas}</tbody>
    </table>
    </div>

    <!-- Modal gestión de cita existente -->
    <div id="modal-cita" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;align-items:center;justify-content:center">
        <div style="background:white;border-radius:12px;padding:28px;width:420px;max-width:95vw;box-shadow:0 20px 60px rgba(0,0,0,.3)">
            <h2 id="modal-titulo" style="margin:0 0 16px;color:#075e54"></h2>
            <p id="modal-info" style="color:#555;margin:0 0 20px"></p>
            <div id="modal-acciones" style="display:flex;flex-direction:column;gap:10px"></div>
            <hr style="margin:16px 0">
            <button onclick="cerrarModal()" style="color:#888;background:none;border:none;cursor:pointer;font-size:14px">✕ Cerrar</button>
        </div>
    </div>

    <!-- Modal nueva cita -->
    <div id="modal-nueva" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.5);z-index:1000;align-items:center;justify-content:center">
        <div style="background:white;border-radius:12px;padding:28px;width:460px;max-width:95vw;box-shadow:0 20px 60px rgba(0,0,0,.3)">
            <h2 style="margin:0 0 16px;color:#075e54">Nueva Cita</h2>
            <form method="post" action="/calendario/nueva-cita" id="form-nueva-cal"
                  onsubmit="if(!document.getElementById('pac-id-hidden').value){{alert('Selecciona un paciente');return false;}}"
                <input type="hidden" name="semana" value="{semana}">
                <label>Fecha</label>
                <input type="date" name="fecha" id="nueva-fecha" required style="margin-bottom:10px">
                <label>Hora</label>
                <input type="time" name="hora" id="nueva-hora" required step="1800" style="margin-bottom:10px">
                <label>Paciente</label>
                <div style="position:relative;margin-bottom:10px">
                    <input type="text" id="pac-buscar" placeholder="Buscar por nombre o teléfono..."
                        oninput="filtrarPacientes(this.value)"
                        style="width:100%;box-sizing:border-box">
                    <div id="pac-dropdown" style="display:none;position:absolute;top:100%;left:0;right:0;
                        background:white;border:1px solid #e5e7eb;border-radius:8px;max-height:180px;
                        overflow-y:auto;z-index:10;box-shadow:0 4px 12px rgba(0,0,0,.1)"></div>
                </div>
                <input type="hidden" name="pac_id" id="pac-id-hidden" required>
                <div id="pac-seleccionado" style="display:none;background:#f0fdf4;border:1px solid #16a34a;
                    border-radius:6px;padding:8px 12px;margin-bottom:10px;font-size:13px;color:#075e54"></div>
                <label>Observación (opcional)</label>
                <textarea name="observacion" rows="2" style="margin-bottom:14px"></textarea>
                <div style="display:flex;gap:10px">
                    <button type="submit" class="btn" style="flex:1">✓ Agendar</button>
                    <button type="button" onclick="cerrarModalNueva()"
                        style="flex:1;background:#e5e7eb;color:#374151;border:none;border-radius:8px;cursor:pointer;padding:10px">Cancelar</button>
                </div>
            </form>
        </div>
    </div>

    <script>
    const PACIENTES = {pac_list};

    /* ── Filtros ── */
    let _filtroEstado = '';
    let _filtroPac    = '';

    function aplicarFiltros() {{
        document.querySelectorAll('[data-cita]').forEach(td => {{
            const estadoOk = !_filtroEstado || td.dataset.estado === _filtroEstado;
            const pacOk    = !_filtroPac    || td.dataset.pac    === _filtroPac;
            if (estadoOk && pacOk) {{
                td.style.opacity = '1';
                td.style.pointerEvents = '';
            }} else {{
                td.style.opacity = '0.12';
                td.style.pointerEvents = 'none';
            }}
        }});
    }}

    function filtrarEstado(e) {{
        _filtroEstado = e;
        // highlight active button
        const ids = ['fb-todos','fb-AGENDADA','fb-REAGENDADA','fb-REALIZADA','fb-CANCELADA'];
        ids.forEach(id => {{
            const b = document.getElementById(id);
            if (!b) return;
            const key = id === 'fb-todos' ? '' : id.replace('fb-','');
            const activo = key === e;
            const colors = {{
                '': ['#075e54','white'],
                'AGENDADA': ['#16a34a','white'],
                'REAGENDADA': ['#84cc16','white'],
                'REALIZADA': ['#3b82f6','white'],
                'CANCELADA': ['#f87171','white'],
            }};
            const [bg, fg] = activo ? (colors[key] || ['#6b7280','white']) : ['white', colors[key]?.[0] || '#374151'];
            b.style.background = bg;
            b.style.color = fg;
        }});
        aplicarFiltros();
    }}

    function filtrarPaciente(v) {{
        _filtroPac = v;
        aplicarFiltros();
    }}

    function limpiarFiltros() {{
        _filtroEstado = '';
        _filtroPac = '';
        document.getElementById('filt-pac').value = '';
        filtrarEstado('');
    }}

    function filtrarPacientes(q) {{
        const dd = document.getElementById('pac-dropdown');
        if (!q) {{ dd.style.display='none'; return; }}
        const ql = q.toLowerCase();
        const matches = PACIENTES.filter(p =>
            (p.pac_nombre_corto||'').toLowerCase().includes(ql) ||
            (p.pac_telefono||'').includes(q)
        ).slice(0, 8);
        if (!matches.length) {{ dd.style.display='none'; return; }}
        dd.innerHTML = matches.map(p =>
            `<div onclick="seleccionarPac(${{p.pac_id}}, '${{p.pac_nombre_corto}}', '${{p.pac_telefono}}')"
                style="padding:10px 14px;cursor:pointer;font-size:13px;border-bottom:1px solid #f3f4f6"
                onmouseover="this.style.background='#f0fdf4'" onmouseout="this.style.background='white'">
                <b>${{p.pac_nombre_corto}}</b> — ${{p.pac_telefono}}
            </div>`
        ).join('');
        dd.style.display = 'block';
    }}

    function seleccionarPac(id, nombre, tel) {{
        document.getElementById('pac-id-hidden').value = id;
        document.getElementById('pac-buscar').value = nombre;
        const sel = document.getElementById('pac-seleccionado');
        sel.textContent = '✓ ' + nombre + ' (' + tel + ')';
        sel.style.display = 'block';
        document.getElementById('pac-dropdown').style.display = 'none';
    }}

    function abrirNueva(fecha, hora) {{
        document.getElementById('nueva-fecha').value = fecha;
        document.getElementById('nueva-hora').value = hora;
        document.getElementById('pac-buscar').value = '';
        document.getElementById('pac-id-hidden').value = '';
        document.getElementById('pac-seleccionado').style.display = 'none';
        document.getElementById('pac-dropdown').style.display = 'none';
        document.getElementById('modal-nueva').style.display = 'flex';
    }}

    function cerrarModalNueva() {{
        document.getElementById('modal-nueva').style.display = 'none';
    }}

    function abrirCita(agenId, pacId, fecha, hora, estado, nombre) {{
        document.getElementById('modal-titulo').textContent = nombre;
        document.getElementById('modal-info').innerHTML =
            `<b>Fecha:</b> ${{fecha}} &nbsp; <b>Hora:</b> ${{hora}} &nbsp; <b>Estado:</b> ${{estado}}`;

        let btns = '';
        if (estado === 'AGENDADA' || estado === 'REAGENDADA') {{
            btns += `<a href="/cita/${{agenId}}/realizar?pac_id=${{pacId}}&from=calendario&semana={semana}"
                class="btn" style="text-align:center">✓ Marcar realizada</a>`;
            btns += `<a href="/cita/${{agenId}}/reagendar?pac_id=${{pacId}}&from=calendario&semana={semana}"
                class="btn" style="background:#d97706;text-align:center">📅 Reagendar</a>`;
            btns += `<form method="post" action="/cita/${{agenId}}/cancelar">
                <input type="hidden" name="pac_id" value="${{pacId}}">
                <input type="hidden" name="from" value="calendario">
                <input type="hidden" name="semana" value="{semana}">
                <button class="btn btn-danger" style="width:100%;text-align:center"
                    onclick="return confirm('¿Cancelar esta cita?')">✕ Cancelar cita</button>
            </form>`;
        }} else if (estado === 'REALIZADA') {{
            btns += `<form method="post" action="/cita/${{agenId}}/desmarcar">
                <input type="hidden" name="pac_id" value="${{pacId}}">
                <input type="hidden" name="from" value="calendario">
                <input type="hidden" name="semana" value="{semana}">
                <button class="btn btn-danger" style="width:100%;text-align:center">↩ Desmarcar realizada</button>
            </form>`;
        }}
        btns += `<a href="/pacientes/${{pacId}}" class="btn"
            style="background:#6b7280;text-align:center">👤 Ver paciente</a>`;

        document.getElementById('modal-acciones').innerHTML = btns;
        document.getElementById('modal-cita').style.display = 'flex';
    }}

    function cerrarModal() {{
        document.getElementById('modal-cita').style.display = 'none';
    }}

    document.getElementById('modal-cita').addEventListener('click', function(e) {{
        if (e.target === this) cerrarModal();
    }});
    document.getElementById('modal-nueva').addEventListener('click', function(e) {{
        if (e.target === this) cerrarModalNueva();
    }});
    </script>
    """
    return layout("Calendario", contenido)

@app.post("/calendario/nueva-cita")
def calendario_nueva_cita(
    pac_id: int = Form(...),
    fecha: str = Form(...),
    hora: str = Form(...),
    observacion: str = Form(""),
    semana: int = Form(0)
):
    # Buscar ficha activa del paciente
    fic_id = None
    try:
        ficha = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas/activa", timeout=3).json()
        fic_id = ficha.get("fic_id")
    except Exception:
        pass

    body = {"pac_id": pac_id, "fic_id": fic_id, "fecha": fecha, "hora": hora, "observacion": observacion}
    resp = requests.post(f"{AGENDA_URL}/agenda", json=body, timeout=3)
    # Crear evento en Google Calendar
    try:
        cita = resp.json()
        agen_id = cita.get("agen_id")
        if agen_id:
            titulo, desc = _gcal_build_desc(agen_id, pac_id)
            gcal_body = {"titulo": titulo, "fecha": fecha, "hora": hora,
                         "descripcion": desc, "ubicacion": CLINIC_LOCATION}
            gcal_resp = requests.post(f"{CALENDAR_URL}/eventos", json=gcal_body, timeout=5)
            if gcal_resp.ok:
                event_id = gcal_resp.json().get("event_id", "")
                if event_id:
                    requests.patch(f"{AGENDA_URL}/agenda/{agen_id}/cal_event",
                                   json={"cal_event_id": event_id}, timeout=3)
    except Exception:
        pass
    # Email confirmación
    notif = send_email_cita(pac_id, "agendada", fecha, hora, agen_id=agen_id or 0)
    return RedirectResponse(url=f"/calendario?semana={semana}&notif={quote(notif, safe='')}", status_code=303)

# ── agenda ─────────────────────────────────────────────────────────────────

@app.get("/agenda", response_class=HTMLResponse)
def agenda_page(fm: str = Query(""), ff: str = Query("")):
    hoy = date.today()
    manana_d = hoy + timedelta(days=1)
    manana   = manana_d.strftime("%Y-%m-%d")
    dias_futuros = [hoy + timedelta(days=i) for i in range(2, 16)]

    try:
        citas_manana_todas = requests.get(f"{AGENDA_URL}/agenda/fecha/{manana}", timeout=3).json()
    except Exception:
        citas_manana_todas = []

    futuras_todas = []
    for d in dias_futuros:
        try:
            futuras_todas.extend(requests.get(f"{AGENDA_URL}/agenda/fecha/{d.strftime('%Y-%m-%d')}", timeout=3).json())
        except Exception:
            pass

    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        pacientes = []

    pac_map = {p["pac_id"]: p for p in pacientes}

    def chips(base_fm, base_ff, param, actual, conteos):
        DEFS = [
            ("",           "Todas",      "#374151"),
            ("AGENDADA",   "Agendada",   "#16a34a"),
            ("REAGENDADA", "Reagendada", "#84cc16"),
            ("REALIZADA",  "Realizada",  "#3b82f6"),
            ("CANCELADA",  "Cancelada",  "#ef4444"),
        ]
        total = sum(conteos.values())
        html = ""
        for val, label, color in DEFS:
            n = total if not val else conteos.get(val, 0)
            if val and n == 0:
                continue
            activo = actual == val
            url = f"/agenda?fm={base_fm}&ff={base_ff}"
            if param == "fm":
                url = f"/agenda?fm={val}&ff={base_ff}"
            else:
                url = f"/agenda?fm={base_fm}&ff={val}"
            html += (
                f'<a href="{url}" style="display:inline-flex;align-items:center;gap:5px;padding:5px 14px;'
                f'border-radius:20px;text-decoration:none;font-size:12px;font-weight:600;'
                f'border:2px solid {color};margin-right:4px;'
                f'{"background:"+color+";color:white" if activo else "color:"+color}">'
                f'{label} <span style="background:{"rgba(255,255,255,.35)" if activo else color};color:white;'
                f'border-radius:8px;padding:0 6px;font-size:11px">{n}</span></a>'
            )
        return f'<div style="display:flex;flex-wrap:wrap;gap:4px;margin-bottom:12px">{html}</div>'

    # ── MAÑANA ──────────────────────────────────────────────────────────────
    citas_manana_todas.sort(key=lambda x: x.get("agen_hora",""))
    conteos_m = {}
    for a in citas_manana_todas:
        e = (a.get("agen_estado","")).upper()
        conteos_m[e] = conteos_m.get(e, 0) + 1

    citas_manana_vis = [a for a in citas_manana_todas
                        if not fm or (a.get("agen_estado","")).upper() == fm]
    citas_manana_activas = [a for a in citas_manana_todas
                            if (a.get("agen_estado") or "").upper() in ("AGENDADA","REAGENDADA")]

    smtp_ok = bool(SMTP_HOST and SMTP_USER and SMTP_PASS)
    tiene_con_email = any(pac_map.get(a.get("pac_id"),{}).get("pac_email") for a in citas_manana_activas)
    enviar_btn = (
        '<form method="post" action="/agenda/enviar-recordatorios" style="display:inline">'
        '<button class="btn" ' +
        ('style="background:#075e54"' if smtp_ok and tiene_con_email else 'disabled style="background:#9ca3af;cursor:not-allowed"') +
        '>📧 Enviar recordatorios</button></form>'
    ) if citas_manana_activas else ""

    rows_manana = ""
    for a in citas_manana_vis:
        pac   = pac_map.get(a.get("pac_id"), {})
        email = pac.get("pac_email","")
        rows_manana += f"""<tr>
            <td>{a.get('agen_hora','')[:5]}</td>
            <td><a href="/pacientes/{a.get('pac_id')}">{pac.get('pac_nombre_corto','—')}</a></td>
            <td>{pac.get('pac_telefono','—')}</td>
            <td>{badge_estado(a.get('agen_estado',''))}</td>
            <td>{"<span style='color:#16a34a;font-size:12px'>✓ " + email + "</span>"
                 if email else "<span style='color:#d1d5db;font-size:12px'>—</span>"}</td>
        </tr>"""

    smtp_warn = "" if smtp_ok else (
        "<div style='background:#fef3c7;border:1px solid #f59e0b;border-radius:6px;"
        "padding:8px 12px;font-size:12px;color:#92400e;margin-top:8px'>"
        "⚠ Configura <b>SMTP_HOST, SMTP_USER, SMTP_PASS</b> en docker-compose.yml para activar el envío.</div>"
    )

    seccion_manana = f"""
    <div style="margin-bottom:32px">
        <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
            <h1 style="margin:0">Agenda mañana
                <small style="font-size:16px;font-weight:400;color:#6b7280">— {manana_d.strftime('%A %d/%m/%Y')}</small>
            </h1>
            {enviar_btn}
        </div>
        {chips(fm, ff, "fm", fm, conteos_m) if conteos_m else ""}
        <table>
            <thead><tr><th>Hora</th><th>Paciente</th><th>Teléfono</th><th>Estado</th><th>Email</th></tr></thead>
            <tbody>{rows_manana if rows_manana else '<tr><td colspan="5" style="color:#aaa;padding:12px">Sin citas</td></tr>'}</tbody>
        </table>
        {smtp_warn}
    </div>"""

    # ── PRÓXIMOS 14 DÍAS ────────────────────────────────────────────────────
    futuras_todas.sort(key=lambda x: (x.get("agen_fecha",""), x.get("agen_hora","")))
    conteos_f = {}
    for a in futuras_todas:
        e = (a.get("agen_estado","")).upper()
        conteos_f[e] = conteos_f.get(e, 0) + 1

    futuras_vis = [a for a in futuras_todas
                   if not ff or (a.get("agen_estado","")).upper() == ff]

    rows_futuras = ""
    for a in futuras_vis:
        pac = pac_map.get(a.get("pac_id"), {})
        rows_futuras += f"""<tr>
            <td>{a.get('agen_fecha','')}</td>
            <td>{a.get('agen_hora','')[:5]}</td>
            <td><a href="/pacientes/{a.get('pac_id')}">{pac.get('pac_nombre_corto','—')}</a></td>
            <td>{badge_estado(a.get('agen_estado',''))}</td>
            <td>{'✅' if a.get('agen_realizada') == 'SI' else '—'}</td>
        </tr>"""

    seccion_futura = f"""
    <div>
        <h1 style="margin-bottom:10px">Agenda próximos 14 días
            <small style="font-size:16px;font-weight:400;color:#6b7280">— desde {(hoy + timedelta(days=2)).strftime('%d/%m')}</small>
        </h1>
        {chips(fm, ff, "ff", ff, conteos_f) if conteos_f else ""}
        <table>
            <thead><tr><th>Fecha</th><th>Hora</th><th>Paciente</th><th>Estado</th><th>Realizada</th></tr></thead>
            <tbody>{rows_futuras if rows_futuras else '<tr><td colspan="5" style="color:#aaa;padding:12px">Sin citas en los próximos 14 días</td></tr>'}</tbody>
        </table>
    </div>"""

    return layout("Agenda", seccion_manana + seccion_futura)

@app.post("/agenda/enviar-recordatorios")
def enviar_recordatorios():
    manana = (date.today() + timedelta(days=1)).strftime("%Y-%m-%d")
    try:
        citas = requests.get(f"{AGENDA_URL}/agenda/fecha/{manana}", timeout=3).json()
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        return RedirectResponse(url="/agenda?msg=error", status_code=303)

    pac_map = {p["pac_id"]: p for p in pacientes}
    enviados = 0

    for cita in citas:
        estado = (cita.get("agen_estado") or "").upper()
        if estado not in ("AGENDADA", "REAGENDADA"):
            continue
        pac = pac_map.get(cita.get("pac_id"), {})
        email = pac.get("pac_email","").strip()
        if not email:
            continue

        hora = (cita.get("agen_hora") or "")[:5]
        nombre = pac.get("pac_nombre_corto","Paciente")

        msg = MIMEMultipart("alternative")
        msg["Subject"] = f"Recordatorio de cita — {manana} {hora}"
        msg["From"]    = FROM_EMAIL
        msg["To"]      = email

        html = f"""
        <div style="font-family:sans-serif;max-width:500px;margin:auto">
            <div style="background:#075e54;padding:20px;border-radius:8px 8px 0 0">
                <h1 style="color:white;margin:0;font-size:20px">Recordatorio de cita</h1>
            </div>
            <div style="border:1px solid #e5e7eb;border-top:none;padding:24px;border-radius:0 0 8px 8px">
                <p>Hola <b>{nombre}</b>,</p>
                <p>Te recordamos que tienes una cita programada para mañana:</p>
                <div style="background:#f0fdf4;border-left:4px solid #16a34a;padding:16px;border-radius:4px;margin:16px 0">
                    <b>📅 Fecha:</b> {manana}<br>
                    <b>⏰ Hora:</b> {hora}
                </div>
                <p style="color:#555">Si necesitas reagendar, comunícate con nosotros.</p>
            </div>
        </div>"""

        msg.attach(MIMEText(html, "html"))
        try:
            with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
                server.starttls()
                server.login(SMTP_USER, SMTP_PASS)
                server.sendmail(FROM_EMAIL, email, msg.as_string())
            enviados += 1
        except Exception as e:
            print(f"[email] Error enviando a {email}: {e}", flush=True)

    return RedirectResponse(url=f"/agenda?enviados={enviados}", status_code=303)

# ── pacientes ──────────────────────────────────────────────────────────────

@app.get("/pacientes", response_class=HTMLResponse)
def pacientes_page():
    try:
        pacientes = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        pacientes = []

    hoy = date.today().strftime("%Y-%m-%d")

    rows = ""
    for p in pacientes:
        pac_id = p["pac_id"]

        # Ficha activa → diagnóstico y total sesiones
        try:
            ficha = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas/activa", timeout=2).json()
        except Exception:
            ficha = None

        if ficha and ficha.get("fic_id"):
            diagnostico = ficha.get("fic_diagnostico") or "—"
            total = ficha.get("fic_cantidad_sesiones", 0)
            fic_id_activa = ficha.get("fic_id")
        else:
            # sin ficha activa, buscar la más reciente entre todas
            try:
                todas = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas", timeout=2).json()
                ultima = sorted(todas, key=lambda f: f.get("fic_id", 0), reverse=True)[0] if todas else None
            except Exception:
                ultima = None
            diagnostico = ultima.get("fic_diagnostico","—") if ultima else "—"
            total = ultima.get("fic_cantidad_sesiones", 0) if ultima else 0
            fic_id_activa = ultima.get("fic_id") if ultima else None

        # Citas del paciente para calcular sesiones y próxima cita
        try:
            citas = requests.get(f"{AGENDA_URL}/agenda/paciente/{pac_id}", timeout=2).json()
        except Exception:
            citas = []

        # Filtrar solo las de la ficha activa/reciente
        citas_ficha = [c for c in citas if c.get("fic_id") == fic_id_activa] if fic_id_activa else []

        realizadas_n  = sum(1 for c in citas_ficha if (c.get("agen_estado") or "").upper() == "REALIZADA")
        agendadas_n   = sum(1 for c in citas_ficha if (c.get("agen_estado") or "").lower() in ("agendada", "reagendada"))
        sin_agendar_n = max(total - realizadas_n - agendadas_n, 0)

        # Próxima cita (agendada/reagendada con fecha >= hoy)
        proximas = sorted(
            [c for c in citas_ficha if (c.get("agen_estado") or "").lower() in ("agendada", "reagendada") and c.get("agen_fecha","") >= hoy],
            key=lambda c: (c.get("agen_fecha",""), c.get("agen_hora",""))
        )
        if proximas:
            prx = proximas[0]
            proxima_html = f'<span style="color:#075e54;font-size:12px">📅 {prx["agen_fecha"]} {prx.get("agen_hora","")[:5]}</span>'
        else:
            proxima_html = '<span style="color:#9ca3af;font-size:12px">Sin cita próxima</span>'

        sesiones_html = ""
        if total:
            sesiones_html = (
                f'<div style="font-size:12px;line-height:1.7">'
                f'<span style="color:#374151">{total} sesiones</span><br>'
                f'<span style="color:#16a34a">✓ {realizadas_n} realizada{"s" if realizadas_n != 1 else ""}</span> &nbsp;'
                f'<span style="color:#d97706">⏳ {agendadas_n} agendada{"s" if agendadas_n != 1 else ""}</span> &nbsp;'
                f'<span style="color:#9ca3af">○ {sin_agendar_n} sin agendar</span>'
                f'</div>'
            )
        else:
            sesiones_html = '<span style="color:#9ca3af;font-size:12px">Sin ficha activa</span>'

        inactivo = (p.get("pac_estado","")).upper() != "ACTIVO"
        row_style = "opacity:0.5" if inactivo else ""
        rows += f"""
        <tr style="{row_style}">
            <td><a href="/pacientes/{pac_id}" style="color:#075e54;font-weight:600">{p.get('pac_nombre_corto','')}</a></td>
            <td>{p.get('pac_telefono','—')}</td>
            <td><b>{diagnostico}</b></td>
            <td>{sesiones_html}</td>
            <td>{proxima_html}</td>
            <td style="white-space:nowrap">
                <a href="/pacientes/{pac_id}/editar" class="btn"
                    style="font-size:11px;padding:3px 9px;background:#6b7280">✏</a>
                <form method="post" action="/pacientes/{pac_id}/desactivar" style="display:inline">
                    <button class="btn {'btn-danger' if not inactivo else ''}"
                        style="font-size:11px;padding:3px 9px;{'background:#9ca3af' if inactivo else ''}"
                        onclick="return confirm('{'¿Reactivar paciente?' if inactivo else '¿Desactivar paciente?'}')"
                        title="{'Reactivar' if inactivo else 'Desactivar'}">
                        {'↩' if inactivo else '🚫'}
                    </button>
                </form>
            </td>
        </tr>
        """

    contenido = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;">
        <h1>Pacientes</h1>
        <a href="/pacientes/nuevo" class="btn">+ Nuevo paciente</a>
    </div>
    <table>
        <thead>
            <tr><th>Nombre</th><th>Teléfono</th><th>Diagnóstico</th><th>Sesiones</th><th>Próxima cita</th><th>Acciones</th></tr>
        </thead>
        <tbody>{rows if rows else '<tr><td colspan="6" style="color:#aaa">Sin pacientes</td></tr>'}</tbody>
    </table>
    """
    return layout("Pacientes", contenido)

@app.post("/pacientes/{pac_id}/desactivar")
def desactivar_paciente(pac_id: int):
    # Toggle: si activo → desactiva, si inactivo → reactiva
    try:
        p = requests.get(f"{PATIENTS_URL}/patients/{pac_id}", timeout=3).json()
        nuevo_estado = "INACTIVO" if p.get("pac_estado","").upper() == "ACTIVO" else "ACTIVO"
        requests.put(f"{PATIENTS_URL}/patients/{pac_id}",
                     json={"nombres": p.get("pac_nombres",""), "apellidos": p.get("pac_apellidos",""),
                           "telefono": p.get("pac_telefono",""), "estado": nuevo_estado},
                     timeout=3)
    except Exception:
        pass
    return RedirectResponse(url="/pacientes", status_code=303)

def _form_paciente(titulo: str, action: str, p: dict = {}) -> str:
    return f"""
    <h1>{titulo}</h1>
    <div class="form-card" style="max-width:680px">
        <form method="post" action="{action}">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Nombres <span style="color:#b91c1c">*</span></label>
                    <input name="pac_nombres" required value="{p.get('pac_nombres','')}">
                </div>
                <div>
                    <label>Apellidos <span style="color:#b91c1c">*</span></label>
                    <input name="pac_apellidos" required value="{p.get('pac_apellidos','')}">
                </div>
            </div>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Nombre corto</label>
                    <input name="pac_nombre_corto" value="{p.get('pac_nombre_corto','')}" placeholder="Ej: Juan P.">
                </div>
                <div>
                    <label>Teléfono</label>
                    <input name="pac_telefono" value="{p.get('pac_telefono','')}" placeholder="+56912345678">
                </div>
            </div>
            <label>Email <small style="color:#9ca3af">(para recordatorios)</small></label>
            <input name="pac_email" type="email" value="{p.get('pac_email','')}" placeholder="paciente@email.com">

            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0">
            <p style="font-weight:700;color:#374151;margin:0 0 12px">📍 Ubicación</p>
            <label>Dirección</label>
            <input name="pac_direccion" value="{p.get('pac_direccion','')}" placeholder="Av. Ejemplo 123">
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Ciudad</label>
                    <input name="pac_ciudad" value="{p.get('pac_ciudad','')}" placeholder="Santiago">
                </div>
                <div>
                    <label>Comuna</label>
                    <input name="pac_comuna" value="{p.get('pac_comuna','')}" placeholder="Las Condes">
                </div>
            </div>

            <hr style="border:none;border-top:1px solid #e5e7eb;margin:16px 0">
            <p style="font-weight:700;color:#374151;margin:0 0 12px">🚨 Contacto de emergencia</p>
            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Nombre</label>
                    <input name="pac_contacto_emergencia" value="{p.get('pac_contacto_emergencia','')}" placeholder="María González">
                </div>
                <div>
                    <label>Teléfono</label>
                    <input name="pac_telefono_emergencia" value="{p.get('pac_telefono_emergencia','')}" placeholder="+56987654321">
                </div>
            </div>
            <br>
            <button type="submit" class="btn">✓ Guardar paciente</button>
            &nbsp;<a href="/pacientes" style="color:#888">Cancelar</a>
        </form>
    </div>"""

@app.get("/pacientes/nuevo", response_class=HTMLResponse)
def nuevo_paciente_form():
    return layout("Nuevo Paciente", _form_paciente("Nuevo Paciente", "/pacientes/nuevo"))

@app.post("/pacientes/nuevo")
def nuevo_paciente_save(
    pac_nombres: str = Form(...),
    pac_apellidos: str = Form(...),
    pac_telefono: str = Form(""),
    pac_email: str = Form(""),
    pac_nombre_corto: str = Form(""),
    pac_direccion: str = Form(""),
    pac_ciudad: str = Form(""),
    pac_comuna: str = Form(""),
    pac_contacto_emergencia: str = Form(""),
    pac_telefono_emergencia: str = Form("")
):
    body = {
        "nombres": pac_nombres,
        "apellidos": pac_apellidos,
        "telefono": pac_telefono,
        "email": pac_email,
        "nombre_corto": pac_nombre_corto or f"{pac_nombres} {pac_apellidos}",
        "direccion": pac_direccion,
        "ciudad": pac_ciudad,
        "comuna": pac_comuna,
        "contacto_emergencia": pac_contacto_emergencia,
        "telefono_emergencia": pac_telefono_emergencia,
    }
    r = requests.post(f"{PATIENTS_URL}/patients", json=body, timeout=3)
    pac_id = r.json().get("pac_id", "")
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

@app.get("/pacientes/{pac_id}/editar", response_class=HTMLResponse)
def editar_paciente_form(pac_id: int):
    try:
        p = requests.get(f"{PATIENTS_URL}/patients/{pac_id}", timeout=3).json()
    except Exception:
        return RedirectResponse(url="/pacientes", status_code=303)
    return layout("Editar Paciente", _form_paciente("Editar Paciente", f"/pacientes/{pac_id}/editar", p))

@app.post("/pacientes/{pac_id}/editar")
def editar_paciente_save(
    pac_id: int,
    pac_nombres: str = Form(...),
    pac_apellidos: str = Form(...),
    pac_telefono: str = Form(""),
    pac_email: str = Form(""),
    pac_nombre_corto: str = Form(""),
    pac_direccion: str = Form(""),
    pac_ciudad: str = Form(""),
    pac_comuna: str = Form(""),
    pac_contacto_emergencia: str = Form(""),
    pac_telefono_emergencia: str = Form("")
):
    body = {
        "nombres": pac_nombres, "apellidos": pac_apellidos,
        "telefono": pac_telefono, "email": pac_email,
        "nombre_corto": pac_nombre_corto,
        "direccion": pac_direccion, "ciudad": pac_ciudad, "comuna": pac_comuna,
        "contacto_emergencia": pac_contacto_emergencia,
        "telefono_emergencia": pac_telefono_emergencia,
    }
    requests.put(f"{PATIENTS_URL}/patients/{pac_id}", json=body, timeout=3)
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

# ── detalle paciente ───────────────────────────────────────────────────────

@app.get("/pacientes/{pac_id}", response_class=HTMLResponse)
def paciente_detalle(pac_id: int, notif: str = Query("")):
    try:
        p = requests.get(f"{PATIENTS_URL}/patients/{pac_id}", timeout=3).json()
    except Exception:
        return layout("Error", "<h2>Paciente no encontrado</h2>")

    try:
        fichas = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas", timeout=3).json()
    except Exception:
        fichas = []

    try:
        agenda = requests.get(f"{AGENDA_URL}/agenda/paciente/{pac_id}", timeout=3).json()
    except Exception:
        agenda = []

    # Agrupar citas por fic_id
    citas_por_ficha: dict = {}
    for a in agenda:
        fid = a.get("fic_id")
        if fid:
            citas_por_ficha.setdefault(fid, []).append(a)

    FILTROS = ["TODOS", "AGENDADA", "REAGENDADA", "REALIZADA", "CANCELADA"]

    ORDEN_ESTADO = {"AGENDADA": 0, "REAGENDADA": 1, "REALIZADA": 2, "CANCELADA": 3}
    COLOR_FILA = {
        "AGENDADA":   ("background:#f0fdf4", "border-left:3px solid #16a34a"),   # verde
        "REAGENDADA": ("background:#f7fee7", "border-left:3px solid #84cc16"),   # verde claro
        "REALIZADA":  ("background:#eff6ff", "border-left:3px solid #3b82f6"),   # azul
        "CANCELADA":  ("background:#fff1f2", "border-left:3px solid #f87171"),   # rojo
    }

    def tabla_citas(citas: list, es_activa: bool, fic_idx: int) -> str:
        hoy = date.today().strftime("%Y-%m-%d")

        def sort_key(x):
            orden = ORDEN_ESTADO.get((x.get("agen_estado","")).upper(), 9)
            return (orden, x.get("agen_fecha",""), x.get("agen_hora",""))

        citas_sorted = sorted(citas, key=sort_key)

        # Filtros de estado por ficha
        botones = ""
        for e in FILTROS:
            bg = "#075e54" if e == "TODOS" else "white"
            color = "white" if e == "TODOS" else "#333"
            botones += (
                f'<button onclick="filtrar({fic_idx}, \'{e}\')" id="btn-{fic_idx}-{e}" '
                f'style="padding:4px 12px;border-radius:20px;border:1px solid #ccc;cursor:pointer;'
                f'font-size:12px;background:{bg};color:{color}">{e}</button>'
            )
        filtro_html = f'<div style="margin:10px 0;display:flex;gap:6px;flex-wrap:wrap">{botones}</div>'

        rows = ""
        for a in citas_sorted:
            agen_id   = a.get("agen_id")
            realizada = a.get("agen_realizada","").upper() == "SI"
            estado    = (a.get("agen_estado","")).upper()
            fecha     = a.get("agen_fecha","")
            observacion = a.get("agen_observacion") or ""

            # ¿Cita vencida? → fecha pasada y aún pendiente
            vencida = (
                estado in ("AGENDADA", "REAGENDADA")
                and fecha < hoy
            )

            bg_fila, borde_fila = COLOR_FILA.get(estado, ("", ""))
            row_style = f"{bg_fila};{borde_fila}"

            # Columna fecha con alerta si vencida
            if vencida:
                fecha_html = (
                    f'<span title="⚠ Cita pasada sin marcar">'
                    f'<b style="color:#b45309">{fecha}</b>'
                    f' <span style="background:#fef3c7;border:1px solid #f59e0b;border-radius:4px;'
                    f'padding:1px 5px;font-size:11px;color:#92400e">⚠ vencida</span>'
                    f'</span>'
                )
            else:
                fecha_html = fecha

            acciones = ""
            if realizada:
                acciones = f"""✅&nbsp;
                <form method="post" action="/cita/{agen_id}/desmarcar" style="display:inline">
                    <input type="hidden" name="pac_id" value="{pac_id}">
                    <button class="btn btn-danger" style="font-size:11px;padding:3px 8px" title="Desmarcar">↩</button>
                </form>"""
            elif es_activa and estado not in ("CANCELADA", "REALIZADA"):
                acciones = (
                    f'<a href="/cita/{agen_id}/realizar?pac_id={pac_id}" class="btn" style="font-size:11px;padding:3px 8px" title="Marcar realizada">✓</a> '
                    f'<a href="/cita/{agen_id}/reagendar?pac_id={pac_id}" class="btn" style="font-size:11px;padding:3px 8px;background:#d97706" title="Reagendar">📅</a> '
                    f'<form method="post" action="/cita/{agen_id}/cancelar" style="display:inline">'
                    f'<input type="hidden" name="pac_id" value="{pac_id}">'
                    f'<button class="btn btn-danger" style="font-size:11px;padding:3px 8px" title="Cancelar" '
                    f'onclick="return confirm(\'¿Cancelar esta cita?\')">✕</button></form>'
                )
            else:
                acciones = "—"

            # Parsear ejercicios del bloque de observación
            obs_nota = observacion
            ejercicios_html = ""
            if estado == "REALIZADA" and observacion:
                lineas = observacion.split("\n")
                eje_items = [l.strip() for l in lineas if l.strip().startswith("•")]
                obs_lineas = [l for l in lineas if not l.strip().startswith("•") and l.strip() != "Ejercicios realizados:"]
                obs_nota = "\n".join(obs_lineas).strip()

                if eje_items:
                    badges = "".join(
                        f'<span style="display:inline-block;background:#dbeafe;color:#1e40af;'
                        f'border-radius:6px;padding:2px 7px;font-size:11px;margin:2px 2px 2px 0;white-space:nowrap">'
                        f'{item.lstrip("• ").split(" — ")[0]}'
                        f'<span style="color:#93c5fd;margin-left:4px">'
                        f'{item.split(" — ")[1] if " — " in item else ""}</span>'
                        f'</span>'
                        for item in eje_items
                    )
                    ejercicios_html = f'<div style="margin-bottom:4px">{badges}</div>'

            obs_html = ""
            if ejercicios_html:
                obs_html += ejercicios_html
            if obs_nota:
                obs_html += f'<small style="color:#6b7280">{obs_nota}</small>'
            if not obs_html:
                obs_html = "—"

            rows += f"""<tr data-estado="{estado}" style="{row_style}">
                <td>{fecha_html}</td>
                <td>{a.get('agen_hora','')}</td>
                <td>{badge_estado(a.get('agen_estado',''))}</td>
                <td>{acciones}</td>
                <td>{obs_html}</td>
            </tr>"""

        if not rows:
            rows = '<tr><td colspan="5" style="color:#aaa;padding:12px">Sin citas asociadas</td></tr>'

        return f"""{filtro_html}
        <table style="margin-top:6px" id="tabla-{fic_idx}">
            <thead><tr><th>Fecha</th><th>Hora</th><th>Estado</th><th>Acción</th><th>Observación</th></tr></thead>
            <tbody>{rows}</tbody>
        </table>"""

    # Ordenar fichas: activa primero, luego por id desc
    fichas_sorted = sorted(fichas, key=lambda f: (
        0 if f.get("fic_estado","").upper() == "ACTIVA" else 1,
        -f.get("fic_id", 0)
    ))

    fichas_html = ""
    for idx, f in enumerate(fichas_sorted):
        fic_id = f.get("fic_id")
        es_activa = f.get("fic_estado","").upper() == "ACTIVA"
        total = f.get("fic_cantidad_sesiones", 0)
        citas_ficha = citas_por_ficha.get(fic_id, [])
        realizadas   = sum(1 for c in citas_ficha if (c.get("agen_estado") or "").upper() == "REALIZADA")
        agendadas    = sum(1 for c in citas_ficha if (c.get("agen_estado") or "").lower() in ("agendada", "reagendada"))
        sin_agendar  = max(total - realizadas - agendadas, 0)
        abierta = "block" if es_activa else "none"

        badge_ficha = '<span class="badge badge-verde">ACTIVA</span>' if es_activa else '<span class="badge" style="background:#e5e7eb;color:#374151">CERRADA</span>'

        nueva_cita_btn = (
            f'<a href="/pacientes/{pac_id}/nueva-cita?fic_id={fic_id}" class="btn" '
            f'style="font-size:12px;padding:5px 12px" onclick="event.stopPropagation()">+ Cita</a>'
            if es_activa else ""
        )

        resumen_sesiones = (
            f'<span style="color:#555">{total} sesiones</span>'
            f' &nbsp;·&nbsp; <span style="color:#075e54">✓ {realizadas} realizada{"s" if realizadas != 1 else ""}</span>'
            f' &nbsp;·&nbsp; <span style="color:#d97706">⏳ {agendadas} pendiente{"s" if agendadas != 1 else ""}</span>'
            f' &nbsp;·&nbsp; <span style="color:#9ca3af">○ {sin_agendar} sin agendar</span>'
        )

        fichas_html += f"""
        <div class="card" style="margin:12px 0;padding:0;{'border-left:4px solid #075e54;' if es_activa else ''}">
            <div onclick="toggle('ficha-{idx}')"
                style="padding:16px 20px;cursor:pointer;display:flex;justify-content:space-between;align-items:center;user-select:none">
                <div>
                    {badge_ficha} &nbsp;
                    <b>{f.get('fic_diagnostico','')}</b>
                    &nbsp;&nbsp;
                    <small>{resumen_sesiones}</small>
                    {f'&nbsp;&nbsp;<small style="color:#888">{f.get("fic_observacion")}</small>' if f.get('fic_observacion') else ''}
                    {f'&nbsp;&nbsp;<small style="color:#6b7280">📅 {f.get("fic_fecha_creacion","")[:10]}</small>' if f.get('fic_fecha_creacion') else ''}
                    {f'&nbsp;&nbsp;<small>📎 <a href="/uploads/fichas/{f.get("fic_documento_path")}" target="_blank" style="color:#16a34a">{f.get("fic_documento_nombre")}</a></small>' if f.get('fic_documento_nombre') else ''}
                </div>
                <div style="display:flex;align-items:center;gap:8px">
                    {nueva_cita_btn}
                    <a href="/fichas/{fic_id}/editar?pac_id={pac_id}" class="btn"
                        style="font-size:12px;padding:5px 10px;background:#6b7280"
                        onclick="event.stopPropagation()" title="Editar ficha">✏</a>
                    <form method="post" action="/fichas/{fic_id}/eliminar" style="display:inline"
                        onclick="event.stopPropagation()">
                        <input type="hidden" name="pac_id" value="{pac_id}">
                        <button class="btn btn-danger" style="font-size:12px;padding:5px 10px"
                            title="Eliminar ficha"
                            onclick="return confirm('¿Eliminar esta ficha y todas sus citas?')">🗑</button>
                    </form>
                    <small style="color:#aaa">Ficha #{fic_id}</small>
                    <span id="arrow-{idx}" style="font-size:18px;color:#075e54">{'▼' if es_activa else '▶'}</span>
                </div>
            </div>
            <div id="ficha-{idx}" style="display:{abierta};padding:0 20px 16px">
                {tabla_citas(citas_ficha, es_activa, idx)}
            </div>
        </div>
        """

    if not fichas_sorted:
        fichas_html = f'<div class="card" style="margin:20px 0"><p>Sin fichas. <a href="/pacientes/{pac_id}/nueva-ficha">Crear primera ficha</a></p></div>'

    # ── Info paciente ───────────────────────────────────────────────────────
    def info_item(label, valor):
        if not valor:
            return ""
        return f'<span style="margin-right:20px"><b style="color:#6b7280;font-size:12px">{label}</b><br>{valor}</span>'

    info_contacto = (
        info_item("📞 Teléfono", p.get("pac_telefono")) +
        info_item("📧 Email", p.get("pac_email")) +
        info_item("📍 Dirección", p.get("pac_direccion")) +
        info_item("🏙 Ciudad / Comuna", " / ".join(filter(None, [p.get("pac_ciudad"), p.get("pac_comuna")])))
    )
    info_emergencia = (
        info_item("🚨 Contacto emergencia", p.get("pac_contacto_emergencia")) +
        info_item("📞 Tel. emergencia", p.get("pac_telefono_emergencia"))
    )

    contenido = f"""
    {_notif_banner(notif)}
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:8px">
        <h1 style="margin:0">{p.get('pac_nombre_corto','')}</h1>
        <div style="display:flex;gap:8px">
            <a href="/pacientes/{pac_id}/editar" class="btn" style="background:#6b7280;font-size:13px">✏ Editar</a>
            <a href="/pacientes/{pac_id}/nueva-ficha" class="btn">+ Nueva ficha</a>
        </div>
    </div>

    <!-- Info paciente -->
    <div class="card" style="margin-bottom:16px;padding:14px 18px;background:#f9fafb">
        <div style="display:flex;flex-wrap:wrap;gap:6px 0;margin-bottom:{'8px' if info_emergencia else '0'}">
            {info_contacto if info_contacto else '<span style="color:#9ca3af;font-size:13px">Sin datos de contacto registrados</span>'}
        </div>
        {f'<div style="margin-top:8px;padding-top:8px;border-top:1px solid #e5e7eb;display:flex;flex-wrap:wrap;gap:6px 0">{info_emergencia}</div>' if info_emergencia else ''}
    </div>

    <h2>Fichas clínicas</h2>
    {fichas_html}

    <script>
    function toggle(id) {{
        const el = document.getElementById(id);
        const idx = id.split('-')[1];
        const arrow = document.getElementById('arrow-' + idx);
        if (el.style.display === 'none') {{
            el.style.display = 'block';
            arrow.textContent = '▼';
        }} else {{
            el.style.display = 'none';
            arrow.textContent = '▶';
        }}
    }}

    function filtrar(idx, estado) {{
        const tabla = document.getElementById('tabla-' + idx);
        const rows = tabla.querySelectorAll('tbody tr[data-estado]');
        rows.forEach(r => {{
            r.style.display = (estado === 'TODOS' || r.dataset.estado === estado) ? '' : 'none';
        }});
        // resaltar botón activo
        ['TODOS','AGENDADA','REAGENDADA','REALIZADA','CANCELADA'].forEach(e => {{
            const btn = document.getElementById('btn-' + idx + '-' + e);
            if (btn) {{
                btn.style.background = (e === estado) ? '#075e54' : 'white';
                btn.style.color = (e === estado) ? 'white' : '#333';
            }}
        }});
    }}
    </script>
    """
    return layout(p.get("pac_nombre_corto","Paciente"), contenido)

# ── nueva ficha ────────────────────────────────────────────────────────────

import os as _os, shutil as _shutil
from fastapi import UploadFile, File
UPLOADS_DIR = "/app/uploads/fichas"

@app.on_event("startup")
async def create_upload_dirs():
    _os.makedirs(UPLOADS_DIR, exist_ok=True)

@app.get("/uploads/fichas/{filename}")
async def serve_documento(filename: str):
    from fastapi.responses import FileResponse
    path = f"{UPLOADS_DIR}/{filename}"
    if _os.path.exists(path):
        return FileResponse(path)
    return HTMLResponse("Archivo no encontrado", status_code=404)

def _form_ficha(titulo: str, action: str, pac_id: int, f: dict = {}) -> str:
    doc_actual = ""
    if f.get("fic_documento_nombre"):
        doc_actual = (
            f'<div style="background:#f0fdf4;border:1px solid #86efac;border-radius:8px;'
            f'padding:8px 12px;font-size:13px;margin-bottom:8px">'
            f'📎 Documento actual: '
            f'<a href="/uploads/fichas/{f["fic_documento_path"]}" target="_blank" '
            f'style="color:#16a34a;font-weight:600">{f["fic_documento_nombre"]}</a>'
            f'</div>'
        )
    return f"""
    <h1>{titulo}</h1>
    <div class="form-card" style="max-width:580px">
        <form method="post" action="{action}" enctype="multipart/form-data">
            <input type="hidden" name="pac_id" value="{pac_id}">
            <label>Diagnóstico <span style="color:#b91c1c">*</span></label>
            <input name="fic_diagnostico" required value="{f.get('fic_diagnostico','')}"
                placeholder="Ej: Tendinitis rotuliana">
            <label>Número de sesiones <span style="color:#b91c1c">*</span></label>
            <input type="number" name="fic_cantidad_sesiones" min="1" max="100" required
                value="{f.get('fic_cantidad_sesiones','')}"
                placeholder="¿Cuántas sesiones se planifican?" style="width:200px">
            <label>Observación</label>
            <textarea name="fic_observacion" rows="3"
                placeholder="Notas adicionales (opcional)">{f.get('fic_observacion','')}</textarea>
            <label>📎 Documento adjunto <small style="color:#9ca3af">(PDF, imagen, Word — máx. 10MB)</small></label>
            {doc_actual}
            <input type="file" name="documento" accept=".pdf,.doc,.docx,.png,.jpg,.jpeg"
                style="padding:6px;border:1px solid #e5e7eb;border-radius:8px;width:100%">
            <br>
            <button type="submit" class="btn">✓ Guardar ficha</button>
            &nbsp;<a href="/pacientes/{pac_id}" style="color:#888">Cancelar</a>
        </form>
    </div>"""

def _guardar_documento(documento: UploadFile, fic_id: int) -> tuple:
    """Guarda el archivo y retorna (path_relativo, nombre_original)"""
    import uuid
    if not documento or not documento.filename:
        return ("", "")
    ext = documento.filename.rsplit(".", 1)[-1] if "." in documento.filename else "bin"
    fname = f"fic{fic_id}_{uuid.uuid4().hex[:8]}.{ext}"
    fpath = f"{UPLOADS_DIR}/{fname}"
    with open(fpath, "wb") as out:
        _shutil.copyfileobj(documento.file, out)
    return (fname, documento.filename)

@app.get("/pacientes/{pac_id}/nueva-ficha", response_class=HTMLResponse)
def nueva_ficha_form(pac_id: int):
    return layout("Nueva Ficha", _form_ficha("Nueva Ficha", f"/pacientes/{pac_id}/nueva-ficha", pac_id))

@app.post("/pacientes/{pac_id}/nueva-ficha")
async def nueva_ficha_save(
    pac_id: int,
    fic_diagnostico: str = Form(...),
    fic_cantidad_sesiones: int = Form(...),
    fic_observacion: str = Form(""),
    documento: UploadFile = File(None)
):
    # Cerrar ficha activa anterior si existe
    try:
        fichas = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas", timeout=3).json()
        activa = next((f for f in fichas if f.get("fic_estado","").upper() == "ACTIVA"), None)
        if activa:
            requests.put(f"{PATIENTS_URL}/fichas/{activa['fic_id']}/cerrar", timeout=3)
    except Exception:
        pass

    body = {
        "diagnostico": fic_diagnostico,
        "cantidad_sesiones": fic_cantidad_sesiones,
        "observacion": fic_observacion
    }
    r = requests.post(f"{PATIENTS_URL}/patients/{pac_id}/fichas", json=body, timeout=3)
    fic_id = r.json().get("fic_id")

    # Guardar documento si se adjuntó
    if fic_id and documento and documento.filename:
        fname, nombre = _guardar_documento(documento, fic_id)
        requests.put(f"{PATIENTS_URL}/fichas/{fic_id}", json={
            "documento_path": fname, "documento_nombre": nombre
        }, timeout=3)

    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

# ── editar / eliminar ficha ─────────────────────────────────────────────────

@app.get("/fichas/{fic_id}/editar", response_class=HTMLResponse)
def editar_ficha_form(fic_id: int, pac_id: int = 0):
    try:
        fichas = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas", timeout=3).json()
        ficha = next((f for f in fichas if f.get("fic_id") == fic_id), None)
    except Exception:
        ficha = None
    if not ficha:
        return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)
    return layout(f"Editar Ficha #{fic_id}", _form_ficha(f"Editar Ficha #{fic_id}", f"/fichas/{fic_id}/editar", pac_id, ficha))

@app.post("/fichas/{fic_id}/editar")
async def editar_ficha_save(
    fic_id: int,
    pac_id: int = Form(0),
    fic_diagnostico: str = Form(...),
    fic_cantidad_sesiones: int = Form(...),
    fic_observacion: str = Form(""),
    documento: UploadFile = File(None)
):
    body = {
        "diagnostico": fic_diagnostico,
        "cantidad_sesiones": fic_cantidad_sesiones,
        "observacion": fic_observacion
    }
    if documento and documento.filename:
        fname, nombre = _guardar_documento(documento, fic_id)
        body["documento_path"] = fname
        body["documento_nombre"] = nombre
    r = requests.put(f"{PATIENTS_URL}/fichas/{fic_id}", json=body, timeout=3)
    print(f"[editar_ficha] PUT /fichas/{fic_id} → {r.status_code} {r.text}", flush=True)
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

@app.post("/fichas/{fic_id}/eliminar")
def eliminar_ficha(fic_id: int, pac_id: int = Form(0)):
    requests.delete(f"{PATIENTS_URL}/fichas/{fic_id}", timeout=3)
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

# ── disponibilidad ──────────────────────────────────────────────────────────

SLOTS = [
    f"{h:02d}:{m:02d}"
    for h in range(9, 18)
    for m in (0, 30)
    if not (h == 17 and m == 30)  # hasta 17:30 inclusive
]
# agrega 17:30 manualmente
SLOTS.append("17:30")

@app.get("/api/disponibilidad")
def api_disponibilidad(fecha: str = Query(...)):
    """Devuelve todos los slots con su disponibilidad para una fecha dada."""
    resultado = []
    for slot in SLOTS:
        try:
            r = requests.get(
                f"{AGENDA_URL}/agenda/disponibilidad",
                params={"fecha": fecha, "hora": slot},
                timeout=3
            ).json()
            libre = r.get("disponible", True)
        except Exception:
            libre = True
        resultado.append({"hora": slot, "libre": libre})
    return JSONResponse(resultado)

def slot_picker_html(form_action: str, back_url: str, extra_hidden: str = "", submit_label: str = "Agendar", submit_color: str = "#075e54") -> str:
    """Widget reutilizable de selector de slots con validación."""
    hoy = date.today().strftime("%Y-%m-%d")
    return f"""
    <div class="form-card" style="max-width:600px">
        <form method="post" action="{form_action}" id="form-cita">
            {extra_hidden}
            <label>Fecha</label>
            <input type="date" id="fecha-input" name="fecha" min="{hoy}" required
                onchange="cargarSlots(this.value)">

            <div id="slots-wrap" style="display:none;margin:10px 0">
                <label>Hora disponible</label>
                <div id="slots-grid" style="display:flex;flex-wrap:wrap;gap:8px;margin-top:8px"></div>
                <input type="hidden" name="hora" id="hora-input" required>
                <div id="slot-error" style="color:#b91c1c;font-size:13px;margin-top:6px;display:none"></div>
            </div>

            <label style="margin-top:12px;display:block">Observación (opcional)</label>
            <textarea name="observacion" rows="3"></textarea>
            <br>
            <button type="submit" class="btn" style="background:{submit_color}">{submit_label}</button>
            &nbsp;<a href="{back_url}" style="color:#888">Cancelar</a>
        </form>
    </div>

    <script>
    async function cargarSlots(fecha) {{
        const grid = document.getElementById('slots-grid');
        const wrap = document.getElementById('slots-wrap');
        const horaInput = document.getElementById('hora-input');
        const err = document.getElementById('slot-error');

        grid.innerHTML = '<span style="color:#888">Cargando...</span>';
        wrap.style.display = 'block';
        horaInput.value = '';
        err.style.display = 'none';

        const res = await fetch('/api/disponibilidad?fecha=' + fecha);
        const slots = await res.json();

        grid.innerHTML = '';
        slots.forEach(s => {{
            const btn = document.createElement('button');
            btn.type = 'button';
            btn.textContent = s.hora;
            btn.style.cssText = `
                padding:8px 14px;border-radius:8px;border:2px solid;
                cursor:${{s.libre ? 'pointer' : 'not-allowed'}};font-size:14px;font-weight:bold;
                background:${{s.libre ? '#f0fdf4' : '#fef2f2'}};
                color:${{s.libre ? '#075e54' : '#b91c1c'}};
                border-color:${{s.libre ? '#075e54' : '#fca5a5'}};
                opacity:${{s.libre ? '1' : '0.6'}};
            `;
            if (s.libre) {{
                btn.onclick = () => {{
                    document.querySelectorAll('#slots-grid button').forEach(b => {{
                        b.style.background = '#f0fdf4';
                        b.style.color = '#075e54';
                        b.style.borderColor = '#075e54';
                    }});
                    btn.style.background = '#075e54';
                    btn.style.color = 'white';
                    horaInput.value = s.hora;
                    err.style.display = 'none';
                }};
            }}
            grid.appendChild(btn);
        }});
    }}

    document.getElementById('form-cita').addEventListener('submit', function(e) {{
        const hora = document.getElementById('hora-input').value;
        const err = document.getElementById('slot-error');
        if (!hora) {{
            e.preventDefault();
            err.textContent = '⚠ Debes seleccionar una hora disponible.';
            err.style.display = 'block';
        }}
    }});
    </script>
    """

# ── nueva cita ─────────────────────────────────────────────────────────────

@app.get("/pacientes/{pac_id}/nueva-cita", response_class=HTMLResponse)
def nueva_cita_form(pac_id: int, fic_id: int = 0):
    picker = slot_picker_html(
        form_action=f"/pacientes/{pac_id}/nueva-cita",
        back_url=f"/pacientes/{pac_id}",
        extra_hidden=f'<input type="hidden" name="fic_id" value="{fic_id}">',
        submit_label="✓ Agendar cita"
    )
    return layout("Nueva Cita", f"<h1>Nueva Cita</h1>{picker}")

@app.post("/pacientes/{pac_id}/nueva-cita")
def nueva_cita_save(
    pac_id: int,
    fic_id: int = Form(0),
    fecha: str = Form(...),
    hora: str = Form(...),
    observacion: str = Form("")
):
    # Validar disponibilidad server-side
    try:
        r = requests.get(f"{AGENDA_URL}/agenda/disponibilidad", params={"fecha": fecha, "hora": hora}, timeout=3).json()
        if not r.get("disponible", True):
            picker = slot_picker_html(
                form_action=f"/pacientes/{pac_id}/nueva-cita",
                back_url=f"/pacientes/{pac_id}",
                extra_hidden=f'<input type="hidden" name="fic_id" value="{fic_id}">',
                submit_label="✓ Agendar cita"
            )
            error = f'<div style="background:#fee2e2;border:1px solid #fca5a5;padding:12px;border-radius:8px;margin-bottom:16px;color:#b91c1c">⚠ El horario <b>{fecha} {hora}</b> ya está ocupado. Selecciona otra hora disponible.</div>'
            return HTMLResponse(layout("Nueva Cita", f"<h1>Nueva Cita</h1>{error}{picker}"))
    except Exception:
        pass

    body = {"pac_id": pac_id, "fic_id": fic_id or None, "fecha": fecha, "hora": hora, "observacion": observacion}
    requests.post(f"{AGENDA_URL}/agenda", json=body, timeout=3)
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

# ── reagendar cita ──────────────────────────────────────────────────────────

@app.get("/cita/{agen_id}/reagendar", response_class=HTMLResponse)
def reagendar_form(agen_id: int, pac_id: int = 0):
    picker = slot_picker_html(
        form_action=f"/cita/{agen_id}/reagendar",
        back_url=f"/pacientes/{pac_id}",
        extra_hidden=f'<input type="hidden" name="pac_id" value="{pac_id}">',
        submit_label="📅 Confirmar reagenda",
        submit_color="#d97706"
    )
    return layout("Reagendar Cita", f"<h1>Reagendar Cita</h1>{picker}")

@app.post("/cita/{agen_id}/reagendar")
def reagendar_save(
    agen_id: int,
    pac_id: int = Form(0),
    fecha: str = Form(...),
    hora: str = Form(...),
    observacion: str = Form("")
):
    # Validar disponibilidad server-side
    try:
        r = requests.get(f"{AGENDA_URL}/agenda/disponibilidad", params={"fecha": fecha, "hora": hora}, timeout=3).json()
        if not r.get("disponible", True):
            picker = slot_picker_html(
                form_action=f"/cita/{agen_id}/reagendar",
                back_url=f"/pacientes/{pac_id}",
                extra_hidden=f'<input type="hidden" name="pac_id" value="{pac_id}">',
                submit_label="📅 Confirmar reagenda",
                submit_color="#d97706"
            )
            error = f'<div style="background:#fee2e2;border:1px solid #fca5a5;padding:12px;border-radius:8px;margin-bottom:16px;color:#b91c1c">⚠ El horario <b>{fecha} {hora}</b> ya está ocupado. Selecciona otra hora disponible.</div>'
            return HTMLResponse(layout("Reagendar Cita", f"<h1>Reagendar Cita</h1>{error}{picker}"))
    except Exception:
        pass

    body = {"nueva_fecha": fecha, "nueva_hora": hora, "observacion": observacion}
    # Obtener fecha/hora original (y pac_id si no vino en el form) antes de reagendar
    try:
        cita_actual = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json()
        fecha_orig = cita_actual.get("agen_fecha", "")
        hora_orig  = cita_actual.get("agen_hora", "")
        if not pac_id:
            pac_id = cita_actual.get("pac_id", 0)
    except Exception:
        fecha_orig, hora_orig = "", ""
    gcal_reagendar(agen_id, pac_id, fecha, hora, fecha_original=fecha_orig, hora_original=hora_orig)
    requests.put(f"{AGENDA_URL}/agenda/{agen_id}/reagendar", json=body, timeout=3)
    notif = send_email_cita(pac_id, "reagendada", fecha, hora, agen_id=agen_id,
                            fecha_orig=fecha_orig, hora_orig=hora_orig)
    return RedirectResponse(url=f"/pacientes/{pac_id}?notif={quote(notif, safe='')}", status_code=303)

@app.post("/cita/{agen_id}/cancelar")
def cancelar_cita(agen_id: int, pac_id: int = Form(0), from_: str = Form("", alias="from"), semana: int = Form(0)):
    # Obtener fecha/hora (y pac_id si no vino en el form) antes de cancelar
    fecha_cit, hora_cit = "", ""
    try:
        cita_info = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json()
        fecha_cit = cita_info.get("agen_fecha", "")
        hora_cit  = cita_info.get("agen_hora", "")
        if not pac_id:
            pac_id = cita_info.get("pac_id", 0)
    except Exception:
        pass
    gcal_eliminar(agen_id)
    requests.put(f"{AGENDA_URL}/agenda/{agen_id}/cancelar", json={}, timeout=3)
    notif = send_email_cita(pac_id, "cancelada", fecha_cit, hora_cit, agen_id=agen_id)
    if from_ == "calendario":
        return RedirectResponse(url=f"/calendario?semana={semana}&notif={quote(notif, safe='')}", status_code=303)
    return RedirectResponse(url=f"/pacientes/{pac_id}?notif={quote(notif, safe='')}", status_code=303)

# ── marcar / desmarcar realizada ───────────────────────────────────────────

@app.get("/cita/{agen_id}/realizar", response_class=HTMLResponse)
def realizar_form(agen_id: int, pac_id: int = 0, from_: str = Query("", alias="from"), semana: int = Query(0)):
    back = f"/calendario?semana={semana}" if from_ == "calendario" else f"/pacientes/{pac_id}"

    # Cargar ejercicios desde activities-service
    try:
        ejercicios = requests.get(f"{ACTIVITIES_URL}/ejercicios", timeout=3).json()
    except Exception:
        ejercicios = []

    # Agrupar por categoría para optgroup
    by_cat: dict = {}
    for e in ejercicios:
        cat = e.get("eje_categoria") or "General"
        by_cat.setdefault(cat, []).append(e)

    options_html = '<option value="">— seleccionar ejercicio —</option>'
    for cat in sorted(by_cat.keys()):
        options_html += f'<optgroup label="{cat}">'
        for e in by_cat[cat]:
            options_html += (
                f'<option value="{e["eje_id"]}" '
                f'data-nombre="{e["eje_nombre"]}" '
                f'data-series="{e.get("eje_series",3)}" '
                f'data-reps="{e.get("eje_repeticiones",10)}">'
                f'{e["eje_nombre"]} ({e.get("eje_series",3)}×{e.get("eje_repeticiones",10)})'
                f'</option>'
            )
        options_html += '</optgroup>'

    contenido = f"""
    <h1>Marcar sesión como realizada</h1>
    <div class="form-card" style="max-width:680px">
        <form method="post" action="/cita/{agen_id}/realizar" id="formRealizar">
            <input type="hidden" name="pac_id" value="{pac_id}">
            <input type="hidden" name="from" value="{from_}">
            <input type="hidden" name="semana" value="{semana}">
            <input type="hidden" name="ejercicios_json" id="ejercicios_json" value="[]">

            <!-- ── Ejercicios realizados ── -->
            <label style="font-weight:700;font-size:14px">🏋 Ejercicios realizados en la sesión</label>

            <div style="background:#f9fafb;border:1px solid #e5e7eb;border-radius:10px;padding:16px;margin-bottom:16px">
                <!-- Selector -->
                <div style="display:flex;gap:8px;align-items:center;margin-bottom:12px">
                    <select id="selectEje" style="flex:1;margin:0">
                        {options_html}
                    </select>
                    <button type="button" onclick="agregarEjercicio()"
                        style="background:#075e54;color:white;border:none;border-radius:8px;padding:8px 14px;cursor:pointer;font-size:13px;white-space:nowrap">
                        + Agregar
                    </button>
                </div>

                <!-- Lista de ejercicios agregados -->
                <div id="listaEjercicios" style="display:flex;flex-direction:column;gap:8px">
                    <p id="listaVacia" style="color:#9ca3af;font-size:13px;margin:0;text-align:center">
                        Ningún ejercicio agregado aún
                    </p>
                </div>
            </div>

            <!-- ── Observación ── -->
            <label>Observación de la sesión (opcional)</label>
            <textarea name="observacion" rows="4"
                placeholder="Evolución del paciente, respuesta a los ejercicios..."></textarea>
            <br>
            <button type="submit" class="btn">✓ Confirmar sesión realizada</button>
            &nbsp;
            <a href="{back}" style="color:#888">Cancelar</a>
        </form>
    </div>

    <script>
    var ejes = [];

    function agregarEjercicio() {{
        var sel = document.getElementById('selectEje');
        var opt = sel.options[sel.selectedIndex];
        if (!opt.value) return;
        ejes.push({{
            id: parseInt(opt.value),
            nombre: opt.getAttribute('data-nombre'),
            series: parseInt(opt.getAttribute('data-series')) || 3,
            reps: parseInt(opt.getAttribute('data-reps')) || 10
        }});
        renderLista();
        sel.selectedIndex = 0;
    }}

    function quitarEjercicio(i) {{
        ejes.splice(i, 1);
        renderLista();
    }}

    function renderLista() {{
        var container = document.getElementById('listaEjercicios');
        if (ejes.length === 0) {{
            container.innerHTML = '<p style="color:#9ca3af;font-size:13px;margin:0;text-align:center">Ningún ejercicio agregado aún</p>';
            return;
        }}
        var html = '';
        for (var i = 0; i < ejes.length; i++) {{
            var e = ejes[i];
            html += '<div style="display:flex;align-items:center;gap:10px;background:white;border:1px solid #e5e7eb;border-radius:8px;padding:10px 12px;margin-bottom:4px">'
                  + '<div style="flex:1;font-size:13px;font-weight:600;color:#1f2937">' + e.nombre + '</div>'
                  + '<span style="font-size:12px;color:#6b7280">Series</span>'
                  + '<input type="number" value="' + e.series + '" min="1" max="20" data-i="' + i + '"'
                  + ' onchange="ejes[this.dataset.i].series=parseInt(this.value)||1"'
                  + ' style="width:55px;margin:0;padding:4px 6px;font-size:13px;text-align:center">'
                  + '<span style="font-size:12px;color:#6b7280">Reps</span>'
                  + '<input type="number" value="' + e.reps + '" min="1" max="100" data-i="' + i + '"'
                  + ' onchange="ejes[this.dataset.i].reps=parseInt(this.value)||1"'
                  + ' style="width:55px;margin:0;padding:4px 6px;font-size:13px;text-align:center">'
                  + '<button type="button" onclick="quitarEjercicio(' + i + ')"'
                  + ' style="background:#fee2e2;color:#b91c1c;border:none;border-radius:6px;padding:4px 10px;cursor:pointer;font-size:13px">✕</button>'
                  + '</div>';
        }}
        container.innerHTML = html;
    }}

    document.getElementById('formRealizar').addEventListener('submit', function() {{
        document.getElementById('ejercicios_json').value = JSON.stringify(ejes);
    }});
    </script>
    """
    return layout("Marcar realizada", contenido)

@app.post("/cita/{agen_id}/realizar")
def realizar_save(agen_id: int, pac_id: int = Form(0), observacion: str = Form(""),
                  ejercicios_json: str = Form("[]"),
                  from_: str = Form("", alias="from"), semana: int = Form(0)):
    import json as _json

    # Construir observación combinada con ejercicios
    obs_final = observacion.strip()
    try:
        ejercicios = _json.loads(ejercicios_json)
        if ejercicios:
            lineas = [f"  • {e['nombre']} — {e['series']} series × {e['reps']} reps" for e in ejercicios]
            bloque = "Ejercicios realizados:\n" + "\n".join(lineas)
            obs_final = (bloque + "\n\n" + obs_final).strip() if obs_final else bloque
    except Exception:
        pass

    # Obtener pac_id y fecha/hora desde la cita si no vino en el form
    fecha_cit, hora_cit = "", ""
    try:
        cita_info = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json()
        fecha_cit = cita_info.get("agen_fecha", "")
        hora_cit  = cita_info.get("agen_hora", "")
        if not pac_id:
            pac_id = cita_info.get("pac_id", 0)
    except Exception:
        pass

    requests.put(f"{AGENDA_URL}/agenda/{agen_id}/realizada", json={"observacion": obs_final}, timeout=3)

    # Incrementar contador de sesiones en la ficha activa
    try:
        ficha = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas/activa", timeout=3).json()
        fic_id = ficha.get("fic_id")
        if fic_id:
            requests.put(f"{PATIENTS_URL}/fichas/{fic_id}/incrementar", timeout=3)
    except Exception:
        pass

    notif = send_email_cita(pac_id, "realizada", fecha_cit, hora_cit, agen_id=agen_id)
    if from_ == "calendario":
        return RedirectResponse(url=f"/calendario?semana={semana}&notif={quote(notif, safe='')}", status_code=303)
    return RedirectResponse(url=f"/pacientes/{pac_id}?notif={quote(notif, safe='')}", status_code=303)

@app.post("/cita/{agen_id}/desmarcar")
def desmarcar(agen_id: int, pac_id: int = Form(0), from_: str = Form("", alias="from"), semana: int = Form(0)):
    if not pac_id:
        try:
            pac_id = requests.get(f"{AGENDA_URL}/agenda/{agen_id}", timeout=3).json().get("pac_id", 0)
        except Exception:
            pass
    requests.put(f"{AGENDA_URL}/agenda/{agen_id}/desmarcar", timeout=3)
    # Decrementar contador de sesiones en la ficha activa
    try:
        ficha = requests.get(f"{PATIENTS_URL}/patients/{pac_id}/fichas/activa", timeout=3).json()
        fic_id = ficha.get("fic_id")
        if fic_id:
            requests.put(f"{PATIENTS_URL}/fichas/{fic_id}/disminuir", timeout=3)
    except Exception:
        pass
    if from_ == "calendario":
        return RedirectResponse(url=f"/calendario?semana={semana}", status_code=303)
    return RedirectResponse(url=f"/pacientes/{pac_id}", status_code=303)

# ── búsqueda ───────────────────────────────────────────────────────────────

@app.get("/api/buscar")
def api_buscar(q: str = Query("")):
    """Live search: retorna lista de {tipo, titulo, subtitulo, url}."""
    if not q or len(q) < 2:
        return JSONResponse([])

    resultados = []

    # Buscar pacientes
    try:
        pacs = requests.get(f"{PATIENTS_URL}/patients/search?q={q}", timeout=3).json()
    except Exception:
        try:
            # fallback: traer todos y filtrar
            todos = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
            ql = q.lower()
            pacs = [p for p in todos if ql in (p.get("pac_nombre_corto","") or "").lower()
                    or ql in (p.get("pac_telefono","") or "").lower()
                    or ql in (p.get("pac_nombres","") or "").lower()
                    or ql in (p.get("pac_apellidos","") or "").lower()]
        except Exception:
            pacs = []

    for p in pacs[:5]:
        resultados.append({
            "tipo": "paciente",
            "titulo": p.get("pac_nombre_corto",""),
            "subtitulo": f"📞 {p.get('pac_telefono','—')} · {p.get('pac_estado','')}",
            "url": f"/pacientes/{p['pac_id']}"
        })

    # Buscar en fichas (por diagnóstico)
    try:
        todos_pacs = requests.get(f"{PATIENTS_URL}/patients", timeout=3).json()
    except Exception:
        todos_pacs = []

    ql = q.lower()
    fichas_encontradas = 0
    for p in todos_pacs:
        if fichas_encontradas >= 5:
            break
        try:
            fichas = requests.get(f"{PATIENTS_URL}/patients/{p['pac_id']}/fichas", timeout=2).json()
            for f in fichas:
                diag = (f.get("fic_diagnostico","") or "").lower()
                obs  = (f.get("fic_observacion","") or "").lower()
                if ql in diag or ql in obs:
                    estado_f = f.get("fic_estado","")
                    resultados.append({
                        "tipo": "ficha",
                        "titulo": f.get("fic_diagnostico",""),
                        "subtitulo": f"👤 {p.get('pac_nombre_corto','')} · Ficha #{f['fic_id']} · {estado_f}",
                        "url": f"/pacientes/{p['pac_id']}#ficha-{f['fic_id']}"
                    })
                    fichas_encontradas += 1
        except Exception:
            pass

    return JSONResponse(resultados[:10])

@app.get("/buscar", response_class=HTMLResponse)
def buscar_page(q: str = Query(""), tipo: str = Query("")):
    """Página de resultados completa."""
    resultados_html = ""

    if q:
        try:
            data = requests.get(f"http://localhost:5000/api/buscar?q={q}", timeout=3).json()
        except Exception:
            data = []

        if not data:
            resultados_html = '<p style="color:#9ca3af;margin-top:20px">Sin resultados para <b>' + q + '</b></p>'
        else:
            for r in data:
                icon = "👤" if r["tipo"] == "paciente" else "📁"
                color = "#075e54" if r["tipo"] == "paciente" else "#7c3aed"
                resultados_html += f"""
                <a href="{r['url']}" style="display:flex;align-items:center;gap:14px;
                    background:white;padding:16px 20px;border-radius:10px;margin-bottom:10px;
                    text-decoration:none;color:#1f2937;box-shadow:0 1px 4px rgba(0,0,0,.08);
                    border-left:4px solid {color};transition:box-shadow .15s"
                    onmouseover="this.style.boxShadow='0 4px 12px rgba(0,0,0,.12)'"
                    onmouseout="this.style.boxShadow='0 1px 4px rgba(0,0,0,.08)'">
                    <span style="font-size:28px">{icon}</span>
                    <div>
                        <div style="font-weight:700;font-size:15px;color:{color}">{r['titulo']}</div>
                        <div style="font-size:13px;color:#6b7280;margin-top:2px">{r['subtitulo']}</div>
                    </div>
                </a>"""

    contenido = f"""
    <h1 style="margin-bottom:20px">Búsqueda{f': <em>{q}</em>' if q else ''}</h1>
    <form action="/buscar" method="get" style="margin-bottom:24px">
        <div style="display:flex;gap:10px;max-width:600px">
            <input name="q" value="{q}" placeholder="Buscar paciente, diagnóstico, ficha..."
                style="flex:1;font-size:16px;padding:12px 18px;border-radius:10px;
                       border:2px solid #075e54;margin:0">
            <button type="submit" class="btn" style="padding:12px 24px;font-size:15px">Buscar</button>
        </div>
    </form>
    {resultados_html if q else '<p style="color:#9ca3af">Escribe algo para buscar pacientes o diagnósticos.</p>'}
    """
    return layout("Búsqueda", contenido)

# ── ejercicios ─────────────────────────────────────────────────────────────

def youtube_embed(url: str) -> str:
    """Convierte URL de YouTube a embed."""
    if not url:
        return ""
    vid = ""
    if "v=" in url:
        vid = url.split("v=")[1].split("&")[0]
    elif "youtu.be/" in url:
        vid = url.split("youtu.be/")[1].split("?")[0]
    if vid:
        return f'<iframe width="280" height="157" src="https://www.youtube.com/embed/{vid}" frameborder="0" allowfullscreen style="border-radius:8px"></iframe>'
    return f'<a href="{url}" target="_blank" class="btn" style="font-size:12px">▶ Ver video</a>'

@app.get("/ejercicios/por-diagnostico", response_class=HTMLResponse)
def ejercicios_por_diagnostico(texto: str = Query("")):
    """Muestra los ejercicios asignados al tipo de diagnóstico que mejor
    coincide con el texto libre de una ficha (mismo matching que usa el bot
    de WhatsApp vía GET /diagnosticos/buscar en activities-service)."""
    diag = None
    if texto:
        try:
            r = requests.get(f"{ACTIVITIES_URL}/diagnosticos/buscar", params={"texto": texto}, timeout=3)
            if r.status_code == 200:
                diag = r.json()
        except Exception:
            diag = None

    if diag:
        ejercicios = diag.get("ejercicios") or []
        rows = ""
        for e in ejercicios:
            video = youtube_embed(e.get("eje_link_youtube","")) if e.get("eje_link_youtube") else "—"
            rows += f"""<tr>
                <td style="font-weight:600">{e.get('eje_nombre','—')}</td>
                <td style="text-align:center">{e.get('eje_series',0)}</td>
                <td style="text-align:center">{e.get('eje_repeticiones',0)}</td>
                <td style="font-size:12px;color:#6b7280">{e.get('eje_detalle','') or '—'}</td>
                <td>{video}</td>
            </tr>"""
        tabla = f"""
        <table>
            <thead><tr><th>Ejercicio</th><th>Series</th><th>Reps</th><th>Detalle</th><th>Video</th></tr></thead>
            <tbody>{rows if rows else '<tr><td colspan="5" style="color:#aaa;padding:20px;text-align:center">Este diagnóstico todavía no tiene ejercicios asociados</td></tr>'}</tbody>
        </table>"""
        titulo = f"Ejercicios — {diag.get('diag_nombre','')}"
        subtitulo = f'<p style="color:#6b7280;margin-top:0">Diagnóstico de la ficha: <b>{texto}</b> → coincide con <b>{diag.get("diag_nombre","")}</b></p>'
    else:
        tabla = ""
        titulo = "Ejercicios por diagnóstico"
        subtitulo = (
            f'<div style="background:#fffbeb;border:1px solid #f59e0b;border-radius:10px;padding:14px 18px;color:#92400e">'
            f'No hay ningún tipo de diagnóstico cargado que coincida con "<b>{texto}</b>". '
            f'Puedes crear uno nuevo y asociarle ejercicios desde la <a href="/ejercicios">biblioteca de ejercicios</a>.'
            f'</div>'
        )

    contenido = f"""
    <div style="margin-bottom:16px"><a href="/fichas" class="btn" style="background:#6b7280">← Volver a fichas</a></div>
    <h1 style="margin-bottom:4px">{titulo}</h1>
    {subtitulo}
    <div style="margin-top:20px">{tabla}</div>
    """
    return layout("Ejercicios por diagnóstico", contenido)


@app.get("/ejercicios", response_class=HTMLResponse)
def ejercicios_page(q: str = Query(""), categoria: str = Query("")):
    try:
        if q:
            items = requests.get(f"{ACTIVITIES_URL}/ejercicios/search?q={q}", timeout=3).json()
        else:
            items = requests.get(f"{ACTIVITIES_URL}/ejercicios?categoria={categoria}", timeout=3).json()
    except Exception:
        items = []

    # Categorías únicas para filtro
    try:
        todas = requests.get(f"{ACTIVITIES_URL}/ejercicios", timeout=3).json()
        categorias = sorted(set(e.get("eje_categoria","") for e in todas if e.get("eje_categoria")))
    except Exception:
        categorias = []

    cat_tabs = '<a href="/ejercicios" style="padding:6px 14px;border-radius:20px;text-decoration:none;font-size:13px;font-weight:600;' + ('background:#075e54;color:white' if not categoria else 'background:white;color:#374151;border:1px solid #e5e7eb') + '">Todos</a>'
    for c in categorias:
        activo = c == categoria
        cat_tabs += f'<a href="/ejercicios?categoria={c}" style="padding:6px 14px;border-radius:20px;text-decoration:none;font-size:13px;font-weight:600;{"background:#075e54;color:white" if activo else "background:white;color:#374151;border:1px solid #e5e7eb"}">{c}</a>'

    cards = ""
    for e in items:
        eje_id = e.get("eje_id")
        thumb = youtube_embed(e.get("eje_link_youtube",""))
        cards += f"""
        <div class="card" style="display:flex;gap:16px;padding:16px;margin-bottom:12px">
            <div style="flex-shrink:0">{thumb if thumb else '<div style="width:280px;height:157px;background:#f3f4f6;border-radius:8px;display:flex;align-items:center;justify-content:center;color:#9ca3af;font-size:13px">Sin video</div>'}</div>
            <div style="flex:1">
                <div style="display:flex;justify-content:space-between;align-items:start">
                    <div>
                        <h3 style="margin:0 0 4px;color:#075e54">{e.get('eje_nombre','')}</h3>
                        {f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 8px;border-radius:10px;font-size:11px">{e.get("eje_categoria","")}</span>' if e.get("eje_categoria") else ''}
                    </div>
                    <div style="display:flex;gap:6px">
                        <a href="/ejercicios/{eje_id}/editar" class="btn" style="font-size:11px;padding:4px 10px;background:#6b7280">✏ Editar</a>
                        <form method="post" action="/ejercicios/{eje_id}/eliminar" style="display:inline">
                            <button class="btn btn-danger" style="font-size:11px;padding:4px 10px"
                                onclick="return confirm('¿Eliminar este ejercicio?')">🗑</button>
                        </form>
                    </div>
                </div>
                <p style="color:#555;font-size:13px;margin:10px 0">{e.get('eje_detalle','') or '<em style="color:#9ca3af">Sin descripción</em>'}</p>
                <div style="display:flex;gap:16px;margin-top:8px">
                    <span style="background:#f0fdf4;color:#16a34a;padding:4px 12px;border-radius:8px;font-size:13px;font-weight:600">
                        🔁 {e.get('eje_series',3)} series
                    </span>
                    <span style="background:#eff6ff;color:#2563eb;padding:4px 12px;border-radius:8px;font-size:13px;font-weight:600">
                        ✕ {e.get('eje_repeticiones',10)} reps
                    </span>
                </div>
            </div>
        </div>"""

    contenido = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h1 style="margin:0">🏋 Biblioteca de ejercicios</h1>
        <a href="/ejercicios/nuevo" class="btn">+ Nuevo ejercicio</a>
    </div>
    <div style="display:flex;gap:8px;margin-bottom:16px;flex-wrap:wrap">
        {cat_tabs}
    </div>
    <form action="/ejercicios" method="get" style="margin-bottom:20px">
        <div style="display:flex;gap:8px;max-width:500px">
            <input name="q" value="{q}" placeholder="Buscar ejercicio..."
                style="flex:1;margin:0;padding:9px 14px">
            <button class="btn" type="submit">Buscar</button>
            {'<a href="/ejercicios" class="btn" style="background:#6b7280">✕</a>' if q else ''}
        </div>
    </form>
    {cards if cards else '<p style="color:#9ca3af">No hay ejercicios registrados. <a href="/ejercicios/nuevo">Crear el primero</a>.</p>'}
    """
    return layout("Ejercicios", contenido)

@app.get("/ejercicios/nuevo", response_class=HTMLResponse)
def nuevo_ejercicio_form():
    contenido = """
    <h1>Nuevo ejercicio</h1>
    <div class="form-card" style="max-width:600px">
        <form method="post" action="/ejercicios/nuevo">
            <label>Nombre <span style="color:#b91c1c">*</span></label>
            <input name="nombre" required placeholder="Ej: Sentadilla con banda">

            <label>Categoría</label>
            <input name="categoria" placeholder="Ej: Rodilla, Hombro, Core, Cadera...">

            <label>Descripción / Detalle</label>
            <textarea name="detalle" rows="4" placeholder="Instrucciones, postura, precauciones..."></textarea>

            <label>Link YouTube</label>
            <input name="link_youtube" type="url" placeholder="https://youtube.com/watch?v=...">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Series</label>
                    <input name="series" type="number" value="3" min="1" max="20" style="width:100%">
                </div>
                <div>
                    <label>Repeticiones</label>
                    <input name="repeticiones" type="number" value="10" min="1" max="100" style="width:100%">
                </div>
            </div>
            <br>
            <button type="submit" class="btn">✓ Guardar ejercicio</button>
            &nbsp;<a href="/ejercicios" style="color:#888">Cancelar</a>
        </form>
    </div>
    """
    return layout("Nuevo Ejercicio", contenido)

@app.post("/ejercicios/nuevo")
def nuevo_ejercicio_save(
    nombre: str = Form(...),
    detalle: str = Form(""),
    categoria: str = Form(""),
    link_youtube: str = Form(""),
    series: int = Form(3),
    repeticiones: int = Form(10)
):
    body = {"nombre": nombre, "detalle": detalle, "categoria": categoria,
            "link_youtube": link_youtube, "series": series, "repeticiones": repeticiones}
    requests.post(f"{ACTIVITIES_URL}/ejercicios", json=body, timeout=3)
    return RedirectResponse(url="/ejercicios", status_code=303)

@app.get("/ejercicios/{eje_id}/editar", response_class=HTMLResponse)
def editar_ejercicio_form(eje_id: int):
    try:
        e = requests.get(f"{ACTIVITIES_URL}/ejercicios/{eje_id}", timeout=3).json()
    except Exception:
        return RedirectResponse(url="/ejercicios", status_code=303)

    contenido = f"""
    <h1>Editar ejercicio</h1>
    <div class="form-card" style="max-width:600px">
        <form method="post" action="/ejercicios/{eje_id}/editar">
            <label>Nombre <span style="color:#b91c1c">*</span></label>
            <input name="nombre" required value="{e.get('eje_nombre','')}">

            <label>Categoría</label>
            <input name="categoria" value="{e.get('eje_categoria','')}">

            <label>Descripción / Detalle</label>
            <textarea name="detalle" rows="4">{e.get('eje_detalle','')}</textarea>

            <label>Link YouTube</label>
            <input name="link_youtube" type="url" value="{e.get('eje_link_youtube','')}">

            <div style="display:grid;grid-template-columns:1fr 1fr;gap:16px">
                <div>
                    <label>Series</label>
                    <input name="series" type="number" value="{e.get('eje_series',3)}" min="1" max="20" style="width:100%">
                </div>
                <div>
                    <label>Repeticiones</label>
                    <input name="repeticiones" type="number" value="{e.get('eje_repeticiones',10)}" min="1" max="100" style="width:100%">
                </div>
            </div>
            <br>
            <button type="submit" class="btn" style="background:#6b7280">✏ Guardar cambios</button>
            &nbsp;<a href="/ejercicios" style="color:#888">Cancelar</a>
        </form>
    </div>
    """
    return layout("Editar Ejercicio", contenido)

@app.post("/ejercicios/{eje_id}/editar")
def editar_ejercicio_save(
    eje_id: int,
    nombre: str = Form(...),
    detalle: str = Form(""),
    categoria: str = Form(""),
    link_youtube: str = Form(""),
    series: int = Form(3),
    repeticiones: int = Form(10)
):
    body = {"nombre": nombre, "detalle": detalle, "categoria": categoria,
            "link_youtube": link_youtube, "series": series, "repeticiones": repeticiones}
    requests.put(f"{ACTIVITIES_URL}/ejercicios/{eje_id}", json=body, timeout=3)
    return RedirectResponse(url="/ejercicios", status_code=303)

@app.post("/ejercicios/{eje_id}/eliminar")
def eliminar_ejercicio(eje_id: int):
    requests.delete(f"{ACTIVITIES_URL}/ejercicios/{eje_id}", timeout=3)
    return RedirectResponse(url="/ejercicios", status_code=303)

# ── diagnósticos (administrador: qué ejercicios trae cada diagnóstico) ─────

@app.get("/diagnosticos", response_class=HTMLResponse)
def diagnosticos_page(q: str = Query("")):
    try:
        items = requests.get(f"{ACTIVITIES_URL}/diagnosticos", timeout=3).json()
    except Exception:
        items = []

    if q:
        ql = q.lower()
        items = [d for d in items if ql in d.get("diag_nombre","").lower() or ql in d.get("diag_zona","").lower()]

    rows = ""
    for d in items:
        ejercicios = d.get("ejercicios") or []
        nombres_ej = ", ".join(e.get("eje_nombre","") for e in ejercicios[:3])
        if len(ejercicios) > 3:
            nombres_ej += f" (+{len(ejercicios)-3})"
        zona_badge = (f'<span style="background:#e0e7ff;color:#3730a3;padding:2px 8px;'
                      f'border-radius:10px;font-size:11px">{d.get("diag_zona","")}</span>') if d.get("diag_zona") else "—"
        rows += f"""<tr>
            <td style="font-weight:600">{d.get('diag_nombre','—')}</td>
            <td>{zona_badge}</td>
            <td style="font-size:12px;color:#6b7280">{nombres_ej or '<em style="color:#d1d5db">Sin ejercicios</em>'}</td>
            <td style="text-align:center">{len(ejercicios)}</td>
            <td style="white-space:nowrap">
                <a href="/diagnosticos/{d.get('diag_id')}/editar" class="btn" style="font-size:12px;padding:4px 10px;background:#6b7280">✏ Editar</a>
                <form method="post" action="/diagnosticos/{d.get('diag_id')}/eliminar" style="display:inline">
                    <button class="btn btn-danger" style="font-size:12px;padding:4px 10px"
                        onclick="return confirm('¿Eliminar este diagnóstico?')">🗑</button>
                </form>
            </td>
        </tr>"""

    contenido = f"""
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
        <h1 style="margin:0">🩺 Diagnósticos</h1>
        <a href="/diagnosticos/nuevo" class="btn">+ Nuevo diagnóstico</a>
    </div>
    <form action="/diagnosticos" method="get" style="margin-bottom:20px">
        <div style="display:flex;gap:8px;max-width:480px">
            <input name="q" value="{q}" placeholder="Buscar por nombre o zona..." style="flex:1;margin:0;padding:9px 14px">
            <button class="btn" type="submit">Buscar</button>
            {'<a href="/diagnosticos" class="btn" style="background:#6b7280">✕</a>' if q else ''}
        </div>
    </form>
    <table>
        <thead><tr><th>Diagnóstico</th><th>Zona</th><th>Ejercicios</th><th style="text-align:center">#</th><th></th></tr></thead>
        <tbody>{rows if rows else '<tr><td colspan="5" style="color:#aaa;padding:20px;text-align:center">Sin diagnósticos registrados</td></tr>'}</tbody>
    </table>
    <p style="color:#9ca3af;font-size:12px;margin-top:8px">{len(items)} diagnósticos</p>
    """
    return layout("Diagnósticos", contenido)


def _ejercicios_checklist(seleccionados: set) -> str:
    """Checklist de ejercicios agrupado por categoría, marcando los que ya
    estén en `seleccionados` (set de eje_id) — usado en crear/editar diagnóstico."""
    try:
        todos = requests.get(f"{ACTIVITIES_URL}/ejercicios", timeout=3).json()
    except Exception:
        todos = []

    por_categoria = {}
    for e in todos:
        cat = e.get("eje_categoria") or "Sin categoría"
        por_categoria.setdefault(cat, []).append(e)

    html = ""
    for cat in sorted(por_categoria.keys()):
        html += (f'<div style="font-weight:700;font-size:12px;color:#6b7280;'
                 f'text-transform:uppercase;margin:14px 0 6px">{cat}</div>')
        for e in por_categoria[cat]:
            eje_id = e.get("eje_id")
            checked = "checked" if eje_id in seleccionados else ""
            html += f"""
            <label style="display:flex;align-items:center;gap:8px;padding:6px 0;font-weight:normal;cursor:pointer">
                <input type="checkbox" name="ejercicio_ids" value="{eje_id}" {checked} style="width:auto;margin:0">
                {e.get('eje_nombre','')}
            </label>"""
    return html or '<p style="color:#9ca3af;font-size:13px">No hay ejercicios cargados todavía. <a href="/ejercicios/nuevo">Crear uno</a>.</p>'


@app.get("/diagnosticos/nuevo", response_class=HTMLResponse)
def nuevo_diagnostico_form():
    checklist = _ejercicios_checklist(set())
    contenido = f"""
    <h1>Nuevo diagnóstico</h1>
    <div class="form-card" style="max-width:640px">
        <form method="post" action="/diagnosticos/nuevo">
            <label>Nombre <span style="color:#b91c1c">*</span></label>
            <input name="nombre" required placeholder="Ej: Esguince de tobillo">

            <label>Zona</label>
            <input name="zona" placeholder="Ej: Tobillo / Pie, Rodilla, Hombro...">

            <label>Palabras clave (separadas por coma)</label>
            <input name="keywords" placeholder="Ej: esguince de tobillo,esguince tobillo">
            <p style="color:#9ca3af;font-size:12px;margin:-10px 0 16px">
                El bot de WhatsApp usa estas palabras para reconocer este diagnóstico en lo que escribe el paciente.
            </p>

            <label>Ejercicios asociados</label>
            <div style="max-height:320px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin-bottom:16px">
                {checklist}
            </div>

            <button type="submit" class="btn">✓ Guardar diagnóstico</button>
            &nbsp;<a href="/diagnosticos" style="color:#888">Cancelar</a>
        </form>
    </div>
    """
    return layout("Nuevo Diagnóstico", contenido)


@app.post("/diagnosticos/nuevo")
def nuevo_diagnostico_save(
    nombre: str = Form(...),
    zona: str = Form(""),
    keywords: str = Form(""),
    ejercicio_ids: list[int] = Form(default=[])
):
    body = {"nombre": nombre, "zona": zona, "keywords": keywords, "ejercicio_ids": ejercicio_ids}
    requests.post(f"{ACTIVITIES_URL}/diagnosticos", json=body, timeout=3)
    return RedirectResponse(url="/diagnosticos", status_code=303)


@app.get("/diagnosticos/{diag_id}/editar", response_class=HTMLResponse)
def editar_diagnostico_form(diag_id: int):
    try:
        d = requests.get(f"{ACTIVITIES_URL}/diagnosticos/{diag_id}", timeout=3).json()
    except Exception:
        return RedirectResponse(url="/diagnosticos", status_code=303)

    seleccionados = {e.get("eje_id") for e in (d.get("ejercicios") or [])}
    checklist = _ejercicios_checklist(seleccionados)

    contenido = f"""
    <h1>Editar diagnóstico</h1>
    <div class="form-card" style="max-width:640px">
        <form method="post" action="/diagnosticos/{diag_id}/editar">
            <label>Nombre <span style="color:#b91c1c">*</span></label>
            <input name="nombre" required value="{d.get('diag_nombre','')}">

            <label>Zona</label>
            <input name="zona" value="{d.get('diag_zona','')}">

            <label>Palabras clave (separadas por coma)</label>
            <input name="keywords" value="{d.get('diag_keywords','')}">
            <p style="color:#9ca3af;font-size:12px;margin:-10px 0 16px">
                El bot de WhatsApp usa estas palabras para reconocer este diagnóstico en lo que escribe el paciente.
            </p>

            <label>Ejercicios asociados</label>
            <div style="max-height:320px;overflow-y:auto;border:1px solid #e5e7eb;border-radius:8px;padding:12px 16px;margin-bottom:16px">
                {checklist}
            </div>

            <button type="submit" class="btn" style="background:#6b7280">✏ Guardar cambios</button>
            &nbsp;<a href="/diagnosticos" style="color:#888">Cancelar</a>
        </form>
    </div>
    """
    return layout("Editar Diagnóstico", contenido)


@app.post("/diagnosticos/{diag_id}/editar")
def editar_diagnostico_save(
    diag_id: int,
    nombre: str = Form(...),
    zona: str = Form(""),
    keywords: str = Form(""),
    ejercicio_ids: list[int] = Form(default=[])
):
    body = {"nombre": nombre, "zona": zona, "keywords": keywords, "ejercicio_ids": ejercicio_ids}
    requests.put(f"{ACTIVITIES_URL}/diagnosticos/{diag_id}", json=body, timeout=3)
    return RedirectResponse(url="/diagnosticos", status_code=303)


@app.post("/diagnosticos/{diag_id}/eliminar")
def eliminar_diagnostico(diag_id: int):
    requests.delete(f"{ACTIVITIES_URL}/diagnosticos/{diag_id}", timeout=3)
    return RedirectResponse(url="/diagnosticos", status_code=303)

# ── Configuración del Bot ───────────────────────────────────────────────────

FELIPE_DEFAULT = """# FINE-TUNING — BOT FELIPE CASTILLO KINESIÓLOGO

Eres el asistente de WhatsApp del Kinesiólogo Felipe Castillo. Respondes EXACTAMENTE como Felipe: corto, directo, sin formalidades.

=== ESTILO DE FELIPE ===
- Respuestas MUY cortas, directas, sin formalismos
- "Oka" u "Ok" SOLO para confirmar una acción del paciente (ej: cita confirmada, reagendamiento). NUNCA al final de una respuesta informativa.
- "Listo" SOLO cuando se completa una gestión (ej: "Listo Camila, quedas agendada"). NUNCA como cierre de una respuesta de preguntas.
- "De nada" o "Ya de nada" para agradecimientos
- Usa nombre de pila del paciente al confirmar
- Responde "Buenos días/tardes/noches" según hora del día
- A saludos genéricos responde: "Buenos días" + "Diga"
- Cierra conversaciones SOLO con "Nos vemos!" cuando el paciente se despide
- NUNCA termines respuestas informativas con "Oka", "Listo", "Ok" ni menús de opciones

=== FLUJOS REALES OBSERVADOS ===

--- FLUJO 1: LEAD DESDE META ---
Paciente: "¡Hola! Quiero más información"
Bot: [mensaje de bienvenida breve]
Bot: "¿Tiene orden médica de derivación de Kinesiología?"

--- FLUJO 2: PACIENTE CON ORDEN MÉDICA (FONASA) ---
Paciente: "Sí" / "si la tengo"
Bot: "¿Cuál es su diagnóstico?"
Paciente: [da diagnóstico + lado]
Bot: [verifica si es una parte o bilateral]
Bot: [si una parte] "Fonasa atiende de lunes a viernes hasta las 2pm. Cuando tenga el bono comprado me avisa para agendar."

--- FLUJO 3: PACIENTE SIN ORDEN MÉDICA ---
Paciente: "No" / "no tengo"
Bot: "Debe conseguir una orden con su médico para empezar las terapias y así su previsión podrá cubrir el tratamiento."

--- FLUJO 4: PACIENTE PARTICULAR ---
Paciente: "Valor particular por favor" / "cuánto sale particular"
Bot: [saludo según hora]
Bot: "¿Cuál es su diagnóstico?"
Paciente: [da diagnóstico]
Bot: "Vale $10.000 por sesión, la duración de cada sesión es de 50 minutos. Con los boletas puede reembolsar en su isapre. Se entregará un informe al final de todas las sesiones."
Bot: "Horarios de atención es de Lunes, Miércoles y Viernes entre las 9:30am - 6pm."

--- FLUJO 6: PACIENTE YA TIENE BONO, QUIERE AGENDAR ---
Paciente: "Ya compré los bonos" / "tengo el bono"
Bot: "Ok"
Bot: "¿Quiere empezar mañana?"
Bot: "Nombre y apellidos?"
Bot: "Listo [nombre]. Debe llevar los bonos ese día y la orden."
Bot: "✅ Hola [nombre], recuerde que tiene una cita el [día], [fecha] a las [hora]\nNombre del Profesional\nFelipe Castillo y Tomas Sepúlveda"

--- FLUJO 7: AGENDAMIENTO PARTICULAR ---
Bot: "La dirección es San Antonio 418, piso 3. Oficina 306. Entre Monjitas y Merced. Santiago Centro"
Bot: "Entonces queda agendada"
Bot: "Lleve ropa cómoda y zapatillas"
Bot: "No se aplique cremas en la [zona afectada]"

--- FLUJO 8: CANCELACIÓN / REAGENDAMIENTO ---
Paciente: "Hola, hoy no puedo asistir"
Bot: "¿Y viernes?" [o el siguiente día disponible]
Bot: "Oka."

--- FLUJO 9: SALUDO GENÉRICO ---
Paciente: "Hola buen día..."
Bot: "Buenos días"
Bot: "Diga"
Bot: "¿Tiene orden médica de derivación de Kinesiología?"

--- FLUJO 10: SERVICIOS QUE NO SE REALIZAN ---
Paciente: [pide servicio no disponible]
Bot: "No lo hacemos"

=== PREGUNTAS FRECUENTES Y RESPUESTAS EXACTAS ===

P: "¿Cuánto salen 5 sesiones?"
R: "No hay promociones con 5 sesiones. Solo con 10"

P: "¿Sigue la promoción del mes pasado?"
R: "Se que es por este mes. No sé si sigue"

P: "¿Es atención individual?"
R: "No es individual"

P: "¿Son 2 bonos?"
R: "Es un programa para la [zona], no son bonos separados"

P: "El bono vale $37.000"
R: "Es un programa de 10 sesiones que vale $37.000 pesos e incluye las 10 sesiones"

P: "¿Aceptan bonos online?"
R: "No, solo Santiago Centro"

P: "¿Los códigos son nivel 1?"
R: "Sí"

P: "¿Puedo ir en la tarde?"
R: "Sí se puede"

P: "¿Tengo que ir a hablar con el kine antes?"
R: "No, coordinamos tu cita por este chat"

P: "¿Puedo empezar sin el bono?"
R: "Oka [hora]. Nombre?" [agenda igual]

=== REGLAS DE DIAGNÓSTICO ===

UNA PARTE DEL CUERPO (cobro normal FONASA):
- Pie/tobillo: fascitis plantar, esguince de tobillo, entesitis calcánea, espolón calcáneo
- Columna: ciática, discopatía, lumbago, lumbalgia, cervicalgia
- Hombro: rotura manguito rotador, tendinitis del hombro, tendinosis del hombro
- Rodilla: condromalacia rotuliana, tendinitis pata de ganso, esguince, meniscopatía, tendinosis rotuliana
- Pierna: tendinosis gemelar medial

REGLA BILATERAL:
- Dos diagnósticos del MISMO lado = UNA parte
- Diagnósticos en lados DISTINTOS o zonas distintas = bilateral → Felipe interviene personalmente
- Si no está claro el lado: "¿Pierna derecha?"
- BILATERAL → "Gracias por la información, en un momento Felipe te contacta personalmente para coordinar su tratamiento."

=== INFORMACIÓN AL CONFIRMAR CITA ===

FONASA: "Listo [nombre]. Debe llevar los bonos ese día y la orden."
+ "✅ Hola [nombre], recuerde que tiene una cita el [día], [fecha] a las [hora]\nNombre del Profesional\nFelipe Castillo y Tomas Sepúlveda"

PARTICULAR: "Entonces queda agendada" + "Lleve ropa cómoda y zapatillas" + "No se aplique cremas en la [zona afectada]"

=== SERVICIOS QUE NO REALIZA ===
- Masajes post operatorio de liposucción → "No lo hacemos"
- Procedimientos post operatorios de cirugías estéticas → "No lo hacemos"
- Ejercicios para piso pélvico → "No lo hacemos"
- Tratamiento de cicatrices → "No lo hacemos"
- Ejercicios post operados de cirugía bariátrica → "No lo hacemos"

=== DATOS OPERACIONALES ===
- No acepta bonos online, solo presencial Santiago Centro
- FONASA atiende lunes a viernes hasta las 2pm
- Cerca de la consulta hay una oficina FONASA (misma calle)
- Se atienden 3 pacientes a la vez (no es individual)
- Horas más demandadas: mañana
- Dirección: San Antonio 418, piso 3. Oficina 306. Entre Monjitas y Merced. Santiago Centro
- Al agendar siempre pedir: nombre Y apellidos
- Al confirmar: llevar zapatillas, no aplicar cremas en zona afectada
"""

@app.get("/configuracion/bot")
def bot_config_page(saved: str = ""):
    cfg = {}
    try:
        cfg = requests.get(f"{PATIENTS_URL}/config/bot", timeout=3).json()
    except Exception:
        pass
    persona = cfg.get("persona", "")
    saved_ok = '<div style="margin-top:12px;padding:10px 16px;background:#d1fae5;border-radius:8px;color:#065f46;font-weight:600">✅ Configuración guardada correctamente.</div>' if saved == "1" else ""

    html = f"""
    <form method="post" action="/configuracion/bot">
        <div style="margin-bottom:16px">
            <label style="display:block;font-weight:600;margin-bottom:6px">
                Personalidad y contexto del bot de WhatsApp
            </label>
            <textarea name="persona" rows="30"
                style="width:100%;padding:12px;border-radius:8px;border:1px solid #d1d5db;
                       font-family:monospace;font-size:13px;line-height:1.6;resize:vertical"
                placeholder="Escribe aquí el manual completo del bot...">{persona or FELIPE_DEFAULT}</textarea>
            <p style="font-size:12px;color:#6b7280;margin-top:6px">
                Este texto se usa como instrucción base para el bot. Incluye estilo, precios, horarios y flujos de conversación.
                Los cambios se aplican en los próximos mensajes (caché 5 min).
            </p>
        </div>
        <div style="display:flex;gap:12px;align-items:center">
            <button type="submit" class="btn">💾 Guardar configuración</button>
            <a href="/" style="color:#6b7280;font-size:14px">Cancelar</a>
        </div>
        {saved_ok}
    </form>
    """
    return HTMLResponse(layout("⚙ Configuración del Bot", html))


@app.post("/configuracion/bot")
def bot_config_save(persona: str = Form(...)):
    try:
        requests.put(f"{PATIENTS_URL}/config/bot", json={"persona": persona, "activo": True}, timeout=5)
        # Invalidar caché en ai-service
        try:
            requests.post(f"{AI_URL}/config/reload", timeout=2)
        except Exception:
            pass
    except Exception as e:
        pass
    return RedirectResponse(url="/configuracion/bot?saved=1", status_code=303)


# ── admin: reset total (para probar el bot como usuario nuevo) ─────────────

@app.get("/admin", response_class=HTMLResponse)
def admin_page(notif: str = Query("")):
    notif_html = _notif_banner(notif)
    html = f"""
    {notif_html}
    <h1>⚙ Administración</h1>
    <div class="form-card" style="max-width:560px;border:2px solid #fecaca">
        <h2 style="color:#b91c1c;margin-top:0">🗑 Zona de peligro</h2>
        <p style="color:#555;font-size:14px">
            Esto elimina <b>TODOS</b> los pacientes, fichas y citas de la base de datos
            (no solo los de prueba). Úsalo solo para dejar el sistema limpio y poder
            probar el bot de WhatsApp desde cero, como si fueras un paciente nuevo.
        </p>
        <p style="color:#991b1b;font-size:13px;font-weight:600">Esta acción no se puede deshacer.</p>
        <form method="post" action="/admin/reset-todo" onsubmit="return confirmarReset()">
            <button type="submit" class="btn btn-danger">🗑 Borrar TODOS los pacientes, fichas y citas</button>
        </form>
    </div>
    <script>
    function confirmarReset() {{
        const texto = prompt('Esto borrará TODOS los pacientes, fichas y citas de la base de datos.\\n\\nEscribe BORRAR TODO para confirmar:');
        return texto === 'BORRAR TODO';
    }}
    </script>
    """
    return HTMLResponse(layout("⚙ Administración", html))


@app.post("/admin/reset-todo")
def admin_reset_todo():
    errores = []
    try:
        r = requests.post(f"{PATIENTS_URL}/admin/reset", timeout=10)
        if not r.ok:
            errores.append(f"patients-service: {r.text}")
    except Exception as e:
        errores.append(f"patients-service: {e}")
    try:
        r = requests.post(f"{AGENDA_URL}/admin/reset", timeout=10)
        if not r.ok:
            errores.append(f"agenda-service: {r.text}")
    except Exception as e:
        errores.append(f"agenda-service: {e}")

    if errores:
        notif = "⚠️ Error al resetear: " + "; ".join(errores)
    else:
        notif = "✅ Listo: se borraron todos los pacientes, fichas y citas."
    return RedirectResponse(url=f"/admin?notif={quote(notif)}", status_code=303)


# ── internal: notificacion de email (llamado desde ai-service / Go) ────────

class NotifyEmailRequest(BaseModel):
    pac_id:  int
    evento:  str          # "agendada" | "reagendada" | "cancelada"
    fecha:   str
    hora:    str
    agen_id: int = 0
    fecha_orig: str = ""
    hora_orig:  str = ""

@app.post("/internal/notify-email")
def internal_notify_email(req: NotifyEmailRequest):
    msg = send_email_cita(
        pac_id=req.pac_id,
        evento=req.evento,
        fecha=req.fecha,
        hora=req.hora,
        agen_id=req.agen_id,
        fecha_orig=req.fecha_orig,
        hora_orig=req.hora_orig,
    )
    return {"notif": msg}


# ── health ─────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}
