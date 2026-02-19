# from services.data_fetching.obtener_equipos import cargar_equipos  <-- Legacy removed
from services.data_fetching.obtener_partidos import cargar_partidos
from config import TEMPORADA_ACTUAL
from models import Partido
from sqlalchemy import or_

def buscar_equipo(id_equipo, equipos):
    equipos_actual = [e for e in equipos if e.temporada == TEMPORADA_ACTUAL]
    equipo = []
    for e in equipos_actual:
        if e.id == id_equipo:
            equipo.append(e)

    return equipo


def buscar_partidos_equipo(id_equipo):
    # Optimización: Cargar partidos desde BD en lugar de pickle
    # Se obtienen todos los partidos donde el equipo juega como local o visitante
    
    partidos_db = Partido.query.filter(
        or_(Partido.id_local == id_equipo, Partido.id_visitante == id_equipo)
    ).order_by(Partido.fecha.desc()).all()
    
    # Agrupar por liga para mantener la estructura legacy
    # Estructura esperada: [{"id_liga": X, "partidos": [...]}, ...]
    partidos_por_liga = {}
    
    for p in partidos_db:
        # Filtrar por temporada actual si es necesario, aunque la query podría hacerlo
        if p.temporada != TEMPORADA_ACTUAL:
            continue
            
        lid = p.id_liga
        if lid not in partidos_por_liga:
            partidos_por_liga[lid] = []
        
        partidos_por_liga[lid].append(p.to_dict())
        
    # Convertir a lista de competiciones
    partidos_equipo = []
    for lid, matches in partidos_por_liga.items():
        competicion = {
            "id_liga": lid,
            "partidos": matches
        }
        partidos_equipo.append(competicion)
        
    return partidos_equipo


def buscar_liga_equipo(id_equipo):
    """Busca todos los registros de un equipo (uno por liga) y la clasificación de cada liga (SQL version)."""
    from models import Equipo
    
    # 1. Buscar todas las instancias de este equipo (una por cada liga donde juega)
    equipos_sql = Equipo.query.filter_by(id=id_equipo).all()
    
    if not equipos_sql:
        return []

    equipos_liga = []
    
    # 2. Para cada liga, obtener la clasificación completa
    for eq in equipos_sql:
        # Filtrar solo temporada actual
        if eq.temporada != TEMPORADA_ACTUAL:
            continue

        # Obtener todos los equipos de esta liga ordenados por posición
        clasificacion = Equipo.query.filter_by(
            id_liga=eq.id_liga, 
            temporada=TEMPORADA_ACTUAL
        ).order_by(Equipo.posicion.asc()).all()
        
        competicion = {
            "id_liga": eq.id_liga,
            "equipo": eq.to_dict(),
            "equipos": [e.to_dict() for e in clasificacion]
        }
        equipos_liga.append(competicion)
        
    return equipos_liga


def obtener_datos_equipo(id_equipo):
    partidos = buscar_partidos_equipo(id_equipo)
    equipos_liga = buscar_liga_equipo(id_equipo)
    datos = {
        "partidos": partidos,
        "equipos": equipos_liga
    }
    return datos
