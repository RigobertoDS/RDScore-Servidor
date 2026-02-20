<p align="center">
  <img src="static/logo_servidor.webp" width="120" alt="RDScore Backend Logo"/>
</p>

<h1 align="center">⚽ RDScore Servidor</h1>

<p align="center">
  <b>Cerebro de Predicciones y API REST para RDScore</b><br/>
  <i>Machine Learning, ETL y Gestión de Datos en Tiempo Real</i>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-3776AB?logo=python&logoColor=white" alt="Python"/>
  <img src="https://img.shields.io/badge/Framework-Flask-000000?logo=flask&logoColor=white" alt="Flask"/>
  <img src="https://img.shields.io/badge/ML-XGBoost%20%7C%20LightGBM-ff69b4" alt="ML Stack"/>
  <img src="https://img.shields.io/badge/DB-MySQL%20%26%20Redis-4479A1?logo=mysql&logoColor=white" alt="Database"/>
</p>

---

## � Acerca de

El **Servidor RDScore** es el núcleo de procesamiento de la plataforma. Se encarga de todo el ciclo de vida de los datos: desde la recolección (ETL) y el entrenamiento de modelos de Inteligencia Artificial, hasta la exposición de una API REST protegida para la aplicación Android.

Este backend automatiza la generación diaria de predicciones de alto valor basándose en algoritmos avanzados de regresión y clasificación, calibrados específicamente para el mercado de apuestas deportivas.

---

## ✨ Características Principales

### 🧠 Pipeline de Machine Learning (v2)
- **Modelos Avanzados**: Implementación de **XGBoost Regressor** y clasificadores **LightGBM** con calibración isotónica.
- **Predicción Multi-mercado**:
  - 🏆 Ganador (1X2)
  - ⚽ Ambos Marcan (BTTS)
  - 📊 Más/Menos de 2.5 Goles
- **Ingeniería de Features**: Procesamiento de más de 50 variables dinámicas (H2H, rachas, ratios de goles, etc.).
- **Optimización de Value Bets**: Cálculo automático de umbrales para estrategias *Conservadora, Moderada y Agresiva*.

### 🔄 Automatización y ETL
- **Recolección Automática**: Integración con API-Sports para obtener fixtures, resultados, standings y cuotas en tiempo real.
- **Workflow Diario**: El script `main.py` gestiona el reentrenamiento, la predicción de nuevas jornadas y el cálculo de ROI de forma autónoma.
- **Backups Inteligentes**: Generación de dumps de base de datos y archivos críticos con subida automática a **Google Drive**.

### 🔐 Seguridad y Usuarios
- **Autenticación JWT**: Gestión de sesiones segura mediante tokens de acceso y refresco.
- **Recuperación de Cuentas**: Sistema de códigos temporales con **Redis** y envío de correos electrónicos vía SMTP.
- **Cifrado**: Almacenamiento seguro de contraseñas mediante **Bcrypt**.

### 🤖 Monitorización (Telegram Bot)
- **Webhook Integrado**: Control remoto del servidor mediante comandos de Telegram.
- **Reportes en Vivo**: Consulta de estados, precisión de modelos y alertas de cuotas calientes directamente desde el móvil.

---

## 🏗️ Stack Tecnológico

| Capa | Tecnología |
|---|---|
| **Lenguaje** | Python 3.12 |
| **Framework Web** | Flask + Flask-Cors |
| **ML Libraries** | Scikit-Learn, XGBoost, LightGBM, Pandas, Numpy |
| **Base de Datos** | MySQL (Flask-SQLAlchemy) + Redis (Redislite) |
| **Seguridad** | Flask-JWT-Extended + Flask-Bcrypt |
| **Integraciones** | Google Drive API, Telegram Bot API, API-Sports |

---

## � Estructura del Proyecto

```text
├── app.py                  # Punto de entrada y configuración de Flask
├── main.py                 # Orquestador del pipeline diario (ETL + ML)
├── models.py               # Definición de tablas y modelos de base de datos
├── routes/                 # Blueprints: API v1, Auth, Admin, Telegram
├── services/               # El "corazón" del backend:
│   ├── ml_v2/              # Lógica de entrenamiento y meta-modelos
│   ├── data_fetching/      # Consumo de APIs externas e ingesta de datos
│   ├── analysis/           # Cálculos de ROI, precisión y umbrales
│   └── backup.py           # Gestión de copias de seguridad en la nube
├── classes/                # Clases nativas y modelos de negocio
├── scripts/                # Utilidades de mantenimiento y auth de Google
├── templates/              # Páginas web estáticas (Privacidad, landing)
└── utils/                  # Formateo de respuestas y manejo de errores
```

---

## 🚀 Instalación y Uso

### Configuración del Entorno
1. Clonar y preparar entorno:
   ```bash
   git clone https://github.com/RigobertoDS/RDScore-Servidor.git
   cd RDScore-Servidor
   python -m venv .venv
   source .venv/bin/activate  # .venv\Scripts\activate en Windows
   pip install -r requirements.txt
   ```

2. Configurar el archivo `.env` con las claves necesarias (DB, API Keys de Fútbol, JWT Secret, etc.).

### Ejecución
- **Para desarrollo (API):** `python app.py`
- **Para el pipeline diario:** `python main.py`

---

## 📄 Licencia

Este proyecto es propiedad de RigobertoDS. Todos los derechos reservados.  
Los términos de privacidad se detallan en la sección correspondiente de la API.

---

<p align="center">
  <b>Desarrollado con 🦾 por <a href="https://github.com/RigobertoDS">RigobertoDS</a></b>
</p>