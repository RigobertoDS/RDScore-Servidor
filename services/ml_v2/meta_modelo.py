"""
Meta-Modelo unificado v2 para RDScore.

Mejoras sobre v1:
- Un solo módulo para los 3 mercados (DRY)
- Más features (probabilidades base + cuotas + contexto)
- LightGBM en vez de Ridge
- Validación temporal interna
"""

import os
import math
import pickle
import numpy as np
import lightgbm as lgb
from sklearn.model_selection import TimeSeriesSplit
from config import BASE_DIR

MODELOS_DIR = os.path.join(BASE_DIR, 'meta_modelos_v2')


def _asegurar_dir():
    os.makedirs(MODELOS_DIR, exist_ok=True)


def guardar(modelo, nombre):
    _asegurar_dir()
    ruta = os.path.join(MODELOS_DIR, f'{nombre}.pkl')
    with open(ruta, 'wb') as f:
        pickle.dump(modelo, f)


def cargar(nombre):
    ruta = os.path.join(MODELOS_DIR, f'{nombre}.pkl')
    with open(ruta, 'rb') as f:
        return pickle.load(f)


# =================================================================
# FEATURE ENGINEERING PARA META-MODELOS
# =================================================================

def _features_resultado(p_dict):
    """Features del meta-modelo para mercado Resultado 1X2."""
    probs = p_dict["prediccion"]["resultado_1x2"]["probabilidades"]
    prob_l = probs["local"]
    prob_e = probs["empate"]
    prob_v = probs["visitante"]

    probs_sorted = sorted([prob_l, prob_e, prob_v], reverse=True)
    prob_max = probs_sorted[0]
    prob_gap = prob_max - probs_sorted[1]
    entropy = -sum(p * math.log(p + 1e-9) for p in [prob_l, prob_e, prob_v])

    pred = p_dict["prediccion"]["resultado_1x2"]["prediccion"]
    if pred == "Local":
        cuota = float(p_dict["cuota_local"])
    elif pred == "Empate":
        cuota = float(p_dict["cuota_empate"])
    elif pred == "Visitante":
        cuota = float(p_dict["cuota_visitante"])
    else:
        return None

    if cuota <= 1.0:
        return None

    implied = 1.0 / cuota
    value = prob_max - implied

    # Features adicionales v2
    cuota_l = float(p_dict.get("cuota_local", -1))
    cuota_e = float(p_dict.get("cuota_empate", -1))
    cuota_v = float(p_dict.get("cuota_visitante", -1))
    overround = 0
    if cuota_l > 1 and cuota_e > 1 and cuota_v > 1:
        overround = (1/cuota_l + 1/cuota_e + 1/cuota_v) - 1

    return [
        prob_max, prob_gap, entropy,
        cuota, implied, value,
        prob_l, prob_e, prob_v,         # Probabilidades individuales
        overround,                      # Overround del mercado
        probs_sorted[2],                # Prob mínima (incertidumbre)
    ]


def _target_resultado(p_dict):
    """Target ROI para Resultado."""
    pred = p_dict["prediccion"]["resultado_1x2"]["prediccion"]
    if pred == "Local":
        cuota = float(p_dict["cuota_local"])
        ok = p_dict["resultado"] == 1
    elif pred == "Empate":
        cuota = float(p_dict["cuota_empate"])
        ok = p_dict["resultado"] == 0
    elif pred == "Visitante":
        cuota = float(p_dict["cuota_visitante"])
        ok = p_dict["resultado"] == 2
    else:
        return None
    if cuota <= 1.0:
        return None
    return cuota - 1 if ok else -1


def _features_btts(p_dict):
    """Features del meta-modelo para mercado BTTS."""
    probabilidad = p_dict["prediccion"]["btts"]["probabilidad"]
    prediccion = p_dict["prediccion"]["btts"]["prediccion"]

    if prediccion == "No":
        prob_si, prob_no = 1 - probabilidad, probabilidad
    else:
        prob_si, prob_no = probabilidad, 1 - probabilidad

    prob_max = max(prob_si, prob_no)
    prob_gap = abs(prob_si - prob_no)
    entropy = -sum(p * math.log(p + 1e-9) for p in [prob_si, prob_no])

    if prediccion == "Sí":
        cuota = float(p_dict["cuota_btts"])
    elif prediccion == "No":
        cuota = float(p_dict["cuota_btts_no"])
    else:
        return None

    if cuota <= 1.0:
        return None

    implied = 1.0 / cuota
    value = prob_max - implied

    cuota_si = float(p_dict.get("cuota_btts", -1))
    cuota_no = float(p_dict.get("cuota_btts_no", -1))
    overround = 0
    if cuota_si > 1 and cuota_no > 1:
        overround = (1/cuota_si + 1/cuota_no) - 1

    return [
        prob_max, prob_gap, entropy,
        cuota, implied, value,
        prob_si, prob_no,
        overround,
    ]


def _target_btts(p_dict):
    """Target ROI para BTTS."""
    pred = p_dict["prediccion"]["btts"]["prediccion"]
    if pred == "Sí":
        cuota = float(p_dict["cuota_btts"])
        ok = p_dict["ambos_marcan"] == 1
    elif pred == "No":
        cuota = float(p_dict["cuota_btts_no"])
        ok = p_dict["ambos_marcan"] == 0
    else:
        return None
    if cuota <= 1.0:
        return None
    return cuota - 1 if ok else -1


def _features_over(p_dict):
    """Features del meta-modelo para mercado Over/Under 2.5."""
    probabilidad = p_dict["prediccion"]["over25"]["probabilidad"]
    prediccion = p_dict["prediccion"]["over25"]["prediccion"]

    if prediccion == "Under":
        prob_o, prob_u = 1 - probabilidad, probabilidad
    else:
        prob_o, prob_u = probabilidad, 1 - probabilidad

    prob_max = max(prob_o, prob_u)
    prob_gap = abs(prob_o - prob_u)
    entropy = -sum(p * math.log(p + 1e-9) for p in [prob_o, prob_u])

    if prediccion == "Over":
        cuota = float(p_dict["cuota_over"])
    elif prediccion == "Under":
        cuota = float(p_dict["cuota_under"])
    else:
        return None

    if cuota <= 1.0:
        return None

    implied = 1.0 / cuota
    value = prob_max - implied

    cuota_ov = float(p_dict.get("cuota_over", -1))
    cuota_un = float(p_dict.get("cuota_under", -1))
    overround = 0
    if cuota_ov > 1 and cuota_un > 1:
        overround = (1/cuota_ov + 1/cuota_un) - 1

    return [
        prob_max, prob_gap, entropy,
        cuota, implied, value,
        prob_o, prob_u,
        overround,
    ]


def _target_over(p_dict):
    """Target ROI para Over 2.5."""
    pred = p_dict["prediccion"]["over25"]["prediccion"]
    goles = p_dict["goles_local"] + p_dict["goles_visitante"]
    if pred == "Over":
        cuota = float(p_dict["cuota_over"])
        ok = goles >= 3
    elif pred == "Under":
        cuota = float(p_dict["cuota_under"])
        ok = goles < 3
    else:
        return None
    if cuota <= 1.0:
        return None
    return cuota - 1 if ok else -1


# Mapeo para unificar
_EXTRACTORES = {
    'resultado': (_features_resultado, _target_resultado),
    'btts':      (_features_btts, _target_btts),
    'over':      (_features_over, _target_over),
}


# =================================================================
# ENTRENAMIENTO
# =================================================================

def crear_meta_modelo(mercado, historial, logger):
    """
    Entrena un meta-modelo para un mercado específico.

    Args:
        mercado: 'resultado', 'btts', o 'over'
        historial: Lista de objetos Partido con prediccion ya asignada
        logger: Logger
    """
    feat_fn, target_fn = _EXTRACTORES[mercado]
    logger.info(f"  Preparando datos Meta-Modelo v2 [{mercado}]...")

    X, y = [], []
    for p in historial:
        p_dict = p.to_dict()
        features = feat_fn(p_dict)
        target = target_fn(p_dict)
        if features is not None and target is not None:
            X.append(features)
            y.append(target)

    if len(X) < 30:
        logger.info(f"  ⚠ Solo {len(X)} muestras para {mercado}, insuficiente.")
        return

    X = np.array(X)
    y = np.array(y)

    logger.info(f"  Entrenando Meta-Modelo v2 [{mercado}] con {len(X)} partidos (LightGBM)...")

    model = lgb.LGBMRegressor(
        n_estimators=100,
        max_depth=4,
        learning_rate=0.05,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_alpha=1.0,
        reg_lambda=5.0,
        random_state=42,
        verbose=-1,
        n_jobs=-1,
    )
    model.fit(X, y)
    guardar(model, f"meta_modelo_{mercado}")
    logger.info(f"  ✓ Meta-Modelo v2 [{mercado}] guardado.")


def crear_meta_modelos(historial, logger):
    """Entrena los 3 meta-modelos v2."""
    logger.info("Entrenando Meta-Modelos v2...")
    for mercado in ['resultado', 'btts', 'over']:
        crear_meta_modelo(mercado, historial, logger)
    logger.info("✓ Todos los Meta-Modelos v2 entrenados.")


def _asignar_predicciones_v2(historial, logger):
    """
    Genera predicciones frescas con los modelos base v2 y las asigna
    a cada partido del historial (reemplazando las predicciones v1).
    """
    import warnings
    import json
    warnings.filterwarnings('ignore')

    from services.ml_v2.features import FeatureExtractor
    from services.data_fetching.obtener_partidos import cargar_partidos

    # Los modelos base están en modelos_v2/
    modelos_dir = os.path.join(BASE_DIR, 'modelos_v2')
    modelos = {}
    for nombre in ['modelo_btts', 'modelo_over25', 'modelo_resultado',
                    'modelo_goles_local', 'modelo_goles_visitante']:
        ruta = os.path.join(modelos_dir, f'{nombre}.pkl')
        if not os.path.exists(ruta):
            logger.info(f"  ⚠ Modelo base {nombre} no encontrado en modelos_v2/")
            return False
        with open(ruta, 'rb') as f:
            modelos[nombre] = pickle.load(f)

    # FeatureExtractor con todos los partidos
    todos = cargar_partidos()
    extractor = FeatureExtractor(todos)
    logger.info(f"  FeatureExtractor inicializado ({len(extractor.partidos_ft)} FT)")

    # Cargar umbrales optimizados
    umbrales_path = os.path.join(BASE_DIR, 'datos', 'umbrales_v2.json')
    with open(umbrales_path, 'r') as f:
        optimos = json.load(f)

    def _rec(mercado, prob, cuota, cuota_no=None, side_idx=None):
        """Calcula recomendación {conservadora, moderada, arriesgada}."""
        rec = {'conservadora': 0, 'moderada': 0, 'arriesgada': 0}
        if cuota <= 1.0: return rec
        
        # Estrategias
        for strat, key in [('agresivo', 'arriesgada'), ('moderado', 'moderada'), ('conservador', 'conservadora')]:
            # Obtener umbral y margen
            # Si mercado es 'resultado', prob y cuota ya son específicos de la predicción
            # Si mercado es 'btts'/'over', prob es de la clase 1
            
            # Check data availability
            if mercado not in optimos[strat]: continue
            
            u_prob = optimos[strat][mercado]['umbral_prob']
            margen = optimos[strat][mercado]['margen']
            
            # Value check
            implied = 1.0 / cuota
            value = prob - implied
            
            if prob >= u_prob and value >= margen:
                rec[key] = 1
                
        return rec

    asignados = 0
    for p in historial:
        try:
            X = extractor.extraer(p).flatten().reshape(1, -1)

            pred_gl = round(float(modelos['modelo_goles_local'].predict(X)[0]), 2)
            pred_gv = round(float(modelos['modelo_goles_visitante'].predict(X)[0]), 2)

            prob_res = modelos['modelo_resultado'].predict_proba(X)[0].astype(float)
            pred_res = int(prob_res.argmax())
            prob_res_max = float(prob_res.max())

            prob_btts = modelos['modelo_btts'].predict_proba(X)[0].astype(float)
            pred_btts_cls = int(prob_btts.argmax())

            prob_over = modelos['modelo_over25'].predict_proba(X)[0].astype(float)
            pred_over_cls = int(prob_over.argmax())

            # --- Calcular Recomendaciones ---
            
            # Resultado
            if pred_res == 1: # Local
                c_res = float(getattr(p, 'cuota_local', -1))
            elif pred_res == 2: # Visitante
                c_res = float(getattr(p, 'cuota_visitante', -1))
            else: # Empate
                c_res = float(getattr(p, 'cuota_empate', -1))
            rec_res = _rec('resultado', prob_res_max, c_res)

            # BTTS
            c_btts_si = float(getattr(p, 'cuota_btts', -1))
            c_btts_no = float(getattr(p, 'cuota_btts_no', -1))
            prob_btts_val = float(prob_btts[pred_btts_cls])
            c_btts_val = c_btts_si if pred_btts_cls == 1 else c_btts_no
            rec_btts = _rec('btts', prob_btts_val, c_btts_val)

            # Over
            c_over_si = float(getattr(p, 'cuota_over', -1))
            c_over_no = float(getattr(p, 'cuota_under', -1))
            prob_over_val = float(prob_over[pred_over_cls])
            c_over_val = c_over_si if pred_over_cls == 1 else c_over_no
            rec_over = _rec('over', prob_over_val, c_over_val)

            # Construir predicción
            p.prediccion = {
                'goles_esperados': {'local': pred_gl, 'visitante': pred_gv},
                'resultado_1x2': {
                    'prediccion': ['Empate', 'Local', 'Visitante'][pred_res],
                    'probabilidades': {
                        'local': float(prob_res[1]),
                        'empate': float(prob_res[0]),
                        'visitante': float(prob_res[2])
                    },
                    'probabilidad_max': prob_res_max,
                    'recomendacion': rec_res
                },
                'btts': {
                    'prediccion': 'Sí' if pred_btts_cls == 1 else 'No',
                    'probabilidad': float(prob_btts[pred_btts_cls]),
                    'recomendacion': rec_btts
                },
                'over25': {
                    'prediccion': 'Over' if pred_over_cls == 1 else 'Under',
                    'probabilidad': float(prob_over[pred_over_cls]),
                    'recomendacion': rec_over
                }
            }
            asignados += 1
        except Exception as e:
            # Skip matches que no tienen datos suficientes
            continue

    logger.info(f"  Predicciones v2 asignadas a {asignados}/{len(historial)} partidos.")
    return True


def crear_meta_modelos_v2_fresh(logger):
    """
    Pipeline completo: genera predicciones frescas con v2 sobre historial
    y entrena los meta-modelos con esas predicciones.

    Uso:
        python -c "from services.ml_v2.meta_modelo import crear_meta_modelos_v2_fresh; \\
                   import logging; crear_meta_modelos_v2_fresh(logging.getLogger())"
    """
    from services.data_fetching.obtener_historial import cargar_historial

    logger.info("=== Meta-Modelos v2: Entrenamiento con predicciones frescas ===")

    # 1. Cargar historial
    historial = cargar_historial()
    logger.info(f"  Historial cargado: {len(historial)} partidos")

    # 2. Asignar predicciones v2
    ok = _asignar_predicciones_v2(historial, logger)
    if not ok:
        logger.info("  ⚠ No se pudieron asignar predicciones v2. Abortando.")
        return

    # 3. Entrenar meta-modelos (usa los extractores existentes sobre las predicciones renovadas)
    crear_meta_modelos(historial, logger)

    logger.info("✓ Meta-Modelos v2 entrenados con predicciones FRESCAS del pipeline v2.")


# =================================================================
# PREDICCIÓN (filtro del meta-modelo)
# =================================================================

def aplicar_filtro_meta(partido, meta_resultado, meta_btts, meta_over):
    """
    Aplica el filtro del meta-modelo sobre las recomendaciones.
    Modifica partido.prediccion in-place.
    """
    p_dict = partido.to_dict()
    pred = partido.prediccion

    # --- Resultado ---
    feat = _features_resultado(p_dict)
    if feat is None:
        pred['resultado_1x2']['recomendacion'] = {
            'conservadora': 0, 'moderada': 0, 'arriesgada': 0
        }
    else:
        ev = meta_resultado.predict(np.array(feat).reshape(1, -1))[0]
        rec = pred['resultado_1x2']['recomendacion']
        if rec.get('conservadora') == 1 and ev < 0.10:
            rec['conservadora'] = 0
        if rec.get('moderada') == 1 and ev < 0.03:
            rec['moderada'] = 0
        if rec.get('arriesgada') == 1 and ev < -0.01:
            rec['arriesgada'] = 0

    # --- BTTS ---
    feat = _features_btts(p_dict)
    if feat is None:
        pred['btts']['recomendacion'] = {
            'conservadora': 0, 'moderada': 0, 'arriesgada': 0
        }
    else:
        ev = meta_btts.predict(np.array(feat).reshape(1, -1))[0]
        rec = pred['btts']['recomendacion']
        if rec.get('conservadora') == 1 and ev < 0.10:
            rec['conservadora'] = 0
        if rec.get('moderada') == 1 and ev < 0.03:
            rec['moderada'] = 0
        if rec.get('arriesgada') == 1 and ev < -0.01:
            rec['arriesgada'] = 0

    # --- Over ---
    feat = _features_over(p_dict)
    if feat is None:
        pred['over25']['recomendacion'] = {
            'conservadora': 0, 'moderada': 0, 'arriesgada': 0
        }
    else:
        ev = meta_over.predict(np.array(feat).reshape(1, -1))[0]
        rec = pred['over25']['recomendacion']
        if rec.get('conservadora') == 1 and ev < 0.10:
            rec['conservadora'] = 0
        if rec.get('moderada') == 1 and ev < 0.03:
            rec['moderada'] = 0
        if rec.get('arriesgada') == 1 and ev < -0.01:
            rec['arriesgada'] = 0
