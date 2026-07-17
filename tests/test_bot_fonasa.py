"""
Tests: Flujos FONASA y orden médica
Valida el proceso completo de atención con previsión.
"""
import pytest
from conftest import respuesta, send
import time

PHONE_FONASA = "56900000030"
PHONE_SIN_ORDEN = "56900000031"
PHONE_BILATERAL = "56900000032"


class TestOrdenMedica:

    def test_tiene_orden_medica(self):
        """Si tiene orden médica, el bot debe preguntar el diagnóstico."""
        r = respuesta("Sí, tengo orden médica", PHONE_FONASA)
        assert "diagnóstico" in r or "diagnostico" in r, f"No preguntó diagnóstico: {r}"

    def test_sin_orden_medica(self):
        """Sin orden médica, debe indicar que consiga una con su médico."""
        r = respuesta("No tengo orden médica", PHONE_SIN_ORDEN)
        assert (
            "médico" in r or "medico" in r
            or "orden" in r
            or "conseguir" in r
            or "consiga" in r
        ), f"No indicó conseguir orden: {r}"

    def test_fonasa_horario(self):
        """Debe mencionar el horario FONASA (hasta las 2pm / 14:00)."""
        r = respuesta("¿Hasta qué hora atienden FONASA?", PHONE_FONASA)
        assert "2pm" in r or "14" in r or "lunes" in r or "viernes" in r, f"No mencionó horario FONASA: {r}"

    def test_fonasa_dias(self):
        """FONASA atiende lunes a viernes."""
        r = respuesta("¿Qué días atienden con FONASA?", PHONE_FONASA)
        assert "lunes" in r or "viernes" in r or "lunes a viernes" in r, f"No mencionó días: {r}"


class TestDiagnostico:

    def test_diagnostico_una_parte(self):
        """Diagnóstico de una zona → flujo FONASA normal."""
        # Primero establece que tiene orden médica
        send("Hola, tengo orden médica", PHONE_FONASA)
        r = respuesta("Tengo tendinitis de hombro derecho", PHONE_FONASA)
        assert (
            "bono" in r or "fonasa" in r or "2pm" in r
            or "agendar" in r or "orden" in r
        ), f"No continuó flujo FONASA: {r}"

    def test_diagnostico_bilateral(self):
        """Diagnóstico bilateral → Felipe contacta personalmente."""
        r = respuesta("Tengo dolor en rodilla derecha y hombro izquierdo", PHONE_BILATERAL)
        assert (
            "felipe" in r
            or "personalmente" in r
            or "contacta" in r
            or "coordinar" in r
        ), f"No derivó a Felipe: {r}"

    def test_lumbago(self):
        """Lumbago es columna (una parte)."""
        r = respuesta("Tengo lumbago", PHONE_FONASA)
        # Debería continuar el flujo o preguntar lado
        assert len(r) > 0, "No respondió nada"

    def test_fascitis_plantar(self):
        """Fascitis plantar es pie/tobillo (una parte)."""
        r = respuesta("Mi diagnóstico es fascitis plantar del pie derecho", PHONE_FONASA)
        assert len(r) > 0, "No respondió nada"
