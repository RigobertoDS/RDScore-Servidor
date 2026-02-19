"""
Optimización de umbrales v2 con Historial Completo.

Estrategia Híbrida:
1. ENTRENAMIENTO: Usa `partidos.pkl` (27k partidos) para aprender patrones.
   - Se excluyen los partidos que estén en `historial.pkl` para evitar leakage.
2. VALIDACIÓN: Usa `historial.pkl` (~1200 partidos con cuotas reales).
   - Se generan predicciones frescas con el modelo v2.
3. OPTIMIZACIÓN: Busca umbrales rentables sobre ese set de validación de alta calidad.

Uso:
  python -c "from services.ml_v2.optimizar_umbrales import run; run()"
"""

import os
import json
import logging
import pickle
import numpy as np
import warnings
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
import xgboost as xgb
import lightgbm as lgb
from datetime import datetime

from config import BASE_DIR
from services.ml_v2.features import FeatureExtractor, _parse_fecha
from services.data_fetching.obtener_partidos import cargar_partidos
from services.data_fetching.obtener_historial import cargar_historial

logger = logging.getLogger("opt_umbrales_v2")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
warnings.filterwarnings("ignore")

# ─── Utilidades ───────────────────────────────────────────────────

def _safe_float(val, default=-1.0):
    try:
        if val is None: return default
        v = float(val)
        return v if v > 1.0 else default
    except (TypeError, ValueError):
        return default

def get_match_id(p):
    """Genera ID único para identificar duplicados (fecha, local, visitante)."""
    d = _parse_fecha(p.fecha)
    d_str = d.strftime("%Y-%m-%d") if d else "1970-01-01"
    # Normalizar nombres simples
    l = p.equipo_local.nombre if hasattr(p.equipo_local, 'nombre') else str(p.equipo_local)
    v = p.equipo_visitante.nombre if hasattr(p.equipo_visitante, 'nombre') else str(p.equipo_visitante)
    return f"{d_str}|{l}|{v}"

def extraer_targets(p):
    """Extrae targets numéricos (gl, gv, btts, over, res)."""
    gl = p.goles_local if p.goles_local >= 0 else 0
    gv = p.goles_visitante if p.goles_visitante >= 0 else 0
    btts = 1 if (gl > 0 and gv > 0) else 0
    over = 1 if (gl + gv) > 2 else 0
    res = 1 if gl > gv else (2 if gv > gl else 0)
    return gl, gv, btts, over, res

# ─── Pipeline Completo ───────────────────────────────────────────

def pipeline_entrenamiento_optimizacion():
    logger.info("=== INICIO: Pipeline de Optimización Híbrida ===")

    # 1. Cargar datos
    logger.info("Cargando `partidos.pkl` (Training candidates)...")
    partidos_raw = cargar_partidos() 
    partidos_ft = [p for p in partidos_raw if p.estado == "FT"]
    
    logger.info("Cargando `historial.pkl` (Validation set)...")
    historial = cargar_historial()
    
    # 2. Identificar y limpiar
    ids_historial = set(get_match_id(p) for p in historial)
    logger.info(f"  Historial tiene {len(historial)} partidos únicos.")

    partidos_train = []
    for p in partidos_ft:
        mid = get_match_id(p)
        if mid not in ids_historial:
            partidos_train.append(p)
    
    logger.info(f"  Partidos para entrenamiento (excluyendo historial): {len(partidos_train)}")
    
    # Ordenar por fecha
    partidos_train.sort(key=lambda p: _parse_fecha(p.fecha) or datetime(1970,1,1))
    
    # 3. Feature Extraction (Train & Validation)
    logger.info("Extrayendo features...")
    # Usamos TODOS para el extractor histórico, pero solo entrenamos con subset
    todos = partidos_train + historial
    todos.sort(key=lambda p: _parse_fecha(p.fecha) or datetime(1970,1,1))
    
    extractor = FeatureExtractor(todos)
    
    # X_train
    X_train = np.array([extractor.extraer(p).flatten() for p in partidos_train])
    y_btts_t = np.array([extraer_targets(p)[2] for p in partidos_train])
    y_over_t = np.array([extraer_targets(p)[3] for p in partidos_train])
    y_res_t  = np.array([extraer_targets(p)[4] for p in partidos_train])

    # X_val (Historial)
    X_val = np.array([extractor.extraer(p).flatten() for p in historial])
    # No necesitamos y_val para entrenar, solo para validar targets
    
    logger.info(f"  Dimensiones: X_train={X_train.shape}, X_val={X_val.shape}")

    # 4. Entrenar Modelos (Base + Calibración interna CV)
    #    Calibramos con CV sobre train para no tocar historial (que es puro validación)
    
    msg_modelo = "LightGBM + CalibratedCV(cv=3)"
    
    def entrenar_modelo(y, name):
        logger.info(f"  Entrenando {name} ({msg_modelo})...")
        base = lgb.LGBMClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.05,
            random_state=42, n_jobs=-1, verbose=-1
        )
        # Calibración interna 3-fold sobre Training Set
        model = CalibratedClassifierCV(base, method='isotonic', cv=3)
        model.fit(X_train, y)
        return model

    m_btts = entrenar_modelo(y_btts_t, "BTTS")
    m_over = entrenar_modelo(y_over_t, "OVER")
    m_res  = entrenar_modelo(y_res_t,  "RESULTADO")

    # 5. Predecir sobre Historial (Generar apuestas)
    logger.info("Generando probabilidades v2 para el historial de validación...")
    
    apuestas = {"btts": [], "over": [], "resultado": []}
    
    # Batch predict
    probs_btts = m_btts.predict_proba(X_val)[:, 1]
    probs_over = m_over.predict_proba(X_val)[:, 1]
    probs_res  = m_res.predict_proba(X_val) # [class 0, 1, 2] -> Empate, Local, Visitante? 
                                            # Ojo: classes_ suelen ser [0, 1, 2] ordenadas
                                            # 0=Empate, 1=Local, 2=Visitante (según targets)
    
    # Verificar orden de clases
    # Mis targets: 1=Local, 0=Empate, 2=Visitante? Revisar extraer_targets
    # extraer_targets: res = 1 (L), 2 (V), 0 (E)
    # classes_ sklearn: [0, 1, 2] sorted.
    # index 0 -> class 0 (Empate)
    # index 1 -> class 1 (Local)
    # index 2 -> class 2 (Visitante)
    
    for i, p in enumerate(historial):
        # Odds reales de historial
        c_btts = _safe_float(getattr(p, 'cuota_btts', -1))
        c_over = _safe_float(getattr(p, 'cuota_over', -1))
        
        # BTTS
        if c_btts > 1.0:
            apuestas["btts"].append({
                "prob": float(probs_btts[i]),
                "cuota": c_btts,
                "acierto": int(p.ambos_marcan == 1)
            })
            
        # OVER
        if c_over > 1.0:
            apuestas["over"].append({
                "prob": float(probs_over[i]),
                "cuota": c_over,
                "acierto": int(p.mas_2_5 == 1)
            })

        # RESULTADO
        # Probabilidades
        p_emp = probs_res[i][0]
        p_loc = probs_res[i][1]
        p_vis = probs_res[i][2]
        
        # Elegir la mayor
        if p_loc > p_emp and p_loc > p_vis:
            pred, prob, c_raw, ok = 1, p_loc, getattr(p, 'cuota_local', -1), p.resultado == 1
        elif p_vis > p_loc and p_vis > p_emp:
            pred, prob, c_raw, ok = 2, p_vis, getattr(p, 'cuota_visitante', -1), p.resultado == 2
        else:
            pred, prob, c_raw, ok = 0, p_emp, getattr(p, 'cuota_empate', -1), p.resultado == 0
            
        c_res = _safe_float(c_raw)
        if c_res > 1.0:
            apuestas["resultado"].append({
                "prob": float(prob),
                "cuota": c_res,
                "acierto": int(ok)
            })

    return apuestas

# ─── Grid Search y Guardado (Reutilizado) ─────────────────────────

def simular_apuestas(datos, umbral_prob, margen_min):
    ganancias = []
    for d in datos:
        prob = d["prob"]
        cuota = d["cuota"]
        value = prob - (1.0 / cuota)
        if prob >= umbral_prob and value >= margen_min:
            ganancia = cuota - 1 if d["acierto"] else -1
            ganancias.append(ganancia)
    return ganancias, len(ganancias)

def grid_search(datos, prob_range, margen_range, min_apuestas=15):
    mejor = {"roi": -999, "umbral_prob": None, "margen": None, "apuestas": 0, "aciertos": 0}
    for umbral in prob_range:
        for margen in margen_range:
            g, n = simular_apuestas(datos, umbral, margen)
            if n >= min_apuestas:
                roi = sum(g) / n * 100
                if roi > mejor["roi"]:
                    aciertos = sum(1 for x in g if x > 0)
                    mejor = {
                        "roi": round(roi, 2),
                        "umbral_prob": round(float(umbral), 2),
                        "margen": round(float(margen), 2),
                        "apuestas": n,
                        "aciertos": aciertos,
                        "accuracy": round(aciertos / n * 100, 1),
                        "beneficio": round(sum(g), 2)
                    }
    return mejor

def optimizar(apuestas):
    res = {"agresivo": {}, "moderado": {}, "conservador": {}}
    
    for mercado in ["btts", "over", "resultado"]:
        datos = apuestas.get(mercado, [])
        if not datos:
            continue
        
        logger.info(f"  ── {mercado.upper()} ({len(datos)} apuestas) ──")
        
        # Agresivo
        agr = grid_search(datos, np.arange(0.40, 0.60, 0.01), np.arange(-0.05, 0.05, 0.005), min_apuestas=30)
        res["agresivo"][mercado] = agr
        logger.info(f"    Agresivo: ROI={agr['roi']:+.1f}% ({agr['apuestas']} ap, {agr.get('accuracy',0)}% acc)")
        
        # Moderado
        mod = grid_search(datos, np.arange(0.50, 0.70, 0.01), np.arange(0.00, 0.10, 0.005), min_apuestas=20)
        res["moderado"][mercado] = mod
        logger.info(f"    Moderado: ROI={mod['roi']:+.1f}% ({mod['apuestas']} ap, {mod.get('accuracy',0)}% acc)")

        # Conservador (Alta Probabilidad, Buen Margen)
        # Relajamos un poco para encontrar apuestas (antes 0.60/0.05 daba 0 bets)
        con = grid_search(datos, np.arange(0.55, 0.80, 0.01), np.arange(0.025, 0.10, 0.005), min_apuestas=10)
        res["conservador"][mercado] = con
        logger.info(f"    Conservador: ROI={con['roi']:+.1f}% ({con['apuestas']} ap, {con.get('accuracy',0)}% acc)")
        
    return res

def guardar_umbrales(resultados):
    ruta = os.path.join(BASE_DIR, 'datos', 'umbrales_v2.json')
    with open(ruta, 'w', encoding='utf-8') as f:
        json.dump(resultados, f, indent=2, ensure_ascii=False)
    logger.info(f"\n✓ Umbrales guardados en {ruta}")

def run():
    print("╔═════════════════════════════════════════════════╗")
    print("║  RDScore — Optimización Híbrida (Train-Val) v2  ║")
    print("╚═════════════════════════════════════════════════╝\n")
    
    apuestas = pipeline_entrenamiento_optimizacion()
    if not apuestas: return
    
    logger.info("\nOptimizando umbrales sobre el HIDDEN TEST SET (Historial)...")
    res = optimizar(apuestas)
    guardar_umbrales(res)
    print("\n✓ Proceso completo. Umbrales listos para producción.")

if __name__ == "__main__":
    run()
