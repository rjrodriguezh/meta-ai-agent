"""
Tests: Agendamiento, cancelación y reagendamiento
"""
import pytest
from conftest import respuesta, send

PHONE_AGENDA = "56900000040"
PHONE_CANCEL = "56900000041"
PHONE_BONO   = "56900000042"


class TestAgendamiento:

    def test_quiere_agendar(self):
        """Quiere agendar → el bot debe continuar el flujo."""
        r = respuesta("Quiero agendar una hora", PHONE_AGENDA)
        assert len(r) > 0, "No respondió"
        # No debe decir 'no entendí'
        assert "no entendí" not in r and "no entend" not in r, f"No entendió: {r}"

    def test_tiene_bono_quiere_empezar(self):
        """Paciente con bono listo para agendar."""
        r = respuesta("Ya compré los bonos", PHONE_BONO)
        assert (
            "ok" in r or "nombre" in r or "mañana" in r
            or "agendar" in r or "empezar" in r or "semana" in r
        ), f"Respuesta inesperada: {r}"

    def test_puede_empezar_sin_bono(self):
        """Puede agendar incluso sin bono todavía."""
        r = respuesta("¿Puedo empezar sin el bono?", PHONE_BONO)
        assert "no" not in r[:20] or "nombre" in r or "oka" in r, f"Rechazó sin bono: {r}"

    def test_informacion_direccion(self):
        """Debe dar la dirección al confirmar cita."""
        r = respuesta("¿Dónde queda la clínica?", PHONE_AGENDA)
        assert (
            "san antonio" in r or "418" in r
            or "piso 3" in r or "santiago" in r
        ), f"No dio dirección: {r}"


class TestCancelacion:

    def test_cancelar_cita(self):
        """Cancelación → el bot debe responder y ofrecer reagendar."""
        r = respuesta("Hoy no puedo asistir a mi cita", PHONE_CANCEL)
        assert (
            "reagendar" in r or "agendar" in r
            or "siguiente" in r or "semana" in r
            or "lunes" in r or "viernes" in r
            or "oka" in r or "ok" in r
        ), f"No manejó cancelación: {r}"

    def test_reagendar(self):
        """Reagendar → debe proponer nuevo día."""
        r = respuesta("Necesito cambiar mi cita para la próxima semana", PHONE_CANCEL)
        assert len(r) > 0 and "no entend" not in r, f"No manejó reagendamiento: {r}"


class TestSaludo:

    def test_saludo_hola(self):
        """Saludo genérico → respuesta de bienvenida."""
        r = respuesta("Hola", PHONE_AGENDA)
        assert (
            "buenos" in r or "hola" in r
            or "ayudar" in r or "diga" in r
        ), f"Saludo inadecuado: {r}"

    def test_saludo_buen_dia(self):
        """Saludo con 'buen día' → responder 'Buenos días' + Diga."""
        r = respuesta("Hola buen día, quería consultar", PHONE_AGENDA)
        assert "días" in r or "diga" in r or "información" in r, f"Respuesta: {r}"

    def test_mas_informacion(self):
        """Lead desde Meta: 'Quiero más información'."""
        r = respuesta("Hola, quiero más información", PHONE_AGENDA)
        assert len(r) > 10 and "no entend" not in r, f"No respondió bien: {r}"
