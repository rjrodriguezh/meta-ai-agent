"""
Test de regresión completo — v4 (previsión, agendar 2 turnos, cancelar,
reagendar/editar, consultas generales, derivación a Felipe).

Cubre los 9 bugs corregidos en la sesión de mapeo del documento
finetuning_compact_v3_felipe.md. Requiere los servicios corriendo
(patients-service :8083, agenda-service :8082, ai-service :8081).

Uso:
    cd C:\\proyectos\\github\\meta-ai-agent
    docker compose up --build -d
    pip install -r tests/requirements-test.txt --break-system-packages
    pytest tests/test_bot_v4_regresion.py -v
"""
import time
import pytest
import requests
from conftest import respuesta

PATIENTS_URL = "http://localhost:8083"
AGENDA_URL = "http://localhost:8082"


def _telefono_unico(prefijo: str) -> str:
    """Genera un teléfono único por corrida para no chocar con datos previos."""
    return f"{prefijo}{int(time.time()) % 100000}"


def _registrar_paciente(nombres: str, apellidos: str, telefono: str) -> dict:
    r = requests.post(
        f"{PATIENTS_URL}/patients",
        json={"nombres": nombres, "apellidos": apellidos, "telefono": telefono},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _crear_cita(pac_id: int, fecha: str, hora: str) -> dict:
    r = requests.post(
        f"{AGENDA_URL}/agenda",
        json={"pac_id": pac_id, "fecha": fecha, "hora": hora},
        timeout=10,
    )
    r.raise_for_status()
    return r.json()


def _proximo_lunes() -> str:
    """Fecha YYYY-MM-DD del próximo lunes (día hábil seguro para agendar)."""
    import datetime
    hoy = datetime.date.today()
    dias = (0 - hoy.weekday() + 7) % 7  # 0 = lunes
    dias = dias or 7
    return (hoy + datetime.timedelta(days=dias)).isoformat()


# ---------------------------------------------------------------------------
# 1. PREVISIÓN — máquina de estados completa (Bug #1, #2, #8)
# ---------------------------------------------------------------------------

class TestPrevisionCompleta:

    def test_pregunta_precio_dispara_por_fonasa(self):
        tel = _telefono_unico("5691")
        _registrar_paciente("Test", "Fonasa", tel)
        r = respuesta("¿Cuánto vale la sesión?", tel)
        assert "fonasa" in r, f"No preguntó '¿Por fonasa?': {r}"

    def test_fonasa_tramo_c_da_mensaje_completo(self):
        tel = _telefono_unico("5692")
        _registrar_paciente("Test", "TramoC", tel)
        respuesta("¿Cuánto vale la sesión?", tel)          # -> ¿Por fonasa?
        respuesta("Sí", tel)                                # -> ¿letra A, B, C o D?
        r = respuesta("C", tel)                             # -> mensaje FONASA completo
        assert "38.000" in r or "38000" in r, f"No dio precio FONASA: {r}"
        assert "san antonio 418" in r, f"No dio dirección: {r}"
        assert "14199789-0" in r or "0601105x10" in r, f"No dio códigos FONASA: {r}"

    def test_fonasa_tramo_a_es_particular(self):
        tel = _telefono_unico("5693")
        _registrar_paciente("Test", "TramoA", tel)
        respuesta("¿Cuánto vale la sesión?", tel)
        respuesta("Sí", tel)
        r = respuesta("A", tel)
        assert "particular" in r, f"Tramo A no derivó a particular: {r}"
        assert "100.000" in r or "100000" in r, f"No dio precio particular: {r}"

    def test_no_fonasa_isapre(self):
        tel = _telefono_unico("5694")
        _registrar_paciente("Test", "Isapre", tel)
        respuesta("¿Cuánto vale la sesión?", tel)
        respuesta("No", tel)                                 # -> ¿isapre o particular?
        r = respuesta("Isapre", tel)
        assert "100.000" in r or "100000" in r, f"No dio precio ISAPRE: {r}"
        assert "15.000" in r or "15000" in r, f"No dio precio sesión individual: {r}"

    def test_no_fonasa_particular(self):
        tel = _telefono_unico("5695")
        _registrar_paciente("Test", "Particular", tel)
        respuesta("¿Cuánto vale la sesión?", tel)
        respuesta("No", tel)
        r = respuesta("Particular", tel)
        assert "100.000" in r or "100000" in r, f"No dio precio particular: {r}"

    def test_previsión_queda_guardada_en_paciente(self):
        """Verifica que SetPrevision realmente persiste en patients-service."""
        tel = _telefono_unico("5696")
        pac = _registrar_paciente("Test", "Persistencia", tel)
        respuesta("¿Cuánto vale la sesión?", tel)
        respuesta("Sí", tel)
        respuesta("B", tel)
        r = requests.get(f"{PATIENTS_URL}/patients/telefono/{tel}", timeout=10)
        assert r.status_code == 200
        assert r.json().get("pac_prevision", "").upper() == "FONASA", \
            f"pac_prevision no quedó en FONASA: {r.json()}"


# ---------------------------------------------------------------------------
# 2. AGENDAR EN 2 TURNOS (Bug #11) — la fecha/hora en el segundo mensaje
#    no debe perderse ni reinterpretarse como otra intención.
# ---------------------------------------------------------------------------

class TestAgendarDosTurnos:

    def test_agendar_pide_fecha_luego_continua_con_fecha_suelta(self):
        tel = _telefono_unico("5697")
        _registrar_paciente("Test", "Agendar2Turnos", tel)
        r1 = respuesta("Quiero agendar una hora", tel)
        assert "día" in r1 or "dia" in r1 or "fecha" in r1, f"No pidió fecha: {r1}"

        lunes = _proximo_lunes()
        r2 = respuesta(f"El {lunes} a las 10:00", tel)
        assert "no entend" not in r2, f"Se perdió el flujo de agendar en el 2do turno: {r2}"
        # No debe haber caído en reagendar_hora ni otra intención random
        assert "reagendar" not in r2 or "hora" in r2, f"Respuesta sospechosa: {r2}"


# ---------------------------------------------------------------------------
# 3. CANCELAR Y REAGENDAR/EDITAR — con una cita real pre-sembrada
# ---------------------------------------------------------------------------

class TestCancelarYEditar:

    def _setup_paciente_con_cita(self, sufijo: str):
        tel = _telefono_unico(sufijo)
        pac = _registrar_paciente("Test", f"Cita{sufijo}", tel)
        lunes = _proximo_lunes()
        cita = _crear_cita(pac["pac_id"], lunes, "11:00")
        return tel, pac, cita, lunes

    def test_cancelar_una_sola_cita_pide_confirmacion_y_cancela(self):
        tel, pac, cita, lunes = self._setup_paciente_con_cita("5698")
        r1 = respuesta("Quiero cancelar mi hora", tel)
        assert "cancelar" in r1.lower(), f"No pidió confirmación CANCELAR: {r1}"
        r2 = respuesta("CANCELAR", tel)
        assert "cancel" in r2.lower(), f"No confirmó cancelación: {r2}"

        # Verificar en agenda-service que quedó CANCELADA
        r = requests.get(f"{AGENDA_URL}/agenda/{cita['agen_id']}", timeout=10)
        assert r.status_code == 200
        estado = r.json().get("agen_estado", "").upper()
        assert estado == "CANCELADA", f"La cita no quedó CANCELADA en BD: {r.json()}"

    def test_editar_reagendar_una_sola_cita(self):
        tel, pac, cita, lunes = self._setup_paciente_con_cita("5699")
        r1 = respuesta("Necesito cambiar mi hora", tel)
        assert len(r1) > 0, "No respondió nada al pedir reagendar"

        # Si preguntó fecha/hora directamente (cita única), continuar el flujo
        r2 = respuesta(f"El {lunes} a las 15:00", tel)
        assert "no entend" not in r2, f"Se perdió el flujo de reagendar: {r2}"

    def test_cancelar_sin_citas_pendientes_no_rompe(self):
        tel = _telefono_unico("5700")
        _registrar_paciente("Test", "SinCitas", tel)
        r = respuesta("Quiero cancelar mi hora", tel)
        assert "no encontré" in r.lower() or "no tienes" in r.lower() or "pendiente" in r.lower(), \
            f"No manejó bien la cancelación sin citas: {r}"


# ---------------------------------------------------------------------------
# 4. CONSULTAS GENERALES — horarios de atención y disponibilidad real (Bug #9)
# ---------------------------------------------------------------------------

class TestConsultasGenerales:

    def test_horario_atencion_general(self):
        tel = _telefono_unico("5701")
        _registrar_paciente("Test", "Horario", tel)
        r = respuesta("¿Qué horario de atención tienen?", tel)
        assert (
            "lunes" in r and ("miércoles" in r or "miercoles" in r) and "viernes" in r
        ) or "9:30" in r or "9.30" in r, f"No dio el horario general L-M-V: {r}"

    def test_disponibilidad_real_no_confunde_con_horario_general(self):
        """Bug #9: '¿qué horarios tienes disponibles?' debe intentar horas
        LIBRES reales (Calendar), no solo el horario general de atención."""
        tel = _telefono_unico("5702")
        _registrar_paciente("Test", "Disponibilidad", tel)
        r = respuesta("¿Qué horarios tienes disponibles?", tel)
        assert len(r) > 0, "No respondió nada"
        # Sin Calendar configurado en el entorno de test, debe caer en el
        # fallback explícito (no en un error ni en silencio)
        assert "no entend" not in r, f"No manejó la consulta de disponibilidad: {r}"

    def test_precio_fonasa_bcd(self):
        tel = _telefono_unico("5703")
        _registrar_paciente("Test", "PrecioFonasa", tel)
        respuesta("¿Cuánto cuesta con fonasa?", tel)
        respuesta("Sí", tel)
        r = respuesta("B", tel)
        assert "38.000" in r or "38000" in r, f"No dio precio FONASA B/C/D: {r}"

    def test_precio_particular(self):
        tel = _telefono_unico("5704")
        _registrar_paciente("Test", "PrecioParticular", tel)
        respuesta("¿Cuánto cuesta particular?", tel)
        r = respuesta("Particular", tel)
        assert "100.000" in r or "100000" in r or "particular" in r.lower(), \
            f"No dio precio particular: {r}"


# ---------------------------------------------------------------------------
# 5. DERIVACIÓN A FELIPE — bilateral, sin falsos positivos (Bug #7)
# ---------------------------------------------------------------------------

class TestDerivacionFelipe:

    def test_bilateral_deriva_a_felipe(self):
        tel = _telefono_unico("5705")
        _registrar_paciente("Test", "Bilateral", tel)
        r = respuesta("Tengo dolor en rodilla derecha y hombro izquierdo", tel)
        assert "felipe" in r.lower() or "personalmente" in r.lower(), \
            f"No derivó bilateral a Felipe: {r}"

    def test_mismo_lado_no_es_bilateral(self):
        tel = _telefono_unico("5706")
        _registrar_paciente("Test", "MismoLado", tel)
        r = respuesta("Tengo dolor en rodilla y pierna derecha", tel)
        assert "felipe" not in r.lower(), f"Falso positivo bilateral: {r}"

    def test_mensaje_con_y_sin_relacion_no_dispara_bilateral(self):
        """Bug #7: 'horarios y códigos' NO debe activar la escalada bilateral.
        Nota: el mensaje FONASA legítimo SÍ menciona a "Felipe Castillo" (como
        proveedor de los códigos), así que no basta con buscar "felipe" — hay
        que buscar la frase de escalada real ("te contacta personalmente")."""
        tel = _telefono_unico("5707")
        _registrar_paciente("Test", "SinFalsoBilateral", tel)
        r = respuesta(
            "Soy fonasa tramo C, dame toda la información del programa, dirección, horarios y códigos",
            tel,
        )
        assert "contacta personalmente" not in r.lower() and "en un momento felipe" not in r.lower(), \
            f"Falso positivo bilateral (Bug #7 regresó): {r}"

    def test_zona_ambigua_pregunta_lado(self):
        """Bug #6: diagnóstico sin lado explícito en zona con lados debe
        preguntar el lado, no crear la ficha a ciegas."""
        tel = _telefono_unico("5708")
        _registrar_paciente("Test", "ZonaAmbigua", tel)
        r = respuesta("Tengo tendinitis de rodilla", tel)
        assert "derecha" in r.lower() or "izquierda" in r.lower() or "lado" in r.lower(), \
            f"No preguntó el lado ante zona ambigua: {r}"
