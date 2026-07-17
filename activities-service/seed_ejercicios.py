"""
Script de seed — carga ejercicios dummy al activities-service.
Uso:
    python seed_ejercicios.py [URL]
    python seed_ejercicios.py http://localhost:8084   (default)
"""
import sys
import requests

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8084"

EJERCICIOS = [
    # ── Cabeza / Cuello ──────────────────────────────────────────────────────
    {"nombre": "Rotación cervical activa",
     "detalle": "Gira la cabeza lentamente hacia cada lado hasta sentir resistencia. Mantén 3 segundos. Ideal para contracturas cervicales y rehabilitación post-tortícolis.",
     "link_youtube": "https://www.youtube.com/watch?v=SMrVQj4-M5U",
     "series": 3, "repeticiones": 10, "categoria": "Cabeza / Cuello"},

    {"nombre": "Flexo-extensión cervical",
     "detalle": "Lleva el mentón al pecho y luego mira al techo de forma controlada. Evita movimientos bruscos. Útil para cervicalgia y rigidez matutina.",
     "link_youtube": "https://www.youtube.com/watch?v=9dCECGMVlaE",
     "series": 3, "repeticiones": 10, "categoria": "Cabeza / Cuello"},

    {"nombre": "Inclinación lateral de cuello",
     "detalle": "Lleva la oreja al hombro del mismo lado sin elevar el hombro contrario. Mantén 5 segundos cada lado. Relaja los escalenos y trapecio superior.",
     "link_youtube": "https://www.youtube.com/watch?v=Yx-PoFxsPEo",
     "series": 3, "repeticiones": 8, "categoria": "Cabeza / Cuello"},

    # ── Hombro ───────────────────────────────────────────────────────────────
    {"nombre": "Péndulo de Codman",
     "detalle": "Inclinado hacia adelante, deja el brazo colgar y realiza movimientos circulares pequeños con el peso del propio brazo. Ideal para lesiones de manguito rotador y capsulitis.",
     "link_youtube": "https://www.youtube.com/watch?v=JnkRjQ-7pnk",
     "series": 3, "repeticiones": 15, "categoria": "Hombro"},

    {"nombre": "Rotación externa con banda elástica",
     "detalle": "Con el codo a 90° pegado al cuerpo, gira el antebrazo hacia afuera contra la resistencia de la banda. Fortalece infraespinoso y redondo menor.",
     "link_youtube": "https://www.youtube.com/watch?v=vn3RCeEd3P8",
     "series": 3, "repeticiones": 12, "categoria": "Hombro"},

    {"nombre": "Elevación lateral de hombro (abducción)",
     "detalle": "Eleva los brazos hasta 90° lateralmente, pulgares hacia arriba. Evita elevar los trapecios. Trabaja deltoides medio y supraespinoso.",
     "link_youtube": "https://www.youtube.com/watch?v=3VcKaXpzqRo",
     "series": 3, "repeticiones": 12, "categoria": "Hombro"},

    # ── Brazo / Codo ─────────────────────────────────────────────────────────
    {"nombre": "Curl de bíceps con banda",
     "detalle": "Parado sobre la banda, flexiona el codo llevando la mano al hombro. Mantén el codo pegado al cuerpo. Rehabilitación tras tendinitis bicipital.",
     "link_youtube": "https://www.youtube.com/watch?v=ykJmrZ5v0Oo",
     "series": 3, "repeticiones": 12, "categoria": "Brazo / Codo"},

    {"nombre": "Extensión de tríceps en polea",
     "detalle": "Con el codo fijo, extiende el antebrazo hacia abajo contra resistencia. Trabaja porción larga y lateral del tríceps. Útil post fractura de codo.",
     "link_youtube": "https://www.youtube.com/watch?v=2-LAMcpzODU",
     "series": 3, "repeticiones": 12, "categoria": "Brazo / Codo"},

    {"nombre": "Pronación y supinación con martillo",
     "detalle": "Sujeta un martillo o pesa ligera con el codo a 90°. Rota el antebrazo palma arriba / palma abajo. Excelente para epicondilitis y epitrocleitis.",
     "link_youtube": "https://www.youtube.com/watch?v=tgY0c9DGPBM",
     "series": 3, "repeticiones": 15, "categoria": "Brazo / Codo"},

    # ── Muñeca / Mano ─────────────────────────────────────────────────────────
    {"nombre": "Extensión de muñeca con banda",
     "detalle": "Apoya el antebrazo en una mesa con la mano colgando. Extiende la muñeca hacia arriba contra la banda. Indicado para epicondilitis lateral (codo de tenista).",
     "link_youtube": "https://www.youtube.com/watch?v=Qjt1m6LHMhQ",
     "series": 3, "repeticiones": 15, "categoria": "Muñeca / Mano"},

    {"nombre": "Flexión de muñeca con pesa ligera",
     "detalle": "Con el antebrazo apoyado, dobla la muñeca llevando los dedos hacia arriba. Trabaja flexores de muñeca. Útil en síndrome del túnel carpiano fase subaguda.",
     "link_youtube": "https://www.youtube.com/watch?v=5_sjXVJ0KuE",
     "series": 3, "repeticiones": 15, "categoria": "Muñeca / Mano"},

    {"nombre": "Pinza de dedos con plastilina terapéutica",
     "detalle": "Aplasta y amasa plastilina resistente con los dedos. Trabaja la musculatura intrínseca de la mano. Ideal tras inmovilización o cirugía de mano.",
     "link_youtube": "",
     "series": 3, "repeticiones": 20, "categoria": "Muñeca / Mano"},

    # ── Core / Abdomen ────────────────────────────────────────────────────────
    {"nombre": "Plancha abdominal isométrica",
     "detalle": "Apoya antebrazos y puntas de pies. Mantén el cuerpo en línea recta sin hundir caderas. Activa transverso y multífidos. Base de todo programa de lumbalgias.",
     "link_youtube": "https://www.youtube.com/watch?v=pvIjsG5Svck",
     "series": 3, "repeticiones": 1, "categoria": "Core / Abdomen"},

    {"nombre": "Dead bug (insecto muerto)",
     "detalle": "Boca arriba, extiende brazo y pierna opuestos manteniendo la zona lumbar pegada al suelo. Controla la respiración. Potente activador del transverso abdominal.",
     "link_youtube": "https://www.youtube.com/watch?v=4XLEnwUr1d8",
     "series": 3, "repeticiones": 10, "categoria": "Core / Abdomen"},

    {"nombre": "Puente de glúteos (bridge)",
     "detalle": "Boca arriba con rodillas flexionadas, eleva la cadera formando una línea hombro-cadera-rodilla. Activa glúteo medio, mayor y estabilizadores lumbares.",
     "link_youtube": "https://www.youtube.com/watch?v=OUgsJ8-Vi0E",
     "series": 3, "repeticiones": 15, "categoria": "Core / Abdomen"},

    # ── Cadera ────────────────────────────────────────────────────────────────
    {"nombre": "Abducción de cadera con banda",
     "detalle": "De pie, banda en tobillos, lleva la pierna hacia el lado sin inclinar el tronco. Fortalece glúteo medio. Clave en rehabilitación de cadera y prevención de lesiones de rodilla.",
     "link_youtube": "https://www.youtube.com/watch?v=SqI9d-RPVOY",
     "series": 3, "repeticiones": 15, "categoria": "Cadera"},

    {"nombre": "Sentadilla a silla (sit-to-stand)",
     "detalle": "Desde sentado, levántate sin apoyo de las manos. Controla el descenso lento. Excelente ejercicio funcional para rehabilitación de cadera y rodilla en adultos mayores.",
     "link_youtube": "https://www.youtube.com/watch?v=sWHPGsIYDOI",
     "series": 3, "repeticiones": 10, "categoria": "Cadera"},

    {"nombre": "Rotación interna de cadera en decúbito",
     "detalle": "Boca arriba con rodillas flexionadas, deja caer ambas rodillas hacia el mismo lado controladamente. Moviliza la articulación coxofemoral y estira piriforme.",
     "link_youtube": "https://www.youtube.com/watch?v=gm4B-qqv0Fk",
     "series": 3, "repeticiones": 10, "categoria": "Cadera"},

    # ── Rodilla ───────────────────────────────────────────────────────────────
    {"nombre": "Extensión de rodilla en silla (quad set)",
     "detalle": "Sentado, contrae el cuádriceps y extiende la rodilla lentamente. Mantén 3 segundos en extensión total. Fundamental en rehabilitación post-cirugía de LCA y menisco.",
     "link_youtube": "https://www.youtube.com/watch?v=YyvBfTJDm4s",
     "series": 3, "repeticiones": 15, "categoria": "Rodilla"},

    {"nombre": "Step up (subida al escalón)",
     "detalle": "Sube a un escalón de 15–20 cm apoyando completamente el pie. Trabaja cuádriceps y glúteos en cadena cerrada. Progresión ideal post lesión de rodilla.",
     "link_youtube": "https://www.youtube.com/watch?v=dQqApCGd5Ss",
     "series": 3, "repeticiones": 12, "categoria": "Rodilla"},

    {"nombre": "Isquiotibiales con banda en prono",
     "detalle": "Boca abajo, banda en tobillo, flexiona la rodilla contra la resistencia. Fortalece isquiotibiales. Indicado en rehabilitación de esguinces y ligamentoplastia.",
     "link_youtube": "https://www.youtube.com/watch?v=Orxowest56U",
     "series": 3, "repeticiones": 12, "categoria": "Rodilla"},

    # ── Tobillo / Pie ─────────────────────────────────────────────────────────
    {"nombre": "Elevación de talones (calf raise)",
     "detalle": "De pie, apoyado en una pared, sube en puntillas y baja lentamente. Trabaja gastrocnemio y sóleo. Clave en rehabilitación de esguince de tobillo y tendinitis aquílea.",
     "link_youtube": "https://www.youtube.com/watch?v=gwLzBJYoWlI",
     "series": 3, "repeticiones": 15, "categoria": "Tobillo / Pie"},

    {"nombre": "Eversión de tobillo con banda elástica",
     "detalle": "Sentado, gira el pie hacia afuera contra la resistencia de la banda. Fortalece el peronéo. Previene recidivas de esguince lateral de tobillo.",
     "link_youtube": "https://www.youtube.com/watch?v=vOADwEMtzaU",
     "series": 3, "repeticiones": 15, "categoria": "Tobillo / Pie"},

    {"nombre": "Equilibrio monopodal con ojos cerrados",
     "detalle": "Apóyate en un solo pie con los ojos cerrados durante 20–30 segundos. Mejora propiocepción del tobillo y estabilidad global. Progresión sobre superficie inestable.",
     "link_youtube": "https://www.youtube.com/watch?v=2y6TIZ0vlbs",
     "series": 3, "repeticiones": 1, "categoria": "Tobillo / Pie"},
]

def seed():
    ok = 0
    err = 0
    for e in EJERCICIOS:
        try:
            r = requests.post(f"{BASE}/ejercicios", json=e, timeout=5)
            if r.status_code in (200, 201):
                print(f"  ✓  [{e['categoria']}] {e['nombre']}")
                ok += 1
            else:
                print(f"  ✗  [{e['categoria']}] {e['nombre']} → {r.status_code} {r.text}")
                err += 1
        except Exception as ex:
            print(f"  ✗  [{e['categoria']}] {e['nombre']} → {ex}")
            err += 1
    print(f"\n{'='*50}")
    print(f"  Seed completado: {ok} OK  |  {err} errores")
    print(f"{'='*50}")

if __name__ == "__main__":
    print(f"\nSeeding {BASE} con {len(EJERCICIOS)} ejercicios...\n")
    seed()
