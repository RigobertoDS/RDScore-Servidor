import os
import pickle
from services.common.herramientas import solicitud_HTTP
from datetime import date
from config import BASE_DIR


# Obtener los datos de la API para una página concreta
def obtener_datos_cuotas(id_liga, temporada, bet, page):
    url = (
        f"https://v3.football.api-sports.io/odds?season={temporada}"
        f"&league={id_liga}&timezone=Europe/Madrid&bookmaker=8"
        f"&bet={bet}&page={page}"
    )
    return solicitud_HTTP(url)


# Guardar archivo de cuotas unificado (todas las páginas)
def guardar_datos_cuotas_unificado(id_liga, temporada, datos_unificados, tipo_cuota):
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'cuotas', f'{tipo_cuota}.pkl')
    carpeta_padre = os.path.dirname(ruta)
    if not os.path.exists(carpeta_padre):
        os.makedirs(carpeta_padre)

    with open(ruta, "wb") as f:
        pickle.dump(datos_unificados, f)


# Cargar archivo unificado
def cargar_datos_cuotas(id_liga, temporada, tipo_cuota):
    ruta = os.path.join(BASE_DIR, 'ligas', str(id_liga), f'temporada{temporada}-{temporada+1}', 'cuotas', f'{tipo_cuota}.pkl')
    with open(ruta, "rb") as f:
        return pickle.load(f)


# Obtener y guardar todas las páginas unificadas
def obtener_y_guardar_datos_cuotas(temporada, id_ligas, bet, tipo_cuota):

    for id_liga in id_ligas:

        # Página 1
        datos_pag1 = obtener_datos_cuotas(id_liga, temporada, bet, page=1)
        if not datos_pag1:
            print(f"Error obteniendo pag 1 cuotas para liga {id_liga}")
            continue

        total_pages = datos_pag1.get("paging", {}).get("total", 1)
        paginas_a_descargar = min(3, total_pages)

        # ---- Crear estructura unificada ----
        datos_unificados = {
            "get": datos_pag1.get("get"),
            "parameters": datos_pag1.get("parameters"),
            "errors": [],
            "results": datos_pag1.get("results", 0),
            "paging": {"total": paginas_a_descargar},
            "response": datos_pag1.get("response", [])
        }

        # Páginas 2 y 3
        for pagina in range(2, paginas_a_descargar + 1):
            datos_pag = obtener_datos_cuotas(id_liga, temporada, bet, page=pagina)
            if datos_pag:
                datos_unificados["response"].extend(datos_pag.get("response", []))
                datos_unificados["results"] += datos_pag.get("results", 0)
            else:
                print(f"Error obteniendo pag {pagina} liga {id_liga}")

        # Guardar archivo unificado
        guardar_datos_cuotas_unificado(id_liga, temporada, datos_unificados, tipo_cuota)


# Buscar la cuota deseada
def obtener_cuota(cuota_buscada, cuotas):
    for c in cuotas:
        if c.get("value") == cuota_buscada:
            return c.get("odd")
    return -1


# Rotación diaria entre resultado – over – btts
def obtener_tipo_cuota_rotativo():
    dia = date.today().timetuple().tm_yday
    rot = dia % 3

    if rot == 0:
        return 1, "datos_cuotas_resultado"
    elif rot == 1:
        return 5, "datos_cuotas_over"
    else:
        return 8, "datos_cuotas_btts"
