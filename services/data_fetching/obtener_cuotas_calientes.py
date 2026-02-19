import pickle
import os
from datetime import date, datetime, timedelta
import logging
from config import BASE_DIR

logger = logging.getLogger(__name__)


# Guardar las cuotas calientes
def guardar_cuotas_calientes(calientes):
    # 3. Guardar en SQL (New)
    try:
        from extensions import db
        from models import CuotaCaliente, Partido
        from flask import current_app

        if current_app:
            fecha_detectado = date.today()
            
            # Borrar las de hoy para evitar duplicados si se re-ejecuta
            CuotaCaliente.query.filter_by(fecha_detectado=fecha_detectado).delete()
            
            for item in calientes:
                partido_id = item.get('id')
                pick = item.get('pick', {})
                
                # Verificar que el partido existe
                if not db.session.get(Partido, partido_id):
                    continue

                nueva = CuotaCaliente(
                    partido_id=partido_id,
                    fecha_detectado=fecha_detectado,
                    mercado=pick.get('mercado'),
                    prediccion=pick.get('prediccion'),
                    probabilidad=pick.get('prob') or pick.get('probabilidad'),
                    cuota=pick.get('cuota'),
                    valor=pick.get('value') or pick.get('valor'),
                    score=pick.get('score')
                )
                db.session.add(nueva)
            
            db.session.commit()
            logger.info("Hot Odds saved to SQL.")
    except Exception as e:
        logger.error(f"Error saving hot odds to SQL: {e}")


# Cargar las cuotas calientes
def cargar_cuotas_calientes():
    # Intentar cargar de SQL primero
    try:
        from models import CuotaCaliente
        from flask import current_app
        
        if current_app:
            # Obtener cuotas de hoy (o las más recientes)
            fecha_hoy = date.today()
            cuotas_sql = CuotaCaliente.query.filter_by(fecha_detectado=fecha_hoy).all()
            
            if cuotas_sql:
                # Reconstruir formato legacy completo
                calientes = []
                for c in cuotas_sql:
                    # Obtener datos del partido relacionado
                    partido_obj = c.partido
                    if not partido_obj:
                         continue
                         
                    nombre_partido = "Desconocido vs Desconocido"
                    if partido_obj.equipo_local and partido_obj.equipo_visitante:
                        nombre_partido = f"{partido_obj.equipo_local.nombre} vs {partido_obj.equipo_visitante.nombre}"
                    
                    nombre_liga = partido_obj.liga.nombre if partido_obj.liga else "Liga desconocida"
                    fecha_str = partido_obj.fecha.strftime("%Y-%m-%d") if partido_obj.fecha else ""

                    calientes.append({
                        'id': c.partido_id,
                        'partido': nombre_partido,
                        'fecha': fecha_str,
                        'liga': nombre_liga,
                        'pick': {
                            'mercado': c.mercado,
                            'prediccion': c.prediccion,
                            'prob': c.probabilidad,
                            'cuota': c.cuota,
                            'value': c.valor,
                            'score': c.score
                        }
                    })
                return calientes
    except Exception as e:
        logger.error(f"Error loading hot odds from SQL: {e}")

    # Fallback a Pickle eliminado
    return []


# Cargar historial de cuotas calientes (Legacy - Eliminado)
def cargar_historial_cuotas_calientes(fecha):
    return []


# Cargar historial de cuotas calientes recibiendo un String YYYY_mm_dd (Legacy - Eliminado)
def cargar_historial_cuotas_calientes_string(fecha):
    return []


# Guardar las partidos calientes (Legacy - ya no necesario con SQL)
def guardar_partidos_calientes(partidos):
    pass


# Cargar las partidos calientes
def cargar_partidos_calientes():
    # Intentar cargar de SQL (Join Partido + CuotaCaliente)
    try:
        from models import Partido, CuotaCaliente
        from flask import current_app
        
        if current_app:
            fecha_hoy = date.today()
            # Subquery o Join distinct
            # Queremos los partidos que tienen una CuotaCaliente hoy
            partidos_sql = Partido.query.join(CuotaCaliente).filter(
                CuotaCaliente.fecha_detectado == fecha_hoy
            ).all()
            
            if partidos_sql:
                return partidos_sql
    except Exception as e:
        logger.error(f"Error loading hot matches from SQL: {e}")

    # Fallback a Pickle eliminado
    return []


# Guardar historial partidos calientes (Legacy - Eliminado)
def guardar_historial_partidos_calientes(partidos):
    pass


# Cargar historial de partidos calientes (Legacy - Eliminado)
def cargar_historial_partidos_calientes(fecha):
    return []


# Cargar historial de partidos calientes recibiendo un String YYYY_mm_dd (Legacy - Eliminado)
def cargar_historial_partidos_calientes_string(fecha):
    return []


# Comprobar si estamos en los próximos 10 días
def en_proximos_10_dias(fecha_str):
    fecha_partido = datetime.strptime(fecha_str, "%d/%m/%Y")
    hoy = datetime.now()
    return hoy <= fecha_partido <= hoy + timedelta(days=10)


# Calcular el "Value Bet"
def calcular_value(prob, cuota):
    if cuota <= 1:
        return None
    return prob - (1 / cuota)


# Filtrar los partidos con cuotas interesantes
def filtrar_cuotas_calientes(partidos):
    calientes = []
    partidos_calientes = []

    for p in partidos:
        if not en_proximos_10_dias(p.fecha):
            continue

        oportunidades = []

        # === GANADOR ===
        prob_ganador = float(p.prediccion['resultado_1x2']['probabilidad_max'])
        prob_ganador = round(prob_ganador, 2)
        pred_ganador = p.prediccion['resultado_1x2']['prediccion']
        cuota_ganador = -1
        if pred_ganador == "Local":
            cuota_ganador = float(p.cuota_local)
        elif pred_ganador == "Visitante":
            cuota_ganador = float(p.cuota_visitante)
        else:
            cuota_ganador = float(p.cuota_empate)

        if prob_ganador >= 0.60 and cuota_ganador >= 2.2:
            value = calcular_value(prob_ganador, cuota_ganador)
            if value and value >= 0.08:
                oportunidades.append({
                    "mercado": "Ganador",
                    "prediccion": pred_ganador,
                    "prob": prob_ganador,
                    "cuota": cuota_ganador,
                    "value": round(value, 2)
                })

        # === BTTS ===
        prob_btts = float(p.prediccion['btts']['probabilidad'])
        prob_btts = round(prob_btts, 2)
        pred_btts = p.prediccion['btts']['prediccion']
        cuota_btts = -1
        if pred_btts == "No":
            cuota_btts = float(p.cuota_btts_no)
        else:
            cuota_btts = float(p.cuota_btts)

        if prob_btts >= 0.58 and cuota_btts >= 1.9:
            value = calcular_value(prob_btts, cuota_btts)
            if value and value >= 0.08:
                oportunidades.append({
                    "mercado": "BTTS",
                    "prediccion": pred_btts,
                    "prob": prob_btts,
                    "cuota": cuota_btts,
                    "value": round(value, 2)
                })

        # === OVER 2.5 ===
        prob_over = float(p.prediccion['over25']['probabilidad'])
        prob_over = round(prob_over, 2)
        pred_over = p.prediccion['over25']['prediccion']
        cuota_over = -1
        if pred_over == "Over":
            cuota_over = float(p.cuota_over)
        else:
            cuota_over = float(p.cuota_under)

        if prob_over >= 0.58 and cuota_over >= 1.85:
            value = calcular_value(prob_over, cuota_over)
            if value and value >= 0.08:
                oportunidades.append({
                    "mercado": "Over 2.5",
                    "prediccion": pred_over,
                    "prob": prob_over,
                    "cuota": cuota_over,
                    "value": round(value, 2)
                })

        if oportunidades:
            partidos_calientes.append(p)
            calientes.append({
                "id": p.id_partido,
                "partido": f'{p.equipo_local.nombre} vs {p.equipo_visitante.nombre}',
                "fecha": p.fecha,
                "liga": p.equipo_local.nombre_liga,
                "oportunidades": oportunidades
            })

    return calientes, partidos_calientes


# Elegir la mejor apuesta para un partido si hay varias
def elegir_mejor_oportunidad(oportunidades):
    mejor = None
    mejor_score = -1

    for o in oportunidades:
        value = float(o['value'])
        prob = float(o['prob'])
        score = value * 0.6 + prob * 0.4

        o['score'] = round(score, 2)

        if score > mejor_score:
            mejor = o
            mejor_score = score

    return mejor


# Filtrar los partidos calientes para mostrar los 5 mejores
def filtrar_5_mejores_cuotas_calientes(partidos):
    cc_filtradas = []
    p_filtrados = []

    cuotas_calientes, partidos_calientes = filtrar_cuotas_calientes(partidos)

    # Filtrar los resultados
    for c in cuotas_calientes:
        oportunidades = c['oportunidades']

        mejor_oportunidad = elegir_mejor_oportunidad(oportunidades)

        c['pick'] = mejor_oportunidad
        del c['oportunidades']  # opcional: ocultar las demás

        cc_filtradas.append(c)

    cc_filtradas.sort(
        key=lambda x: (
            -x['pick']['score']
        )
    )

    cc_filtradas = cc_filtradas[:5]

    cc_filtradas.sort(
        key=lambda x: (
            x['fecha']
        )
    )

    for c in cc_filtradas:
        id_c = c['id']
        for p in partidos_calientes:
            id_p = p.id_partido
            if id_p == id_c:
                p_filtrados.append(p)

    guardar_cuotas_calientes(cc_filtradas)
    guardar_partidos_calientes(p_filtrados)
    guardar_historial_partidos_calientes(p_filtrados)

