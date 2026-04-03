from flask import Flask, request
import requests
import os
import time
import json
from collections import defaultdict

app = Flask(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
VK_TOKEN = os.environ.get("VK_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
CONFIRMATION_CODE = os.environ.get("CONFIRMATION_CODE")
# =========================================

# Хранилище истории диалогов для каждого пользователя
user_histories = defaultdict(list)

# Максимальное количество пар сообщений (вопрос-ответ), которое помнит бот
MAX_HISTORY_PAIRS = 10

def get_keyboard():
    """Клавиатура с кнопкой Помощь"""
    keyboard = {
        "one_time": False,
        "buttons": [
            [
                {
                    "action": {
                        "type": "text",
                        "label": "❓ Помощь",
                        "payload": json.dumps({"cmd": "help"})
                    },
                    "color": "primary"
                }
            ]
        ]
    }
    return keyboard

def send_message(user_id, text, keyboard=None):
    """Отправляет сообщение пользователю"""
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    try:
        params = {
            "user_id": user_id,
            "message": text,
            "random_id": int(time.time() * 1000),
            "access_token": VK_TOKEN,
            "v": "5.199"
        }
        
        if keyboard:
            params["keyboard"] = json.dumps(keyboard, ensure_ascii=False)
        
        requests.post(
            url="https://api.vk.com/method/messages.send",
            params=params,
            timeout=10
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def send_typing_status(user_id):
    """Отправляет статус 'печатает'"""
    try:
        requests.post(
            url="https://api.vk.com/method/messages.setActivity",
            params={
                "user_id": user_id,
                "type": "typing",
                "access_token": VK_TOKEN,
                "v": "5.199"
            },
            timeout=5
        )
    except:
        pass

def get_user_history(user_id):
    """Возвращает историю диалога пользователя"""
    history = user_histories.get(user_id, [])
    return history[-(MAX_HISTORY_PAIRS * 2):]

def add_to_history(user_id, role, content):
    """Добавляет сообщение в историю"""
    user_histories[user_id].append({"role": role, "content": content})
    
    if len(user_histories[user_id]) > MAX_HISTORY_PAIRS * 2:
        user_histories[user_id] = user_histories[user_id][-(MAX_HISTORY_PAIRS * 2):]

def clear_history(user_id):
    """Очищает историю диалога"""
    if user_id in user_histories:
        user_histories[user_id] = []
    return True

def ask_ai(user_id, prompt):
    """Отправляет запрос в нейросеть с учётом истории"""
    try:
        history = get_user_history(user_id)
        
        messages = [
            {
                "role": "system",
                "content": "Ты — DeepSeek AI-ассистент. Отвечай ТОЛЬКО на русском языке. Будь дружелюбным и полезным. Учитывай предыдущие сообщения в диалоге."
            }
        ]
        
        messages.extend(history)
        messages.append({"role": "user", "content": prompt})
        
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "deepseek/deepseek-r1:free",
                "messages": messages,
                "max_tokens": 500,
                "temperature": 0.7
            },
            timeout=60
        )
        
        if response.status_code == 200:
            result = response.json()
            return result["choices"][0]["message"]["content"]
        else:
            return f"❌ Ошибка API: {response.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

def handle_command(user_id, text):
    """Обрабатывает команды"""
    text_lower = text.lower()
    
    # Очистка истории
    if text_lower == "/clear":
        clear_history(user_id)
        send_message(user_id, "🧹 История диалога очищена!", get_keyboard())
        return True
    
    # Помощь
    if "помощь" in text_lower or text_lower == "/help":
        help_text = """🤖 *Помощь по боту*

Я помню историю нашего диалога! Можешь задавать уточняющие вопросы.

📌 *Команды:*
• /clear — очистить историю диалога
• /help — это сообщение

Просто пиши любые вопросы, и я отвечу!"""
        
        send_message(user_id, help_text, get_keyboard())
        return True
    
    return False

# Защита от дубликатов
processed_messages = {}
CACHE_TTL = 300

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    
    if data.get('type') == 'confirmation':
        return CONFIRMATION_CODE
    
    elif data.get('type') == 'message_new':
        message = data['object']['message']
        user_id = message['from_id']
        text = message.get('text', '').strip()
        message_id = str(message.get('id', ''))
        
        # Защита от дубликатов
        if message_id:
            current_time = time.time()
            if message_id in processed_messages:
                if current_time - processed_messages[message_id] < CACHE_TTL:
                    return 'ok', 200
            processed_messages[message_id] = current_time
        
        if not text:
            return 'ok', 200
        
        print(f"📩 Пользователь {user_id}: {text[:50]}")
        
        # Очистка старого кэша
        for msg_id in list(processed_messages.keys()):
            if time.time() - processed_messages[msg_id] > CACHE_TTL:
                del processed_messages[msg_id]
        
        # Сохраняем вопрос в историю
        add_to_history(user_id, "user", text)
        
        # Проверяем команды
        is_command = handle_command(user_id, text)
        
        if not is_command:
            send_typing_status(user_id)
            answer = ask_ai(user_id, text)
            add_to_history(user_id, "assistant", answer)
            send_message(user_id, answer, get_keyboard())
            print(f"✅ Ответ отправлен")
    
    return 'ok', 200

@app.route('/')
def index():
    return "Bot is running!", 200

@app.route('/ping')
def ping():
    return "pong", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
