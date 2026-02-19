import json
import requests
import time
from config import API_KEY, TG_TOKEN, TG_CHAT_ID


# Método para hacer la solicitud http
def solicitud_HTTP(url):

    # Encabezados de la solicitud
    headers = {
        'x-apisports-key': API_KEY,
    }

    # Realizar la solicitud GET a la API con encabezados personalizados
    response = requests.get(url, headers=headers)

    # Verificar si la solicitud fue exitosa (código de estado 200)
    if response.status_code == 200:
        # Convertir la respuesta a formato JSON (si tu API devuelve JSON)
        data = response.json()
        # Pausa de 6 segundos
        time.sleep(6)
        return data
    else:
        print(
            f'Error en la solicitud. Código de estado: {response.status_code}'
            )


# Método imprimir limpio
def imprimir(json_data):
    indent = 4  # Número de espacios para la indentación
    print(json.dumps(json_data, indent=indent))


# Método para verificar si hay valores nulos
def verificar_valores_nulos(instancias):
    # Convertir objetos en array tipo diccionario
    array_valido = []
    for instancia in instancias:
        array_valido.append(instancia.to_dict())

    # Verificar si hay valores nulos
    for objeto in array_valido:
        if any(value is None for value in objeto.values()):
            return True
    return False


# Método para mandar un mensaje por Telegram
def enviar_telegram(mensaje: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    r = requests.post(url, data=payload, timeout=5)
    return r.ok, r.text
