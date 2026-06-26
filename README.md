# 🎵 Telegram Music Bot — Инструкция по запуску

## 📋 Что нужно

- Python 3.11+
- ffmpeg (для конвертации аудио)
- Токен Telegram бота
- API ключ Last.fm (бесплатно)

---

## 🚀 Быстрый старт

### 1. Установить ffmpeg

**Ubuntu/Debian:**
```bash
sudo apt install ffmpeg -y
```

**macOS:**
```bash
brew install ffmpeg
```

**Windows:**
Скачать с https://ffmpeg.org/download.html и добавить в PATH

---

### 2. Создать бота в Telegram

1. Написать @BotFather
2. `/newbot` → дать имя → получить токен
3. Вставить токен в `config.py`

---

### 3. Получить Last.fm API ключ (бесплатно)

1. Зарегистрироваться на https://www.last.fm
2. Перейти на https://www.last.fm/api/account/create
3. Заполнить форму (Application name: "My Music Bot")
4. Скопировать API key → вставить в `config.py`

---

### 4. Установить зависимости

```bash
cd music_bot
pip install -r requirements.txt
```

---

### 5. Настроить config.py

```python
BOT_TOKEN = "1234567890:AAxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"  # от @BotFather
LASTFM_API_KEY = "xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx"        # от Last.fm
```

---

### 6. Запустить бота

```bash
python bot.py
```

---

## 🖥 Запуск на VPS (фоновый режим)

### Вариант 1: systemd (рекомендуется)

Создать файл `/etc/systemd/system/music-bot.service`:

```ini
[Unit]
Description=Telegram Music Bot
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/music_bot
ExecStart=/usr/bin/python3 /home/ubuntu/music_bot/bot.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

```bash
sudo systemctl enable music-bot
sudo systemctl start music-bot
sudo systemctl status music-bot
```

### Вариант 2: screen (проще)

```bash
screen -S music-bot
python bot.py
# Ctrl+A, D — отключиться от screen
```

### Вариант 3: nohup

```bash
nohup python bot.py > bot.log 2>&1 &
```

---

## 📁 Структура файлов

```
music_bot/
├── bot.py              # Точка входа — запускать это
├── config.py           # Токены и настройки
├── database.py         # SQLite операции
├── music.py            # yt-dlp поиск/скачивание
├── lastfm.py           # Last.fm рекомендации
├── handlers/
│   ├── search.py       # 🔍 Поиск
│   ├── favorites.py    # ❤️ Избранное
│   └── wave.py         # 🌊 Моя Волна
├── requirements.txt
├── music_bot.db        # База данных (создаётся автоматически)
└── temp_music/         # Временные MP3 (создаётся автоматически)
```

---

## 🔧 Возможные проблемы

**"ffmpeg not found"**
→ Установить ffmpeg (см. шаг 1)

**Волна не работает**
→ Проверить LASTFM_API_KEY в config.py

**Трек не скачивается**
→ YouTube мог заблокировать. yt-dlp обновляется: `pip install -U yt-dlp`

**Бот не отвечает**
→ Проверить токен в config.py
