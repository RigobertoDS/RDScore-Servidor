from flask import Blueprint, request, jsonify
from utils.errors import ErrorCode, api_error
from utils.success import SuccessCode, api_success
from extensions import db, mail
from models import Usuario, TokenBlocklist
from flask_jwt_extended import (
    create_access_token, create_refresh_token, jwt_required,
    get_jwt_identity, get_jwt, decode_token
)
from flask_mail import Message
import redislite
import os
import secrets
import string
from datetime import timedelta
from config import BASE_DIR, MAIL_USERNAME

auth_bp = Blueprint('auth', __name__)

# Método para crear el código de recuperación corto
def generar_codigo_corto(length=8):
    alfabeto = string.ascii_uppercase + string.digits
    return ''.join(secrets.choice(alfabeto) for _ in range(length))

# Método para mandar E-Mails con Gmail usando Flask-Mail
def enviar_email_reset(usuario, reset_token, expires):
    # Diccionario de mensajes traducidos para el email
    mensaje_email = {
        'asunto': 'RDScore - Confirmación de correo electrónico',
            'cuerpo': (
                'Hola {usuario.username},\n\n'
                'Has solicitado restablecer tu contraseña, '
                'usa el siguiente código para cambiarla (válido 15 minutos):\n\n'
                '{reset_token}\n\n'
                'Este mensaje ha sido generado automáticamente, por favor no contestes.\n'
                'Si no solicitaste este cambio, ignora este mensaje.\n\n'
                'Saludos,\n'
                'RDScore')
        }

    # Obtener la URL de confirmación
    # Crear el mensaje utilizando el idioma seleccionado
    asunto = mensaje_email['asunto']
    cuerpo = mensaje_email['cuerpo'].format(usuario=usuario, reset_token=reset_token)

    msg = Message(asunto, sender=MAIL_USERNAME, recipients=[usuario.email])
    msg.body = cuerpo

    # Enviar el correo
    mail.send(msg)

import requests
from config import TG_TOKEN, TG_CHAT_ID

def enviar_telegram_simple(mensaje: str):
    url = f"https://api.telegram.org/bot{TG_TOKEN}/sendMessage"
    payload = {
        "chat_id": TG_CHAT_ID,
        "text": mensaje,
        "parse_mode": "Markdown"
    }
    try:
        requests.post(url, data=payload, timeout=5)
    except Exception as e:
        print(f"Error sending telegram: {e}")

@auth_bp.route('/register', methods=['POST'])
def register_user():
    data = request.get_json()
    if not data or 'username' not in data or 'email' not in data or 'password' not in data:
        return api_error(ErrorCode.AUTH_MISSING_FIELDS, "Faltan campos obligatorios (nombre, email, password)", 400)

    if Usuario.query.filter_by(username=data['username']).first():
        return api_error(ErrorCode.AUTH_USERNAME_EXISTS, "El nombre de usuario no está disponible", 409)

    if Usuario.query.filter_by(email=data['email']).first():
        return api_error(ErrorCode.AUTH_EMAIL_EXISTS, "El email ya está registrado", 409)

    usuario = Usuario(
        username=data['username'].strip(),
        email=data['email'].strip().lower()
    )
    usuario.set_password(data['password'])
    db.session.add(usuario)
    db.session.commit()

    enviar_telegram_simple(
        f"Nuevo usuario registrado:\n"
        f"- Usuario: {data['username']}\n"
        f"- Email: {data['email']}"
    )

    return api_success(SuccessCode.AUTH_REGISTER_SUCCESS, "Cuenta creada con éxito", 201)

@auth_bp.route('/login', methods=['POST'])
def login_user():
    data = request.get_json()
    if not data or 'username' not in data or 'password' not in data:
        return api_error(ErrorCode.AUTH_MISSING_FIELDS, "Faltan username o password", 400)

    usuario = Usuario.query.filter_by(username=data['username'].strip()).first()

    if usuario and usuario.check_password(data['password']):
        access_token = create_access_token(identity=str(usuario.id))
        refresh_token = create_refresh_token(identity=str(usuario.id))
        return api_success(SuccessCode.AUTH_LOGIN_SUCCESS, "Login correcto", 200, {"access_token": access_token, "refresh_token": refresh_token})

    return api_error(ErrorCode.AUTH_INVALID_CREDENTIALS, "Credenciales incorrectas", 401)

@auth_bp.route("/logout", methods=["POST"])
@jwt_required()
def logout_user():
    try:
        jti = get_jwt()["jti"]
        db.session.add(TokenBlocklist(jti=jti))
        db.session.commit()
        return api_success(SuccessCode.AUTH_LOGOUT_SUCCESS, "Sesión cerrada correctamente", 200)
    except Exception:
        return api_error(ErrorCode.SERVER_INTERNAL_ERROR, "Fallo al cerrar sesión.", 403)

@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    try:
        current_user_id = get_jwt_identity()
        
        # Verificar que el usuario aún existe en la BD
        usuario = Usuario.query.get(current_user_id)
        if not usuario:
            return api_error(ErrorCode.AUTH_USER_NOT_FOUND, "Usuario no encontrado", 401)
            
        new_access_token = create_access_token(identity=current_user_id)
        return jsonify(access_token=new_access_token)
    except Exception:
        return api_error(ErrorCode.AUTH_TOKEN_EXPIRED, "Tu sesión ha expirado.", 403)

@auth_bp.route('/forgot-password', methods=['POST'])
def forgot_password():
    data = request.get_json()
    email = data.get('email')
    if not email:
        return api_error(ErrorCode.AUTH_MISSING_FIELDS, "Email obligatorio", 400)

    usuario = Usuario.query.filter_by(email=email).first()
    if not usuario:
        return api_success(SuccessCode.AUTH_PASSWORD_RESET_EMAIL_SENT, "Si tu email está registrado, recibirás un correo.", 200)

    expires = timedelta(minutes=15)
    jwt_largo = create_access_token(
        identity=str(usuario.id),
        expires_delta=expires,
        additional_claims={"purpose": "password_reset"}
    )

    codigo_corto = generar_codigo_corto(8)
    r = redislite.Redis(os.path.join(BASE_DIR, 'redis-reset.db'))
    r.setex(codigo_corto, 60*15, jwt_largo)

    try:
        enviar_email_reset(usuario, codigo_corto, expires)
    except Exception as e:
        print(f"Error email: {e}")
        return api_error(ErrorCode.SERVER_INTERNAL_ERROR, "Error al enviar email", 500)

    return api_success(SuccessCode.AUTH_PASSWORD_RESET_EMAIL_SENT, "Se ha enviado el email.", 200)

@auth_bp.route('/reset-password', methods=['POST'])
def reset_password():
    codigo_corto = request.json.get('code') or request.args.get('code')
    new_password = request.json.get('new_password')

    if not codigo_corto or not new_password:
        return api_error(ErrorCode.AUTH_MISSING_FIELDS, "Faltan datos", 400)

    r = redislite.Redis(os.path.join(BASE_DIR, 'redis-reset.db'))
    jwt_largo = r.get(codigo_corto)
    if not jwt_largo:
        return api_error(ErrorCode.AUTH_TOKEN_INVALID, "Código inválido o expirado", 403)

    try:
        claims = decode_token(jwt_largo)
        if claims.get('purpose') != 'password_reset':
            return api_error(ErrorCode.AUTH_TOKEN_INVALID, "Token inválido", 403)

        usuario = Usuario.query.get(int(claims['sub']))
        usuario.set_password(new_password)
        db.session.commit()
        r.delete(codigo_corto)

        jti = claims.get("jti")
        if jti:
            db.session.add(TokenBlocklist(jti=jti))
            db.session.commit()

        return api_success(SuccessCode.AUTH_PASSWORD_RESET_SUCCESS, "Contraseña actualizada correctamente.", 200)

    except Exception:
        return api_error(ErrorCode.AUTH_TOKEN_INVALID, "Token inválido o expirado", 403)

@auth_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    current_user_id = get_jwt_identity()
    usuario = Usuario.query.get(current_user_id)
    if not usuario:
        return api_error(ErrorCode.AUTH_USER_NOT_FOUND, "Usuario no encontrado", 404)
    return jsonify(usuario.to_dict()), 200

@auth_bp.route('/modificar-datos', methods=['PUT'])
@jwt_required()
def modificar_datos():
    current_user_id = get_jwt_identity()
    usuario = Usuario.query.get(current_user_id)
    if not usuario:
        return api_error(ErrorCode.AUTH_USER_NOT_FOUND, "Usuario no encontrado", 404)

    data = request.get_json()
    if 'username' in data:
        if Usuario.query.filter(Usuario.username == data['username'], Usuario.id != current_user_id).first():
            return api_error(ErrorCode.AUTH_USERNAME_EXISTS, "El nombre de usuario ya existe", 409)
        usuario.username = data['username'].strip()

    if 'email' in data:
        if Usuario.query.filter(Usuario.email == data['email'], Usuario.id != current_user_id).first():
            return api_error(ErrorCode.AUTH_EMAIL_EXISTS, "El email ya existe", 409)
        usuario.email = data['email'].strip().lower()

    db.session.commit()
    return jsonify(usuario.to_dict())

@auth_bp.route('/cambiar-password', methods=['PUT'])
@jwt_required()
def cambiar_password():
    current_user_id = get_jwt_identity()
    usuario = Usuario.query.get(current_user_id)
    if not usuario:
        return api_error(ErrorCode.AUTH_USER_NOT_FOUND, "Usuario no encontrado", 404)

    data = request.get_json()
    current_password = data.get('current_password')
    new_password = data.get('new_password')

    if not current_password or not new_password:
        return api_error(ErrorCode.AUTH_MISSING_FIELDS, "Faltan la contraseña actual o la nueva", 400)

    if not usuario.check_password(current_password):
        return api_error(ErrorCode.AUTH_INVALID_CREDENTIALS, "La contraseña actual es incorrecta", 401)

    usuario.set_password(new_password)
    db.session.commit()
    return api_success(SuccessCode.AUTH_PASSWORD_CHANGED, "Contraseña actualizada correctamente", 200)

@auth_bp.route('/eliminar-cuenta', methods=['DELETE'])
@jwt_required()
def eliminar_usuario():
    current_user_id = get_jwt_identity()
    usuario_a_eliminar = Usuario.query.get(current_user_id)
    if not usuario_a_eliminar:
        return api_error(ErrorCode.AUTH_USER_NOT_FOUND, "Usuario no encontrado", 404)

    try:
        db.session.delete(usuario_a_eliminar)
        db.session.commit()
        return api_success(SuccessCode.AUTH_ACCOUNT_DELETED, "Tu cuenta ha sido eliminada correctamente", 200)
    except Exception:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No tienes permiso para realizar esta acción", 403)
