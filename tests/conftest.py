import pytest
import requests
import time

AI_URL = "http://localhost:8081"
TEST_PHONE = "56900000001"  # número ficticio para tests


def send(mensaje: str, numero: str = TEST_PHONE) -> dict:
    """Envía un mensaje al ai-service y retorna la respuesta."""
    r = requests.post(
        f"{AI_URL}/process",
        json={"numero": numero, "mensaje": mensaje},
        timeout=30,
    )
    r.raise_for_status()
    return r.json()


def respuesta(mensaje: str, numero: str = TEST_PHONE) -> str:
    """Helper: retorna solo el texto de respuesta."""
    return send(mensaje, numero).get("respuesta", "").lower()


@pytest.fixture(scope="session", autouse=True)
def check_service():
    """Verifica que el ai-service esté disponible antes de correr tests."""
    try:
        r = requests.get(f"{AI_URL}/health", timeout=5)
        assert r.status_code == 200, "ai-service no responde"
    except Exception as e:
        pytest.skip(f"ai-service no disponible: {e}")
