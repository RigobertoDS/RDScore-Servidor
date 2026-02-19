"""
Benchmark Final: v1 (Legacy) vs v2 (Full Pipeline).

Compara el rendimiento real sobre el historial de validación.
v1: Predicciones guardadas en historial.pkl (tal cual se hicieron en su día).
v2: Predicciones generadas AHORA con el pipeline completo:
    - Modelos Base v2 (entrenados sin leakage)
    - Umbrales optimizados v2 (Agresivo/Moderado/Conservador)
    - Meta-Modelos v2 (Filtro de EV/ROI)

Uso:
  python -c "from services.ml_v2.benchmark_full import run; run()"
"""

import logging
import pickle
import os
import numpy as np
import warnings
from copy import deepcopy

from config import BASE_DIR
from services.data_fetching.obtener_historial import cargar_historial
from services.ml_v2.meta_modelo import _asignar_predicciones_v2, cargar, aplicar_filtro_meta

logger = logging.getLogger("benchmark_full")
logging.basicConfig(level=logging.INFO, format="[%(asctime)s] %(message)s", datefmt="%H:%M:%S")
warnings.filterwarnings("ignore")

def _safe_float(val, default=-1.0):
    try:
        v = float(val)
        return v if v > 1.0 else default
    except:
        return default

def evaluar_roi(partidos, version="v1"):
    """
    Calcula ROI para las 3 estrategias (Con, Mod, Agr) en los 3 mercados.
    Retorna dict con métricas.
    """
    metrics = {
        'btts': {'agresivo': [], 'moderado': [], 'conservador': []},
        'over': {'agresivo': [], 'moderado': [], 'conservador': []},
        'resultado': {'agresivo': [], 'moderado': [], 'conservador': []}
    }

    for p in partidos:
        # Ignorar si no tiene predicción válida
        if not hasattr(p, 'prediccion') or not isinstance(p.prediccion, dict):
            continue

        pred = p.prediccion
        
        # Mapping de claves de recomendación (v1 vs v2 suele ser igual)
        # v1 keys: 'conservadora', 'moderada', 'arriesgada'
        # v2 keys: 'conservadora', 'moderada', 'arriesgada'
        
        strat_map = {
            'conservador': 'conservadora',
            'moderado': 'moderada',
            'agresivo': 'arriesgada'
        }

        # --- BTTS ---
        try:
            rec = pred.get('btts', {}).get('recomendacion', {})
            side = pred.get('btts', {}).get('prediccion') # 'Sí' / 'No'
            
            # Cuota real
            c_si = _safe_float(getattr(p, 'cuota_btts', -1))
            c_no = _safe_float(getattr(p, 'cuota_btts_no', -1))
            
            cuota_bet = c_si if side == 'Sí' else c_no
            win = (p.ambos_marcan == 1) if side == 'Sí' else (p.ambos_marcan == 0)
            
            if cuota_bet > 1.0:
                for strat_name, key in strat_map.items():
                    if rec.get(key) == 1:
                        profit = cuota_bet - 1 if win else -1
                        metrics['btts'][strat_name].append(profit)
        except: pass

        # --- OVER ---
        try:
            rec = pred.get('over25', {}).get('recomendacion', {})
            side = pred.get('over25', {}).get('prediccion') # 'Over' / 'Under'
            
            c_over = _safe_float(getattr(p, 'cuota_over', -1))
            c_under = _safe_float(getattr(p, 'cuota_under', -1))
            
            cuota_bet = c_over if side == 'Over' else c_under
            win = (p.mas_2_5 == 1) if side == 'Over' else (p.mas_2_5 == 0)
            
            if cuota_bet > 1.0:
                for strat_name, key in strat_map.items():
                    if rec.get(key) == 1:
                        profit = cuota_bet - 1 if win else -1
                        metrics['over'][strat_name].append(profit)
        except: pass

        # --- RESULTADO ---
        try:
            rec = pred.get('resultado_1x2', {}).get('recomendacion', {})
            side = pred.get('resultado_1x2', {}).get('prediccion') # 'Local'/'Empate'/'Visitante'
            
            c_1 = _safe_float(getattr(p, 'cuota_local', -1))
            c_x = _safe_float(getattr(p, 'cuota_empate', -1))
            c_2 = _safe_float(getattr(p, 'cuota_visitante', -1))
            
            if side == 'Local':
                cuota_bet, win = c_1, p.resultado == 1
            elif side == 'Empate':
                cuota_bet, win = c_x, p.resultado == 0
            elif side == 'Visitante':
                cuota_bet, win = c_2, p.resultado == 2
            else:
                cuota_bet = -1
                
            if cuota_bet > 1.0:
                for strat_name, key in strat_map.items():
                    if rec.get(key) == 1:
                        profit = cuota_bet - 1 if win else -1
                        metrics['resultado'][strat_name].append(profit)
        except: pass

    # Resumen
    resumen = {}
    for m in metrics: # mercados
        resumen[m] = {}
        for s in metrics[m]: # estrategias
            profits = metrics[m][s]
            n = len(profits)
            roi = sum(profits)/n*100 if n > 0 else 0
            hits = sum(1 for x in profits if x > 0)
            acc = hits/n*100 if n > 0 else 0
            resumen[m][s] = {'roi': roi, 'n': n, 'acc': acc, 'profit': sum(profits)}
            
    return resumen

def print_comparison(r1, r2):
    print("\n" + "="*80)
    print(f"{'MERCADO / ESTRATEGIA':<25} | {'v1 (LEGACY)':<22} | {'v2 (FULL PIPELINE)':<22}")
    print("="*80)
    
    for m in ['btts', 'over', 'resultado']:
        print(f"--- {m.upper()} ---")
        for s in ['agresivo', 'moderado', 'conservador']:
            d1 = r1[m][s]
            d2 = r2[m][s]
            
            # Formato strings
            s1 = f"ROI {d1['roi']:+5.1f}% ({d1['n']})"
            s2 = f"ROI {d2['roi']:+5.1f}% ({d2['n']})"
            
            # Highlight mejor
            better = ""
            if d2['roi'] > d1['roi'] and d2['n'] > 10:
                better = " << v2 Wins"
            elif d1['roi'] > d2['roi'] and d1['n'] > 10:
                better = " << v1 Wins"
                
            print(f"{s.capitalize():<25} | {s1:<22} | {s2:<22}{better}")
            
def run():
    print("======================================================")
    print("  RDScore -- Benchmark Final: v1 vs v2 Full Stack     ")
    print("======================================================\n")
    
    # Debug thresholds
    import json
    try:
        with open(os.path.join(BASE_DIR, 'datos', 'umbrales_v2.json'), 'r') as f:
            u = json.load(f)
            logger.info(f"Umbrales cargados: {list(u['agresivo'].keys())}")
    except:
        logger.warning("No se pudieron cargar umbrales_v2.json para debug")

    # 1. Cargar Historial
    logger.info("Cargando historial completo...")
    historial = cargar_historial()
    logger.info(f"  Total partidos: {len(historial)}")
    
    # 2. Evaluar v1 (tal cual está guardado)
    logger.info("Evaluando predicciones v1 (Legacy)...")
    res_v1 = evaluar_roi(historial, "v1")
    
    # 3. Generar predicciones v2 (Base)
    logger.info("Generando predicciones v2 (Base + Umbrales)...")
    # Clonamos para no ensuciar si quisiéramos reusar historial original (aunque aquí da igual)
    historial_v2 = deepcopy(historial)
    ok = _asignar_predicciones_v2(historial_v2, logger)
    if not ok: return

    # 4. Cargar Meta-Modelos y Aplicar Filtro
    logger.info("Cargando Meta-Modelos y aplicando filtro...")
    meta_res = cargar("meta_modelo_resultado")
    meta_btts = cargar("meta_modelo_btts")
    meta_over = cargar("meta_modelo_over")
    
    n_before = sum(1 for p in historial_v2 if p.prediccion['btts']['recomendacion'].get('arriesgada') == 1)
    logger.info(f"  BTTS Arriesgada antes de filtro: {n_before}")

    for p in historial_v2:
        aplicar_filtro_meta(p, meta_res, meta_btts, meta_over)
        
    n_after = sum(1 for p in historial_v2 if p.prediccion['btts']['recomendacion'].get('arriesgada') == 1)
    logger.info(f"  BTTS Arriesgada despues de filtro: {n_after}")
        
    # 5. Evaluar v2 (Full Stack)
    logger.info("Evaluando predicciones v2 (Full Stack)...")
    res_v2 = evaluar_roi(historial_v2, "v2")
    
    # 6. Imprimir Comparativa (Simple)
    print("\n--- RESULTADOS COMPARATIVOS ---")
    print(f"{'MERCADO':<10} | {'ESTRATEGIA':<12} | {'v1 ROI (n)':<20} | {'v2 ROI (n)':<20}")
    print("-" * 70)
    
    for m in ['btts', 'over', 'resultado']:
        for s in ['agresivo', 'moderado', 'conservador']:
            d1 = res_v1[m][s]
            d2 = res_v2[m][s]
            s1 = f"{d1['roi']:+.1f}% ({d1['n']})"
            s2 = f"{d2['roi']:+.1f}% ({d2['n']})"
            print(f"{m.upper():<10} | {s.capitalize():<12} | {s1:<20} | {s2:<20}")
    
    logger.info("\nDone.")

if __name__ == "__main__":
    run()
