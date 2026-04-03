from flask import Flask, request
import requests
import os

app = Flask(__name__)

# Берём секреты из переменных окружения
VK_TOKEN = os.environ.get("VK_TOKEN")
GROUP_ID = os.environ.get("GROUP_ID")           # Добавили GROUP_ID
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
CONFIRMATION_CODE = os.environ.get("CONFIRMATION_CODE")

def send_message(user_id, text):
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    try:
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
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def ask_ai(prompt):
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
                "max_tokens": 500
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
    
    if data.get('type') == 'confirmation':
        return CONFIRMATION_CODE
    
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
    return "Bot is running", 200

@app.route('/ping')
def ping():
    return "pong", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
