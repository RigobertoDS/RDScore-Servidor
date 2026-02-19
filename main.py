#!/home/RigobertoDS/.venv/bin/python3.12

import logging
import os
import json
from datetime import date
from config import(
    TEMPORADA_ACTUAL,
    TEMPORADAS,
    ID_LIGAS,
    BASE_DIR
)
from services.data_fetching.obtener_equipos import (
    cargar_equipos,
    obtener_y_guardar_equipos,
    obtener_y_guardar_datos_standings
)
from services.data_fetching.obtener_cuotas import (
    obtener_y_guardar_datos_cuotas,
    obtener_tipo_cuota_rotativo
)
from services.data_fetching.obtener_partidos import (
    obtener_partidos_a_predecir,
    obtener_partidos_jugados,
    obtener_y_guardar_partidos,
    obtener_y_guardar_datos_fixtures
)
from services.ml_v2.entrenar import (
    crear_modelos,
    cargar_partidos_predecidos,
    predecir_lista_partidos,
    obtener_partidos_a_predecir_10
)
from services.recargar import recargar_webapp
from services.analysis.comprobar_precision import analizar_resultados
from services.data_fetching.obtener_historial import obtener_historial
from services.data_fetching.obtener_cuotas_calientes import filtrar_5_mejores_cuotas_calientes
from services.analysis.comprobar_precision_cuotas_calientes import (
    comprobar_precision_cuotas_calientes
)
from services.backup import crear_backup_completo
from app import create_app


# Configuración del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s -- %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()  # salida por consola (lo que ve PythonAnywhere)
    ]
)

logger = logging.getLogger(__name__)


def obtener_datos_api():
    """
    Agrupa toda la lógica de llamadas a la API:
    - Standings
    - Cuotas
    - Fixtures
    """
    # 1. Standings
    logger.info('Obteniendo equipos (standings)...')
    obtener_y_guardar_datos_standings(TEMPORADA_ACTUAL, ID_LIGAS)
    logger.info('Datos standings guardados')

    # 2. Cuotas
    bet, tipo_cuota = obtener_tipo_cuota_rotativo()
    logger.info(f"Obteniendo cuotas tipo: {tipo_cuota} (bet={bet})")
    obtener_y_guardar_datos_cuotas(TEMPORADA_ACTUAL, ID_LIGAS, bet, tipo_cuota)
    logger.info("Datos cuotas guardados")

    # 3. Fixtures
    logger.info('Obteniendo partidos (fixtures)...')
    obtener_y_guardar_datos_fixtures(TEMPORADA_ACTUAL, ID_LIGAS)
    logger.info('Datos fixtures guardados')


def guardar_datos():
    """
    Agrupa toda la lógica de guardado de datos:
    - Equipos
    - Partidos
    """
    # 1. Equipos
    obtener_y_guardar_equipos(TEMPORADAS, ID_LIGAS)
    logger.info('Equipos guardados')

    # 2. Recargamos equipos para comprobar
    equipos = cargar_equipos()
    logger.info('Equipos cargados')

    # 3. Partidos detallados
    obtener_y_guardar_partidos(TEMPORADAS, ID_LIGAS, equipos)
    logger.info('Partidos guardados')


def actualizar_historial():
    """Obtiene y guarda el historial de partidos."""
    logger.info('Obteniendo el historial de partidos...')
    obtener_historial(logger)
    logger.info('Historial guardado.')


def entrenar_modelos():
    """Carga partidos jugados y entrena los modelos base."""
    logger.info('Cargando partidos para entrenar modelos...')
    partidos_entrenar = obtener_partidos_jugados()
    logger.info('Partidos para entrenar modelo cargados.')
    crear_modelos(partidos_entrenar, logger)


def entrenar_meta_modelos():
    """
    V2: Meta-modelos desactivados temporalmente (ver task.md).
    Seguir probando e implementar cuando sea rentable. Hasta entonces no usar.
    """
    pass


def realizar_predicciones():
    """
    Optimiza umbrales y realiza predicciones para los próximos días.
    V2: Carga umbrales pre-calculados (umbrales_v2.json).
    """
    logger.info('Cargando partidos a predecir...')
    partidos_predecir = obtener_partidos_a_predecir()
    logger.info('Partidos a predecir cargados.')

    logger.info('Cargando umbrales optimizados v2...')
    try:
        ruta_umbrales = os.path.join(BASE_DIR, 'datos', 'umbrales_v2.json')
        with open(ruta_umbrales, 'r') as f:
            optimos = json.load(f)
    except FileNotFoundError:
        logger.error(f"EROR CRÍTICO: {ruta_umbrales} no encontrado. Ejecuta optimizar_umbrales.py primero.")
        return


    partidos_10_dias = obtener_partidos_a_predecir_10(partidos_predecir)
    predecir_lista_partidos(partidos_10_dias, optimos)
    logger.info('Predicciones hechas')

    partidos_predecidos = cargar_partidos_predecidos(date.today())
    logger.info('Partidos predecidos cargados')
    logger.info(f'Partidos de los próximos 10 días: {len(partidos_predecidos)}')


def evaluar_modelos_y_roi():
    """Calcula la precisión real de los modelos y el ROI."""
    logger.info('Calculando la precisión de los modelos...')
    analizar_resultados()
    logger.info('Precisión calculada y guardada.')


def procesar_cuotas_calientes():
    """Filtra 'cuotas calientes' y analiza su precisión."""
    logger.info('Obteniendo partidos con cuotas calientes...')
    partidos_analizar = cargar_partidos_predecidos(date.today())
    filtrar_5_mejores_cuotas_calientes(partidos_analizar)
    logger.info('Partidos con cuotas calientes guardados.')

    logger.info('Calculando la precisión de las recomendaciones calientes...')
    comprobar_precision_cuotas_calientes()
    logger.info('Historial y precisión de cuotas calientes guardado.')


def main():
    # Inicializar App de Flask para tener contexto (necesario para SQL)
    app = create_app()

    with app.app_context():
        obtener_datos_api()          # Llamadas a API externa

        guardar_datos()              # Guardado de datos

        actualizar_historial()       # Obtener historial de partidos

        entrenar_modelos()           # Entrenar modelos base

        entrenar_meta_modelos()      # Entrenar meta-modelos

        realizar_predicciones()      # Generar predicciones nuevas

        evaluar_modelos_y_roi()      # Analizar resultados pasados

        procesar_cuotas_calientes()  # Generar y analizar cuotas calientes

        crear_backup_completo()      # Respaldar datos y DB en Google Drive

    # Recargar servidor (fuera del contexto de la app)
    recargar_webapp()


if __name__ == "__main__":
    main()
