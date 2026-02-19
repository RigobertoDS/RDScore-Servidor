import logging
from datetime import datetime
from flask import current_app
from extensions import db
from models import Liga, Equipo, Partido
from sqlalchemy.dialects.mysql import insert

# Configure logging
logger = logging.getLogger(__name__)

def guardar_ligas_en_bd(equipos_legacy):
    """
    Extrae y guarda las ligas únicas de una lista de objetos Equipo legacy.
    """
    if not current_app:
        return

    try:
        # 1. Mapear ligas únicas
        ligas_map = {}
        for t in equipos_legacy:
            if t.id_liga and t.id_liga > 0:
                if t.id_liga not in ligas_map:
                    ligas_map[t.id_liga] = Liga(
                        id=t.id_liga,
                        nombre=t.nombre_liga or "Liga Desconocida",
                        pais=t.pais or "N/A",
                        bandera=t.bandera or "",
                        logo=t.logo_liga or ""
                    )
        
        # 2. Guardar (Merge)
        for liga in ligas_map.values():
            db.session.merge(liga)
        
        db.session.commit()
    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving leagues to SQL: {e}")

def guardar_equipos_en_bd(equipos_legacy):
    """
    Guarda una lista de objetos Equipo legacy en la BD con clave compuesta (id, id_liga).
    """
    if not current_app:
        return

    try:
        count = 0
        for t in equipos_legacy:
            if not t.id or t.id <= 0: continue
            if not t.id_liga or t.id_liga <= 0: continue

            # Stats JSON (todo lo que no es columna explícita)
            stats = {
                "PT": t.PT, "VT": t.VT, "ET": t.ET, "DT": t.DT,
                "PC": t.PC, "VC": t.VC, "EC": t.EC, "DC": t.DC,
                "PF": t.PF, "VF": t.VF, "EF": t.EF, "DF": t.DF,
                "goles_favor": t.goles_favor,
                "goles_contra": t.goles_contra,
                "diferencia_goles": getattr(t, 'dif_goles', 0),
                "ultimos_5": getattr(t, 'ultimos_5', "")
            }

            equipo_sql = Equipo(
                id=t.id,
                id_liga=t.id_liga,
                nombre=t.nombre,
                logo=t.logo,
                posicion=t.posicion,
                puntos=t.puntos,
                forma=t.forma,
                temporada=t.temporada,
                stats_json=stats
            )
            db.session.merge(equipo_sql)
            count += 1
        
        db.session.commit()
        logger.info(f"SQL Persistence: Saved {count} teams.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving teams to SQL: {e}")

def guardar_partidos_en_bd(partidos_legacy):
    """
    Guarda partidos (fixtures/resultados). 
    NO SOBREESCRIBE predicciones ni cuotas si ya existen en BD.
    """
    if not current_app:
        return

    try:
        count = 0
        # Pre-validacion de equipos para evitar IntegrityError masivo
        # Cargar IDs de equipos validos en memoria
        # (Si son muchos equipos, esto podria ser costoso, pero para < 5000 esta ok)
        equipos_validos = set(
            (id_eq, id_lg) for id_eq, id_lg in db.session.query(Equipo.id, Equipo.id_liga).all()
        )

        for p in partidos_legacy:
            if not p.id_partido or p.id_partido <= 0: continue
            
            # Validar IDs minimos
            if not p.id_liga or p.id_liga <= 0: continue
            # Usar ids_equipos seguros
            if not hasattr(p, 'equipo_local') or not hasattr(p, 'equipo_visitante'): continue
            
            id_local = getattr(p.equipo_local, 'id', 0)
            id_visitante = getattr(p.equipo_visitante, 'id', 0)
            
            if id_local <= 0 or id_visitante <= 0: 
                # logger.warning(f"Skipping match {p.id_partido}: Invalid team IDs ({id_local}, {id_visitante})")
                continue
                
            # Validar FK contra equipos existentes
            if (id_local, p.id_liga) not in equipos_validos:
                # logger.warning(f"Skipping match {p.id_partido}: Local Team {id_local} not found in League {p.id_liga}")
                continue
            if (id_visitante, p.id_liga) not in equipos_validos:
                # logger.warning(f"Skipping match {p.id_partido}: Visitor Team {id_visitante} not found in League {p.id_liga}")
                continue

            # Parse fechas
            fecha_obj = None
            if p.fecha:
                try:
                    fecha_obj = datetime.strptime(p.fecha, "%d/%m/%Y").date()
                except ValueError:
                    pass
            
            # Info extra
            info_json = {
                "ciudad": getattr(p, 'ciudad', ""),
                "estadio": getattr(p, 'estadio', ""),
                "arbitro": getattr(p, 'arbitro', "")
            }

            # Lógica de Merge Manual para preservar predicción
            existing = db.session.get(Partido, p.id_partido)
            
            if existing:
                # Actualizar campos base
                existing.fecha = fecha_obj
                existing.hora = getattr(p, 'hora', "00:00")
                existing.estado = getattr(p, 'estado', "NS")
                existing.jornada = getattr(p, 'jornada', "")
                existing.goles_local = getattr(p, 'goles_local', None) if getattr(p, 'goles_local', -1) != -1 else None
                existing.goles_visitante = getattr(p, 'goles_visitante', None) if getattr(p, 'goles_visitante', -1) != -1 else None
                existing.resultado = getattr(p, 'resultado', -1)
                
                # Stats explícitos
                existing.ambos_marcan = getattr(p, 'ambos_marcan', -1)
                existing.local_marca = getattr(p, 'local_marca', -1)
                existing.visitante_marca = getattr(p, 'visitante_marca', -1)
                existing.mas_2_5 = getattr(p, 'mas_2_5', -1)
                
                # Actualizar info extra
                existing.info_extra = info_json
                
                # NO TOCAMOS cuotas NI prediccion aquí
            else:
                # Insertar nuevo
                try:
                    nuevo = Partido(
                        id=p.id_partido,
                        fecha=fecha_obj,
                        hora=getattr(p, 'hora', "00:00"),
                        estado=getattr(p, 'estado', "NS"),
                        id_liga=p.id_liga,
                        temporada=getattr(p, 'temporada', 2025),
                        jornada=getattr(p, 'jornada', ""),
                        id_local=id_local,
                        id_visitante=id_visitante,
                        goles_local=getattr(p, 'goles_local', None) if getattr(p, 'goles_local', -1) != -1 else None,
                        goles_visitante=getattr(p, 'goles_visitante', None) if getattr(p, 'goles_visitante', -1) != -1 else None,
                        resultado=getattr(p, 'resultado', -1),
                        ambos_marcan=getattr(p, 'ambos_marcan', -1),
                        local_marca=getattr(p, 'local_marca', -1),
                        visitante_marca=getattr(p, 'visitante_marca', -1),
                        mas_2_5=getattr(p, 'mas_2_5', -1),
                        info_extra=info_json,
                        cuotas={}, # Vacío por defecto
                        prediccion={} # Vacío por defecto
                    )
                    db.session.add(nuevo)
                except Exception as e:
                    logger.error(f"Error creating match object {p.id_partido}: {e}")
            
            count += 1
            
            # Commit periódico para no recargar memoria y manejar errores por bloque si fuera necesario
            if count % 1000 == 0:
                db.session.commit()
                
        db.session.commit()
        logger.info(f"SQL Persistence: Saved {count} matches (filtered valid ones).")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving matches to SQL: {e}")

def guardar_predicciones_en_bd(partidos_predichos):
    """
    Actualiza SOLO las cuotas y predicciones de partidos existentes.
    """
    if not current_app:
        return

    try:
        count = 0
        for p in partidos_predichos:
            if not p.id_partido: continue
            
            existing = db.session.get(Partido, p.id_partido)
            if existing:
                # Extraer cuotas
                cuotas_json = {
                    "1": getattr(p, 'cuota_local', -1), 
                    "X": getattr(p, 'cuota_empate', -1), 
                    "2": getattr(p, 'cuota_visitante', -1),
                    "O25": getattr(p, 'cuota_over', -1), 
                    "U25": getattr(p, 'cuota_under', -1),
                    "BTTS": getattr(p, 'cuota_btts', -1), 
                    "BTTS_NO": getattr(p, 'cuota_btts_no', -1)
                }
                
                # Extraer predicción
                pred_json = getattr(p, 'prediccion', {})
                # Si es string (error legacy), intentar convertir o dejar vacío
                if not isinstance(pred_json, dict):
                    pred_json = {}

                existing.cuotas = cuotas_json
                existing.prediccion = pred_json
                count += 1
        
        db.session.commit()
        logger.info(f"SQL Persistence: Updated {count} predictions.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Error saving predictions to SQL: {e}")
