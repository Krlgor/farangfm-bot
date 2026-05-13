# FARANG.FM Telegram Bot

Тропическое радио из Таиланда в Telegram.

## Функции

- 🎧 **Telegram Mini App** — плеер прямо в Telegram
- 🌍 **Мультиязычность** — Русский, English, ภาษาไทย
- 🤖 **AI-генерация постов** через Groq
- 📅 **Автопостинг** по расписанию
- ✅ **Модерация** постов с кнопками Publish/Reject/Edit
- 📻 **4 стрима**: LOFI, CHILL, ROAD, DANCE

## Быстрый старт

### 1. Создайте бота у @BotFather
\\\
/newbot → FARANGFM_Bot → @farangfm_bot
\\\

### 2. Получите необходимые токены
- \BOT_TOKEN\ — от @BotFather
- \ADMIN_ID\ — у @userinfobot
- \CHANNEL_ID\ — создайте канал и добавьте бота админом
- \GROQ_API_KEY\ — на https://console.groq.com

### 3. Деплой на Render
[![Deploy to Render](https://render.com/images/deploy-to-render-button.svg)](https://render.com/deploy)

### 4. Локальный тест (Windows)
\\\powershell
python -m venv venv
.\venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
# Отредактируйте .env
python bot.py
\\\

## Команды админа
- \/post LOFI текст\ — ручная публикация
- \/generate LOFI тема\ — генерация через AI
- \/pending\ — посты на модерации
- \/schedule\ — управление расписанием

## Лицензия
MIT
