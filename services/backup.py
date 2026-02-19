
import os
import shutil
import logging
import datetime
import subprocess
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from config import DB_USER, DB_PASS, DB_HOST, DB_NAME, BASE_DIR

logger = logging.getLogger(__name__)

# Directorios a respaldar (nombres relativos al proyecto)
DIRS_TO_BACKUP = [
    'datos',
    'modelos_v2',
    'meta_modelos_v2',
    'ligas'
]

def get_drive_service():
    """Autentica con OAuth2 (token personal del usuario) y devuelve el servicio de Drive."""
    token_path = os.getenv('GOOGLE_DRIVE_TOKEN_PATH')
    if not token_path or not os.path.exists(token_path):
        logger.error(f"No se encontró el token de OAuth en: {token_path}")
        return None
    
    try:
        creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/drive'])
        
        # Refrescar token si ha expirado
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
            # Guardar el token actualizado
            with open(token_path, 'w') as f:
                f.write(creds.to_json())
            logger.info("Token de OAuth refrescado correctamente.")
        
        return build('drive', 'v3', credentials=creds)
    except Exception as e:
        logger.error(f"Error al autenticar con Google Drive: {e}")
        return None

def subir_a_google_drive(file_path, folder_id, service):
    """Sube un archivo a una carpeta específica de Google Drive."""
    try:
        file_metadata = {
            'name': os.path.basename(file_path),
            'parents': [folder_id]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        logger.info(f"Archivo subido a Drive: {os.path.basename(file_path)} (ID: {file.get('id')})")
        return True
    except Exception as e:
        logger.error(f"Error al subir {file_path} a Drive: {e}")
        return False

def crear_backup_datos():
    """Comprime las carpetas de datos en un ZIP."""
    fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
    zip_filename = f"server_{fecha_hoy}.zip"
    
    logger.info(f"Creando backup de datos: {zip_filename}...")
    
    # Crear un directorio temporal para agrupar lo que vamos a comprimir
    temp_dir = os.path.join(BASE_DIR, "temp_backup_data")
    if os.path.exists(temp_dir):
        shutil.rmtree(temp_dir)
    os.makedirs(temp_dir)
    
    try:
        # Copiar carpetas al directorio temporal
        for folder in DIRS_TO_BACKUP:
            folder_path = os.path.join(BASE_DIR, folder)
            if os.path.exists(folder_path):
                shutil.copytree(folder_path, os.path.join(temp_dir, folder))
        
        # Comprimir
        zip_path = os.path.join(BASE_DIR, zip_filename.replace('.zip', ''))
        shutil.make_archive(zip_path, 'zip', temp_dir)
        full_zip = zip_path + '.zip'
        logger.info("Backup de datos comprimido correctamente.")
        return full_zip
    except Exception as e:
        logger.error(f"Error al comprimir datos: {e}")
        return None
    finally:
        # Limpiar directorio temporal
        if os.path.exists(temp_dir):
            shutil.rmtree(temp_dir)

def crear_backup_db():
    """Realiza un dump de la base de datos MySQL."""
    fecha_hoy = datetime.date.today().strftime("%Y-%m-%d")
    dump_filename = os.path.join(BASE_DIR, f"db_{fecha_hoy}.sql.gz")
    
    logger.info(f"Creando dump de base de datos: {dump_filename}...")
    
    # Nota: mysqldump -h host -u user -p password 'dbname' | gzip > file
    command = f"mysqldump -h {DB_HOST} -u {DB_USER} --password='{DB_PASS}' '{DB_NAME}' | gzip > {dump_filename}"
    
    try:
        process = subprocess.run(command, shell=True, check=True, stderr=subprocess.PIPE)
        logger.info("Dump de base de datos creado correctamente.")
        return dump_filename
    except subprocess.CalledProcessError as e:
        logger.error(f"Error al ejecutar mysqldump: {e.stderr.decode()}")
        return None
    except Exception as e:
        logger.error(f"Error desconocido al crear dump DB: {e}")
        return None

def crear_backup_completo():
    """Orquesta todo el proceso de backup."""
    logger.info("--- INICIANDO PROCESO DE BACKUP ---")
    
    service = get_drive_service()
    if not service:
        logger.error("No se pudo iniciar el servicio de Drive. Cancelando backup.")
        return

    # 1. Backup de Datos (Server)
    server_zip = crear_backup_datos()
    if server_zip:
        folder_id = os.getenv('GDRIVE_FOLDER_ID_SERVER')
        if folder_id:
            if subir_a_google_drive(server_zip, folder_id, service):
                os.remove(server_zip)
                logger.info(f"Archivo local {server_zip} eliminado.")
        else:
             logger.error("GDRIVE_FOLDER_ID_SERVER no definido en .env")

    # 2. Backup de Base de Datos
    db_dump = crear_backup_db()
    if db_dump:
        folder_id = os.getenv('GDRIVE_FOLDER_ID_DB')
        if folder_id:
            if subir_a_google_drive(db_dump, folder_id, service):
                os.remove(db_dump)
                logger.info(f"Archivo local {db_dump} eliminado.")
        else:
             logger.error("GDRIVE_FOLDER_ID_DB no definido en .env")
             
    logger.info("--- PROCESO DE BACKUP FINALIZADO ---")
