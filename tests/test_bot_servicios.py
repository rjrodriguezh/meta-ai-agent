"""
Tests: Servicios que NO se realizan
Valida que el bot rechace servicios fuera de alcance.
"""
import pytest
from conftest import respuesta

PHONE = "56900000020"

SERVICIOS_NO_DISPONIBLES = [
    "Necesito masajes post operatorio de liposucción",
    "¿Hacen procedimientos post cirugía estética?",
    "Quiero ejercicios para piso pélvico",
    "¿Tratan cicatrices?",
    "Necesito recuperación post cirugía bariátrica",
]


@pytest.mark.parametrize("pregunta", SERVICIOS_NO_DISPONIBLES)
def test_servicio_no_disponible(pregunta):
    """Para servicios fuera de alcance, el bot debe indicar que no lo hace."""
    r = respuesta(pregunta, PHONE)
    assert (
        "no lo hacemos" in r
        or "no realizamos" in r
        or "no ofrecemos" in r
        or "no hacemos" in r
        or "no hacemo" in r
    ), f"No rechazó el servicio correctamente para: '{pregunta}'\nRespuesta: {r}"


class TestServiciosDisponibles:

    def test_atencion_individual(self):
        """No es atención individual (se atienden 3 a la vez)."""
        r = respuesta("¿Es atención individual?", PHONE)
        assert "no es individual" in r or "no individual" in r or "individual" in r, f"Respuesta: {r}"

    def test_no_necesita_ir_antes(self):
        """No hay que ir a hablar con el kine antes."""
        r = respuesta("¿Tengo que ir a hablar con el kine antes?", PHONE)
        assert "no" in r or "chat" in r or "coordina" in r, f"Respuesta: {r}"

    def test_puede_ir_en_tarde(self):
        """Sí se puede ir en la tarde."""
        r = respuesta("¿Puedo ir en la tarde?", PHONE)
        assert "sí" in r or "si" in r or "puede" in r, f"Respuesta: {r}"
