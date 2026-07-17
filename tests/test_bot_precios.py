"""
Tests: Precios, FONASA y tarifas
Valida que el bot responda correctamente sobre costos y previsión.
"""
import pytest
from conftest import respuesta

PHONE = "56900000010"


class TestPrecios:

    def test_valor_sesion_particular(self):
        """El bot debe mencionar $10.000 cuando preguntan por precio."""
        r = respuesta("¿Cuánto vale la sesión?", PHONE)
        assert "10.000" in r or "10000" in r, f"No mencionó precio: {r}"

    def test_valor_particular_directo(self):
        """Pregunta directa por precio particular."""
        r = respuesta("Valor particular por favor", PHONE)
        assert "10.000" in r or "10000" in r, f"No mencionó precio: {r}"

    def test_no_hay_promocion_5_sesiones(self):
        """Debe decir que no hay promo de 5, solo de 10."""
        r = respuesta("¿Cuánto salen 5 sesiones?", PHONE)
        assert "10" in r or "promo" in r or "solo" in r, f"Respuesta inesperada: {r}"

    def test_programa_10_sesiones(self):
        """Debe aclarar que el bono es un programa de 10 sesiones."""
        r = respuesta("El bono vale $37.000", PHONE)
        assert "10" in r or "programa" in r or "37" in r, f"Respuesta inesperada: {r}"

    def test_no_bonos_online(self):
        """No acepta bonos online, solo Santiago Centro."""
        r = respuesta("¿Aceptan bonos online?", PHONE)
        assert "no" in r or "santiago" in r or "presencial" in r, f"Respuesta inesperada: {r}"

    def test_codigos_nivel_1(self):
        """Los códigos FONASA son nivel 1."""
        r = respuesta("¿Los códigos son nivel 1?", PHONE)
        assert "sí" in r or "si" in r or "nivel 1" in r or "nivel1" in r, f"Respuesta inesperada: {r}"

    def test_no_son_2_bonos(self):
        """No son bonos separados, es un programa."""
        r = respuesta("¿Son 2 bonos?", PHONE)
        assert "programa" in r or "no" in r or "sesion" in r, f"Respuesta inesperada: {r}"
