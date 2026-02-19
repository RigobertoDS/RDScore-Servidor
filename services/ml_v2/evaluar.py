"""
Métricas de evaluación para modelos ML v2.

Calcula Brier Score, Log Loss, Accuracy, ROI simulado,
y Expected Calibration Error (ECE) para evaluar la calidad
de las predicciones de forma honesta (out-of-sample).
"""

import numpy as np
from sklearn.metrics import brier_score_loss, log_loss, accuracy_score


def calcular_metricas_clasificacion(y_true, y_pred_proba, y_pred_class, cuotas_si=None, nombre=""):
    """
    Calcula métricas completas para un clasificador binario.

    Args:
        y_true: Labels reales (0/1)
        y_pred_proba: Probabilidades predichas para la clase positiva
        y_pred_class: Clases predichas (0/1)
        nombre: Nombre del modelo (para logging)

    Returns:
        dict con accuracy, brier, logloss, ece
    """
    if len(y_true) == 0:
        return {'accuracy': 0, 'brier': 1, 'logloss': 1, 'ece': 1, 'n': 0}

    y_true = np.array(y_true)
    y_pred_proba = np.array(y_pred_proba)
    y_pred_class = np.array(y_pred_class)

    acc = accuracy_score(y_true, y_pred_class) * 100  # En %
    brier = brier_score_loss(y_true, y_pred_proba)

    # Log loss necesita probabilidades para ambas clases
    proba_2d = np.column_stack([1 - y_pred_proba, y_pred_proba])
    ll = log_loss(y_true, proba_2d, labels=[0, 1])

    ece = _expected_calibration_error(y_true, y_pred_proba)

    metrics = {
        'accuracy': round(acc, 2),
        'brier': round(brier, 4),
        'logloss': round(ll, 4),
        'ece': round(ece, 4),
        'n': len(y_true)
    }

    if cuotas_si is not None:
        roi_data = calcular_roi_simulado(y_true, y_pred_class, cuotas_si, y_pred_proba)
        metrics['roi'] = roi_data['roi']
        metrics['apuestas'] = roi_data['apuestas']
        metrics['beneficio'] = roi_data['beneficio']

    return metrics


def calcular_metricas_multiclase(y_true, y_pred_proba, y_pred_class, nombre=""):
    """
    Calcula métricas para clasificador multiclase (resultado 1X2).

    Args:
        y_true: Labels reales (0=empate, 1=local, 2=visitante)
        y_pred_proba: Probabilidades predichas shape (n, 3)
        y_pred_class: Clases predichas
        nombre: Nombre del modelo

    Returns:
        dict con accuracy, logloss, n
    """
    if len(y_true) == 0:
        return {'accuracy': 0, 'logloss': 1, 'n': 0}

    acc = accuracy_score(y_true, y_pred_class) * 100
    ll = log_loss(y_true, y_pred_proba, labels=[0, 1, 2])

    return {
        'accuracy': round(acc, 2),
        'logloss': round(ll, 4),
        'n': len(y_true)
    }


def calcular_roi_simulado(y_true_list, y_pred_class_list, cuotas_list,
                          prob_list, umbral_prob=0.55, margen=0.03):
    """
    Simula ROI de apuestas sobre un set de validación.

    Args:
        y_true_list: Lista de resultados reales
        y_pred_class_list: Lista de predicciones
        cuotas_list: Lista de cuotas para la predicción elegida
        prob_list: Lista de probabilidades del modelo
        umbral_prob: Umbral mínimo de probabilidad
        margen: Margen mínimo de value

    Returns:
        dict con roi, beneficio, apuestas, aciertos
    """
    beneficio = 0.0
    apuestas = 0
    aciertos = 0

    for y_real, y_pred, cuota_raw, prob in zip(
        y_true_list, y_pred_class_list, cuotas_list, prob_list
    ):
        try:
            cuota = float(cuota_raw)
        except (ValueError, TypeError):
            continue

        if cuota <= 1.0:
            continue
        implied = 1.0 / cuota
        value = prob - implied

        if prob >= umbral_prob and value >= margen:
            apuestas += 1
            if y_real == y_pred:
                beneficio += cuota - 1
                aciertos += 1
            else:
                beneficio -= 1

    roi = (beneficio / apuestas * 100) if apuestas > 0 else 0

    return {
        'roi': round(roi, 2),
        'beneficio': round(beneficio, 2),
        'apuestas': apuestas,
        'aciertos': aciertos,
        'accuracy': round(aciertos / apuestas * 100, 2) if apuestas > 0 else 0
    }


def _expected_calibration_error(y_true, y_pred_proba, n_bins=10):
    """
    Expected Calibration Error (ECE).

    Mide si las probabilidades del modelo son calibradas:
    ¿cuando dice 60%, acierta ~60% de las veces?

    Returns:
        float entre 0 (perfecto) y 1 (terrible)
    """
    y_true = np.array(y_true)
    y_pred_proba = np.array(y_pred_proba)

    bin_edges = np.linspace(0, 1, n_bins + 1)
    ece = 0.0

    for i in range(n_bins):
        mask = (y_pred_proba >= bin_edges[i]) & (y_pred_proba < bin_edges[i + 1])
        if mask.sum() == 0:
            continue
        bin_acc = y_true[mask].mean()
        bin_conf = y_pred_proba[mask].mean()
        ece += mask.sum() * abs(bin_acc - bin_conf)

    return ece / len(y_true) if len(y_true) > 0 else 0


def imprimir_metricas(metricas, nombre):
    """Imprime métricas formateadas."""
    print(f"\n  === {nombre} ===")
    for k, v in metricas.items():
        if k == 'n':
            print(f"    Muestras: {v}")
        elif k in ('accuracy', 'roi'):
            print(f"    {k.capitalize()}: {v:+.2f}%")
        else:
            print(f"    {k.capitalize()}: {v:.4f}")
