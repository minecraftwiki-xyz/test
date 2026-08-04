#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webshare_bot.py — Telegram Bot для webshare.io
Токен берется из переменной окружения BOT_TOKEN
"""
import sys
import io
import json
import os
import re
import time
import random
import string
import base64
import logging
import smtplib
from pathlib import Path
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════════════════════════
#  Конфигурация
# ══════════════════════════════════════════════════════════════

BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    print("❌ Ошибка: BOT_TOKEN не найден в переменных окружения!")
    print("Установите: export BOT_TOKEN='ваш_токен'")
    sys.exit(1)

WEBSHARE_SITEKEY = "6LeHZ6UUAAAAAKat_YS--O2tj_by3gv3r_l03j9d"
WEBSHARE_REGISTER_URL = "https://proxy.webshare.io/register"
API_BASE = "https://proxy.webshare.io/api/v2"
MAX_REG_TRIES = 3

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "webshare_accounts.json"
REG_COOLDOWN_FILE = BASE_DIR / "webshare_reg_cooldown.json"

# ══════════════════════════════════════════════════════════════
#  Логирование
# ══════════════════════════════════════════════════════════════

logging.basicConfig(
    format='%(asctime)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# ══════════════════════════════════════════════════════════════
#  Импорты
# ══════════════════════════════════════════════════════════════

try:
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    TELEBOT_AVAILABLE = True
except ImportError:
    TELEBOT_AVAILABLE = False
    print("❌ telebot не установлен. Добавьте в requirements.txt: pyTelegramBotAPI")
    sys.exit(1)

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("❌ requests не установлен. Добавьте в requirements.txt")
    sys.exit(1)

# ══════════════════════════════════════════════════════════════
#  Инициализация бота
# ══════════════════════════════════════════════════════════════

bot = TeleBot(BOT_TOKEN)

# ══════════════════════════════════════════════════════════════
#  Account helpers
# ══════════════════════════════════════════════════════════════

def load_accounts() -> dict:
    if ACCOUNTS_FILE.exists():
        try:
            return json.loads(ACCOUNTS_FILE.read_text(encoding="utf-8"))
        except:
            pass
    return {"user_accounts": {}}

def save_accounts(data: dict) -> None:
    ACCOUNTS_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")

def _reg_cooldown_until() -> float:
    if REG_COOLDOWN_FILE.exists():
        try:
            return json.loads(REG_COOLDOWN_FILE.read_text()).get("until", 0)
        except:
            pass
    return 0.0

def _set_reg_cooldown(seconds: int) -> None:
    REG_COOLDOWN_FILE.write_text(json.dumps({"until": time.time() + seconds + 10}))

# ══════════════════════════════════════════════════════════════
#  Генераторы
# ══════════════════════════════════════════════════════════════

_FIRST_NAMES = [
    "james", "john", "robert", "michael", "william", "david", "richard",
    "joseph", "thomas", "charles", "emma", "olivia", "ava", "isabella",
    "sophia", "mia", "charlotte", "amelia", "harper", "evelyn"
]
_LAST_NAMES = [
    "smith", "johnson", "williams", "brown", "jones", "garcia", "miller",
    "davis", "wilson", "moore", "taylor", "anderson", "thomas", "jackson"
]

def gen_email() -> str:
    first = random.choice(_FIRST_NAMES)
    last = random.choice(_LAST_NAMES)
    sep = random.choice([".", "_", ""])
    suffix = random.choice(["", str(random.randint(1, 99)), str(random.randint(1970, 2005))])
    return f"{first}{sep}{last}{suffix}@gmail.com"

def gen_password() -> str:
    chars = (
        random.choices(string.ascii_uppercase, k=3) +
        random.choices(string.ascii_lowercase, k=random.randint(6, 8)) +
        random.choices(string.digits, k=3) +
        random.choices("!@#$%^*()", k=2)
    )
    random.shuffle(chars)
    return "".join(chars)

# ══════════════════════════════════════════════════════════════
#  Проверка Gmail
# ══════════════════════════════════════════════════════════════

def check_gmail_exists(email: str) -> bool:
    try:
        with smtplib.SMTP("aspmx.l.google.com", 25, timeout=5) as smtp:
            smtp.ehlo("check.example.com")
            smtp.mail("")
            code, _ = smtp.rcpt(email)
            return code == 250
    except Exception as e:
        logger.debug(f"SMTP check failed: {e}")
        return True

def find_valid_gmail() -> str:
    for _ in range(20):
        email = gen_email()
        if check_gmail_exists(email):
            return email
        time.sleep(0.2)
    return gen_email()

# ══════════════════════════════════════════════════════════════
#  reCAPTCHA SOLVER: recaptcha.net bypass
# ══════════════════════════════════════════════════════════════

def solve_recaptcha() -> Optional[str]:
    """
    recaptcha.net bypass — работает через requests
    """
    try:
        co = base64.urlsafe_b64encode(b"https://proxy.webshare.io:443").decode().rstrip("=")
        base_url = "https://www.recaptcha.net"
        sitekey = WEBSHARE_SITEKEY
        
        logger.info("Solving captcha via recaptcha.net...")
        
        # 1. Получаем версию
        resp = requests.get(
            f"{base_url}/recaptcha/api.js?render={sitekey}",
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
                "Accept-Language": "en-US,en;q=0.9",
            },
            timeout=10
        )
        version_match = re.search(r"releases/([^/]+)/recaptcha", resp.text)
        if not version_match:
            logger.warning("Could not get version")
            return None
        version = version_match.group(1)
        
        # 2. Получаем anchor token
        anchor_url = f"{base_url}/recaptcha/api2/anchor?ar=1&k={sitekey}&co={co}&hl=en&v={version}&size=invisible"
        resp = requests.get(
            anchor_url,
            headers={
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
                "Referer": WEBSHARE_REGISTER_URL,
            },
            timeout=10
        )
        anchor_match = re.search(r'id="recaptcha-token"\s+value="([^"]+)"', resp.text)
        if not anchor_match:
            logger.warning("Could not get anchor token")
            return None
        anchor_token = anchor_match.group(1)
        
        # 3. Получаем rresp token
        reload_url = f"{base_url}/recaptcha/api2/reload?k={sitekey}"
        data = {
            "v": version,
            "reason": "q",
            "c": anchor_token,
            "k": sitekey,
            "co": co,
            "hl": "en",
            "size": "invisible",
        }
        resp = requests.post(
            reload_url,
            data=data,
            headers={
                "Content-Type": "application/x-www-form-urlencoded",
                "Referer": anchor_url,
                "Origin": base_url,
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            },
            timeout=15
        )
        
        # Ищем rresp в ответе
        rr_match = re.search(r'\["rresp","([^"]+)"', resp.text)
        if rr_match:
            token = rr_match.group(1)
            if len(token) > 30:
                logger.info("✅ recaptcha.net success!")
                return token
        
        # Пробуем другой паттерн
        rr_match = re.search(r'"rresp","([^"]+)"', resp.text)
        if rr_match:
            token = rr_match.group(1)
            if len(token) > 30:
                logger.info("✅ recaptcha.net success!")
                return token
            
    except Exception as e:
        logger.error(f"recaptcha.net error: {e}")
    
    return None

# ══════════════════════════════════════════════════════════════
#  API headers
# ══════════════════════════════════════════════════════════════

def _api_headers(token: str = "") -> dict:
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Content-Type": "application/json",
        "Origin": "https://proxy.webshare.io",
        "Referer": WEBSHARE_REGISTER_URL,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
        "Accept-Language": "en-US,en;q=0.9",
    }
    if token:
        headers["Authorization"] = f"Token {token}"
    return headers

# ══════════════════════════════════════════════════════════════
#  Регистрация на webshare.io
# ══════════════════════════════════════════════════════════════

def register_account() -> Optional[dict]:
    cooldown = _reg_cooldown_until()
    if cooldown > time.time():
        remaining = int(cooldown - time.time())
        logger.warning(f"Rate limited for {remaining}s")
        return None

    for attempt in range(1, MAX_REG_TRIES + 1):
        logger.info(f"Registration attempt {attempt}/{MAX_REG_TRIES}")
        
        email = find_valid_gmail()
        password = gen_password()
        
        captcha_token = solve_recaptcha()
        if not captcha_token:
            logger.warning("No captcha token, retrying...")
            time.sleep(2)
            continue
        
        payload = {
            "email": email,
            "password": password,
            "recaptcha": captcha_token,
            "tos_accepted": True,
            "marketing_email_accepted": False,
        }
        
        try:
            resp = requests.post(
                f"{API_BASE}/register/",
                json=payload,
                headers=_api_headers(),
                timeout=30
            )
            
            if resp.status_code in (200, 201):
                data = resp.json()
                token = data.get("token") or data.get("api_key")
                if token:
                    logger.info(f"✅ Registered: {email}")
                    return {
                        "email": email,
                        "password": password,
                        "token": token,
                        "registered_at": int(time.time()),
                        "last_used": 0,
                        "proxy_count": 0,
                    }
            
            elif resp.status_code == 429:
                _set_reg_cooldown(700)
                logger.error("Rate limited (700s)")
                return None
            
            elif resp.status_code == 400:
                body = resp.text.lower()
                if "recaptcha" in body or "captcha" in body:
                    logger.warning("Captcha invalid")
                    continue
                if "suspicious" in body:
                    logger.warning("Suspicious email")
                    continue
                if "already" in body or "exists" in body:
                    logger.warning("Email already used")
                    continue
                logger.warning(f"400 error: {resp.text[:100]}")
            
            else:
                logger.warning(f"Status {resp.status_code}: {resp.text[:100]}")
                
        except requests.exceptions.Timeout:
            logger.error("Timeout")
        except Exception as e:
            logger.error(f"Registration error: {e}")
        
        time.sleep(3 * attempt)
    
    return None

# ══════════════════════════════════════════════════════════════
#  Получение прокси
# ══════════════════════════════════════════════════════════════

def get_proxies(token: str, count: int = 10) -> list:
    try:
        resp = requests.get(
            f"{API_BASE}/proxy/list/",
            params={"mode": "direct", "page": 1, "page_size": max(count, 25)},
            headers=_api_headers(token),
            timeout=20
        )
        if resp.status_code == 200:
            proxies = []
            for p in resp.json().get("results", []):
                user, pw = p.get("username", ""), p.get("password", "")
                host, port = p.get("proxy_address", ""), p.get("port", 80)
                if user and pw and host and port:
                    proxies.append(f"{host}:{port}:{user}:{pw}")
                    if len(proxies) >= count:
                        break
            return proxies
    except Exception as e:
        logger.error(f"Fetch error: {e}")
    return []

def get_free_proxies(count: int = 10) -> list:
    accounts = load_accounts()
    user_accounts = accounts.get("user_accounts", {})
    
    # Пробуем существующий аккаунт
    if "default" in user_accounts:
        acc = user_accounts["default"]
        token = acc.get("token")
        if token:
            proxies = get_proxies(token, count)
            if proxies:
                return proxies
    
    # Регистрируем новый
    new_acc = register_account()
    if new_acc:
        time.sleep(3)
        proxies = get_proxies(new_acc["token"], count)
        if proxies:
            user_accounts["default"] = new_acc
            save_accounts(accounts)
            return proxies
    
    return []

# ══════════════════════════════════════════════════════════════
#  Telegram Bot Handlers
# ══════════════════════════════════════════════════════════════

def main_keyboard():
    keyboard = InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        InlineKeyboardButton("🔄 Получить прокси", callback_data="get"),
        InlineKeyboardButton("📊 Статус", callback_data="status"),
        InlineKeyboardButton("🗑 Сбросить", callback_data="reset"),
        InlineKeyboardButton("📝 Помощь", callback_data="help")
    )
    return keyboard

@bot.message_handler(commands=['start', 'help'])
def send_welcome(message):
    text = """🤖 *Webshare Proxy Bot*

⚡ *Метод решения:*
• recaptcha.net bypass (без зависимостей)

📌 *Команды:*
/get — Получить прокси
/status — Статус аккаунта
/reset — Сбросить аккаунт
/help — Помощь"""
    
    bot.send_message(
        message.chat.id,
        text,
        parse_mode="Markdown",
        reply_markup=main_keyboard()
    )

@bot.message_handler(commands=['get'])
def get_command(message):
    bot.send_message(message.chat.id, "⏳ *Получение прокси...*", parse_mode="Markdown")
    process_get_proxies(message.chat.id)

@bot.message_handler(commands=['status'])
def status_command(message):
    send_status(message.chat.id)

@bot.message_handler(commands=['reset'])
def reset_command(message):
    reset_account(message.chat.id)

@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    if call.data == "get":
        bot.answer_callback_query(call.id, "⏳ Начинаю...")
        bot.send_message(call.message.chat.id, "⏳ *Получение прокси...*", parse_mode="Markdown")
        process_get_proxies(call.message.chat.id)
    elif call.data == "status":
        send_status(call.message.chat.id)
        bot.answer_callback_query(call.id)
    elif call.data == "reset":
        reset_account(call.message.chat.id)
        bot.answer_callback_query(call.id)
    elif call.data == "help":
        bot.edit_message_text(
            "📝 *Помощь*\n\n"
            "🔹 /get — Получить прокси\n"
            "🔹 /status — Статус аккаунта\n"
            "🔹 /reset — Сбросить аккаунт\n\n"
            "⚙️ *Метод решения:*\n"
            "• recaptcha.net bypass",
            call.message.chat.id,
            call.message.message_id,
            parse_mode="Markdown",
            reply_markup=main_keyboard()
        )
        bot.answer_callback_query(call.id)

def process_get_proxies(chat_id):
    try:
        bot.send_message(chat_id, "🔄 *Регистрация...*", parse_mode="Markdown")
        proxies = get_free_proxies(10)
        
        if proxies:
            text = f"✅ *Получено {len(proxies)} прокси!*\n\n```\n"
            for i, p in enumerate(proxies, 1):
                parts = p.split(":")
                if len(parts) == 4:
                    text += f"{i:2}. {parts[0]}:{parts[1]}  ({parts[2]}:****)\n"
            text += "```"
            bot.send_message(chat_id, text, parse_mode="Markdown")
            
            import io
            bot.send_document(
                chat_id,
                ("proxies.txt", io.StringIO("\n".join(proxies)).getvalue()),
                caption="📁 *Список прокси*",
                parse_mode="Markdown"
            )
        else:
            bot.send_message(
                chat_id,
                "❌ *Не удалось получить прокси.*\n\n"
                "Возможные причины:\n"
                "• Лимит регистраций (подождите 10-15 минут)\n"
                "• recaptcha.net не сработал\n\n"
                "Попробуйте позже",
                parse_mode="Markdown",
                reply_markup=main_keyboard()
            )
    except Exception as e:
        bot.send_message(chat_id, f"❌ *Ошибка:* {str(e)}", parse_mode="Markdown")

def send_status(chat_id):
    accounts = load_accounts()
    user_accounts = accounts.get("user_accounts", {})
    
    if "default" in user_accounts:
        acc = user_accounts["default"]
        text = "📊 *Статус*\n\n"
        text += f"📧 Email: `{acc.get('email', '?')}`\n"
        text += f"🔢 Прокси: `{acc.get('proxy_count', 0)}`\n"
        last = acc.get('last_used', 0)
        if last:
            text += f"🕐 Использован: `{datetime.fromtimestamp(last).strftime('%Y-%m-%d %H:%M')}`"
    else:
        text = "📊 *Нет аккаунтов*"
    
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_keyboard())

def reset_account(chat_id):
    if ACCOUNTS_FILE.exists():
        ACCOUNTS_FILE.unlink()
        text = "🗑 *Аккаунт сброшен!*"
    else:
        text = "🗑 *Нет аккаунтов*"
    bot.send_message(chat_id, text, parse_mode="Markdown", reply_markup=main_keyboard())

# ══════════════════════════════════════════════════════════════
#  Запуск
# ══════════════════════════════════════════════════════════════

if __name__ == "__main__":
    print("""
    ╔══════════════════════════════════════════════════════════════╗
    ║  🤖 Webshare Proxy Bot                                      ║
    ║  recaptcha.net bypass — БЕЗ тяжелых зависимостей          ║
    ║  БЕСПЛАТНО — БЕЗ API КЛЮЧЕЙ                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    print(f"✅ Токен: {BOT_TOKEN[:10]}...")
    print("✅ Метод: recaptcha.net bypass")
    print()
    print("🚀 Бот запущен!")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
