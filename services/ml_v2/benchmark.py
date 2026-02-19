"""
Benchmark v1 vs v2: Compara ambos pipelines sobre el mismo historial.

MODO RIGUROSO:
1. v2 usa 'features.py' modificado (sin leakage de puntos/posicion).
2. v1 se entrena DESDE CERO usando los mismos datos de train que v2.
   (Ya no usa los modelos pre-entrenados que tenían leakage).

Esto permite ver qué arquitectura es realmente mejor.
"""

import os
import sys
import pickle
import numpy as np
from datetime import datetime
import xgboost as xgb
import lightgbm as lgb
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.calibration import CalibratedClassifierCV
from sklearn.metrics import accuracy_score, brier_score_loss, log_loss

# Asegurar que el path raíz esté en sys.path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from config import BASE_DIR
from services.data_fetching.obtener_partidos import (
    obtener_partidos_jugados,
    cargar_partidos
)
from services.ml_v2.features import FeatureExtractor, _parse_fecha
from services.ml_v2.evaluar import (
    calcular_metricas_clasificacion,
    calcular_metricas_multiclase,
    imprimir_metricas,
)

# Importar extractor v1
from services.ml.crear_modelo import extraer_features as extraer_features_v1


class BenchmarkLogger:
    """Logger simple que imprime con timestamp."""
    def info(self, msg, end="\n"):
        ts = datetime.now().strftime("%H:%M:%S")
        print(f"[{ts}] {msg}", end=end)


def entrenar_evaluar_v1_retrained(partidos_train, partidos_val, logger):
    """
    Entrena la arquitectura v1 desde cero con los datos de train de v2.
    Evalúa sobre el set de validación de v2.
    """
    logger.info("=== Pipeline v1 (RE-ENTRENADO): Preparando datos ===")

    # 1. Extraer features usando lógica v1
    # Copiado de crear_modelo.py lógica de extracción
    def get_data(partidos):
        X, y_btts, y_over, y_res = [], [], [], []
        for p in partidos:
            try:
                # Features v1
                feat = extraer_features_v1(p).flatten()
                X.append(feat)
                # Targets
                y_btts.append(p.ambos_marcan)
                y_over.append(p.mas_2_5)
                y_res.append(p.resultado)
            except Exception:
                continue
        return np.array(X), np.array(y_btts), np.array(y_over), np.array(y_res)

    X_train, y_btts_t, y_over_t, y_res_t = get_data(partidos_train)
    X_val, y_btts_v, y_over_v, y_res_v = get_data(partidos_val)

    logger.info(f"  Datos v1: Train={len(X_train)}, Val={len(X_val)}")

    # 2. Definir modelos (Arquitectura v1 exacta)
    # 2. BTTS & Over 2.5 & Resultado → LightGBM
    modelo_clasif = Pipeline([
        ('scaler', StandardScaler()),
        ('model', lgb.LGBMClassifier(
            n_estimators=500,
            max_depth=8,
            learning_rate=0.05,
            subsample=0.8,
            colsample_bytree=0.8,
            random_state=42,
            n_jobs=-1,
            verbose=-1
        ))
    ])

    # 3. Entrenar y Calibrar
    def entrenar(y_train, y_val, nombre):
        logger.info(f"  → Entrenando v1 {nombre}...")
        from sklearn.base import clone
        m = clone(modelo_clasif)
        m.fit(X_train, y_train)
        
        # v1 original calibraba sobre TRAIN (leakage). 
        # Para ser justos con la arquitectura pero honestos con la validación,
        # deberíamos calibrar como v1 lo hacía (CV intra-train) o sobre val?
        # v1 código: calibrated = CalibratedClassifierCV(model, method='isotonic', cv=3)
        # Esto es cross-validation sobre train. Es correcto (no leakage externo).
        
        calibrated = CalibratedClassifierCV(m, method='isotonic', cv=3, n_jobs=-1)
        calibrated.fit(X_train, y_train)
        return calibrated

    m_btts = entrenar(y_btts_t, y_btts_v, "BTTS")
    m_over = entrenar(y_over_t, y_over_v, "Over25")
    m_res = entrenar(y_res_t, y_res_v, "Resultado")

    # 4. Evaluar
    logger.info("\n=== MÉTRICAS v1 (RE-ENTRENADO) ===")

    # Extraer cuotas validación
    cuotas_btts = [getattr(p, 'cuota_btts', -1) for p in partidos_val]
    cuotas_over = [getattr(p, 'cuota_over', -1) for p in partidos_val]

    # Resultado
    prob_res = m_res.predict_proba(X_val)
    pred_res = prob_res.argmax(axis=1)
    met_res = calcular_metricas_multiclase(y_res_v, prob_res, pred_res)
    
    # BTTS
    prob_btts = m_btts.predict_proba(X_val)[:, 1]
    pred_btts = (prob_btts >= 0.5).astype(int)
    met_btts = calcular_metricas_clasificacion(y_btts_v, prob_btts, pred_btts, cuotas_si=cuotas_btts)
    
    # Over
    prob_over = m_over.predict_proba(X_val)[:, 1]
    pred_over = (prob_over >= 0.5).astype(int)
    met_over = calcular_metricas_clasificacion(y_over_v, prob_over, pred_over, cuotas_si=cuotas_over)

    return {'resultado': met_res, 'btts': met_btts, 'over': met_over}


def comparar(met_v1, met_v2):
    """Imprime tabla comparativa."""
    print("\n" + "="*60)
    print(" COMPARATIVA FINAL: v1 (Re-entrenado) vs v2 (Clean)")
    print("="*60)

    for mercado in ['resultado', 'btts', 'over']:
        m1 = met_v1.get(mercado, {})
        m2 = met_v2.get(mercado, {})

        print(f"\n  --- {mercado.upper()} ---")
        for key in ['accuracy', 'roi', 'logloss', 'brier', 'ece']:
            v1_val = m1.get(key, 'N/A')
            v2_val = m2.get(key, 'N/A')
            if isinstance(v1_val, (int, float)) and isinstance(v2_val, (int, float)):
                diff = v2_val - v1_val
                arrow = "↑" if (key == 'accuracy' and diff > 0) or \
                              (key != 'accuracy' and diff < 0) else "↓"
                print(f"    {key:>10}: v1={v1_val:>8.4f}  v2={v2_val:>8.4f}  ({arrow} {abs(diff):.4f})")
            else:
                print(f"    {key:>10}: v1={v1_val}  v2={v2_val}")


def run():
    """Ejecuta benchmark completo."""
    print("╔══════════════════════════════════════════╗")
    print("║    RDScore — Benchmark RIGUROSO          ║")
    print("╚══════════════════════════════════════════╝")
    
    logger = BenchmarkLogger()

    # 1. Obtener datos y hacer split (determinista)
    partidos = obtener_partidos_jugados()
    
    # Ordenar y split 80/20 igual que en entrenar.py
    partidos_con_fecha = [(p, _parse_fecha(p.fecha)) for p in partidos]
    partidos_con_fecha = [(p, f) for p, f in partidos_con_fecha if f is not None]
    partidos_con_fecha.sort(key=lambda x: x[1])

    split_idx = int(len(partidos_con_fecha) * 0.80)
    partidos_train = [p for p, _ in partidos_con_fecha[:split_idx]]
    partidos_val = [p for p, _ in partidos_con_fecha[split_idx:]]
    
    print(f"\n[DATOS] Total: {len(partidos_con_fecha)} | Train: {len(partidos_train)} | Val: {len(partidos_val)}")

    # 2. Entrenar y evaluar v2 (CLEAN)
    print("\n>>> Paso 1: Entrenando v2 (Features Históricos ONLY)...")
    from services.ml_v2.entrenar import crear_modelos
    met_v2 = crear_modelos(partidos, logger)

    # 3. Entrenar y evaluar v1 (RETRAINED)
    print("\n>>> Paso 2: Entrenando v1 (Arquitectura original, sin memorización)...")
    met_v1 = entrenar_evaluar_v1_retrained(partidos_train, partidos_val, logger)

    # 4. Comparar
    comparar(met_v1, met_v2)

    print("\n✓ Benchmark completo.")
