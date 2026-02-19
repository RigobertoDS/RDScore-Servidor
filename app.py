from flask import Flask
from flask_cors import CORS
from extensions import db, bcrypt, jwt, mail
from config import (
    SQLALCHEMY_DATABASE_URI,
    JWT_SECRET_KEY,
    JWT_ACCESS_TOKEN_EXPIRES,
    JWT_REFRESH_TOKEN_EXPIRES,
    JWT_RESET_PASSWORD_TOKEN_EXPIRES,
    MAIL_USERNAME,
    MAIL_PASSWORD
)

# Importar Blueprints
from routes.auth import auth_bp
from routes.api_v1 import api_v1_bp
from routes.admin import admin_bp
from routes.telegram import telegram_bp
from routes.web import web_bp

def create_app():
    app = Flask(__name__)

    # Restringir CORS a producción
    CORS(app, resources={r"/*": {"origins": ["https://www.rdscore.com"]}}, supports_credentials=True)

    # Configuración de la Base de Datos
    app.config['SQLALCHEMY_DATABASE_URI'] = SQLALCHEMY_DATABASE_URI
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    app.config['SQLALCHEMY_ENGINE_OPTIONS'] = {
        "pool_pre_ping": True,
        "pool_recycle": 280,
    }

    # Configuración de JWT
    app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
    app.config['JWT_ACCESS_TOKEN_EXPIRES'] = JWT_ACCESS_TOKEN_EXPIRES
    app.config['JWT_REFRESH_TOKEN_EXPIRES'] = JWT_REFRESH_TOKEN_EXPIRES
    app.config['JWT_RESET_PASSWORD_TOKEN_EXPIRES'] = JWT_RESET_PASSWORD_TOKEN_EXPIRES

    # Configuración de Mail
    app.config.update(
        MAIL_SERVER='smtp.gmail.com',
        MAIL_PORT=465,
        MAIL_USE_SSL=True,
        MAIL_USE_TLS=False,
        MAIL_USERNAME=MAIL_USERNAME,
        MAIL_PASSWORD=MAIL_PASSWORD,
        MAIL_DEFAULT_SENDER=MAIL_USERNAME
    )

    # Inicialización de extensiones
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    mail.init_app(app)

    # Callback para Blocklist
    @jwt.token_in_blocklist_loader
    def check_if_token_in_blocklist(jwt_header, jwt_payload):
        jti = jwt_payload["jti"]
        # Importar aquí para evitar ciclos
        from models import TokenBlocklist
        token = db.session.query(TokenBlocklist.id).filter_by(jti=jti).scalar()
        return token is not None

    # Registro de Blueprints
    app.register_blueprint(auth_bp)
    app.register_blueprint(api_v1_bp, url_prefix='/api/v1')
    app.register_blueprint(admin_bp)
    app.register_blueprint(telegram_bp)
    app.register_blueprint(web_bp)

    return app

if __name__ == '__main__':
    app = create_app()
    app.run(debug=True)
