"""
Script de autenticación de Google Drive (ejecutar UNA SOLA VEZ en local).

Este script abre tu navegador para que inicies sesión con tu cuenta de Google.
Genera un archivo 'token.json' que se usará en el servidor para subir backups.

Uso:
    pip install google-auth-oauthlib google-api-python-client
    python scripts/auth_google.py

Después de ejecutar:
    1. Se creará un archivo 'token.json' en la raíz del proyecto.
    2. Sube ese archivo a PythonAnywhere (~/mysite/token.json).
"""

import os
from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ['https://www.googleapis.com/auth/drive']

def main():
    client_secret_path = os.path.join(os.path.dirname(__file__), '..', 'client_secret.json')
    token_path = os.path.join(os.path.dirname(__file__), '..', 'token.json')

    if not os.path.exists(client_secret_path):
        print("ERROR: No se encontró 'client_secret.json' en la raíz del proyecto.")
        print("Descárgalo desde Google Cloud Console > APIs y servicios > Credenciales > OAuth 2.0")
        return

    flow = InstalledAppFlow.from_client_secrets_file(client_secret_path, SCOPES)
    creds = flow.run_local_server(port=0)

    # Guardar token
    with open(token_path, 'w') as f:
        f.write(creds.to_json())

    print(f"\n✅ Token guardado en: {os.path.abspath(token_path)}")
    print("Ahora sube 'token.json' a PythonAnywhere (~/mysite/token.json)")

if __name__ == '__main__':
    main()
