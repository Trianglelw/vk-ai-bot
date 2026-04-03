from flask import Flask, request
import requests
import json

app = Flask(__name__)

# ========== НАСТРОЙКИ (ЗАМЕНИТЕ НА СВОИ) ==========
VK_TOKEN = "ваш_токен_группы"
GROUP_ID = "123456789"
OPENROUTER_KEY = "ваш_ключ_openrouter"
CONFIRMATION_CODE = "ваш_код_подтверждения"  # Получите в настройках Callback API ВК
# =================================================

def send_message(user_id, text):
    """Отправляет сообщение пользователю"""
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    requests.post(
        url="https://api.vk.com/method/messages.send",
        params={
            "user_id": user_id,
            "message": text,
            "random_id": 0,
            "access_token": VK_TOKEN,
            "v": "5.199"
        }
    )

def ask_ai(prompt):
    """Отправляет запрос в нейросеть"""
    try:
        response = requests.post(
            url="https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {OPENROUTER_KEY}",
                "Content-Type": "application/json"
            },
            json={
                "model": "qwen/qwen3.6-plus:free",
                "messages": [
                    {"role": "system", "content": "Ты — AI-ассистент. Отвечай ТОЛЬКО на русском языке."},
                    {"role": "user", "content": prompt}
                ],
                "max_tokens": 1000
            },
            timeout=60
        )
        
        if response.status_code == 200:
            return response.json()["choices"][0]["message"]["content"]
        return f"❌ Ошибка API: {response.status_code}"
    except Exception as e:
        return f"❌ Ошибка: {str(e)}"

@app.route('/', methods=['POST'])
def webhook():
    data = request.get_json()
    
    # Подтверждение сервера
    if data.get('type') == 'confirmation':
        return CONFIRMATION_CODE
    
    # Обработка нового сообщения
    elif data.get('type') == 'message_new':
        message = data['object']['message']
        user_id = message['from_id']
        text = message.get('text', '').strip()
        
        if text:
            answer = ask_ai(text)
            send_message(user_id, answer)
    
    return 'ok', 200

@app.route('/')
def index():
    return "Бот работает! 🚀", 200

@app.route('/ping')
def ping():
    return "pong", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)