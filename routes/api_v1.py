import os
import json
from flask import Blueprint, jsonify, request
from utils.errors import ErrorCode, api_error
from flask_jwt_extended import jwt_required
from datetime import datetime
from models import Partido, Liga
from config import BASE_DIR
from services.analysis.comprobar_precision import cargar_resumen, cargar_resumen_tipo_apuesta
from services.analysis.comprobar_precision_cuotas_calientes import (
    cargar_resumen_cuotas_calientes,
    obtener_historial_cuotas_calientes
)
from services.data_fetching.obtener_cuotas_calientes import cargar_cuotas_calientes, cargar_partidos_calientes

api_v1_bp = Blueprint('api_v1', __name__)

RUTA_MANTENIMIENTO = os.path.join(BASE_DIR, 'datos', 'mantenimiento.json')

# --- ENDPOINT DE MANTENIMIENTO (público, sin auth) ---

@api_v1_bp.route("/mantenimiento", methods=["GET"])
def get_mantenimiento():
    """
    Devuelve el estado de mantenimiento del servidor.
    No requiere autenticación para que la app pueda consultarlo al iniciar.
    """
    try:
        with open(RUTA_MANTENIMIENTO, 'r', encoding='utf-8') as f:
            data = json.load(f)
            activo = data.get("activo", False)
    except (FileNotFoundError, json.JSONDecodeError):
        activo = False
    return jsonify({"activo": activo}), 200

# --- ENDPOINTS DE PARTIDOS ---

@api_v1_bp.route("/partidos", methods=["GET"])
@jwt_required()
def get_partidos_por_fecha():
    """
    Obtiene todos los partidos de una fecha específica (jugados o por jugar).
    """
    fecha_str = request.args.get('fecha') # Formato esperado: YYYY-MM-DD
    
    if not fecha_str:
        return api_error(ErrorCode.DATA_INVALID_FORMAT, "Parámetro 'fecha' requerido (YYYY-MM-DD)", 400)
        
    try:
        # Validar formato
        fecha_obj = datetime.strptime(fecha_str, "%Y-%m-%d").date()
        
        # Query: Ordenada por hora
        partidos = Partido.query.filter_by(fecha=fecha_obj).order_by(Partido.hora.asc()).all()
        
        return jsonify({
            "fecha": fecha_str,
            "count": len(partidos),
            "partidos": [p.to_dict() for p in partidos]
        }), 200
        
    except ValueError:
        return api_error(ErrorCode.DATA_INVALID_FORMAT, "Formato de fecha inválido. Use YYYY-MM-DD", 400)

# --- ENDPOINTS DE DATOS ---

@api_v1_bp.route("/datos-equipo/<int:id_equipo>", methods=["GET"])
@jwt_required()
def get_datos_equipo(id_equipo):
    """
    Obtiene datos completos de un equipo (partidos + clasificación de sus ligas).
    Usado por la pantalla de detalle de equipo en Android.
    """
    from services.data_fetching.obtener_datos_equipo import obtener_datos_equipo
    try:
        datos = obtener_datos_equipo(id_equipo)
    except Exception as e:
        print(f"Error en datos-equipo: {e}")
        return api_error(ErrorCode.DATA_FETCH_ERROR, "Error al obtener datos del equipo", 500)
    return jsonify({"datos": datos}), 200

@api_v1_bp.route("/ligas", methods=["GET"])
@jwt_required()
def get_ligas():
    ligas = Liga.query.all()
    return jsonify({
        "ligas": [l.to_dict() for l in ligas]
    }), 200

# --- ENDPOINTS DE ESTADÍSTICAS Y CUOTAS CALIENTES ---

@api_v1_bp.route("/precision", methods=["GET"])
@jwt_required()
def get_precision():
    try:
        texto = cargar_resumen()
    except Exception:
        return api_error(ErrorCode.DATA_NOT_FOUND, "Error al obtener los datos.", 404)
    return jsonify({"mensaje": texto}), 200

@api_v1_bp.route("/precision-apuesta", methods=["GET"])
@jwt_required()
def get_precision_tipo_apuesta():
    try:
        texto = cargar_resumen_tipo_apuesta()
    except Exception:
        return api_error(ErrorCode.DATA_NOT_FOUND, "Error al obtener los datos.", 404)
    return jsonify({"mensaje": texto}), 200

@api_v1_bp.route("/cuotas-calientes", methods=["GET"])
@jwt_required()
def get_cuotas_calientes():
    try:
        calientes = cargar_cuotas_calientes()
        partidos = cargar_partidos_calientes()
    except Exception:
        return api_error(ErrorCode.DATA_NOT_FOUND, "Error al obtener los datos.", 404)
    return jsonify({"partidos": [p.to_dict() for p in partidos], "cuotas_calientes": calientes}), 200

@api_v1_bp.route("/precision-cuotas-calientes", methods=["GET"])
@jwt_required()
def get_precision_cuotas_calientes():
    """
    Devuelve el resumen de precisión de las cuotas calientes (V2).
    """
    try:
        resumen = cargar_resumen_cuotas_calientes()
    except Exception:
        return api_error(ErrorCode.DATA_NOT_FOUND, "Error al obtener los datos.", 404)
    return jsonify({"resumen": resumen}), 200

@api_v1_bp.route("/historial-cuotas-calientes", methods=["GET"])
@jwt_required()
def get_historial_cuotas_calientes():
    """
    Devuelve el historial de partidos de cuotas calientes ya terminados con su resultado.
    """
    try:
        historial = obtener_historial_cuotas_calientes()
    except Exception as e:
        print(f"Error historial cuotas: {e}")
        return api_error(ErrorCode.DATA_FETCH_ERROR, "Error al obtener historial.", 500)
    return jsonify({"historial": historial}), 200
