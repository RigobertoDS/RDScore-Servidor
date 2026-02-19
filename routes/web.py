from flask import Blueprint, render_template

web_bp = Blueprint('web', __name__)

@web_bp.route('/privacidad', methods=['GET'])
def politica_privacidad():
    return render_template('privacidad.html')

@web_bp.route('/')
def rdscore():
    return render_template('rdscore.html')
