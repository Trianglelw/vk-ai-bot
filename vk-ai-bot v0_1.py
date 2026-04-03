from flask import Flask, request
import requests
import os
import time
from collections import defaultdict

app = Flask(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
VK_TOKEN = os.environ.get("VK_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
CONFIRMATION_CODE = os.environ.get("CONFIRMATION_CODE")
# =========================================

# Кэш для обработки повторных запросов (храним ID обработанных сообщений)
processed_messages = defaultdict(lambda: {"processed": False, "timestamp": 0})
CACHE_TTL = 300  # 5 минут - храним ID сообщения

# Модели в порядке приоритета
MODELS = [
    "deepseek/deepseek-r1:free",
    "qwen/qwen3.6-plus:free",
    "nvidia/nemotron-3-super:free",
    "meta-llama/llama-3.3-70b-instruct:free",
]

current_model_index = 0

def send_message(user_id, text):
    """Отправляет сообщение пользователю"""
    if len(text) > 4000:
        text = text[:3997] + "..."
    
    try:
        requests.post(
            url="https://api.vk.com/method/messages.send",
            params={
                "user_id": user_id,
                "message": text,
                "random_id": int(time.time() * 1000),  # Уникальный ID
                "access_token": VK_TOKEN,
                "v": "5.199"
            },
            timeout=10
        )
    except Exception as e:
        print(f"Ошибка отправки: {e}")

def ask_ai(prompt):
    """Отправляет запрос в нейросеть"""
    global current_model_index
    
    for attempt in range(len(MODELS)):
        model = MODELS[current_model_index]
        
        try:
            print(f"🔄 Пробую модель: {model}")
            
            response = requests.post(
                url="https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {OPENROUTER_KEY}",
                    "Content-Type": "application/json"
                },
                json={
                    "model": model,
                    "messages": [
                        {
                            "role": "system",
                            "content": "Ты — DeepSeek AI-ассистент. Отвечай ТОЛЬКО на русском языке. Будь кратким, дружелюбным и полезным."
                        },
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ],
                    "max_tokens": 500,
                    "temperature": 0.7
                },
                timeout=60
            )
            
            if response.status_code == 200:
                result = response.json()
                answer = result["choices"][0]["message"]["content"]
                print(f"✅ Модель {model} ответила!")
                return answer
            elif response.status_code == 429:
                print(f"⚠️ Модель {model}: превышен лимит (429)")
                current_model_index = (current_model_index + 1) % len(MODELS)
            else:
                print(f"⚠️ Ошибка {response.status_code} с моделью {model}")
                current_model_index = (current_model_index + 1) % len(MODELS)
                
        except requests.exceptions.Timeout:
            print(f"⚠️ Таймаут модели {model}")
            current_model_index = (current_model_index + 1) % len(MODELS)
        except Exception as e:
            print(f"⚠️ Ошибка: {str(e)[:100]}")
            current_model_index = (current_model_index + 1) % len(MODELS)
    
    return "❌ Извините, все модели временно недоступны. Попробуйте позже!"

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
        message_id = message.get('id')  # Уникальный ID сообщения
        
        # ✅ ПРОВЕРКА НА ДУБЛИКАТ
        if message_id:
            current_time = time.time()
            # Если сообщение уже обработано и прошло меньше CACHE_TTL секунд
            if processed_messages[message_id]["processed"]:
                if current_time - processed_messages[message_id]["timestamp"] < CACHE_TTL:
                    print(f"⚠️ Пропускаю дубликат сообщения {message_id}")
                    return 'ok', 200
            
            # Отмечаем сообщение как обрабатываемое
            processed_messages[message_id]["processed"] = True
            processed_messages[message_id]["timestamp"] = current_time
        
        if not text:
            return 'ok', 200
        
        print(f"📩 Обрабатываю сообщение {message_id}: {text[:50]}")
        
        # Получаем ответ от ИИ
        answer = ask_ai(text)
        
        # Отправляем ответ
        send_message(user_id, answer)
        
        # Небольшая задержка, чтобы ВК успел получить ответ
        time.sleep(0.5)
    
    return 'ok', 200

@app.route('/')
def index():
    return "Bot with DeepSeek-R1 is running!", 200

@app.route('/ping')
def ping():
    return "pong", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
