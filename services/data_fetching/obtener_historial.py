import pickle
import os
from services.data_fetching.obtener_partidos import obtener_partidos_jugados
from datetime import date, timedelta, datetime
from config import BASE_DIR

def cargar_partidos_predecidos_string(fecha):
    import os
    # Crear la ruta del archivo
    ruta = os.path.join(BASE_DIR, 'datos', 'archivo', f'{fecha}__partidos_predecidos.pkl')
    # Guardar los datos en el archivo
    if not os.path.exists(ruta):
        return []
        
    with open(ruta, 'rb') as f:
        partidos = pickle.load(f)
    return partidos

def cargar_partidos_jugados_de_un_dia(fecha_str):
    partidos = obtener_partidos_jugados()
    return [p for p in partidos if p.fecha == fecha_str]


PRIMER_DIA = "2025-12-03"  # Primer día con datos limpios


################################################################
# Guardar el historial
def guardar_historial(historial):
    ruta = os.path.join(BASE_DIR, 'datos', 'historial.pkl')
    with open(ruta, "wb") as f:
        pickle.dump(historial, f)


# Cargar el historial
def cargar_historial():
    ruta = os.path.join(BASE_DIR, 'datos', 'historial.pkl')
    if not os.path.exists(ruta):
        return []
    with open(ruta, "rb") as f:
        return pickle.load(f)


# Cargar el historial filtrado por fecha (formato: YYYY-MM-DD)
def cargar_historial_por_fecha(fecha_str):
    """Devuelve solo los partidos del día especificado.
    
    Args:
        fecha_str: Fecha en formato 'YYYY-MM-DD' (ej: '2025-01-30')
    
    Returns:
        Lista de partidos del día, o lista vacía si no hay.
    """
    historial = cargar_historial()
    
    # Convertir de YYYY-MM-DD a DD/MM/YYYY (formato interno)
    try:
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d")
        fecha_interna = fecha_obj.strftime("%d/%m/%Y")
    except ValueError:
        return []  # Formato inválido
    
    return [p for p in historial if p.fecha == fecha_interna]



# Otener los partidos jugados por fecha
def get_partidos_admin(fecha):
    # Llama a tu función para cargar partidos pasándole una fecha específica
    partidos = cargar_partidos_jugados_de_un_dia(fecha)

    # Devolver los partidos
    return partidos


# Obtener los partidos predichos por fecha
def get_precision_admin(fecha):
    # Parsear el string original
    fecha_obj = datetime.strptime(fecha, "%Y_%m_%d")

    # Formatearlo al nuevo formato
    nueva_fecha_str = fecha_obj.strftime("%d/%m/%Y")

    # Obtener los partidos del dia (contiene desde ese día a 10 días en adelante)
    partidos = cargar_partidos_predecidos_string(fecha)

    # Obtener los partidos del día elegido solamente
    partidos_dia = [p for p in partidos if p.fecha == nueva_fecha_str]

    # Devolver los partidos
    return partidos_dia


# Comprobar partidos de un día
def asignar_predicciones(p_jugados, p_predichos):
    # Iniciar partidos para almacenar
    partidos = []

    # Recorrer los partidos jugados
    for p in p_jugados:
        # Obtener el ID del partido
        id_buscado = p.id_partido

        # Recorrer los partidos predecidos y buscar el ID
        for pp in p_predichos:
            # Si el ID coincide - partido predecido
            if pp.id_partido == id_buscado:
                p.prediccion = pp.prediccion
                partidos.append(p)

    # Devolver los partidos pasados con prediccion
    return partidos


# Obtener resultados
def obtener_historial(logger):
    # Cargar el historial existente
    historial = cargar_historial()

    # Obtener fecha del día anterior (ayer)
    fecha = date.today() - timedelta(days=1)
    fecha_str = fecha.strftime("%d/%m/%Y")  # Para partidos jugados
    fecha_archivo = fecha.strftime("%Y_%m_%d")  # Para predicciones

    # Cargar partidos jugados y predichos del día anterior
    p_jugados = get_partidos_admin(fecha_str)
    p_predichos = get_precision_admin(fecha_archivo)

    # Asignar predicciones a partidos jugados
    predicciones_dia = asignar_predicciones(p_jugados, p_predichos)

    # Verificar que la fecha NO existe ya en el historial
    fechas_existentes = {p.fecha for p in historial}
    if fecha_str not in fechas_existentes:
        # Agregar los partidos al historial
        historial.extend(predicciones_dia)

        # Guardar historial
        guardar_historial(historial)
        logger.info(f"Añadidos {len(predicciones_dia)} partidos del {fecha_str}")
    else:
        logger.info(f"Día {fecha_str} ya existe en historial (saltado)")


# Crear historial por si necesito hacerlo nuevo
def crear_historial_nuevo():
    fecha_actual = date.today()
    fecha_inicio = date.fromisoformat(PRIMER_DIA)
    fecha_fin = fecha_actual - timedelta(days=1)

    historial = []
    while fecha_inicio <= fecha_fin:
        p_jugados = get_partidos_admin(fecha_inicio.strftime("%d/%m/%Y"))
        p_predichos = get_precision_admin(fecha_inicio.strftime("%Y_%m_%d"))

        # Obtener los resultados del día
        predicciones_dia = asignar_predicciones(p_jugados, p_predichos)

        # Ir agregando las predicciones del día
        historial.extend(predicciones_dia)

        # Incrementar fecha
        fecha_inicio += timedelta(days=1)

    # Guardar historial
    guardar_historial(historial)
