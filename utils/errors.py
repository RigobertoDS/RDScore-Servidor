from flask import jsonify
from enum import Enum

class ErrorCode(Enum):
    # Auth Errors
    AUTH_MISSING_FIELDS = "AUTH_MISSING_FIELDS"
    AUTH_USERNAME_EXISTS = "AUTH_USERNAME_EXISTS"
    AUTH_EMAIL_EXISTS = "AUTH_EMAIL_EXISTS"
    AUTH_INVALID_CREDENTIALS = "AUTH_INVALID_CREDENTIALS"
    AUTH_USER_NOT_FOUND = "AUTH_USER_NOT_FOUND"
    AUTH_TOKEN_EXPIRED = "AUTH_TOKEN_EXPIRED"
    AUTH_TOKEN_INVALID = "AUTH_TOKEN_INVALID"
    AUTH_PERMISSION_DENIED = "AUTH_PERMISSION_DENIED"
    
    # Data Errors
    DATA_INVALID_FORMAT = "DATA_INVALID_FORMAT"
    DATA_NOT_FOUND = "DATA_NOT_FOUND"
    DATA_FETCH_ERROR = "DATA_FETCH_ERROR"
    
    # Server Errors
    SERVER_INTERNAL_ERROR = "SERVER_INTERNAL_ERROR"

def api_error(code: ErrorCode, message: str, status_code: int = 400, details: dict = None):
    """
    Returns a standardized JSON error response.
    Maintains backward compatibility by including the 'error' key.
    """
    response = {
        "error": message,        # Legacy support for live Android App
        "error_code": code.value # New standard
    }
    if details:
        response["details"] = details
        
    return jsonify(response), status_code
