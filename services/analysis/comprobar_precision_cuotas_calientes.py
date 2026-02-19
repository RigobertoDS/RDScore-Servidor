
from datetime import date, timedelta, datetime
from flask import current_app
from extensions import db
from models import Partido, CuotaCaliente
from services.analysis.comprobar_precision import guardar_reporte_sql, cargar_reporte_sql
import logging

logger = logging.getLogger(__name__)


def ajustar_prediccion(prediccion):
    if prediccion == 'Local':
        return 1
    elif prediccion == 'Empate':
        return 0
    elif prediccion == 'Visitante':
        return 2
    elif prediccion == 'No':
        return 0
    elif prediccion == 'Si':
        return 1
    elif prediccion == 'Under':
        return 0
    elif prediccion == 'Over':
        return 1
    else:
        return None


def comprobar_acierto(partido, mercado, prediccion_str):
    # Mercados: Ganador, BTTS, Over 2.5
    # Ganador: Local [1], Visitante [2], Empate [0]
    # BTTS: No [0], Sí [1]
    # Over 2.5: Under [0], Over [1]
    
    prediccion = ajustar_prediccion(prediccion_str)

    if mercado == 'Ganador':
        if prediccion == partido.resultado:
            return 1
    elif mercado == 'BTTS':
        if prediccion == partido.ambos_marcan:
            return 1
    elif mercado == 'Over 2.5':
        if prediccion == partido.mas_2_5:
            return 1
            
    return 0


def guardar_resumen_cuotas_calientes(resumen):
    guardar_reporte_sql('resumen_cuotas_calientes', resumen)


def cargar_resumen_cuotas_calientes():
    return cargar_reporte_sql('resumen_cuotas_calientes')

# Funciones legacy vacías o redirigidas para no romper imports, 
# aunque idealmente se deberían borrar del todo si nadie las llama.
def guardar_historial_cuotas_calientes(idx=None): pass
def cargar_historial_cuotas_calientes(): return []
def cargar_historial_partidos_calientes(): return []


def comprobar_precision_cuotas_calientes():
    if not current_app:
        return

    PRIMER_DIA = "2026-02-13"
    primer_dia_obj = datetime.strptime(PRIMER_DIA, "%Y-%m-%d").date()

    # Obtener todas las cuotas calientes de partidos TERMINADOS
    # Join CuotaCaliente -> Partido
    # IMPORTANTE: Filtrar por fecha_detectado (cuando se hizo la predicción v2)
    # y no por fecha del partido (que puede ser posterior pero predicho con v1)
    resultados = db.session.query(CuotaCaliente, Partido).join(Partido).filter(
        Partido.estado == 'FT',
        CuotaCaliente.fecha_detectado >= primer_dia_obj
    ).all()

    partidos_count = 0 
    aciertos = 0
    beneficio = 0.0
    
    # Set para contar partidos únicos (una cuota puede haber varias por partido, o no)
    # El código original iteraba sobre "partidos_filtrados" y "cuotas_filtradas" que estaban alineados 1 a 1.
    # Aquí 'resultados' es una lista de tuplas (CuotaCaliente, Partido)
    
    # Asumimos que queremos estadísticas por CUOTA (Oportunidad)
    # Si hay 2 cuotas calientes en un partido, cuentan como 2 apuestas.
    
    for cuota_obj, partido_obj in resultados:
        partidos_count += 1
        
        acierto = comprobar_acierto(partido_obj, cuota_obj.mercado, cuota_obj.prediccion)
        
        if acierto:
            aciertos += 1
            # Beneficio: (Cuota - 1) * Unidad
            # Asumimos Unidad = 1
            beneficio += (cuota_obj.cuota - 1)
        else:
            beneficio -= 1

    precision = aciertos / partidos_count if partidos_count > 0 else 0
    roi = beneficio / partidos_count if partidos_count > 0 else 0

    resumen = {
        "partidos": partidos_count, # Total de apuestas evaluadas
        "aciertos": aciertos,
        "precision": precision,
        "beneficio": beneficio,
        "roi": roi
    }
    
    guardar_resumen_cuotas_calientes(resumen)
    logger.info(f"Precisión Cuotas Calientes calculada: {precision:.2%} (ROI: {roi:.2f}u)")


def obtener_historial_cuotas_calientes():
    """
    Devuelve la lista de cuotas calientes de partidos TERMINADOS (desde el 13/02/2026),
    con el detalle de si se acertó o no.
    """
    if not current_app:
        return []

    PRIMER_DIA = "2026-02-13"
    primer_dia_obj = datetime.strptime(PRIMER_DIA, "%Y-%m-%d").date()

    # Query igual que en comprobar_precision
    resultados = db.session.query(CuotaCaliente, Partido).join(Partido).filter(
        Partido.estado == 'FT',
        CuotaCaliente.fecha_detectado >= primer_dia_obj
    ).order_by(Partido.fecha.desc()).all()

    historial = []
    
    for cuota_obj, partido_obj in resultados:
        acierto = comprobar_acierto(partido_obj, cuota_obj.mercado, cuota_obj.prediccion)
        
        # Formatear respuesta
        nombre_partido = "Desconocido vs Desconocido"
        if partido_obj.equipo_local and partido_obj.equipo_visitante:
            nombre_partido = f"{partido_obj.equipo_local.nombre} vs {partido_obj.equipo_visitante.nombre}"
        
        nombre_liga = partido_obj.liga.nombre if partido_obj.liga else "Liga desconocida"

        item = {
            "id": partido_obj.id,
            "partido": nombre_partido,
            "liga": nombre_liga,
            "fecha": partido_obj.fecha.strftime("%Y-%m-%d") if partido_obj.fecha else "",
            "pick": {
                "mercado": cuota_obj.mercado,
                "prediccion": cuota_obj.prediccion,
                "cuota": cuota_obj.cuota,
                "prob": cuota_obj.probabilidad,
                "value": cuota_obj.valor,
                "score": cuota_obj.score
            },
            "resultado_partido": f"{partido_obj.goles_local}-{partido_obj.goles_visitante}" if partido_obj.goles_local is not None else "N/A",
            "acierto": bool(acierto)
        }
        historial.append(item)
    
    return historial
