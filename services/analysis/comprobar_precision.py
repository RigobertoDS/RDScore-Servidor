from datetime import datetime
import os
from flask import current_app
from extensions import db
from models import Partido, Reporte
from config import BASE_DIR


# PRIMER_DIA = "2025-12-03"  # Primer día con todos los datos limpios version V1 - ya no vale
PRIMER_DIA = "2026-02-13"  # Primer día con todos los datos limpios version V2 - actual
APUESTA_POR_PARTIDO = 1.0  # 1 Euro


################################################################
# Funciones varias

# Guardar/Cargar Reportes Genéricos en SQL
def guardar_reporte_sql(clave, contenido):
    if not current_app: return
    try:
        reporte = Reporte.query.get(clave)
        if not reporte:
            reporte = Reporte(clave=clave, contenido=contenido)
            db.session.add(reporte)
        else:
            reporte.contenido = contenido
            reporte.updated_at = datetime.utcnow()
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        print(f"Error saving report {clave} to SQL: {e}")

def cargar_reporte_sql(clave):
    if not current_app: return {}
    try:
        reporte = Reporte.query.get(clave)
        return reporte.contenido if reporte else {}
    except Exception as e:
        print(f"Error loading report {clave} from SQL: {e}")
        return {}


# Wrappers para compatibilidad
# Wrappers para compatibilidad y backup en Pickle
def guardar_precision(texto):
    guardar_reporte_sql('precision_texto', texto)

def cargar_precision():
    return cargar_reporte_sql('precision_texto')

def guardar_resumen(resumen):
    guardar_reporte_sql('resumen_modelos', resumen)

def cargar_resumen():
    return cargar_reporte_sql('resumen_modelos')

def guardar_resumen_tipo_apuesta(resumen):
    guardar_reporte_sql('resumen_tipo_apuesta', resumen)

def cargar_resumen_tipo_apuesta():
    return cargar_reporte_sql('resumen_tipo_apuesta')

# Comprobar si el partido tiene todas las cuotas bien
def cuotas_validas(cuotas):
    for cuota in cuotas:
        if cuota == -1:
            return False
    return True

# Comprobar partidos simplificado
def comprobar_partidos():
    if not current_app:
        return {} # No podemos analizar sin contexto de app
        
    primer_dia_obj = datetime.strptime(PRIMER_DIA, "%Y-%m-%d").date()
    
    # Cargar historial de SQL filtrando por fecha y estado terminado
    historial = Partido.query.filter(
        Partido.fecha >= primer_dia_obj,
        Partido.estado == 'FT'
    ).all()

    partidos_totales = 0
    partidos_apuesta_moderada_resultado = 0
    partidos_apuesta_moderada_btts = 0
    partidos_apuesta_moderada_over25 = 0
    partidos_apuesta_conservadora_resultado = 0
    partidos_apuesta_conservadora_btts = 0
    partidos_apuesta_conservadora_over25 = 0
    partidos_apuesta_agresiva_resultado = 0
    partidos_apuesta_agresiva_btts = 0
    partidos_apuesta_agresiva_over25 = 0
    aciertos_moderada_resultado = 0
    aciertos_moderada_btts = 0
    aciertos_moderada_over25 = 0
    aciertos_conservadora_resultado = 0
    aciertos_conservadora_btts = 0
    aciertos_conservadora_over25 = 0
    aciertos_agresiva_resultado = 0
    aciertos_agresiva_btts = 0
    aciertos_agresiva_over25 = 0

    beneficio_moderada_resultado = 0.0
    beneficio_conservadora_resultado = 0.0
    beneficio_agresiva_resultado = 0.0

    beneficio_moderada_btts = 0.0
    beneficio_conservadora_btts = 0.0
    beneficio_agresiva_btts = 0.0

    beneficio_moderada_over25 = 0.0
    beneficio_conservadora_over25 = 0.0
    beneficio_agresiva_over25 = 0.0

    for partido in historial:
        p = partido.to_dict()

        # Aumentar partidos totales
        partidos_totales += 1

        # Obtener los datos del partido ya jugado
        resultado = p['resultado']
        btts = p['ambos_marcan']
        over25 = p['mas_2_5']

        # Obtener los datos del partido predecido
        prediccion = p['prediccion']

        #########################################################
        # RESULTADO #
        #########################################################
        # Comprobar si tiene cuotas válidas
        cuotas = [p['cuota_local'],
                  p['cuota_empate'],
                  p['cuota_visitante']]

        if cuotas_validas(cuotas):
            rec_mod_res = prediccion.get('resultado_1x2')\
                .get('recomendacion').get('moderada')
            if rec_mod_res == 1:
                partidos_apuesta_moderada_resultado += 1
            rec_con_res = prediccion.get('resultado_1x2')\
                .get('recomendacion').get('conservadora')
            if rec_con_res == 1:
                partidos_apuesta_conservadora_resultado += 1
            rec_agr_res = prediccion.get('resultado_1x2')\
                .get('recomendacion').get('arriesgada')
            if rec_agr_res == 1:
                partidos_apuesta_agresiva_resultado += 1
            pred_resultado = prediccion.get('resultado_1x2')\
                .get('prediccion')
            p_resultado = -1
            if pred_resultado == 'Local':
                p_resultado = 1
            elif pred_resultado == 'Empate':
                p_resultado = 0
            elif pred_resultado == 'Visitante':
                p_resultado = 2

            # Hacer las comprobaciones
            cuota = p['cuota_local'] if p_resultado == 1 \
                else p['cuota_empate'] if p_resultado == 0 \
                else p['cuota_visitante']

            if p_resultado == resultado:
                # GANASTE
                if rec_mod_res == 1:
                    aciertos_moderada_resultado += 1
                    beneficio_moderada_resultado += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_con_res == 1:
                    aciertos_conservadora_resultado += 1
                    beneficio_conservadora_resultado += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_agr_res == 1:
                    aciertos_agresiva_resultado += 1
                    beneficio_agresiva_resultado += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
            else:
                # PERDISTE
                if rec_mod_res == 1:
                    beneficio_moderada_resultado -= \
                        APUESTA_POR_PARTIDO
                if rec_con_res == 1:
                    beneficio_conservadora_resultado -= \
                        APUESTA_POR_PARTIDO
                if rec_agr_res == 1:
                    beneficio_agresiva_resultado -= \
                        APUESTA_POR_PARTIDO

        #########################################################
        # AMBOS MARCAN #
        #########################################################
        # Comprobar si tiene cuotas válidas
        cuotas = [p['cuota_btts'], p['cuota_btts_no']]

        if cuotas_validas(cuotas):
            rec_mod_btts = prediccion.get('btts').get('recomendacion')\
                .get('moderada')
            if rec_mod_btts == 1:
                partidos_apuesta_moderada_btts += 1
            rec_con_btts = prediccion.get('btts').get('recomendacion')\
                .get('conservadora')
            if rec_con_btts == 1:
                partidos_apuesta_conservadora_btts += 1
            rec_agr_btts = prediccion.get('btts').get('recomendacion')\
                .get('arriesgada')
            if rec_agr_btts == 1:
                partidos_apuesta_agresiva_btts += 1
            pred_btts = prediccion.get('btts').get('prediccion')
            p_btts = -1
            if pred_btts == 'Sí':
                p_btts = 1
            elif pred_btts == 'No':
                p_btts = 0

            # Hacer las comprobaciones
            cuota = p['cuota_btts'] if p_btts == 1 \
                else p['cuota_btts_no']
            if p_btts == btts:
                if rec_mod_btts == 1:
                    aciertos_moderada_btts += 1
                    beneficio_moderada_btts += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_con_btts == 1:
                    aciertos_conservadora_btts += 1
                    beneficio_conservadora_btts += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_agr_btts == 1:
                    aciertos_agresiva_btts += 1
                    beneficio_agresiva_btts += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
            else:
                if rec_mod_btts == 1:
                    beneficio_moderada_btts -= \
                        APUESTA_POR_PARTIDO
                if rec_con_btts == 1:
                    beneficio_conservadora_btts -= \
                        APUESTA_POR_PARTIDO
                if rec_agr_btts == 1:
                    beneficio_agresiva_btts -= \
                        APUESTA_POR_PARTIDO

        #########################################################
        # OVER 2.5 #
        #########################################################
        # Comprobar si tiene cuotas válidas
        cuotas = [p['cuota_over'], p['cuota_under']]

        if cuotas_validas(cuotas):
            rec_mod_2_5 = prediccion.get('over25')\
                .get('recomendacion').get('moderada')
            if rec_mod_2_5 == 1:
                partidos_apuesta_moderada_over25 += 1
            rec_con_2_5 = prediccion.get('over25')\
                .get('recomendacion').get('conservadora')
            if rec_con_2_5 == 1:
                partidos_apuesta_conservadora_over25 += 1
            rec_agr_2_5 = prediccion.get('over25')\
                .get('recomendacion').get('arriesgada')
            if rec_agr_2_5 == 1:
                partidos_apuesta_agresiva_over25 += 1
            pred_over_2_5 = prediccion.get('over25').get('prediccion')
            p_over_2_5 = -1
            if pred_over_2_5 == 'Over':
                p_over_2_5 = 1
            elif pred_over_2_5 == 'Under':
                p_over_2_5 = 0

            # Hacer las comprobaciones
            cuota = p['cuota_over'] if p_over_2_5 == 1 \
                else p['cuota_under']
            if p_over_2_5 == over25:
                if rec_mod_2_5 == 1:
                    aciertos_moderada_over25 += 1
                    beneficio_moderada_over25 += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_con_2_5 == 1:
                    aciertos_conservadora_over25 += 1
                    beneficio_conservadora_over25 += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
                if rec_agr_2_5 == 1:
                    aciertos_agresiva_over25 += 1
                    beneficio_agresiva_over25 += \
                        (float(cuota) - 1) * APUESTA_POR_PARTIDO
            else:
                if rec_mod_2_5 == 1:
                    beneficio_moderada_over25 -= \
                        APUESTA_POR_PARTIDO
                if rec_con_2_5 == 1:
                    beneficio_conservadora_over25 -= \
                        APUESTA_POR_PARTIDO
                if rec_agr_2_5 == 1:
                    beneficio_agresiva_over25 -= \
                        APUESTA_POR_PARTIDO

    # Devolver los resultados
    return {
        "partidos_jugados": partidos_totales,
        "beneficio": {
            "resultado": {
                "moderada": round(beneficio_moderada_resultado, 3),
                "conservadora": round(beneficio_conservadora_resultado, 3),
                "agresiva": round(beneficio_agresiva_resultado, 3),
            },
            "btts": {
                "moderada": round(beneficio_moderada_btts, 3),
                "conservadora": round(beneficio_conservadora_btts, 3),
                "agresiva": round(beneficio_agresiva_btts, 3),
            },
            "over25": {
                "moderada": round(beneficio_moderada_over25, 3),
                "conservadora": round(beneficio_conservadora_over25, 3),
                "agresiva": round(beneficio_agresiva_over25, 3),
            }
        },
        "resultado": {
            "moderada": partidos_apuesta_moderada_resultado,
            "conservadora": partidos_apuesta_conservadora_resultado,
            "agresiva": partidos_apuesta_agresiva_resultado,
            "aciertos_moderada": aciertos_moderada_resultado,
            "aciertos_conservadora": aciertos_conservadora_resultado,
            "aciertos_agresiva": aciertos_agresiva_resultado
        },
        "btts": {
            "moderada": partidos_apuesta_moderada_btts,
            "conservadora": partidos_apuesta_conservadora_btts,
            "agresiva": partidos_apuesta_agresiva_btts,
            "aciertos_moderada": aciertos_moderada_btts,
            "aciertos_conservadora": aciertos_conservadora_btts,
            "aciertos_agresiva": aciertos_agresiva_btts
        },
        "over25": {
            "moderada": partidos_apuesta_moderada_over25,
            "conservadora": partidos_apuesta_conservadora_over25,
            "agresiva": partidos_apuesta_agresiva_over25,
            "aciertos_moderada": aciertos_moderada_over25,
            "aciertos_conservadora": aciertos_conservadora_over25,
            "aciertos_agresiva": aciertos_agresiva_over25
        }
    }


# Analizar resultados y ponerlo bonito
def analizar_resultados():
    # Obtener los resultados
    resultados = comprobar_partidos()

    # Obtener el total de partidos jugados
    total_partidos = resultados['partidos_jugados']

    # Obtener los partidos apostados de cada estilo
    moderada = resultados['resultado']['moderada']
    conservadora = resultados['resultado']['conservadora']
    agresiva = resultados['resultado']['agresiva']
    btts_moderada = resultados['btts']['moderada']
    btts_conservadora = resultados['btts']['conservadora']
    btts_agresiva = resultados['btts']['agresiva']
    over25_moderada = resultados['over25']['moderada']
    over25_conservadora = resultados['over25']['conservadora']
    over25_agresiva = resultados['over25']['agresiva']

    # Obtener los aciertos de cada estilo
    aciertos_moderada = resultados['resultado']['aciertos_moderada']
    aciertos_conservador = resultados['resultado']['aciertos_conservadora']
    aciertos_agresiva = resultados['resultado']['aciertos_agresiva']
    aciertos_btts_moderada = resultados['btts']['aciertos_moderada']
    aciertos_btts_conservador = resultados['btts']['aciertos_conservadora']
    aciertos_btts_agresiva = resultados['btts']['aciertos_agresiva']
    aciertos_over25_moderada = resultados['over25']['aciertos_moderada']
    aciertos_over25_conservador = resultados['over25']['aciertos_conservadora']
    aciertos_over25_agresiva = resultados['over25']['aciertos_agresiva']

    # Calcular las métricas
    # Resultado
    if moderada == 0:
        porcentaje_acierto_moderada = 0
    else:
        porcentaje_acierto_moderada = \
            (aciertos_moderada / moderada) * 100
    if conservadora == 0:
        porcentaje_acierto_conservadora = 0
    else:
        porcentaje_acierto_conservadora = \
            (aciertos_conservador / conservadora) * 100
    if agresiva == 0:
        porcentaje_acierto_agresiva = 0
    else:
        porcentaje_acierto_agresiva = \
            (aciertos_agresiva / agresiva) * 100

    # Ambos Marcan
    if btts_moderada == 0:
        porcentaje_acierto_btts_moderada = 0
    else:
        porcentaje_acierto_btts_moderada = \
            (aciertos_btts_moderada / btts_moderada) * 100
    if btts_conservadora == 0:
        porcentaje_acierto_btts_conservadora = 0
    else:
        porcentaje_acierto_btts_conservadora = \
            (aciertos_btts_conservador / btts_conservadora) * 100
    if btts_agresiva == 0:
        porcentaje_acierto_btts_agresiva = 0
    else:
        porcentaje_acierto_btts_agresiva = \
            (aciertos_btts_agresiva / btts_agresiva) * 100

    # Over 2.5
    if over25_moderada == 0:
        porcentaje_acierto_over25_moderada = 0
    else:
        porcentaje_acierto_over25_moderada = \
            (aciertos_over25_moderada / over25_moderada) * 100
    if over25_conservadora == 0:
        porcentaje_acierto_over25_conservadora = 0
    else:
        porcentaje_acierto_over25_conservadora = \
            (aciertos_over25_conservador / over25_conservadora) * 100
    if over25_agresiva == 0:
        porcentaje_acierto_over25_agresiva = 0
    else:
        porcentaje_acierto_over25_agresiva = \
            (aciertos_over25_agresiva / over25_agresiva) * 100

    # Calcular el beneficio neto
    beneficio_moderada_resultado = \
        resultados['beneficio']['resultado']['moderada']
    inversion_mod_res = moderada * APUESTA_POR_PARTIDO
    roi_mod_res = \
        (beneficio_moderada_resultado / inversion_mod_res * 100) if \
        inversion_mod_res > 0 else 0

    beneficio_conservadora_resultado = \
        resultados['beneficio']['resultado']['conservadora']
    inversion_con_res = conservadora * APUESTA_POR_PARTIDO
    roi_con_res = \
        (beneficio_conservadora_resultado / inversion_con_res * 100) if \
        inversion_con_res > 0 else 0

    beneficio_agresiva_resultado = \
        resultados['beneficio']['resultado']['agresiva']
    inversion_ag_res = agresiva * APUESTA_POR_PARTIDO
    roi_ag_res = \
        (beneficio_agresiva_resultado / inversion_ag_res * 100) if \
        inversion_ag_res > 0 else 0

    beneficion_moderada_btts = \
        resultados['beneficio']['btts']['moderada']
    inversion_mod_btts = btts_moderada * APUESTA_POR_PARTIDO
    roi_mod_btts = \
        (beneficion_moderada_btts / inversion_mod_btts * 100) if \
        inversion_mod_btts > 0 else 0

    beneficion_conservadora_btts = \
        resultados['beneficio']['btts']['conservadora']
    inversion_con_btts = btts_conservadora * APUESTA_POR_PARTIDO
    roi_con_btts = \
        (beneficion_conservadora_btts / inversion_con_btts * 100) if \
        inversion_con_btts > 0 else 0

    beneficion_agresiva_btts = \
        resultados['beneficio']['btts']['agresiva']
    inversion_ag_btts = btts_agresiva * APUESTA_POR_PARTIDO
    roi_ag_btts = \
        (beneficion_agresiva_btts / inversion_ag_btts * 100) if \
        inversion_ag_btts > 0 else 0

    beneficion_moderada_over25 = \
        resultados['beneficio']['over25']['moderada']
    inversion_mod_over25 = over25_moderada * APUESTA_POR_PARTIDO
    roi_mod_over25 = \
        (beneficion_moderada_over25 / inversion_mod_over25 * 100) if \
        inversion_mod_over25 > 0 else 0

    beneficion_conservadora_over25 = \
        resultados['beneficio']['over25']['conservadora']
    inversion_con_over25 = over25_conservadora * APUESTA_POR_PARTIDO
    roi_con_over25 = \
        (beneficion_conservadora_over25 / inversion_con_over25 * 100) if \
        inversion_con_over25 > 0 else 0

    beneficion_agresiva_over25 = \
        resultados['beneficio']['over25']['agresiva']
    inversion_ag_over25 = over25_agresiva * APUESTA_POR_PARTIDO
    roi_ag_over25 = \
        (beneficion_agresiva_over25 / inversion_ag_over25 * 100) if \
        inversion_ag_over25 > 0 else 0

    # Devolver los resultados bonitos
    lineas = []
    lineas.append(f'Total de partidos analizados: {total_partidos}\n')
    lineas.append("Resultados:")
    lineas.append(f"  - Moderada: {porcentaje_acierto_moderada:.2f}%")
    lineas.append(f"    - Partidos recomendados: {moderada}")
    lineas.append(f"    - Beneficio neto: {beneficio_moderada_resultado:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_mod_res:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_mod_res:.1f} unidades")
    lineas.append(f"  - Conservadora: {porcentaje_acierto_conservadora:.2f}%")
    lineas.append(f"    - Partidos recomendados: {conservadora}")
    lineas.append(f"    - Beneficio neto: {beneficio_conservadora_resultado:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_con_res:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_con_res:.1f} unidades")
    lineas.append(f"  - Agresiva: {porcentaje_acierto_agresiva:.2f}%")
    lineas.append(f"    - Partidos recomendados: {agresiva}")
    lineas.append(f"    - Beneficio neto: {beneficio_agresiva_resultado:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_ag_res:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_ag_res:.1f} unidades")
    lineas.append('')
    lineas.append("Ambos Marcan:")
    lineas.append(f"  - Moderada: {porcentaje_acierto_btts_moderada:.2f}%")
    lineas.append(f"    - Partidos recomendados: {btts_moderada}")
    lineas.append(f"    - Beneficio neto: {beneficion_moderada_btts:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_mod_btts:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_mod_btts:.1f} unidades")
    lineas.append(f"  - Conservadora: {porcentaje_acierto_btts_conservadora:.2f}%")
    lineas.append(f"    - Partidos recomendados: {btts_conservadora}")
    lineas.append(f"    - Beneficio neto: {beneficion_conservadora_btts:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_con_btts:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_con_btts:.1f} unidades")
    lineas.append(f"  - Agresiva: {porcentaje_acierto_btts_agresiva:.2f}%")
    lineas.append(f"    - Partidos recomendados: {btts_agresiva}")
    lineas.append(f"    - Beneficio neto: {beneficion_agresiva_btts:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_ag_btts:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_ag_btts:.1f} unidades")
    lineas.append('')
    lineas.append("Mas/Menos 2.5:")
    lineas.append(f"  - Moderada: {porcentaje_acierto_over25_moderada:.2f}%")
    lineas.append(f"    - Partidos recomendados: {over25_moderada}")
    lineas.append(f"    - Beneficio neto: {beneficion_moderada_over25:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_mod_over25:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_mod_over25:.1f} unidades")
    lineas.append(f"  - Conservadora: {porcentaje_acierto_over25_conservadora:.2f}%")
    lineas.append(f"    - Partidos recomendados: {over25_conservadora}")
    lineas.append(f"    - Beneficio neto: {beneficion_conservadora_over25:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_con_over25:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_con_over25:.1f} unidades")
    lineas.append(f"  - Agresiva: {porcentaje_acierto_over25_agresiva:.2f}%")
    lineas.append(f"    - Partidos recomendados: {over25_agresiva}")
    lineas.append(f"    - Beneficio neto: {beneficion_agresiva_over25:+.2f} unidades")
    lineas.append(f"    - ROI (Yield): {roi_ag_over25:+.2f}%")
    lineas.append(f"    - Inversión total: {inversion_ag_over25:.1f} unidades")
    lineas.append('')
    lineas.append('')
    # Resumen
    lineas.append('Resumen por tipo de apuesta:')
    lineas.append('')
    lineas.append('  - Resultados:')
    lineas.append('    - Moderada:')
    if moderada == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_moderada/moderada)*100:.2f}% - {moderada}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_mod_res:.2f}%')
    lineas.append('    - Conservadora:')
    if conservadora == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_conservador/conservadora)*100:.2f}% - {conservadora}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_con_res:.2f}%')
    lineas.append('    - Agresiva:')
    if agresiva == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_agresiva/agresiva)*100:.2f}% - {agresiva}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_ag_res:.2f}%')
    lineas.append('')
    lineas.append('  - Ambos Marcan:')
    lineas.append('    - Moderada:')
    if btts_moderada == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_btts_moderada/btts_moderada)*100:.2f}% - {btts_moderada}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_mod_btts:.2f}%')
    lineas.append('    - Conservadora:')
    if btts_conservadora == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: '
              f'\t{(aciertos_btts_conservador/btts_conservadora)*100:.2f}% - '
              f'{btts_conservadora}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_con_btts:.2f}%')
    lineas.append('    - Agresiva:')
    if btts_agresiva == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_btts_agresiva/btts_agresiva)*100:.2f}% - {btts_agresiva}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_ag_btts:.2f}%')
    lineas.append('')
    lineas.append('  - Más/Menos 2.5:')
    lineas.append('    - Moderada:')
    if over25_moderada == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_over25_moderada/over25_moderada)*100:.2f}% - {over25_moderada}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_mod_over25:.2f}%')
    lineas.append('    - Conservadora:')
    if over25_conservadora == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_over25_conservador/over25_conservadora)*100:.2f}% - {over25_conservadora}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_con_over25:.2f}%')
    lineas.append('    - Agresiva:')
    if over25_agresiva == 0:
        lineas.append('      - Aciertos: \t0.00% - 0 apostados.')
    else:
        lineas.append(f'      - Aciertos: \t{(aciertos_over25_agresiva/over25_agresiva)*100:.2f}% - {over25_agresiva}/{total_partidos} apostados.')
    lineas.append(f'      - Rentabilidad: {roi_ag_over25:.2f}%')
    lineas.append('')
    lineas.append('Resumen Modelo Moderado:')
    lineas.append('')
    # ROI Moderado (todos los mercados)
    inversion_moderada_tota = inversion_mod_res + inversion_mod_btts + \
        inversion_mod_over25
    beneficio_moderada_total = beneficio_moderada_resultado + \
        beneficion_moderada_btts + beneficion_moderada_over25
    roi_moderada_total = \
        (beneficio_moderada_total / inversion_moderada_tota * 100) \
        if inversion_moderada_tota > 0 else 0
    lineas.append(f"  - ROI MODERADO: {roi_moderada_total:+.2f}%")
    lineas.append(f"  - Beneficio neto: {beneficio_moderada_total:+.2f}")
    lineas.append(f"  - Inversión total: {inversion_moderada_tota}")
    lineas.append(f"  - Apuestas totales: {inversion_moderada_tota/APUESTA_POR_PARTIDO:.0f}")

    lineas.append('')
    lineas.append('Resumen Modelo Conservadora:')
    lineas.append('')
    # ROI Conservadora (todos los mercados)
    inversion_conservadora_tota = inversion_con_res + inversion_con_btts + \
        inversion_con_over25
    beneficio_conservadora_total = beneficio_conservadora_resultado + \
        beneficion_conservadora_btts + beneficion_conservadora_over25
    roi_conservadora_total = \
        (beneficio_conservadora_total / inversion_conservadora_tota * 100) \
        if inversion_conservadora_tota > 0 else 0
    lineas.append(f"  - ROI CONSERVADORA: {roi_conservadora_total:+.2f}%")
    lineas.append(f"  - Beneficio neto: {beneficio_conservadora_total:+.2f}")
    lineas.append(f"  - Inversión total: {inversion_conservadora_tota}")
    lineas.append(f"  - Apuestas totales: {inversion_conservadora_tota/APUESTA_POR_PARTIDO:.0f}")

    lineas.append('')
    lineas.append('Resumen Modelo Agresiva:')
    lineas.append('')
    # ROI Agresiva (todos los mercados)
    inversion_agresiva_tota = inversion_ag_res + inversion_ag_btts + \
        inversion_ag_over25
    beneficio_agresiva_total = beneficio_agresiva_resultado + \
        beneficion_agresiva_btts + beneficion_agresiva_over25
    roi_agresiva_total = \
        (beneficio_agresiva_total / inversion_agresiva_tota * 100) \
        if inversion_agresiva_tota > 0 else 0
    lineas.append(f"  - ROI AGRESIVA: {roi_agresiva_total:+.2f}%")
    lineas.append(f"  - Beneficio neto: {beneficio_agresiva_total:+.2f}")
    lineas.append(f"  - Inversión total: {inversion_agresiva_tota}")
    lineas.append(f"  - Apuestas totales: {inversion_agresiva_tota/APUESTA_POR_PARTIDO:.0f}")

    lineas.append('')
    lineas.append('Resumen global:')
    lineas.append('')
    # ROI Global (todos los niveles y mercados)
    inversion_global = (
        inversion_moderada_tota +
        inversion_conservadora_tota +
        inversion_agresiva_tota
    )
    beneficio_global = (
        beneficio_moderada_total +
        beneficio_conservadora_total +
        beneficio_agresiva_total
    )
    roi_global = \
        (beneficio_global / inversion_global * 100) \
        if inversion_global > 0 else 0
    lineas.append(f"  - ROI GLOBAL: {roi_global:+.2f}%")
    lineas.append(f"  - Beneficio neto global: {beneficio_global:+.2f} unidades")
    lineas.append(f"  - Inversión global: {inversion_global:.1f} unidades")
    lineas.append(f"  - Apuestas globales: {inversion_global / APUESTA_POR_PARTIDO:.0f}")

    resumen_modelos = {
        "partidos_totales": total_partidos,

        "modelo_moderado": {
            "aciertos": (
                (aciertos_moderada + aciertos_btts_moderada + aciertos_over25_moderada) /
                (moderada + btts_moderada + over25_moderada) * 100
            ) if (moderada + btts_moderada + over25_moderada) > 0 else 0,
            "aciertos_brutos": (
                aciertos_moderada + aciertos_btts_moderada + aciertos_over25_moderada
            ),
            "roi": roi_moderada_total,
            "beneficio": beneficio_moderada_total,
            "inversion": inversion_moderada_tota,
            "apuestas": (inversion_moderada_tota / APUESTA_POR_PARTIDO)
        },

        "modelo_conservador": {
            "aciertos": (
                (aciertos_conservador + aciertos_btts_conservador + aciertos_over25_conservador) /
                (conservadora + btts_conservadora + over25_conservadora) * 100
            ) if (conservadora + btts_conservadora + over25_conservadora) > 0 else 0,
            "aciertos_brutos": (
                aciertos_conservador + aciertos_btts_conservador + aciertos_over25_conservador
            ),
            "roi": roi_conservadora_total,
            "beneficio": beneficio_conservadora_total,
            "inversion": inversion_conservadora_tota,
            "apuestas": (inversion_conservadora_tota / APUESTA_POR_PARTIDO)
        },

        "modelo_arriesgado": {
            "aciertos": (
                (aciertos_agresiva + aciertos_btts_agresiva + aciertos_over25_agresiva) /
                (agresiva + btts_agresiva + over25_agresiva) * 100
            ) if (agresiva + btts_agresiva + over25_agresiva) > 0 else 0,
            "aciertos_brutos": (
                aciertos_agresiva + aciertos_btts_agresiva + aciertos_over25_agresiva
            ),
            "roi": roi_agresiva_total,
            "beneficio": beneficio_agresiva_total,
            "inversion": inversion_agresiva_tota,
            "apuestas": (inversion_agresiva_tota / APUESTA_POR_PARTIDO)
        },

        "modelo_global": {
            "aciertos": (
                (aciertos_moderada + aciertos_btts_moderada + aciertos_over25_moderada +
                 aciertos_conservador + aciertos_btts_conservador + aciertos_over25_conservador +
                 aciertos_agresiva + aciertos_btts_agresiva + aciertos_over25_agresiva) /
                (moderada + btts_moderada + over25_moderada +
                 conservadora + btts_conservadora + over25_conservadora +
                 agresiva + btts_agresiva + over25_agresiva) * 100
            ) if (
                moderada + btts_moderada + over25_moderada +
                conservadora + btts_conservadora + over25_conservadora +
                agresiva + btts_agresiva + over25_agresiva
            ) > 0 else 0,
            "aciertos_brutos": (
                aciertos_moderada + aciertos_btts_moderada + aciertos_over25_moderada +
                aciertos_conservador + aciertos_btts_conservador + aciertos_over25_conservador +
                aciertos_agresiva + aciertos_btts_agresiva + aciertos_over25_agresiva
            ),
            "roi": roi_global,
            "beneficio": beneficio_global,
            "inversion": inversion_global,
            "apuestas": (inversion_global / APUESTA_POR_PARTIDO)
        }
    }

    resumen_tipo_prediccion = {
        "resultado": {
            "conservador": {
                "aciertos": porcentaje_acierto_conservadora,
                "aciertos_brutos": aciertos_conservador,
                "apuestas": conservadora,
                "roi": roi_con_res,
                "beneficio": beneficio_conservadora_resultado,
                "inversion": inversion_con_res
            },
            "moderado": {
                "aciertos": porcentaje_acierto_moderada,
                "aciertos_brutos": aciertos_moderada,
                "apuestas": moderada,
                "roi": roi_mod_res,
                "beneficio": beneficio_moderada_resultado,
                "inversion": inversion_mod_res
            },
            "agresivo": {
                "aciertos": porcentaje_acierto_agresiva,
                "aciertos_brutos": aciertos_agresiva,
                "apuestas": agresiva,
                "roi": roi_ag_res,
                "beneficio": beneficio_agresiva_resultado,
                "inversion": inversion_ag_res
            }
        },
        "btts": {
            "conservador": {
                "aciertos": porcentaje_acierto_btts_conservadora,
                "aciertos_brutos": aciertos_btts_conservador,
                "apuestas": btts_conservadora,
                "roi": roi_con_btts,
                "beneficio": beneficion_conservadora_btts,
                "inversion": inversion_con_btts
            },
            "moderado": {
                "aciertos": porcentaje_acierto_btts_moderada,
                "aciertos_brutos": aciertos_btts_moderada,
                "apuestas": btts_moderada,
                "roi": roi_mod_btts,
                "beneficio": beneficion_moderada_btts,
                "inversion": inversion_mod_btts
            },
            "agresivo": {
                "aciertos": porcentaje_acierto_btts_agresiva,
                "aciertos_brutos": aciertos_btts_agresiva,
                "apuestas": btts_agresiva,
                "roi": roi_ag_btts,
                "beneficio": beneficion_agresiva_btts,
                "inversion": inversion_ag_btts
            }
        },
        "over": {
            "conservador": {
                "aciertos": porcentaje_acierto_over25_conservadora,
                "aciertos_brutos": aciertos_over25_conservador,
                "apuestas": over25_conservadora,
                "roi": roi_con_over25,
                "beneficio": beneficion_conservadora_over25,
                "inversion": inversion_con_over25
            },
            "moderado": {
                "aciertos": porcentaje_acierto_over25_moderada,
                "aciertos_brutos": aciertos_over25_moderada,
                "apuestas": over25_moderada,
                "roi": roi_mod_over25,
                "beneficio": beneficion_moderada_over25,
                "inversion": inversion_mod_over25
            },
            "agresivo": {
                "aciertos": porcentaje_acierto_over25_agresiva,
                "aciertos_brutos": aciertos_over25_agresiva,
                "apuestas": over25_agresiva,
                "roi": roi_ag_over25,
                "beneficio": beneficion_agresiva_over25,
                "inversion": inversion_ag_over25
            }
        }
    }

    # Guardar el texto
    lineas_format = "\n".join(lineas)
    guardar_precision(lineas_format)
    guardar_resumen(resumen_modelos)
    guardar_resumen_tipo_apuesta(resumen_tipo_prediccion)
