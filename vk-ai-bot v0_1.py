from flask import Flask, request
import requests
import os
import time

app = Flask(__name__)

# ========== ПЕРЕМЕННЫЕ ОКРУЖЕНИЯ ==========
VK_TOKEN = os.environ.get("VK_TOKEN")
OPENROUTER_KEY = os.environ.get("OPENROUTER_KEY")
CONFIRMATION_CODE = os.environ.get("CONFIRMATION_CODE")
# =========================================

# Простой словарь для хранения обработанных сообщений
processed_messages = {}
CACHE_TTL = 300  # 5 минут

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
                "random_id": int(time.time() * 1000),
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
        message_id = str(message.get('id', ''))
        
        # Проверка на дубликат
        if message_id:
            current_time = time.time()
            if message_id in processed_messages:
                if current_time - processed_messages[message_id] < CACHE_TTL:
                    print(f"⚠️ Пропускаю дубликат сообщения {message_id}")
                    return 'ok', 200
            
            processed_messages[message_id] = current_time
        
        if not text:
            return 'ok', 200
        
        print(f"📩 Обрабатываю: {text[:50]}")
        
        # Очищаем старые записи в кэше
        for msg_id in list(processed_messages.keys()):
            if current_time - processed_messages[msg_id] > CACHE_TTL:
                del processed_messages[msg_id]
        
        answer = ask_ai(text)
        send_message(user_id, answer)
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
