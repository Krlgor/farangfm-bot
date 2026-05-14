import os
import json
import logging
from flask import Flask, request, jsonify
import requests

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = os.getenv("ADMIN_ID")
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

@app.route('/webhook', methods=['POST'])
def webhook_receiver():
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization', '')
        if WEBHOOK_SECRET and auth_header != f'Bearer {WEBHOOK_SECRET}':
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        post_id = data.get('post_id')
        rewritten_text = data.get('rewritten_text', '')
        source = data.get('source', 'unknown')
        category = data.get('category', 'news')

        # Отправляем админу на модерацию (НЕ в канал!)
        keyboard = {
            "inline_keyboard": [
                [
                    {"text": "✅ Publish", "callback_data": f"approve_{post_id}"},
                    {"text": "❌ Reject", "callback_data": f"reject_{post_id}"}
                ],
                [{"text": "✏️ Edit", "callback_data": f"edit_{post_id}"}]
            ]
        }

        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": f"📝 <b>Новый пост от {source}</b>\n\n{rewritten_text[:300]}\n\n<i>Категория: {category}</i>",
            "parse_mode": "HTML",
            "reply_markup": json.dumps(keyboard)
        }
        requests.post(send_url, json=payload)

        logger.info(f"Post {post_id} sent to admin for moderation")
        return jsonify({"status": "ok", "id": post_id}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
