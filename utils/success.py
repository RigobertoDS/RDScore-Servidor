from flask import jsonify
from enum import Enum

class SuccessCode(Enum):
    # Auth Success
    AUTH_REGISTER_SUCCESS = "AUTH_REGISTER_SUCCESS"
    AUTH_LOGIN_SUCCESS = "AUTH_LOGIN_SUCCESS"
    AUTH_LOGOUT_SUCCESS = "AUTH_LOGOUT_SUCCESS"
    AUTH_PASSWORD_RESET_EMAIL_SENT = "AUTH_PASSWORD_RESET_EMAIL_SENT"
    AUTH_PASSWORD_RESET_SUCCESS = "AUTH_PASSWORD_RESET_SUCCESS"
    AUTH_ACCOUNT_DELETED = "AUTH_ACCOUNT_DELETED"
    AUTH_PASSWORD_CHANGED = "AUTH_PASSWORD_CHANGED"

def api_success(code: SuccessCode, message: str, status_code: int = 200, data: dict = None):
    """
    Returns a standardized JSON success response.
    Maintains backward compatibility by including the 'mensaje' key.
    """
    response = {
        "mensaje": message,        # Legacy support for live Android App
        "success_code": code.value # New standard
    }
    if data:
        response.update(data)
        
    return jsonify(response), status_code
