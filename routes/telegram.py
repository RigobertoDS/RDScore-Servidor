from flask import Blueprint, request
import requests
from config import ADMIN_KEY
from services.common.herramientas import enviar_telegram

telegram_bp = Blueprint('telegram', __name__)

def emoji_modelo(modelo):
    return {
        "conservador": "🟢 Conservador",
        "moderado": "🟡 Moderado",
        "agresivo": "🔴 Agresivo"
    }.get(modelo, modelo)

def emoji_tipo(tipo):
    return {
        "resultado": "🏆 RESULTADO",
        "btts": "⚽ BTTS",
        "over": "🔥 OVER 2.5"
    }.get(tipo, tipo.upper())

def formatear_precision_tipo_apuesta(data: dict) -> str:
    lineas = []
    lineas.append("📊 *PRECISIÓN POR TIPO DE APUESTA*\n")

    for tipo, modelos in data.items():
        lineas.append(f"{emoji_tipo(tipo)}")

        for modelo, stats in modelos.items():
            aciertos_pct = round(stats["aciertos"], 1)
            aciertos_brutos = stats["aciertos_brutos"]
            apuestas = stats["apuestas"]
            roi = round(stats["roi"], 2)
            beneficio = round(stats["beneficio"], 2)

            lineas.append(f"{emoji_modelo(modelo)}")
            lineas.append(
                f"• Aciertos: {aciertos_pct}% ({aciertos_brutos}/{apuestas})\n"
                f"• ROI: {'+' if roi >= 0 else ''}{roi}%\n"
                f"• Beneficio: {'+' if beneficio >= 0 else ''}{beneficio}€\n"
            )

        lineas.append("")  # salto entre tipos

    return "\n".join(lineas)

@telegram_bp.post("/telegram-webhook")
def telegram_webhook():
    data = request.json

    if "message" not in data:
        return "OK", 200

    text = data["message"].get("text", "")

    # Comando /status
    if text == "/status":
        r = requests.get(
            "https://www.rdscore.com/status",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=10
        )
        ok, resp = enviar_telegram(r.text)

    # Comando /salud
    elif text == "/salud":
        r = requests.get(
            "https://www.rdscore.com/salud",
            timeout=5
        )
        ok, resp = enviar_telegram(r.text)

    # Comando /precision_modelos
    elif text == "/precision_modelos":
        r = requests.get(
            "https://www.rdscore.com/precision_modelos",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=5
        )
        ok, resp = enviar_telegram(r.text)

    # Comando /precision_tipo_apuesta
    elif text == "/precision_tipo_apuesta":
        r = requests.get(
            "https://www.rdscore.com/precision_tipo_apuesta",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=5
        )
        data = r.json()
        mensaje = formatear_precision_tipo_apuesta(data)
        ok, resp = enviar_telegram(mensaje)

    # Comando /cuotas_calientes
    elif text == "/cuotas_calientes":
        r = requests.get(
            "https://www.rdscore.com/precision_cuotas_calientes",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=5
        )
        data = r.json()
        mensaje = (
            "🔥 *Cuotas calientes*\n\n"
            f"📊 Partidos: {data['partidos']}\n"
            f"✅ Aciertos: {data['aciertos']}\n"
            f"🎯 Precisión: {data['precision'] * 100:.2f}%\n"
            f"💰 Beneficio: {data['beneficio']:.2f}\n"
            f"📉 ROI: {data['roi'] * 100:.2f}%"
        )
        ok, resp = enviar_telegram(mensaje)

    # Comando /usuarios
    elif text == "/usuarios":
        r = requests.get(
            "https://www.rdscore.com/usuarios",
            headers={"X-Admin-Key": ADMIN_KEY},
            timeout=5
        )
        ok, resp = enviar_telegram(r.text)

    return "OK", 200
