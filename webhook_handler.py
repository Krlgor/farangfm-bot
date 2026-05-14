import os
import json
import logging
from flask import Flask, request, jsonify
from telegram import Bot, InlineKeyboardButton, InlineKeyboardMarkup
from database import get_db_connection

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
WEBHOOK_SECRET = os.getenv("WEBHOOK_SECRET", "")

# Инициализируем бота для отправки сообщений админу
bot = Bot(token=BOT_TOKEN) if BOT_TOKEN else None

@app.route('/webhook', methods=['POST'])
def webhook_receiver():
    """Принимает посты от n8n и отправляет админу на модерацию."""
    try:
        # Проверка авторизации
        auth_header = request.headers.get('Authorization', '')
        if WEBHOOK_SECRET and auth_header != f'Bearer {WEBHOOK_SECRET}':
            logger.warning(f"Unauthorized attempt")
            return jsonify({"error": "Unauthorized"}), 401

        data = request.get_json()
        if not data:
            return jsonify({"error": "No data"}), 400

        post_id = data.get('post_id')
        rewritten_text = data.get('rewritten_text', '')
        source = data.get('source', 'unknown')
        category = data.get('category', 'news')

        if not post_id:
            return jsonify({"error": "Missing post_id"}), 400

        # Сохраняем в БД со статусом 'pending'
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    INSERT INTO posts (id, original_text, rewritten_text, source, category, status)
                    VALUES (%s, %s, %s, %s, %s, 'pending')
                    ON CONFLICT (id) DO UPDATE SET
                        rewritten_text = EXCLUDED.rewritten_text,
                        status = 'pending'
                """, (post_id, data.get('original_text', ''), rewritten_text, source, category))
                conn.commit()

        # Отправляем админу на модерацию
        keyboard = InlineKeyboardMarkup([
            [InlineKeyboardButton("✅ Publish", callback_data=f"approve_{post_id}"),
             InlineKeyboardButton("❌ Reject", callback_data=f"reject_{post_id}")],
            [InlineKeyboardButton("✏️ Edit", callback_data=f"edit_{post_id}")]
        ])

        preview = rewritten_text[:300] + ("..." if len(rewritten_text) > 300 else "")
        
        # Отправляем сообщение админу (через requests, так как в Flask нет async)
        import requests
        send_url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
        payload = {
            "chat_id": ADMIN_ID,
            "text": f"📝 <b>Новый пост от {source}</b>\n\n{preview}\n\n<i>Категория: {category}</i>",
            "parse_mode": "HTML",
            "reply_markup": json.dumps({
                "inline_keyboard": [
                    [{"text": "✅ Publish", "callback_data": f"approve_{post_id}"},
                     {"text": "❌ Reject", "callback_data": f"reject_{post_id}"}],
                    [{"text": "✏️ Edit", "callback_data": f"edit_{post_id}"}]
                ]
            })
        }
        requests.post(send_url, json=payload)

        logger.info(f"Post {post_id} sent to admin for moderation")
        return jsonify({"status": "ok", "id": post_id}), 200

    except Exception as e:
        logger.error(f"Webhook error: {e}")
        return jsonify({"error": str(e)}), 500

@app.route('/health', methods=['GET'])
def health():
    """Health check для UptimeRobot и Render"""
    return jsonify({"status": "ok"}), 200

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port)
