#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Proxy Bot — Бот для получения прокси с webshare.io
100% бесплатно, ручной ввод капчи
"""

import asyncio
import json
import os
import random
import re
import string
import time
import urllib.request
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime

import httpx
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, CallbackQueryHandler, ContextTypes, MessageHandler, filters

# ──────────────────────────────────────────────────────────────
#  НАСТРОЙКИ ИЗ ПЕРЕМЕННЫХ ОКРУЖЕНИЯ
# ──────────────────────────────────────────────────────────────

TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
if not TOKEN:
    raise ValueError("❌ TELEGRAM_BOT_TOKEN не найден в переменных окружения!")

WEBSHARE_RECAPTCHA_SITEKEY = "6LeHZ6UUAAAAAKat_YS--O2tj_by3gv3r_l03j9d"
WEBSHARE_REGISTER_URL = "https://proxy.webshare.io/register"
API_BASE = "https://proxy.webshare.io/api/v2"
MAX_REG_TRIES = 5

# ─── БОЛЬШОЙ СПИСОК АНГЛИЙСКИХ ИМЕН ─────────────────────────

_FIRST_NAMES = [
    "james", "john", "robert", "michael", "william", "david", "richard", "joseph", "thomas",
    "charles", "christopher", "daniel", "matthew", "anthony", "mark", "donald", "steven",
    "paul", "andrew", "joshua", "kenneth", "kevin", "brian", "timothy", "ronald", "edward",
    "jason", "jeffrey", "ryan", "jacob", "gary", "nicholas", "eric", "jonathan", "stephen",
    "larry", "justin", "scott", "brandon", "benjamin", "samuel", "raymond", "gregory",
    "frank", "alexander", "patrick", "jack", "dennis", "jerry", "tyler", "aaron", "jose",
    "nathan", "adam", "henry", "zachary", "todd", "willie", "sean", "billy", "chad",
    "carl", "dean", "elijah", "ethan", "gabriel", "harry", "ian", "isaac", "jordan",
    "logan", "luke", "max", "noah", "oliver", "owen", "peter", "philip", "ralph",
    "randy", "ruben", "seth", "shawn", "simon", "stanley", "stephen", "steve", "terry",
    "victor", "vincent", "warren", "wayne", "wesley", "willard", "winston", "xavier",
    "emma", "olivia", "ava", "isabella", "sophia", "mia", "charlotte", "amelia", "harper",
    "evelyn", "emily", "abigail", "ella", "elizabeth", "camila", "luna", "sofia", "avery",
    "mila", "aria", "scarlett", "victoria", "madison", "layla", "chloe", "penelope",
    "riley", "zoey", "nora", "lily", "eleanor", "hannah", "addison", "stella", "nova",
    "leah", "zara", "naomi", "eliana", "claire", "audrey", "julia", "sarah", "grace",
    "sophie", "lucy", "isla", "rose", "olivia", "emily", "ella", "ava", "mia", "charlotte",
    "amelia", "evelyn", "abigail", "harper", "elizabeth", "camila", "luna", "sofia", "avery",
    "millie", "amber", "paige", "brooke", "maria", "megan", "alice", "jane", "mary", "kate",
    "linda", "barbara", "carol", "jennifer", "lisa", "susan", "jessica", "karen", "sandra",
    "nancy", "betty", "helen", "kimberly", "anna", "ruth", "joan", "frances", "judy", "victoria",
    "joyce", "diane", "martha", "teresa", "catherine", "carolyn", "janet", "kathleen", "laura"
]

# ─── БОЛЬШОЙ СПИСОК АНГЛИЙСКИХ ФАМИЛИЙ ──────────────────────

_LAST_NAMES = [
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller", "davis", "wilson",
    "moore", "taylor", "anderson", "thomas", "jackson", "white", "harris", "martin", "thompson",
    "young", "allen", "king", "wright", "scott", "torres", "nguyen", "hill", "flores", "green",
    "adams", "nelson", "baker", "hall", "rivera", "campbell", "mitchell", "carter", "roberts",
    "turner", "phillips", "evans", "collins", "edwards", "stewart", "morris", "murphy", "cook",
    "rogers", "morgan", "peterson", "cooper", "reed", "bailey", "bell", "howard", "ward",
    "cox", "diaz", "richardson", "wood", "watson", "brooks", "bennett", "gray", "james",
    "reyes", "cruz", "hughes", "price", "myers", "long", "foster", "sanders", "ross",
    "powell", "sullivan", "russell", "ortiz", "jenkins", "perry", "butler", "barnes",
    "fisher", "henderson", "coleman", "simmons", "patterson", "jordan", "reynolds", "hamilton",
    "graham", "kim", "gonzalez", "alexander", "ramos", "wallace", "griffin", "west", "cole",
    "hayes", "chavez", "gibson", "bryant", "ellis", "stevens", "murray", "ford", "marshall",
    "owens", "mcdonald", "harrison", "ruiz", "kennedy", "wells", "alvarez", "wood", "mendoza",
    "castillo", "olsen", "webb", "simpson", "stevenson", "carroll", "frazier", "snyder",
    "burns", "mccarthy", "willis", "schmidt", "riley", "mills", "wilkins", "bates", "daniels",
    "williamson", "johnston", "bryant", "jensen", "armstrong", "porter", "bradley", "flores",
    "hunt", "stone", "dixon", "graham", "shaw", "reynolds", "jordan", "freeman", "cross",
    "weaver", "dunn", "harvey", "spencer", "carpenter", "weaver", "riley", "harper", "fox",
    "lopez", "martinez", "fernandez", "gonzales", "santos", "chavez", "ruiz", "diaz", "ramos",
    "perez", "reyes", "gutierrez", "ortega", "silva", "mendoza", "castillo", "gomez", "cruz"
]

# ─── ДОМЕНЫ EMAIL ─────────────────────────────────────────────

_EMAIL_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com", "icloud.com", "mail.com", "protonmail.com"]

# ─── ФАЙЛЫ ────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "webshare_accounts.json"
REG_COOLDOWN_FILE = BASE_DIR / "webshare_reg_cooldown.json"
USER_STATES_FILE = BASE_DIR / "user_states.json"

# ─── СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ────────────────────────────────

USER_STATES: Dict[int, Dict[str, Any]] = {}

def load_user_states() -> Dict[int, Dict[str, Any]]:
    """Загружает состояния пользователей"""
    if USER_STATES_FILE.exists():
        try:
            with open(USER_STATES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            return {}
    return {}

def save_user_states():
    """Сохраняет состояния пользователей"""
    try:
        with open(USER_STATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(USER_STATES, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ
# ──────────────────────────────────────────────────────────────

def gen_username() -> str:
    """Генерирует username по разным паттернам"""
    patterns = [
        lambda: f"{random.choice(_FIRST_NAMES)}.{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_FIRST_NAMES)}{random.randint(1, 9999)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}_{random.randint(1, 999)}",
        lambda: f"{random.choice(_FIRST_NAMES)[0]}{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_LAST_NAMES)}{random.randint(1, 9999)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}_{random.randint(2000, 2024)}",
    ]
    return random.choice(patterns)()

def gen_email() -> str:
    return f"{gen_username()}@{random.choice(_EMAIL_DOMAINS)}"

def gen_password() -> str:
    chars = (random.choices(string.ascii_uppercase, k=3) + 
             random.choices(string.ascii_lowercase, k=random.randint(6, 9)) +
             random.choices(string.digits, k=4) + 
             random.choices("!@#$%^&*", k=3))
    random.shuffle(chars)
    return "".join(chars)

def load_accounts() -> dict:
    if ACCOUNTS_FILE.exists():
        try:
            data = json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
            if "user_accounts" not in data:
                data["user_accounts"] = {}
            return data
        except Exception:
            pass
    return {"accounts": [], "user_accounts": {}}

def save_accounts(data: dict) -> None:
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _reg_cooldown_until() -> float:
    try:
        d = json.loads(REG_COOLDOWN_FILE.read_text(encoding="utf-8"))
        return float(d.get("until", 0))
    except Exception:
        return 0.0

def _set_reg_cooldown(seconds: int) -> None:
    until = time.time() + seconds + 10
    REG_COOLDOWN_FILE.write_text(json.dumps({"until": until}), encoding="utf-8")

def _api_headers(token: str = "") -> dict:
    h = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://proxy.webshare.io",
        "Referer": "https://proxy.webshare.io/register",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    }
    if token:
        h["Authorization"] = f"Token {token}"
    return h

def _smtp_check_gmail(email: str) -> bool | None:
    try:
        import smtplib
        with smtplib.SMTP("aspmx.l.google.com", 25, timeout=3) as smtp:
            smtp.ehlo("check.example.com")
            smtp.mail("")
            code, _ = smtp.rcpt(str(email))
            return code == 250
    except Exception:
        return None

async def check_email_exists(email: str) -> bool:
    smtp_result = await asyncio.to_thread(_smtp_check_gmail, email)
    if smtp_result is not None:
        return smtp_result
    return True

async def find_valid_email(max_tries: int = 30) -> str:
    for _ in range(max_tries):
        email = gen_email()
        if await check_email_exists(email):
            return email
        await asyncio.sleep(0.3)
    return gen_email()

async def validate_token(token: str) -> bool:
    try:
        async with httpx.AsyncClient(timeout=12) as client:
            resp = await client.get(
                f"{API_BASE}/proxy/list/",
                params={"mode": "direct", "page": 1, "page_size": 1},
                headers=_api_headers(token)
            )
            return resp.status_code == 200
    except Exception:
        return False

async def fetch_proxies(token: str, count: int = 10) -> list[str]:
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            resp = await client.get(
                f"{API_BASE}/proxy/list/",
                params={"mode": "direct", "page": 1, "page_size": max(count, 25)},
                headers=_api_headers(token)
            )
            if resp.status_code == 200:
                results = resp.json().get("results", [])
                proxies = []
                for p in results:
                    user, pw = p.get("username", ""), p.get("password", "")
                    host, port = p.get("proxy_address", ""), p.get("port", 80)
                    if user and pw and host and port:
                        proxies.append(f"{host}:{port}:{user}:{pw}")
                        if len(proxies) >= count:
                            break
                return proxies
    except Exception:
        pass
    return []

# ──────────────────────────────────────────────────────────────
#  РЕГИСТРАЦИЯ АККАУНТА
# ──────────────────────────────────────────────────────────────

class _RateLimitedError(Exception):
    pass

class _AlreadyRegisteredError(Exception):
    pass

async def _register_once(email: str, captcha_token: str) -> dict | None:
    password = gen_password()
    
    payload = {
        "email": email,
        "password": password,
        "recaptcha": captcha_token,
        "tos_accepted": True,
        "marketing_email_accepted": False,
    }
    
    try:
        async with httpx.AsyncClient(timeout=25) as client:
            resp = await client.post(
                f"{API_BASE}/register/",
                json=payload,
                headers=_api_headers()
            )
            
            if resp.status_code in (200, 201):
                data = resp.json()
                api_token = data.get("token") or data.get("api_key") or ""
                if api_token:
                    return {
                        "email": email,
                        "password": password,
                        "token": api_token,
                        "registered_at": int(time.time()),
                        "last_used": 0,
                        "proxy_count": 0
                    }
            elif resp.status_code == 400:
                body = resp.text.lower()
                if "already" in body or "exists" in body:
                    raise _AlreadyRegisteredError()
            elif resp.status_code == 429:
                _set_reg_cooldown(700)
                raise _RateLimitedError()
    except Exception:
        pass
    return None

# ──────────────────────────────────────────────────────────────
#  ТЕЛЕГРАМ БОТ
# ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start"""
    user_id = update.effective_user.id
    
    # Загружаем состояния
    global USER_STATES
    USER_STATES = load_user_states()
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    keyboard = [
        [InlineKeyboardButton("📥 Получить прокси", callback_data="get_proxies")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 *Добро пожаловать в Proxy Bot!*\n\n"
        "Я помогаю получать бесплатные прокси с webshare.io.\n\n"
        "📌 *Как это работает:*\n"
        "1. Нажми «Получить прокси»\n"
        "2. Реши капчу вручную в браузере\n"
        "3. Вставь токен в бота\n"
        "4. Получи прокси!\n\n"
        "⚠️ *Всё абсолютно бесплатно!*"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик кнопок"""
    query = update.callback_query
    await query.answer()
    
    user_id = update.effective_user.id
    
    if query.data == "get_proxies":
        await get_proxies_start(update, context)
    elif query.data == "stats":
        await show_stats(update, context)
    elif query.data == "help":
        await show_help(update, context)
    elif query.data == "cancel":
        await cancel_operation(update, context)

async def get_proxies_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Начало получения прокси"""
    user_id = update.effective_user.id
    
    # Проверяем состояние
    if user_id in USER_STATES and USER_STATES[user_id].get("waiting_for_token"):
        await update.callback_query.edit_message_text(
            "⏳ У вас уже есть активный процесс. Введите токен капчи."
        )
        return
    
    # Создаем состояние
    USER_STATES[user_id] = {
        "waiting_for_token": True,
        "step": "waiting_token"
    }
    save_user_states()
    
    # Инструкция
    instruction = (
        "🔐 *Для получения прокси нужно решить капчу вручную*\n\n"
        "📋 *Инструкция:*\n"
        "1. Открой браузер и перейди по ссылке:\n"
        f"`{WEBSHARE_REGISTER_URL}`\n"
        "2. Найди reCAPTCHA и реши её (нажми «Я не робот»)\n"
        "3. Открой инструменты разработчика (F12)\n"
        "4. Перейди на вкладку Console\n"
        "5. Вставь команду и нажми Enter:\n"
        "`document.querySelector('[name=g-recaptcha-response]').value`\n"
        "6. Скопируй полученную длинную строку (токен)\n"
        "7. *Вставь токен в сообщение этому боту*\n\n"
        "⏳ Токен действителен ~2 минуты\n"
        "❌ Для отмены отправь /cancel"
    )
    
    await update.callback_query.edit_message_text(
        instruction,
        parse_mode="Markdown"
    )

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка введенного токена"""
    user_id = update.effective_user.id
    token_text = update.message.text.strip()
    
    # Проверяем состояние
    if user_id not in USER_STATES or not USER_STATES[user_id].get("waiting_for_token"):
        await update.message.reply_text(
            "❌ У вас нет активного процесса.\n"
            "Нажми /start и выбери «Получить прокси»"
        )
        return
    
    if len(token_text) < 30:
        await update.message.reply_text(
            "❌ Токен слишком короткий! Попробуй еще раз.\n"
            "Отправь /cancel чтобы отменить."
        )
        return
    
    await update.message.reply_text(
        "⏳ Проверяю токен и регистрирую аккаунт..."
    )
    
    # Ищем валидный email
    email = await find_valid_email()
    await update.message.reply_text(f"📧 Использую email: `{email}`", parse_mode="Markdown")
    
    # Регистрируем аккаунт
    try:
        account = await _register_once(email, token_text)
        
        if account:
            # Получаем прокси
            await update.message.reply_text("⏳ Получаю прокси...")
            await asyncio.sleep(2)
            
            proxies = await fetch_proxies(account["token"], count=10)
            
            if proxies:
                # Форматируем прокси
                proxy_text = "\n".join([f"`{p}`" for p in proxies[:10]])
                
                # Сохраняем аккаунт
                accounts_data = load_accounts()
                accounts_data["accounts"].append(account)
                save_accounts(accounts_data)
                
                # Очищаем состояние
                USER_STATES[user_id] = {}
                save_user_states()
                
                await update.message.reply_text(
                    f"✅ *Получено {len(proxies)} прокси!*\n\n"
                    f"{proxy_text}\n\n"
                    "💾 Прокси сохранены в формате: `ip:port:username:password`\n"
                    "📌 Используй /start для новых прокси",
                    parse_mode="Markdown"
                )
            else:
                await update.message.reply_text(
                    "❌ Аккаунт создан, но не удалось получить прокси.\n"
                    "Попробуй позже или используй /start для новой попытки."
                )
        else:
            await update.message.reply_text(
                "❌ Не удалось зарегистрировать аккаунт.\n"
                "Возможно токен устарел или email уже используется.\n"
                "Используй /start для новой попытки."
            )
            
    except _AlreadyRegisteredError:
        await update.message.reply_text(
            "❌ Email уже используется. Попробуй еще раз."
        )
    except _RateLimitedError:
        await update.message.reply_text(
            "⚠️ Слишком много запросов! Попробуй через 10-15 минут."
        )
    except Exception as e:
        await update.message.reply_text(f"❌ Ошибка: {str(e)}")
    
    # Очищаем состояние если что-то пошло не так
    if user_id in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает статистику"""
    accounts_data = load_accounts()
    total_accounts = len(accounts_data.get("accounts", []))
    user_accounts = len(accounts_data.get("user_accounts", {}))
    
    stats_text = (
        f"📊 *Статистика бота*\n\n"
        f"📦 Всего аккаунтов: {total_accounts + user_accounts}\n"
        f"👤 Пользовательских: {user_accounts}\n"
        f"📋 В общем пуле: {total_accounts}\n\n"
        f"🔄 Активных процессов: {len([u for u in USER_STATES.values() if u.get('waiting_for_token')])}"
    )
    
    await update.callback_query.edit_message_text(
        stats_text,
        parse_mode="Markdown"
    )

async def show_help(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показывает помощь"""
    help_text = (
        "❓ *Помощь*\n\n"
        "🤖 *Команды:*\n"
        "/start - Главное меню\n"
        "/cancel - Отменить текущую операцию\n"
        "/stats - Показать статистику\n\n"
        "📌 *Как получить прокси:*\n"
        "1. Нажми «Получить прокси»\n"
        "2. Реши капчу вручную в браузере\n"
        "3. Вставь токен в бота\n"
        "4. Получи прокси\n\n"
        "⚠️ *Бот работает полностью бесплатно!*\n"
        "💡 Токен нужно вводить при каждом запросе."
    )
    
    await update.callback_query.edit_message_text(
        help_text,
        parse_mode="Markdown"
    )

async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Отмена операции"""
    user_id = update.effective_user.id
    
    if user_id in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    await update.callback_query.edit_message_text(
        "✅ Операция отменена.\n"
        "Используй /start для нового запроса."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /cancel"""
    user_id = update.effective_user.id
    
    if user_id in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    await update.message.reply_text(
        "✅ Операция отменена.\n"
        "Используй /start для нового запроса."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /stats"""
    accounts_data = load_accounts()
    total_accounts = len(accounts_data.get("accounts", []))
    user_accounts = len(accounts_data.get("user_accounts", {}))
    
    stats_text = (
        f"📊 *Статистика*\n\n"
        f"📦 Всего аккаунтов: {total_accounts + user_accounts}\n"
        f"👤 Пользовательских: {user_accounts}\n"
        f"📋 В общем пуле: {total_accounts}"
    )
    
    await update.message.reply_text(stats_text, parse_mode="Markdown")

# ──────────────────────────────────────────────────────────────
#  ЗАПУСК БОТА
# ──────────────────────────────────────────────────────────────

def main():
    """Запуск бота"""
    # Создаем приложение
    application = Application.builder().token(TOKEN).build()
    
    # Регистрируем обработчики
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token))
    
    # Загружаем состояния при старте
    global USER_STATES
    USER_STATES = load_user_states()
    
    print("🤖 Бот запущен!")
    print(f"📊 Загружено состояний: {len(USER_STATES)}")
    print("🚀 Нажми Ctrl+C для остановки")
    
    # Запускаем бота
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()