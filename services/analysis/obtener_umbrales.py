from services.data_fetching.obtener_historial import cargar_historial
import numpy as np


def normalizar_cuota(cuota):
    try:
        cuota = float(cuota)
        if cuota <= 1:
            return None
        return cuota
    except (TypeError, ValueError):
        return None


def extraer_apuestas():
    partidos = cargar_historial()
    partidos_dict = [p.to_dict() for p in partidos]

    apuestas = {
        "resultado": [],
        "btts": [],
        "over": []
    }

    for p in partidos_dict:
        if p.get("estado") != "FT":
            continue

        # ===== RESULTADO 1X2 =====
        r = p["prediccion"]["resultado_1x2"]
        prob = float(r["probabilidad_max"])

        if r["prediccion"] == "Local":
            cuota = normalizar_cuota(p.get("cuota_local"))
            acierto = p["resultado"] == 1
        elif r["prediccion"] == "Empate":
            cuota = normalizar_cuota(p.get("cuota_empate"))
            acierto = p["resultado"] == 0
        else:
            cuota = normalizar_cuota(p.get("cuota_visitante"))
            acierto = p["resultado"] == 2

        if cuota:
            apuestas["resultado"].append({
                "prob": prob,
                "cuota": cuota,
                "acierto": int(acierto)
            })

        # ===== BTTS =====
        b = p["prediccion"]["btts"]
        prob = float(b["probabilidad"])
        cuota = normalizar_cuota(p.get("cuota_btts"))

        if cuota:
            apuestas["btts"].append({
                "prob": prob,
                "cuota": cuota,
                "acierto": int(p["ambos_marcan"] == 1)
            })

        # ===== OVER 2.5 =====
        o = p["prediccion"]["over25"]
        prob = float(o["probabilidad"])
        cuota = normalizar_cuota(p.get("cuota_over"))

        if cuota:
            apuestas["over"].append({
                "prob": prob,
                "cuota": cuota,
                "acierto": int(p["mas_2_5"] == 1)
            })

    return apuestas


def optimizar_umbrales(apuestas, min_apuestas_base=30):
    resultados = {
        "agresivo": {},
        "moderado": {},
        "conservador": {}
    }

    for mercado in apuestas:
        datos = apuestas[mercado]

        # === AGRESIVO: más volumen, ROI positivo aunque bajo ===
        mejor_agresivo = {"roi": -999, "umbral_prob": None, "margen": None, "apuestas": 0}
        for umbral_prob in np.arange(0.50, 0.62, 0.01):      # umbrales más bajos
            for margen in np.arange(0.00, 0.08, 0.01):       # margen muy permisivo
                ganancias, n = simular_apuestas(datos, umbral_prob, margen)
                if n >= min_apuestas_base:
                    roi = sum(ganancias) / n if n > 0 else -999
                    if roi > mejor_agresivo["roi"]:
                        mejor_agresivo = {"roi": round(roi, 4), "umbral_prob": round(umbral_prob, 2),
                                          "margen": round(margen, 2), "apuestas": n}

        # === MODERADO: equilibrio (tu optimización actual, pero más amplio) ===
        mejor_moderado = {"roi": -999, "umbral_prob": None, "margen": None, "apuestas": 0}
        for umbral_prob in np.arange(0.53, 0.68, 0.01):
            for margen in np.arange(0.01, 0.12, 0.01):
                ganancias, n = simular_apuestas(datos, umbral_prob, margen)
                if n >= min_apuestas_base:
                    roi = sum(ganancias) / n if n > 0 else -999
                    if roi > mejor_moderado["roi"]:
                        mejor_moderado = {"roi": round(roi, 4), "umbral_prob": round(umbral_prob, 2),
                                          "margen": round(margen, 2), "apuestas": n}

        # === CONSERVADOR: alta calidad, ROI alto aunque pocas apuestas ===
        mejor_conservador = {"roi": -999, "umbral_prob": None, "margen": None, "apuestas": 0}
        for umbral_prob in np.arange(0.60, 0.80, 0.01):     # umbrales altos
            for margen in np.arange(0.06, 0.20, 0.02):      # margen exigente
                ganancias, n = simular_apuestas(datos, umbral_prob, margen)
                if n >= min_apuestas_base // 2:
                    roi = sum(ganancias) / n if n > 0 else -999
                    if roi > mejor_conservador["roi"]:
                        mejor_conservador = {"roi": round(roi, 4), "umbral_prob": round(umbral_prob, 2),
                                             "margen": round(margen, 2), "apuestas": n}

        DEFAULTS = {
            "resultado": {"umbral_prob": 0.54, "margen": 0.03},
            "btts":      {"umbral_prob": 0.56, "margen": 0.03},
            "over":      {"umbral_prob": 0.62, "margen": 0.03},
        }

        # Luego dentro del bucle:
        def get_default(mercado):
            return {
                "roi": 0.0,
                "umbral_prob": DEFAULTS[mercado]["umbral_prob"],
                "margen": DEFAULTS[mercado]["margen"],
                "apuestas": 0
            }

        resultados["agresivo"][mercado] = mejor_agresivo if mejor_agresivo["apuestas"] > 0 else get_default(mercado)

        resultados["moderado"][mercado] = mejor_moderado if mejor_moderado["apuestas"] > 0 else get_default(mercado)

        resultados["conservador"][mercado] = mejor_conservador if mejor_conservador["apuestas"] > 0 else get_default(mercado)


    return resultados


# Función auxiliar para no repetir código
def simular_apuestas(datos, umbral_prob, margen):
    ganancias = []
    for a in datos:
        prob = a["prob"]
        cuota = a["cuota"]
        acierto = a["acierto"]
        value = prob - (1 / cuota)
        if prob >= umbral_prob and value >= margen:
            ganancias.append(cuota - 1 if acierto else -1)
    return ganancias, len(ganancias)
