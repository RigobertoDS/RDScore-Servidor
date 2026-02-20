import os
import json
from flask import Blueprint, jsonify, request
from utils.errors import ErrorCode, api_error
from sqlalchemy import text
import time
from models import db, Usuario
from config import ADMIN_KEY, BASE_DIR
from services.analysis.comprobar_precision import cargar_precision, cargar_resumen_tipo_apuesta
from services.analysis.comprobar_precision_cuotas_calientes import cargar_resumen_cuotas_calientes

admin_bp = Blueprint('admin', __name__)
START_TIME = time.time()
RUTA_MANTENIMIENTO = os.path.join(BASE_DIR, 'datos', 'mantenimiento.json')

@admin_bp.route("/status", methods=["GET"])
def status_avanzado():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)

    respuesta = []
    respuesta.append(f"Server: OK")

    uptime_seconds = int(time.time() - START_TIME)
    horas = uptime_seconds // 3600
    minutos = (uptime_seconds % 3600) // 60
    respuesta.append(f"Uptime: {horas}h {minutos}m")

    try:
        with open(RUTA_MANTENIMIENTO, 'r', encoding='utf-8') as f:
            mant = json.load(f)
        estado_mant = "🔴 ACTIVADO" if mant.get("activo", False) else "🟢 DESACTIVADO"
    except (FileNotFoundError, json.JSONDecodeError):
        estado_mant = "🟢 DESACTIVADO"
    respuesta.append(f"Mantenimiento: {estado_mant}")

    try:
        db.session.execute(text("SELECT 1"))
        respuesta.append(f"MySQL: OK")
    except Exception as e:
        respuesta_error = f"MySQL: ERROR: {str(e)}"
        return jsonify(respuesta_error), 200

    try:
        total_usuarios = Usuario.query.count()
        respuesta.append(f"Total Usuarios: {total_usuarios}")
    except Exception as e:
        respuesta.append(f"Total Usuarios: ERROR: {str(e)}")

    try:
        ultimo = Usuario.query.order_by(Usuario.id.desc()).first()
        if ultimo:
            respuesta.append(f"Último Usuario:")
            respuesta.append(f" - id: {ultimo.id}")
            respuesta.append(f" - username: {ultimo.username}")
            respuesta.append(f" - email: {ultimo.email}")
        else:
            respuesta.append(f"Último Usuario: No hay usuarios")
    except Exception as e:
        respuesta.append(f"Último Usuario: ERROR: {str(e)}")

    return "\n".join(respuesta), 200

@admin_bp.route("/precision_modelos", methods=["GET"])
def get_precision_modelos():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)
    return cargar_precision(), 200

@admin_bp.route("/precision_tipo_apuesta", methods=["GET"])
def get_precision_tipo_apuesta_admin():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)
    return cargar_resumen_tipo_apuesta(), 200

@admin_bp.route("/precision_cuotas_calientes", methods=["GET"])
def get_precision_cuotas_calientes():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)
    return jsonify(cargar_resumen_cuotas_calientes())

@admin_bp.route("/usuarios", methods=["GET"])
def listar_usuarios():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)

    try:
        usuarios = (
            Usuario.query
            .order_by(Usuario.id.desc())
            .limit(10)
            .all()
        )

        respuesta = [f"Total usuarios: {Usuario.query.count()}"]
        respuesta.append("Últimos usuarios:")

        for u in usuarios:
            respuesta.append(f"- {u.id} | {u.username} | {u.created_at}")

        return "\n".join(respuesta), 200

    except Exception as e:
        return f"ERROR usuarios: {str(e)}", 200

@admin_bp.route("/salud", methods=["GET"])
def health():
    return "Vamos bien.", 200

@admin_bp.route("/mantenimiento", methods=["GET", "POST"])
def mantenimiento():
    api_key = request.headers.get("X-Admin-Key")
    if api_key != ADMIN_KEY:
        return api_error(ErrorCode.AUTH_PERMISSION_DENIED, "No autorizado", 401)

    if request.method == "GET":
        try:
            with open(RUTA_MANTENIMIENTO, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except (FileNotFoundError, json.JSONDecodeError):
            data = {"activo": False}
        return jsonify(data), 200

    # POST: Actualizar estado
    body = request.get_json(silent=True)
    if not body or "activo" not in body:
        return api_error(ErrorCode.DATA_INVALID_FORMAT, "Se requiere el campo 'activo' (true/false)", 400)

    data = {"activo": bool(body["activo"])}

    with open(RUTA_MANTENIMIENTO, 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

    estado = "🔴 ACTIVADO" if data["activo"] else "🟢 DESACTIVADO"
    return jsonify({"resultado": f"Mantenimiento {estado}", "activo": data["activo"]}), 200

