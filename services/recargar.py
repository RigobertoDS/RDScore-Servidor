#!/home/RigobertoDS/.venv/bin/python3.12

import requests
import logging
import os
from dotenv import load_dotenv

# Configuración del logger
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s -- %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S',
    handlers=[
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# Cargar variables de entorno
# El archivo está en services/, así que el root es BASE_DIR/..
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
env_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(env_path):
    load_dotenv(env_path)
else:
    load_dotenv('/home/RigobertoDS/mysite/.env')

# Recargar el servidor
def recargar_webapp():
    username = os.getenv("PA_USERNAME")
    api_token = os.getenv("PA_API_TOKEN")
    domain_name = "www.rdscore.com"

    if not username or not api_token:
        logger.error("Faltan credenciales PA_USERNAME o PA_API_TOKEN en el .env")
        exit(1)

    response = requests.post(
        'https://www.pythonanywhere.com/api/v0/user/{username}/webapps/{domain_name}/reload/'.format(
            username=username, domain_name=domain_name
        ),
        headers={'Authorization': 'Token {token}'.format(token=api_token)}
    )
    if response.status_code == 200:
        logger.info('Recarga OK')
    else:
        logger.info('Error inesperado {}: {!r}'.format(response.status_code, response.content))
        
if __name__ == "__main__":
    recargar_webapp()
