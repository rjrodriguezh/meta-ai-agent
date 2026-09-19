"""
Script de seed — carga tipos de diagnóstico y los vincula con ejercicios ya
existentes en activities-service (correr DESPUÉS de seed_ejercicios.py).

Es idempotente: si un diagnóstico ya existe (por nombre), lo actualiza en
vez de fallar por duplicado — se puede correr las veces que quieras.

Uso:
    python seed_diagnosticos.py [URL]
    python seed_diagnosticos.py http://localhost:8084   (default)
"""
import sys
import requests

BASE = sys.argv[1].rstrip("/") if len(sys.argv) > 1 else "http://localhost:8084"

# 25 diagnósticos, 3 ejercicios cada uno (el set completo de su zona en el
# catálogo actual de 24 ejercicios / 8 zonas — cada zona tiene exactamente 3).
DIAGNOSTICOS = [
    # ── Cabeza / Cuello ──────────────────────────────────────────────────────
    {"nombre": "Cervicalgia", "zona": "Cabeza / Cuello",
     "keywords": "cervicalgia,cervical",
     "ejercicios": ["Rotación cervical activa", "Flexo-extensión cervical", "Inclinación lateral de cuello"]},
    {"nombre": "Torticolis", "zona": "Cabeza / Cuello",
     "keywords": "torticolis,tortícolis",
     "ejercicios": ["Rotación cervical activa", "Flexo-extensión cervical", "Inclinación lateral de cuello"]},
    {"nombre": "Contractura cervical", "zona": "Cabeza / Cuello",
     "keywords": "contractura cervical,contractura de cuello,rigidez cervical",
     "ejercicios": ["Rotación cervical activa", "Flexo-extensión cervical", "Inclinación lateral de cuello"]},

    # ── Hombro ───────────────────────────────────────────────────────────────
    {"nombre": "Tendinitis de hombro / Manguito rotador", "zona": "Hombro",
     "keywords": "manguito rotador,tendinitis de hombro,tendinitis hombro,tendinosis de hombro",
     "ejercicios": ["Péndulo de Codman", "Rotación externa con banda elástica", "Elevación lateral de hombro (abducción)"]},
    {"nombre": "Capsulitis adhesiva (hombro congelado)", "zona": "Hombro",
     "keywords": "capsulitis,hombro congelado",
     "ejercicios": ["Péndulo de Codman", "Rotación externa con banda elástica", "Elevación lateral de hombro (abducción)"]},
    {"nombre": "Bursitis subacromial", "zona": "Hombro",
     "keywords": "bursitis subacromial,bursitis de hombro,bursitis hombro",
     "ejercicios": ["Péndulo de Codman", "Rotación externa con banda elástica", "Elevación lateral de hombro (abducción)"]},

    # ── Brazo / Codo ─────────────────────────────────────────────────────────
    {"nombre": "Epicondilitis (codo de tenista)", "zona": "Brazo / Codo",
     "keywords": "epicondilitis,codo de tenista",
     "ejercicios": ["Curl de bíceps con banda", "Extensión de tríceps en polea", "Pronación y supinación con martillo"]},
    {"nombre": "Epitrocleitis (codo de golfista)", "zona": "Brazo / Codo",
     "keywords": "epitrocleitis,codo de golfista",
     "ejercicios": ["Curl de bíceps con banda", "Extensión de tríceps en polea", "Pronación y supinación con martillo"]},
    {"nombre": "Tendinitis bicipital", "zona": "Brazo / Codo",
     "keywords": "tendinitis bicipital,biceps,bíceps",
     "ejercicios": ["Curl de bíceps con banda", "Extensión de tríceps en polea", "Pronación y supinación con martillo"]},

    # ── Muñeca / Mano ─────────────────────────────────────────────────────────
    {"nombre": "Síndrome del túnel carpiano", "zona": "Muñeca / Mano",
     "keywords": "tunel carpiano,túnel carpiano",
     "ejercicios": ["Extensión de muñeca con banda", "Flexión de muñeca con pesa ligera", "Pinza de dedos con plastilina terapéutica"]},
    {"nombre": "Tenosinovitis de De Quervain", "zona": "Muñeca / Mano",
     "keywords": "de quervain,tenosinovitis",
     "ejercicios": ["Extensión de muñeca con banda", "Flexión de muñeca con pesa ligera", "Pinza de dedos con plastilina terapéutica"]},
    {"nombre": "Rehabilitación post-inmovilización de mano", "zona": "Muñeca / Mano",
     "keywords": "post inmovilizacion,post cirugia de mano,post fractura de muñeca,post fractura de muneca",
     "ejercicios": ["Extensión de muñeca con banda", "Flexión de muñeca con pesa ligera", "Pinza de dedos con plastilina terapéutica"]},

    # ── Core / Abdomen ────────────────────────────────────────────────────────
    {"nombre": "Lumbago / Lumbalgia", "zona": "Core / Abdomen",
     "keywords": "lumbago,lumbalgia,lumbago no especificado",
     "ejercicios": ["Plancha abdominal isométrica", "Dead bug (insecto muerto)", "Puente de glúteos (bridge)"]},
    {"nombre": "Ciática", "zona": "Core / Abdomen",
     "keywords": "ciatica,ciática,discopatia,discopatía,espondiloartrosis lumbar,foramino estenosis lumbar",
     "ejercicios": ["Plancha abdominal isométrica", "Dead bug (insecto muerto)", "Puente de glúteos (bridge)"]},
    {"nombre": "Recuperación post-parto (diástasis abdominal)", "zona": "Core / Abdomen",
     "keywords": "diastasis,post parto,postparto",
     "ejercicios": ["Plancha abdominal isométrica", "Dead bug (insecto muerto)", "Puente de glúteos (bridge)"]},

    # ── Cadera ────────────────────────────────────────────────────────────────
    {"nombre": "Rehabilitación de cadera (artrosis/prótesis)", "zona": "Cadera",
     "keywords": "cadera,coxofemoral,protesis de cadera,prótesis de cadera,artrosis de cadera",
     "ejercicios": ["Abducción de cadera con banda", "Sentadilla a silla (sit-to-stand)", "Rotación interna de cadera en decúbito"]},
    {"nombre": "Bursitis trocantérea", "zona": "Cadera",
     "keywords": "bursitis trocanterea,trocanter,trocánter",
     "ejercicios": ["Abducción de cadera con banda", "Sentadilla a silla (sit-to-stand)", "Rotación interna de cadera en decúbito"]},
    {"nombre": "Síndrome piriforme", "zona": "Cadera",
     "keywords": "piriforme",
     "ejercicios": ["Abducción de cadera con banda", "Sentadilla a silla (sit-to-stand)", "Rotación interna de cadera en decúbito"]},

    # ── Rodilla ───────────────────────────────────────────────────────────────
    {"nombre": "Condromalacia rotuliana", "zona": "Rodilla",
     "keywords": "condromalacia rotuliana,condromalacia",
     "ejercicios": ["Extensión de rodilla en silla (quad set)", "Step up (subida al escalón)", "Isquiotibiales con banda en prono"]},
    {"nombre": "Meniscopatía / Esguince de rodilla", "zona": "Rodilla",
     "keywords": "meniscopatia,meniscopatía,esguince de rodilla",
     "ejercicios": ["Extensión de rodilla en silla (quad set)", "Step up (subida al escalón)", "Isquiotibiales con banda en prono"]},
    {"nombre": "Post-cirugía de rodilla (LCA / ligamentoplastia)", "zona": "Rodilla",
     "keywords": "lca,ligamentoplastia,post cirugia de rodilla,post quirurgico de rodilla",
     "ejercicios": ["Extensión de rodilla en silla (quad set)", "Step up (subida al escalón)", "Isquiotibiales con banda en prono"]},
    {"nombre": "Tendinitis pata de ganso", "zona": "Rodilla",
     "keywords": "pata de ganso,tendinosis rotuliana",
     "ejercicios": ["Extensión de rodilla en silla (quad set)", "Step up (subida al escalón)", "Isquiotibiales con banda en prono"]},

    # ── Tobillo / Pie ─────────────────────────────────────────────────────────
    {"nombre": "Esguince de tobillo", "zona": "Tobillo / Pie",
     "keywords": "esguince de tobillo,esguince tobillo,esguince ligamento peroneoastragalino",
     "ejercicios": ["Elevación de talones (calf raise)", "Eversión de tobillo con banda elástica", "Equilibrio monopodal con ojos cerrados"]},
    {"nombre": "Fascitis plantar", "zona": "Tobillo / Pie",
     "keywords": "fascitis plantar,fascitis",
     "ejercicios": ["Elevación de talones (calf raise)", "Eversión de tobillo con banda elástica", "Equilibrio monopodal con ojos cerrados"]},
    {"nombre": "Tendinosis gemelar / Aquílea", "zona": "Tobillo / Pie",
     "keywords": "tendinosis gemelar,gemelar,tendinitis aquilea,tendinitis aquílea,entesitis,espolon calcaneo,espolón calcáneo",
     "ejercicios": ["Elevación de talones (calf raise)", "Eversión de tobillo con banda elástica", "Equilibrio monopodal con ojos cerrados"]},
]


def obtener_mapa_ejercicios():
    r = requests.get(f"{BASE}/ejercicios", timeout=10)
    r.raise_for_status()
    return {e["eje_nombre"]: e["eje_id"] for e in r.json()}


def obtener_mapa_diagnosticos():
    r = requests.get(f"{BASE}/diagnosticos", timeout=10)
    r.raise_for_status()
    return {d["diag_nombre"]: d["diag_id"] for d in r.json()}


def seed():
    mapa_ej = obtener_mapa_ejercicios()
    if not mapa_ej:
        print("⚠️  No hay ejercicios cargados todavía. Corre primero: python seed_ejercicios.py")
        return
    mapa_diag = obtener_mapa_diagnosticos()

    creados = 0
    actualizados = 0
    err = 0
    for d in DIAGNOSTICOS:
        ids = [mapa_ej[n] for n in d["ejercicios"] if n in mapa_ej]
        faltantes = [n for n in d["ejercicios"] if n not in mapa_ej]
        if faltantes:
            print(f"  ⚠️  [{d['nombre']}] ejercicios no encontrados (¿nombre distinto?): {faltantes}")

        existente_id = mapa_diag.get(d["nombre"])
        try:
            if existente_id:
                payload = {"zona": d["zona"], "keywords": d["keywords"], "ejercicio_ids": ids}
                r = requests.put(f"{BASE}/diagnosticos/{existente_id}", json=payload, timeout=5)
                if r.status_code == 200:
                    print(f"  ↻  {d['nombre']} → actualizado ({len(ids)} ejercicios)")
                    actualizados += 1
                else:
                    print(f"  ✗  {d['nombre']} → {r.status_code} {r.text}")
                    err += 1
            else:
                payload = {"nombre": d["nombre"], "zona": d["zona"], "keywords": d["keywords"], "ejercicio_ids": ids}
                r = requests.post(f"{BASE}/diagnosticos", json=payload, timeout=5)
                if r.status_code in (200, 201):
                    print(f"  ✓  {d['nombre']} → creado ({len(ids)} ejercicios)")
                    creados += 1
                else:
                    print(f"  ✗  {d['nombre']} → {r.status_code} {r.text}")
                    err += 1
        except Exception as ex:
            print(f"  ✗  {d['nombre']} → {ex}")
            err += 1

    print(f"\n{'='*50}")
    print(f"  Seed completado: {creados} creados | {actualizados} actualizados | {err} errores")
    print(f"  Total diagnósticos definidos: {len(DIAGNOSTICOS)}")
    print(f"{'='*50}")


if __name__ == "__main__":
    print(f"\nSeeding {BASE} con {len(DIAGNOSTICOS)} tipos de diagnóstico...\n")
    seed()
