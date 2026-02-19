import os
import pickle
from clases.equipo import Equipo
from services.common.herramientas import solicitud_HTTP
from config import BASE_DIR


# Obtener datos de la API
def obtener_datos_standings(id_liga, temporada):
    url = 'https://v3.football.api-sports.io/standings?' + \
        'season=' + str(temporada) + '&league=' + str(id_liga)
    datos = solicitud_HTTP(url)
    return datos


# Guardar datos en un archivo
def guardar_datos_standings(id_liga, temporada, datos):
    # Crear la ruta del archivo
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'equipos', 'datos_standings.pkl')
    # Verificar si la carpeta padre existe, si no, crearla
    carpeta_padre = os.path.dirname(ruta)
    if not os.path.exists(carpeta_padre):
        os.makedirs(carpeta_padre)
    # Guardar los datos en el archivo
    with open(ruta, 'wb') as f:
        pickle.dump(datos, f)


# Cargar datos de un archivo
def cargar_datos_standings(id_liga, temporada):
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'equipos', 'datos_standings.pkl')
    with open(ruta, 'rb') as f:
        datos = pickle.load(f)
    return datos


# Hacer las solicitudes y guardar los datos standings
def obtener_y_guardar_datos_standings(temporada, id_ligas):
    for id in id_ligas:
        datos_standings = obtener_datos_standings(id, temporada)
        guardar_datos_standings(id, temporada, datos_standings)


# Obtener los datos de la liga para el equipo
def obtener_datos_liga(datos_standings):
    try:
        json_data = datos_standings.get('response', [])[0].get('league', {})
        liga = {
            'id': json_data.get('id', None),
            'nombre': json_data.get('name', None),
            'pais': json_data.get('country', None),
            'bandera': json_data.get('flag', None),
            'logo': json_data.get('logo', None),
            'equipos': json_data.get('standings', [])[0]
        }
        return liga
    except KeyError as e:
        print(f"Error: Key {e} does not exist in the dictionary")
        return None


# Obtener los datos de un equipo
def obtener_datos_equipos(datos_liga, temporada):
    equipos = []

    lista_equipos = datos_liga.get("equipos", [])

    for e in lista_equipos:

        # Seguridad total en TODAS las lecturas (evita NoneType)
        team = e.get("team", {}) or {}
        all_data = e.get("all", {}) or {}
        home = e.get("home", {}) or {}
        away = e.get("away", {}) or {}

        id = team.get("id", 0)
        nombre = team.get("name", "")
        logo = team.get("logo", "")

        posicion = e.get("rank", 0)
        puntos = e.get("points", 0)
        forma = e.get("form", "")

        PT = all_data.get("played", 0)
        VT = all_data.get("win", 0)
        ET = all_data.get("draw", 0)
        DT = all_data.get("lose", 0)

        PC = home.get("played", 0)
        VC = home.get("win", 0)
        EC = home.get("draw", 0)
        DC = home.get("lose", 0)

        PF = away.get("played", 0)
        VF = away.get("win", 0)
        EF = away.get("draw", 0)
        DF = away.get("lose", 0)

        goles_favor = all_data.get("goals", {}).get("for", 0)
        goles_contra = all_data.get("goals", {}).get("against", 0)

        goles_favor_casa = home.get("goals", {}).get("for", 0)
        goles_contra_casa = home.get("goals", {}).get("against", 0)

        goles_favor_fuera = away.get("goals", {}).get("for", 0)
        goles_contra_fuera = away.get("goals", {}).get("against", 0)

        id_liga = datos_liga.get("id", 0)
        nombre_liga = datos_liga.get("nombre", "")
        pais = datos_liga.get("pais", "")
        bandera = datos_liga.get("bandera", "")
        logo_liga = datos_liga.get("logo", "")

        equipo = Equipo(id, nombre, logo, posicion, puntos, forma,
                        PT, VT, ET, DT, PC, VC, EC, DC,
                        PF, VF, EF, DF,
                        temporada,
                        goles_favor, goles_contra,
                        goles_favor_casa, goles_contra_casa,
                        goles_favor_fuera, goles_contra_fuera,
                        id_liga, nombre_liga, pais, bandera, logo_liga)

        equipos.append(equipo)

    return equipos


# Guardar los equipos
def guardar_equipos(equipos):
    # Crear la ruta del archivo
    ruta = os.path.join(BASE_DIR, 'datos', 'equipos.pkl')
    # Verificar si la carpeta padre existe, si no, crearla
    carpeta_padre = os.path.dirname(ruta)
    if not os.path.exists(carpeta_padre):
        os.makedirs(carpeta_padre)
    # Guardar los datos en el archivo
    with open(ruta, 'wb') as f:
        pickle.dump(equipos, f)
    
    # 2. Guardar también en SQL (Dual Write)
    try:
        from services.persistence.db_persistence import (
            guardar_ligas_en_bd, 
            guardar_equipos_en_bd
        )
        guardar_ligas_en_bd(equipos)
        guardar_equipos_en_bd(equipos)
    except Exception as e:
        print(f"Warning: Could not save teams to SQL: {e}")


# Cargar los equipos
def cargar_equipos():
    ruta = os.path.join(BASE_DIR, 'datos', 'equipos.pkl')
    if not os.path.exists(ruta):
        return []
    with open(ruta, "rb") as f:
        return pickle.load(f)


# Obtener los equipos
def obtener_y_guardar_equipos(temporadas, id_ligas):
    equipos = []

    for temporada in temporadas:
        for id_liga in id_ligas:
            datos_standings = cargar_datos_standings(id_liga, temporada)
            datos_liga = obtener_datos_liga(datos_standings)
            equipos_liga = obtener_datos_equipos(datos_liga, temporada)
            equipos.extend(equipos_liga)

    guardar_equipos(equipos)

    return equipos
