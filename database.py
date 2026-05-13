import os
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
import logging

logger = logging.getLogger(__name__)

def get_db_connection():
    \"\"\"Получение соединения с PostgreSQL\"\"\"
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        logger.error("DATABASE_URL not set!")
        raise ValueError("DATABASE_URL environment variable is required")
    return psycopg2.connect(database_url, cursor_factory=RealDictCursor)

def init_db():
    \"\"\"Инициализация таблиц БД\"\"\"
    try:
        with get_db_connection() as conn:
            with conn.cursor() as cur:
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS posts (
                        id VARCHAR(50) PRIMARY KEY,
                        original_text TEXT,
                        rewritten_text TEXT,
                        source VARCHAR(200),
                        category VARCHAR(50),
                        status VARCHAR(20) DEFAULT 'pending',
                        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                cur.execute("""
                    CREATE TABLE IF NOT EXISTS schedule (
                        key_name VARCHAR(50) PRIMARY KEY,
                        display_name VARCHAR(100),
                        time_value VARCHAR(10),
                        stream VARCHAR(20),
                        template TEXT,
                        enabled BOOLEAN DEFAULT TRUE
                    )
                """)
                conn.commit()
                logger.info("✅ Database tables initialized")
    except Exception as e:
        logger.error(f"Database init error: {e}")
        raise

def get_post(post_id: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM posts WHERE id = %s", (post_id,))
            return cur.fetchone()

def update_post_status(post_id: str, status: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE posts SET status = %s WHERE id = %s", (status, post_id))
            conn.commit()

def update_post_text(post_id: str, new_text: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE posts SET rewritten_text = %s WHERE id = %s", (new_text, post_id))
            conn.commit()

def get_pending_posts(limit=10):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT * FROM posts 
                WHERE status = 'pending' 
                ORDER BY created_at DESC 
                LIMIT %s
            """, (limit,))
            return cur.fetchall()

def get_schedule():
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("SELECT * FROM schedule")
            rows = cur.fetchall()
            return {row['key_name']: row for row in rows}

def toggle_scheduled_post(key: str, enabled: bool):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("UPDATE schedule SET enabled = %s WHERE key_name = %s", (enabled, key))
            conn.commit()

def remove_scheduled_post(key: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("DELETE FROM schedule WHERE key_name = %s", (key,))
            conn.commit()

def add_scheduled_post(key: str, display_name: str, time_val: str, stream: str, template: str):
    with get_db_connection() as conn:
        with conn.cursor() as cur:
            cur.execute("""
                INSERT INTO schedule (key_name, display_name, time_value, stream, template, enabled)
                VALUES (%s, %s, %s, %s, %s, TRUE)
                ON CONFLICT (key_name) DO UPDATE SET
                    display_name = EXCLUDED.display_name,
                    time_value = EXCLUDED.time_value,
                    stream = EXCLUDED.stream,
                    template = EXCLUDED.template
            """, (key, display_name, time_val, stream, template))
            conn.commit()
            logger.info(f"✅ Scheduled post added: {key} at {time_val}")
