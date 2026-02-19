from datetime import datetime
import os
import pickle
from clases.equipo import Equipo
from clases.partido import Partido
from services.common.herramientas import solicitud_HTTP
from services.data_fetching.obtener_cuotas import cargar_datos_cuotas, obtener_cuota
from config import TEMPORADA_ACTUAL, BASE_DIR


# Obtener los datos de la API
def obtener_datos_fixtures(id, temporada):
    url = 'https://v3.football.api-sports.io/fixtures?season=' + \
        str(temporada) + '&league=' + str(id) + '&timezone=Europe/Madrid'
    datos = solicitud_HTTP(url)
    return datos


# Guardar datos en un archivo
def guardar_datos_fixtures(id_liga, temporada, datos):
    # Crear la ruta del archivo
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'partidos', 'datos_fixtures.pkl')
    # Verificar si la carpeta padre existe, si no, crearla
    carpeta_padre = os.path.dirname(ruta)
    if not os.path.exists(carpeta_padre):
        os.makedirs(carpeta_padre)
    # Guardar los datos en el archivo
    with open(ruta, 'wb') as f:
        pickle.dump(datos, f)


# Cargar datos de un archivo
def cargar_datos_fixtures(id_liga, temporada):
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'partidos', 'datos_fixtures.pkl')
    with open(ruta, 'rb') as f:
        datos = pickle.load(f)
    return datos


# Hacer las solicitudes y guardar los datos fixtures
def obtener_y_guardar_datos_fixtures(temporada, id_ligas):
    for id in id_ligas:
        datos_fixtures = obtener_datos_fixtures(id, temporada)
        guardar_datos_fixtures(id, temporada, datos_fixtures)


# Buscar un equipo en la lista
def buscar_equipo(temporada, equipos, id_equipo, id_liga_partido):
    for equipo in equipos:
        # Añade la comprobación del ID de la liga del equipo
        if equipo.id == id_equipo and equipo.temporada == temporada and equipo.id_liga == id_liga_partido:
            return equipo

    # Si no encuentra nada, devuelve el equipo por defecto
    return Equipo(
        0, "Equipo no encontrado", "Logo no encontrado", 0,
        0, "", 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, temporada, 0, 0, 0,
        0, 0, 0, 0, "Liga desconocida", "País desconocido",
        "Bandera desconocida", "Logo desconocido"
    )


# Separar la fecha y la hora
def separar_fecha_hora(fecha_hora):
    if not fecha_hora:
        return "01/01/1970", "00:00"

    try:
        fecha_hora_obj = datetime.strptime(fecha_hora, "%Y-%m-%dT%H:%M:%S%z")
    except Exception:
        try:
            fecha_hora_obj = datetime.strptime(fecha_hora, "%Y-%m-%dT%H:%M:%S")
        except Exception:
            return "01/01/1970", "00:00"

    return fecha_hora_obj.strftime("%d/%m/%Y"), \
        fecha_hora_obj.strftime("%H:%M")


# Obtener los datos de un partido
def obtener_datos_partidos(datos_fixtures, temporada, equipos):
    json_data = datos_fixtures.get("response", [])
    partidos = []

    for p in json_data:
        fx = p.get("fixture", {})
        lg = p.get("league", {})
        tm = p.get("teams", {})
        sc = p.get("score", {})
        full = sc.get("fulltime", {})

        id_partido = fx.get("id", -1)
        id_liga = lg.get("id", -1)
        jornada = lg.get("round", "Jornada desconocida")

        # Equipos
        id_local = tm.get("home", {}).get("id", -1)
        id_visitante = tm.get("away", {}).get("id", -1)
        equipo_local = buscar_equipo(temporada, equipos, id_local, id_liga)
        equipo_visitante = buscar_equipo(temporada, equipos, id_visitante, id_liga)

        # Fecha/hora
        fecha, hora = separar_fecha_hora(fx.get("date"))

        # Venue
        venue = fx.get("venue", {})
        ciudad = venue.get("city", "Ciudad desconocida")
        estadio = venue.get("name", "Estadio desconocido")
        arbitro = fx.get("referee") or "Árbitro no disponible"

        # Status
        estado = fx.get("status", {}).get("short", "Estado desconocido")

        # Marcadores seguros
        goles_local = full.get("home", -1)
        goles_visitante = full.get("away", -1)

        # Cuotas resultado
        cuota_local = cuota_empate = cuota_visitante = -1

        if temporada == TEMPORADA_ACTUAL:
            try:
                datos_cuotas_resultado = cargar_datos_cuotas(
                    id_liga, temporada, 'datos_cuotas_resultado')
                for fx_cuota in datos_cuotas_resultado.get("response", []):
                    if fx_cuota.get("fixture", {}).get("id") == id_partido:
                        bets = fx_cuota.get("bookmakers", [])[0].\
                            get("bets", [])[0].get("values", [])
                        cuota_local = obtener_cuota("Home", bets) or -1
                        cuota_empate = obtener_cuota("Draw", bets) or -1
                        cuota_visitante = obtener_cuota("Away", bets) or -1
            except Exception as e:
                print(f"Error loading result odds for league {id_liga}: {e}")

        # Cuotas over/under
        cuota_over = cuota_under = -1

        if temporada == TEMPORADA_ACTUAL:
            try:
                datos_cuotas_over = cargar_datos_cuotas(
                    id_liga, temporada, 'datos_cuotas_over')
                for fx_cuota in datos_cuotas_over.get("response", []):
                    if fx_cuota.get("fixture", {}).get("id") == id_partido:
                        bets = fx_cuota.get("bookmakers", [])[0].\
                            get("bets", [])[0].get("values", [])
                        cuota_over = obtener_cuota("Over 2.5", bets) or -1
                        cuota_under = obtener_cuota("Under 2.5", bets) or -1
            except Exception as e:
                print(f"Error loading over/under odds for league {id_liga}: {e}")

        # Cuotas btts/btts no
        cuota_btts = cuota_btts_no = -1

        if temporada == TEMPORADA_ACTUAL:
            try:
                datos_cuotas_btts = cargar_datos_cuotas(
                    id_liga, temporada, 'datos_cuotas_btts')
                for fx_cuota in datos_cuotas_btts.get("response", []):
                    if fx_cuota.get("fixture", {}).get("id") == id_partido:
                        bets = fx_cuota.get("bookmakers", [])[0].\
                            get("bets", [])[0].get("values", [])
                        cuota_btts = obtener_cuota("Yes", bets) or -1
                        cuota_btts_no = obtener_cuota("No", bets) or -1
            except Exception as e:
                print(f"Error loading btts odds for league {id_liga}: {e}")

        # Crear el objeto Partido
        partido = Partido(
            id_partido, estado, id_liga, temporada, jornada,
            equipo_local, equipo_visitante,
            fecha, hora, ciudad, estadio, arbitro,
            cuota_local, cuota_empate, cuota_visitante,
            cuota_over, cuota_under, cuota_btts, cuota_btts_no,
            goles_local, goles_visitante
        )

        partidos.append(partido)

    return partidos


# Guardar los partidos
def guardar_partidos(partidos):
    ruta = os.path.join(BASE_DIR, 'datos', 'partidos.pkl')
    with open(ruta, "wb") as f:
        pickle.dump(partidos, f)
        
    # 2. Guardar también en SQL (Dual Write)
    # 2. Guardar también en SQL (Dual Write)
    try:
        from services.persistence.db_persistence import guardar_partidos_en_bd
        guardar_partidos_en_bd(partidos)
    except Exception as e:
        print(f"Warning: Could not save matches to SQL: {e}")


# Cargar los partidos
def cargar_partidos():
    ruta = os.path.join(BASE_DIR, 'datos', 'partidos.pkl')
    if not os.path.exists(ruta):
        return []
    with open(ruta, "rb") as f:
        return pickle.load(f)


# Obtener todos los partidos
def obtener_y_guardar_partidos(temporadas, id_ligas, equipos):
    partidos = []

    for temporada in temporadas:
        for id_liga in id_ligas:
            datos_fixtures = cargar_datos_fixtures(id_liga, temporada)
            partidos.extend(
                obtener_datos_partidos(datos_fixtures, temporada, equipos))

    guardar_partidos(partidos)
    return partidos


# Obtener los partidos jugados
def obtener_partidos_jugados():
    partidos = cargar_partidos()
    # Filtrar
    partidos = [p for p in partidos if p.estado == "FT"]
    return partidos


# Obtener los partidos a predecir
def obtener_partidos_a_predecir():
    partidos = cargar_partidos()
    partidos = [p for p in partidos if p.estado == "NS"]
    return partidos
