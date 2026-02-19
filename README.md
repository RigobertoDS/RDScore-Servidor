# RDScore Servidor ⚽📊

Servidor backend para **RDScore**, una plataforma de análisis y predicción de apuestas deportivas (fútbol). Este proyecto está construido con **Flask** y se encarga de recolectar datos de ligas y partidos, entrenar modelos de Machine Learning (XGBoost, LightGBM) para predecir resultados, gestionar usuarios y servir una API REST para aplicaciones cliente (Android/Web).

## 🚀 Características Principales

* **Autenticación y Gestión de Usuarios**: Sistema de registro e inicio de sesión seguro usando tokens JWT (`flask-jwt-extended`). Incluye recuperación de contraseñas mediante códigos temporales manejados con Redis (`redislite`) y envío de emails.
* **Recolección de Datos Deportivos (ETL)**: Integración con la API externa de fútbol (`api-sports.io`) para descargar automáticamente clasificaciones, partidos (fixtures), equipos y cuotas de las casas de apuestas.
* **Machine Learning (Pipeline v2)**: 
    * Predicción de **Resultado (1X2)**, **Ambos Marcan (BTTS)** y **Más/Menos de 2.5 goles (Over/Under)**.
    * Arquitectura basada en modelos de **XGBoost Regressor** y clasificadores de **LightGBM** calibrados (isotonic).
    * Extracción de más de 50 *features* (histórico H2H, rachas, ratios, etc.).
    * Optimización de umbrales para estrategias de riesgo: *Conservador, Moderado y Agresivo* buscando *Value Bets*.
    * Generación diaria de **"Cuotas Calientes"** con seguimiento de rentabilidad y ROI.
* **API RESTful (`/api/v1/`)**: Endpoints documentados y protegidos para el consumo de ligas, historial de partidos, estadísticas avanzadas de los equipos y métricas de precisión de la plataforma.
* **Bot de Telegram Integrado**: Webhook que permite mediante comandos (`/status`, `/precision_modelos`, `/cuotas_calientes`, etc.) monitorear el servidor y recibir reportes directamente en un chat de administración.
* **Automatización y Backups**: Mediante el script `main.py`, se ejecuta diariamente todo el flujo de trabajo: obtiene datos, reentrena modelos base y meta-modelos, genera predicciones y sube una copia de seguridad (archivos y base de datos MySQL) automáticamente a **Google Drive**.

## 🛠️ Stack Tecnológico

* **Backend**: Python 3.12, Flask, Flask-Cors
* **Base de Datos**: MySQL (vía Flask-SQLAlchemy) y Redis (`redislite`)
* **Machine Learning**: Scikit-Learn, XGBoost, LightGBM, Pandas, Numpy
* **Seguridad**: Flask-Bcrypt, Flask-JWT-Extended
* **Integraciones**: Football API (api-sports), Telegram Bot API, Google Drive API

## 📂 Estructura del Proyecto

```text
└── rigobertods-rdscore-servidor/
    ├── app.py                  # Factory de la aplicación y configuración Flask
    ├── main.py                 # Pipeline diario (ETL, ML, predicciones y backup)
    ├── models.py               # Modelos de SQLAlchemy (Tablas BD)
    ├── config.py               # Variables de entorno y configuración
    ├── clases/                 # Clases nativas de objetos (Equipo, Partido)
    ├── routes/                 # Blueprints de Flask (api_v1, auth, admin, telegram, web)
    ├── scripts/                # Scripts utilitarios (ej. auth_google.py)
    ├── services/               # Lógica principal de negocio:
    │   ├── analysis/           # Comprobación de ROI, precisión y obtención de umbrales
    │   ├── data_fetching/      # Lógica de consumo de API-Sports (cuotas, standings, fixtures)
    │   ├── ml_v2/              # Nuevo Pipeline ML: features, entrenamiento, evaluación y metamodelos
    │   ├── persistence/        # Persistencia en base de datos
    │   └── backup.py           # Subida de dumps a Google Drive
    ├── templates/              # Páginas web renderizadas y plantillas (Privacidad, web)
    └── utils/                  # Respuestas estandarizadas de Error/Success

⚙️ Instalación y Configuración

1. Clonar el repositorio y navegar a la carpeta principal:

    git clone <tu-repositorio>
    cd rigobertods-rdscore-servidor

2. Crear y activar un entorno virtual:

    python3.12 -m venv .venv
    source .venv/bin/activate  # En Linux/Mac
    # .venv\Scripts\activate   # En Windows

3. Instalar dependencias:

    pip install -r requirements.txt

4. Variables de Entorno:

    Asegúrate de configurar las credenciales necesarias en el archivo .env o en tu entorno de despliegue.
    
    Ejemplos de variables requeridas:

    - SQLALCHEMY_DATABASE_URI (Conexión a MySQL)

    - JWT_SECRET_KEY (Clave para firmar tokens)

    - ADMIN_KEY (Clave estática para las rutas de administración)

    - API_KEY (Tu API Key de api-sports.io)

    - MAIL_USERNAME / MAIL_PASSWORD (Credenciales SMTP para recuperación de cuentas)

    - TG_TOKEN / TG_CHAT_ID (Para notificaciones de Telegram)

5. Autenticación en Google Drive (Para Backups):

    Si vas a utilizar los backups automáticos, en un entorno local ejecuta:
    
    python scripts/auth_google.py
    
    Sigue los pasos en el navegador y luego sube el archivo generado (token.json) a tu servidor en producción.

▶️ Uso

1. Iniciar la API REST (Servidor Web):

    Para levantar el backend (en desarrollo):
    
    python app.py
    
    (El servidor se ejecutará en http://127.0.0.1:5000)

2. Ejecutar el Pipeline Principal (Tareas Programadas):

    El archivo main.py está diseñado para ejecutarse como un cronjob diario.
    Se encargará de descargar las nuevas cuotas, reentrenar modelos si hay nuevos partidos terminados, predecir los siguientes días y respaldar la BD.
    
    python main.py
    
📜 Licencia / Legal

Todos los términos de uso y privacidad se rigen según lo expuesto en el portal web (ruta /privacidad).