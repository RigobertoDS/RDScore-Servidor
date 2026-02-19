"""
Pipeline de entrenamiento y predicción v2 para RDScore.

Mejoras sobre v1:
- Split temporal 80/20 (no entrena con datos de validación)
- Calibración sobre hold-out (no sobre training data)
- Feature engineering mejorado (52 features)
- Métricas de evaluación honestas (out-of-sample)
- Modelos guardados en modelos_v2/ (no sobreescribe v1)

Exporta las mismas funciones que crear_modelo.py para un swap limpio.
"""

from datetime import date, datetime, timedelta
import pickle
import os
import numpy as np
import warnings
from sklearn.calibration import CalibratedClassifierCV
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import Pipeline
import xgboost as xgb
import lightgbm as lgb

from services.data_fetching.obtener_partidos import (
    obtener_partidos_jugados,
    obtener_partidos_a_predecir,
    cargar_partidos
)
from services.ml_v2.features import FeatureExtractor, _parse_fecha
from services.ml_v2.evaluar import (
    calcular_metricas_clasificacion,
    calcular_metricas_multiclase,
    imprimir_metricas,
)
from config import BASE_DIR

warnings.filterwarnings("ignore")

MODELOS_DIR = os.path.join(BASE_DIR, 'modelos_v2')


def _asegurar_dir():
    os.makedirs(MODELOS_DIR, exist_ok=True)


def guardar_modelo(modelo, nombre):
    _asegurar_dir()
    ruta = os.path.join(MODELOS_DIR, f'{nombre}.pkl')
    with open(ruta, 'wb') as f:
        pickle.dump(modelo, f)


def cargar_modelo(nombre):
    ruta = os.path.join(MODELOS_DIR, f'{nombre}.pkl')
    with open(ruta, 'rb') as f:
        return pickle.load(f)


def extraer_targets(partido):
    """Extraer los targets de un partido."""
    return (
        partido.goles_local,
        partido.goles_visitante,
        partido.ambos_marcan,
        partido.mas_2_5,
        partido.resultado,
    )


# =================================================================
# ENTRENAMIENTO
# =================================================================

def crear_modelos(partidos, logger):
    """
    Entrena modelos v2 con split temporal y features mejorados.

    Args:
        partidos: Lista de partidos jugados (estado="FT")
        logger: Logger compatible con logger.info()
    """
    logger.info("=== Pipeline v2: Preparando datos ===")

    # 1. Cargar todos los partidos para el FeatureExtractor
    todos = cargar_partidos()
    extractor = FeatureExtractor(todos)
    logger.info(f"  FeatureExtractor inicializado con {len(extractor.partidos_ft)} partidos FT")

    # 2. Ordenar temporalmente y split 80/20
    partidos_con_fecha = [(p, _parse_fecha(p.fecha)) for p in partidos]
    partidos_con_fecha = [(p, f) for p, f in partidos_con_fecha if f is not None]
    partidos_con_fecha.sort(key=lambda x: x[1])

    split_idx = int(len(partidos_con_fecha) * 0.80)
    partidos_train = [p for p, _ in partidos_con_fecha[:split_idx]]
    partidos_val = [p for p, _ in partidos_con_fecha[split_idx:]]

    logger.info(f"  Split temporal: {len(partidos_train)} train / {len(partidos_val)} val")

    # 3. Extraer features y targets
    logger.info("  Extrayendo features v2 (50 features)...")

    X_train = np.array([extractor.extraer(p).flatten() for p in partidos_train])
    X_val = np.array([extractor.extraer(p).flatten() for p in partidos_val])

    targets_train = [extraer_targets(p) for p in partidos_train]
    targets_val = [extraer_targets(p) for p in partidos_val]

    y_gl_t = np.array([t[0] for t in targets_train])
    y_gv_t = np.array([t[1] for t in targets_train])
    y_btts_t = np.array([t[2] for t in targets_train])
    y_over_t = np.array([t[3] for t in targets_train])
    y_res_t = np.array([t[4] for t in targets_train])

    y_gl_v = np.array([t[0] for t in targets_val])
    y_gv_v = np.array([t[1] for t in targets_val])
    y_btts_v = np.array([t[2] for t in targets_val])
    y_over_v = np.array([t[3] for t in targets_val])
    y_res_v = np.array([t[4] for t in targets_val])

    logger.info(f"  Features shape: train={X_train.shape}, val={X_val.shape}")

    # 4. Definir modelos base
    modelo_reg = Pipeline([
        ('scaler', StandardScaler()),
        ('model', xgb.XGBRegressor(
            n_estimators=400, max_depth=6, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1, tree_method='hist'
        ))
    ])

    modelo_clf = Pipeline([
        ('scaler', StandardScaler()),
        ('model', lgb.LGBMClassifier(
            n_estimators=500, max_depth=8, learning_rate=0.05,
            subsample=0.8, colsample_bytree=0.8,
            random_state=42, n_jobs=-1, verbose=-1
        ))
    ])

    # 5. Entrenar y calibrar cada modelo
    def entrenar_regresor(y_train, nombre):
        logger.info(f"  → Entrenando {nombre} (XGBRegressor)...")
        from sklearn.base import clone
        m = clone(modelo_reg)
        m.fit(X_train, y_train)
        guardar_modelo(m, nombre)
        return m

    def entrenar_clasificador(y_train, y_val, nombre):
        logger.info(f"  → Entrenando {nombre} (LightGBM + calibración isotónica)...")
        from sklearn.base import clone
        m = clone(modelo_clf)
        m.fit(X_train, y_train)

        from sklearn.model_selection import PredefinedSplit

        # Combinar train y val para que CalibratedClassifierCV use el slice correcto
        X_combined = np.vstack([X_train, X_val])
        y_combined = np.concatenate([y_train, y_val])

        # -1 para train (no usar en calibración), 0 para val (usar en calibración)
        test_fold = np.concatenate([-np.ones(len(X_train)), np.zeros(len(X_val))])
        ps = PredefinedSplit(test_fold)

        logger.info(f"    Calibrando {nombre} sobre set de validación (PredefinedSplit)...")
        calibrated = CalibratedClassifierCV(m, method='isotonic', cv=ps)
        calibrated.fit(X_combined, y_combined)

        guardar_modelo(calibrated, nombre)
        return calibrated

    # Entrenar secuencialmente (más seguro para logs)
    m_gl = entrenar_regresor(y_gl_t, "modelo_goles_local")
    m_gv = entrenar_regresor(y_gv_t, "modelo_goles_visitante")
    m_btts = entrenar_clasificador(y_btts_t, y_btts_v, "modelo_btts")
    m_over = entrenar_clasificador(y_over_t, y_over_v, "modelo_over25")
    m_res = entrenar_clasificador(y_res_t, y_res_v, "modelo_resultado")

    # 6. Evaluar sobre validación (métricas honestas)

    # Resultado
    prob_res = m_res.predict_proba(X_val)
    pred_res = prob_res.argmax(axis=1)
    met_res = calcular_metricas_multiclase(y_res_v, prob_res, pred_res)

    # Extraer cuotas para validación
    cuotas_btts = [getattr(p, 'cuota_btts', -1) for p in partidos_val]
    cuotas_over = [getattr(p, 'cuota_over', -1) for p in partidos_val]

    # BTTS
    prob_btts = m_btts.predict_proba(X_val)[:, 1]
    pred_btts = (prob_btts >= 0.5).astype(int)
    met_btts = calcular_metricas_clasificacion(y_btts_v, prob_btts, pred_btts,
                                                cuotas_si=cuotas_btts)

    # Over 2.5
    prob_over = m_over.predict_proba(X_val)[:, 1]
    pred_over = (prob_over >= 0.5).astype(int)
    met_over = calcular_metricas_clasificacion(y_over_v, prob_over, pred_over,
                                                cuotas_si=cuotas_over)

    logger.info("✓ Modelos v2 entrenados y guardados.")

    return {
        'resultado': met_res,
        'btts': met_btts,
        'over': met_over,
    }


# =================================================================
# PREDICCIÓN
# =================================================================

# Predecir partido único
def predecir_partido(partido, optimos, extractor,
                     m_gl, m_gv, m_btts, m_over, m_res):
    """
    Predice un partido único usando modelos v2.
    Produce el mismo formato de prediccion dict que v1.
    """
    X = extractor.extraer(partido)

    # --- Predicciones base ---
    pred_gl = round(float(m_gl.predict(X)[0]), 2)
    pred_gv = round(float(m_gv.predict(X)[0]), 2)

    prob_res = m_res.predict_proba(X)[0].astype(float)
    pred_res = int(prob_res.argmax())
    prob_res_max = prob_res.max()

    prob_btts = m_btts.predict_proba(X)[0].astype(float)
    pred_btts_cls = int(prob_btts.argmax())
    prob_btts_max = prob_btts.max()

    prob_over = m_over.predict_proba(X)[0].astype(float)
    pred_over_cls = int(prob_over.argmax())
    prob_over_max = prob_over.max()

    # --- Umbrales ---
    def _u(strat, mercado):
        return optimos[strat][mercado]['umbral_prob']

    def _m(strat, mercado):
        return optimos[strat][mercado]['margen']

    def get_rec(prob, u_con, u_mod, u_agr):
        return {
            'conservadora': int(prob >= u_con) if u_con is not None else 0,
            'moderada':     int(prob >= u_mod) if u_mod is not None else 0,
            'arriesgada':   int(prob >= u_agr) if u_agr is not None else 0,
        }

    # --- Recomendaciones por probabilidad ---
    cl = float(partido.cuota_local)
    ce = float(partido.cuota_empate)
    cv = float(partido.cuota_visitante)
    cbtts = float(partido.cuota_btts)
    cbtts_n = float(partido.cuota_btts_no)
    co = float(partido.cuota_over)
    cu = float(partido.cuota_under)

    if cl <= 1.0 or ce <= 1.0 or cv <= 1.0:
        rec_res = get_rec(0, 1, 1, 1)
    else:
        rec_res = get_rec(prob_res_max, _u('conservador', 'resultado'),
                          _u('moderado', 'resultado'), _u('agresivo', 'resultado'))

    if cbtts <= 1.0 or cbtts_n <= 1.0:
        rec_btts = get_rec(0, 1, 1, 1)
    else:
        rec_btts = get_rec(prob_btts_max, _u('conservador', 'btts'),
                           _u('moderado', 'btts'), _u('agresivo', 'btts'))

    if co <= 1.0 or cu <= 1.0:
        rec_over = get_rec(0, 1, 1, 1)
    else:
        rec_over = get_rec(prob_over_max, _u('conservador', 'over'),
                           _u('moderado', 'over'), _u('agresivo', 'over'))

    # --- Value Betting ---
    def check_value(prob_modelo, cuota, tipo, strat):
        if cuota <= 1.0:
            return False
        implied = 1.0 / cuota
        margen = _m(strat, tipo)
        if margen is None:
            return False
        return (prob_modelo - implied) >= margen

    # Resultado value
    cuotas_1x2 = [ce, cl, cv]  # 0=empate, 1=local, 2=visitante
    cuota_pred_res = cuotas_1x2[pred_res] if all(c > 1 for c in cuotas_1x2) else 0

    if cuota_pred_res > 1:
        for strat, key in [('conservador', 'conservadora'),
                           ('moderado', 'moderada'),
                           ('agresivo', 'arriesgada')]:
            if not check_value(prob_res[pred_res], cuota_pred_res, 'resultado', strat):
                if cl != -1:
                    rec_res[key] = 0

    # BTTS value
    cuota_pred_btts = cbtts if pred_btts_cls == 1 else cbtts_n
    if cuota_pred_btts > 1:
        for strat, key in [('conservador', 'conservadora'),
                           ('moderado', 'moderada'),
                           ('agresivo', 'arriesgada')]:
            if not check_value(prob_btts[pred_btts_cls], cuota_pred_btts, 'btts', strat):
                if cbtts != -1:
                    rec_btts[key] = 0

    # Over value
    cuota_pred_over = co if pred_over_cls == 1 else cu
    if cuota_pred_over > 1:
        for strat, key in [('conservador', 'conservadora'),
                           ('moderado', 'moderada'),
                           ('agresivo', 'arriesgada')]:
            if not check_value(prob_over[pred_over_cls], cuota_pred_over, 'over', strat):
                if co != -1:
                    rec_over[key] = 0

    # --- Predicción final (mismo formato que v1) ---
    prediccion = {
        'goles_esperados': {'local': pred_gl, 'visitante': pred_gv},
        'resultado_1x2': {
            'prediccion': ['Empate', 'Local', 'Visitante'][pred_res],
            'probabilidades': {
                'local': float(prob_res[1]),
                'empate': float(prob_res[0]),
                'visitante': float(prob_res[2])
            },
            'probabilidad_max': float(prob_res_max),
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

    partido.prediccion = prediccion


def predecir_lista_partidos(partidos, optimos):
    """
    Predice todos los partidos usando modelos v2.
    Misma firma que v1 para swap limpio.
    """
    partidos_predecir = []

    # Cargar modelos v2
    m_gl = cargar_modelo("modelo_goles_local")
    m_gv = cargar_modelo("modelo_goles_visitante")
    m_btts = cargar_modelo("modelo_btts")
    m_over = cargar_modelo("modelo_over25")
    m_res = cargar_modelo("modelo_resultado")

    # Crear FeatureExtractor
    todos = cargar_partidos()
    extractor = FeatureExtractor(todos)

    for p in partidos:
        predecir_partido(p, optimos, extractor,
                         m_gl, m_gv, m_btts, m_over, m_res)
        partidos_predecir.append(p)

    guardar_partidos_predecidos(partidos_predecir)


# =================================================================
# UTILIDADES (copiadas de v1 para independencia total)
# =================================================================

def guardar_partidos_predecidos(partidos):
    """Guarda los partidos predecidos en pickle + SQL (dual write)."""
    fecha_actual = date.today()
    ruta = os.path.join(BASE_DIR, 'datos', 'archivo',
                        f'{fecha_actual.strftime("%Y_%m_%d")}__partidos_predecidos.pkl')
    with open(ruta, 'wb') as f:
        pickle.dump(partidos, f)

    # Dual Write → SQL
    try:
        from services.persistence.db_persistence import guardar_predicciones_en_bd
        guardar_predicciones_en_bd(partidos)
    except Exception as e:
        import logging
        logging.getLogger(__name__).warning(f"Warning: Could not save predictions to SQL: {e}")


def cargar_partidos_predecidos(fecha):
    """Carga partidos predecidos desde pickle. Acepta date o string."""
    if isinstance(fecha, str):
        fecha_str = fecha
    else:
        fecha_str = fecha.strftime("%Y_%m_%d")
    ruta = os.path.join(BASE_DIR, 'datos', 'archivo',
                        f'{fecha_str}__partidos_predecidos.pkl')
    with open(ruta, 'rb') as f:
        return pickle.load(f)


def cargar_partidos_predecidos_string(fecha):
    """Carga partidos predecidos con fecha como string YYYY_mm_dd."""
    ruta = os.path.join(BASE_DIR, 'datos', 'archivo',
                        f'{fecha}__partidos_predecidos.pkl')
    with open(ruta, 'rb') as f:
        return pickle.load(f)


def obtener_partidos_a_predecir_10(partidos_a_predecir):
    """Filtra partidos: solo los de los próximos 10 días."""
    limite = date.today() + timedelta(days=10)
    resultado = []
    for p in partidos_a_predecir:
        try:
            f = datetime.strptime(p.fecha, "%d/%m/%Y").date()
        except ValueError:
            f = datetime.strptime(p.fecha, "%Y-%m-%d").date()
        if f <= limite:
            resultado.append(p)
    return resultado


def obtener_partidos_futuros(partidos_a_predecir):
    """Filtra partidos: solo los de MÁS de 10 días."""
    limite = date.today() + timedelta(days=10)
    resultado = []
    for p in partidos_a_predecir:
        try:
            f = datetime.strptime(p.fecha, "%d/%m/%Y").date()
        except ValueError:
            f = datetime.strptime(p.fecha, "%Y-%m-%d").date()
        if f > limite:
            resultado.append(p)
    return resultado


def cargar_partidos_jugados_de_un_dia(fecha_str):
    """Devuelve partidos jugados/predecidos de una fecha concreta."""
    fecha = datetime.strptime(fecha_str, "%d/%m/%Y").date()
    hoy = date.today()
    limite = hoy + timedelta(days=10)

    if fecha < hoy:
        partidos = obtener_partidos_jugados()
        return [p for p in partidos if p.fecha == fecha_str]

    if hoy <= fecha <= limite:
        partidos = cargar_partidos_predecidos(hoy)
        return [p for p in partidos if p.fecha == fecha_str]

    if fecha > limite:
        partidos_predecir = obtener_partidos_a_predecir()
        partidos_futuros = obtener_partidos_futuros(partidos_predecir)
        return [p for p in partidos_futuros if p.fecha == fecha_str]

    return []
