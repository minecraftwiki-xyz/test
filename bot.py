#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
webshare_bot.py — Telegram Bot для webshare.io
ЛЕГКАЯ ВЕРСИЯ — использует только recaptcha.net bypass
БЕЗ тяжелых зависимостей (whisper, playwright, selenium)
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
import asyncio
import smtplib
from pathlib import Path
from datetime import datetime
from typing import Optional

# ══════════════════════════════════════════════════════════════
#  Конфигурация
# ══════════════════════════════════════════════════════════════

# Токен берется из переменной окружения BOT_TOKEN
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
#  Импорты с обработкой ошибок
# ══════════════════════════════════════════════════════════════

try:
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    TELEBOT_AVAILABLE = True
except ImportError:
    TELEBOT_AVAILABLE = False
    print("❌ telebot не установлен. Добавьте в requirements.txt: pyTelegramBotAPI")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("❌ requests не установлен. Добавьте в requirements.txt")

# ══════════════════════════════════════════════════════════════
#  Инициализация бота
# ══════════════════════════════════════════════════════════════

bot = TeleBot(BOT_TOKEN) if TELEBOT_AVAILABLE else None

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
    except:
        return True

def find_valid_gmail() -> str:
    for _ in range(20):
        email = gen_email()
        if check_gmail_exists(email):
            return email
        time.sleep(0.2)
    return gen_email()

# ══════════════════════════════════════════════════════════════
#  reCAPTCHA SOLVER: recaptcha.net bypass (ЛЕГКИЙ, без зависимостей)
# ══════════════════════════════════════════════════════════════

def solve_recaptcha() -> Optional[str]:
    """
    recaptcha.net bypass — НЕ ТРЕБУЕТ дополнительных пакетов!
    Работает только через requests
    """
    if not REQUESTS_AVAILABLE:
        return None
    
    try:
        co = base64.urlsafe_b64encode(b"https://proxy.webshare.io:443").decode().rstrip("=")
        base_url = "https://www.recaptcha.net"
        sitekey = WEBSHARE_SITEKEY
        
        logger.info("Solving captcha via recaptcha.net...")
        
        # Получаем версию
        resp = requests.get(
            f"{base_url}/recaptcha/api.js?render={sitekey}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10
        )
        version_match = re.search(r"releases/([^/]+)/recaptcha", resp.text)
        if not version_match:
            return None
        version = version_match.group(1)
        
        # Получаем anchor token
        anchor_url = f"{base_url}/recaptcha/api2/anchor?ar=1&k={sitekey}&co={co}&hl=en&v={version}&size=invisible"
        resp = requests.get(anchor_url, headers={"Referer": WEBSHARE_REGISTER_URL}, timeout=10)
        anchor_match = re.search(r'id="recaptcha-token"\s+value="([^"]+)"', resp.text)
        if not anchor_match:
            return None
        anchor_token = anchor_match.group(1)
        
        # Получаем rresp token
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
        rr_match = re.search(r'\["rresp","([^"]+)"', resp.text)
        if rr_match:
            token = rr_match.group(1)
            if len(token) > 30:
                logger.info("✅ recaptcha.net success!")
                return token
    except Exception as e:
        logger.error(f"recaptcha.net error: {e}")
    
    return None

# ══════════════════════════════════════════════════════════════
#  Регистрация на webshare.io
# ══════════════════════════════════════════════════════════════

def _api_headers(token: str = "") -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://proxy.webshare.io",
        "Referer": WEBSHARE_REGISTER_URL,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": f"Token {token}" if token else "",
    }

def register_account() -> Optional[dict]:
    if not REQUESTS_AVAILABLE:
        return None
    
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
                timeout=25
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
                if "recaptcha" in resp.text.lower() or "captcha" in resp.text.lower():
                    logger.warning("Captcha invalid")
                    continue
                if "suspicious" in resp.text.lower():
                    logger.warning("Suspicious email")
                    continue
                if "already" in resp.text.lower():
                    logger.warning("Email already used")
                    continue
                logger.warning(f"400 error: {resp.text[:100]}")
            
            else:
                logger.warning(f"Status {resp.status_code}: {resp.text[:100]}")
                
        except Exception as e:
            logger.error(f"Registration error: {e}")
        
        time.sleep(3 * attempt)
    
    return None

# ══════════════════════════════════════════════════════════════
#  Получение прокси
# ══════════════════════════════════════════════════════════════

def get_proxies(token: str, count: int = 10) -> list:
    if not REQUESTS_AVAILABLE:
        return []
    
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
#  Telegram Bot
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
    text = """🤖 *Webshare Proxy Bot* (Легкая версия)

⚡ *Метод решения:*
• recaptcha.net bypass (без дополнительных зависимостей)

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
            "• recaptcha.net bypass (быстрый, без зависимостей)",
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
    ║  🤖 Webshare Proxy Bot (ЛЕГКАЯ ВЕРСИЯ)                     ║
    ║  Использует recaptcha.net bypass — БЕЗ тяжелых зависимостей║
    ║  БЕСПЛАТНО — БЕЗ API КЛЮЧЕЙ                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    if not TELEBOT_AVAILABLE:
        print("❌ Ошибка: telebot не установлен!")
        print("📦 Добавьте в requirements.txt: pyTelegramBotAPI")
        sys.exit(1)
    
    print(f"✅ Токен: {BOT_TOKEN[:10]}...")
    print("✅ Метод решения: recaptcha.net bypass")
    print()
    print("🚀 Бот запущен!")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")        # Пытаемся импортировать playwright, если не установлен - устанавливаем
        try:
            import playwright
        except ImportError:
            print("📦 Устанавливаю playwright...")
            subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'playwright'])
        
        # Устанавливаем браузеры
        print("📦 Устанавливаю браузеры для Playwright (firefox, chromium)...")
        subprocess.check_call([
            sys.executable, '-m', 'playwright', 'install', 'firefox', 'chromium'
        ])
        print("✅ Playwright браузеры установлены!")
        return True
    except Exception as e:
        print(f"⚠️ Ошибка установки Playwright: {e}")
        print("ℹ️ Бот будет работать без методов, требующих Playwright")
        return False

# Запускаем установку браузеров при первом запуске
PLAYWRIGHT_INSTALLED = install_playwright_browsers()

# ══════════════════════════════════════════════════════════════
#  Конфигурация
# ══════════════════════════════════════════════════════════════
BOT_TOKEN = ""
WEBSHARE_SITEKEY = "6LeHZ6UUAAAAAKat_YS--O2tj_by3gv3r_l03j9d"
WEBSHARE_REGISTER_URL = "https://proxy.webshare.io/register"
API_BASE = "https://proxy.webshare.io/api/v2"
MAX_REG_TRIES = 3

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "webshare_accounts.json"
REG_COOLDOWN_FILE = BASE_DIR / "webshare_reg_cooldown.json"

# ══════════════════════════════════════════════════════════════
#  Импорты с обработкой ошибок
# ══════════════════════════════════════════════════════════════

try:
    from telebot import TeleBot
    from telebot.types import InlineKeyboardMarkup, InlineKeyboardButton
    TELEBOT_AVAILABLE = True
except ImportError:
    TELEBOT_AVAILABLE = False
    print("❌ telebot не установлен. Добавьте в requirements.txt: pyTelegramBotAPI")

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False
    print("❌ requests не установлен. Добавьте в requirements.txt")

# ══════════════════════════════════════════════════════════════
#  Проверка дополнительных зависимостей
# ══════════════════════════════════════════════════════════════

WHISPER_AVAILABLE = False
PLAYWRIGHT_AVAILABLE = False
PLAYWRIGHT_RECAPTCHA_AVAILABLE = False
SELENIUM_AVAILABLE = False
SPEECH_AVAILABLE = False
PYDUB_AVAILABLE = False
CURL_AVAILABLE = False

try:
    from faster_whisper import WhisperModel
    WHISPER_AVAILABLE = True
except:
    pass

try:
    from playwright.async_api import async_playwright
    PLAYWRIGHT_AVAILABLE = True
except:
    pass

try:
    from playwright_recaptcha import recaptchav2
    PLAYWRIGHT_RECAPTCHA_AVAILABLE = True
except:
    pass

try:
    from selenium import webdriver
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.common.keys import Keys
    SELENIUM_AVAILABLE = True
except:
    pass

try:
    import speech_recognition as sr
    SPEECH_AVAILABLE = True
except:
    pass

try:
    from pydub import AudioSegment
    PYDUB_AVAILABLE = True
except:
    pass

try:
    from curl_cffi.requests import AsyncSession
    CURL_AVAILABLE = True
except:
    pass

def check_ffmpeg():
    try:
        subprocess.run(['ffmpeg', '-version'], capture_output=True, check=True)
        return True
    except:
        return False

FFMPEG_AVAILABLE = check_ffmpeg()

# ══════════════════════════════════════════════════════════════
#  Инициализация бота
# ══════════════════════════════════════════════════════════════

bot = TeleBot(BOT_TOKEN) if TELEBOT_AVAILABLE else None

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
    except:
        return True

def find_valid_gmail() -> str:
    for _ in range(20):
        email = gen_email()
        if check_gmail_exists(email):
            return email
        time.sleep(0.2)
    return gen_email()

# ══════════════════════════════════════════════════════════════
#  МЕТОД 1: Whisper + Playwright (аудио+AI)
# ══════════════════════════════════════════════════════════════

async def solve_with_whisper_playwright() -> Optional[str]:
    if not (WHISPER_AVAILABLE and PLAYWRIGHT_AVAILABLE and FFMPEG_AVAILABLE):
        return None
    
    try:
        from faster_whisper import WhisperModel
        from playwright.async_api import async_playwright
        
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            await page.goto(WEBSHARE_REGISTER_URL, wait_until="networkidle")
            await page.wait_for_timeout(2000)
            
            iframes = await page.frame_locator('iframe[src*="recaptcha"]').all()
            if not iframes:
                return None
            
            frame = iframes[0] if len(iframes) == 1 else iframes[1]
            await frame.locator('#recaptcha-audio-button').click()
            await page.wait_for_timeout(3000)
            
            audio_path = None
            async def intercept(route):
                nonlocal audio_path
                resp = await route.fetch()
                body = await resp.body()
                if len(body) > 10000:
                    audio_path = tempfile.mktemp(suffix=".mp3")
                    with open(audio_path, "wb") as f:
                        f.write(body)
                await route.fulfill(response=resp)
            
            await page.route("**/*payload*", intercept)
            await page.route("**/*audio*", intercept)
            
            await frame.locator('.rc-audiochallenge-play-button button').click()
            await page.wait_for_timeout(5000)
            
            if not audio_path:
                return None
            
            wav_path = tempfile.mktemp(suffix=".wav")
            subprocess.run(
                ['ffmpeg', '-i', audio_path, '-acodec', 'pcm_s16le', '-ac', '1', '-ar', '16000', wav_path],
                check=True, capture_output=True
            )
            
            model = WhisperModel("tiny", device="cpu", compute_type="int8")
            segments, _ = model.transcribe(wav_path, language="en")
            answer = " ".join(s.text.strip() for s in segments)
            
            await frame.locator('#audio-response').fill(answer)
            await frame.locator('#recaptcha-verify-button').click()
            await page.wait_for_timeout(3000)
            
            token = await page.evaluate("document.querySelector('[name=\"g-recaptcha-response\"]')?.value || ''")
            
            os.unlink(audio_path)
            os.unlink(wav_path)
            await browser.close()
            
            if token and len(token) > 30:
                return token
    except:
        pass
    return None

# ══════════════════════════════════════════════════════════════
#  МЕТОД 2: Playwright Recaptcha Solver
# ══════════════════════════════════════════════════════════════

async def solve_with_playwright_recaptcha() -> Optional[str]:
    if not (PLAYWRIGHT_RECAPTCHA_AVAILABLE and PLAYWRIGHT_AVAILABLE):
        return None
    
    try:
        from playwright.async_api import async_playwright
        from playwright_recaptcha import recaptchav2
        
        async with async_playwright() as p:
            browser = await p.firefox.launch(headless=True)
            page = await browser.new_page()
            await page.goto(WEBSHARE_REGISTER_URL, wait_until="networkidle")
            
            async with recaptchav2.AsyncSolver(page) as solver:
                token = await solver.solve_recaptcha(wait=True)
                await browser.close()
                if token and len(token) > 30:
                    return token
    except:
        pass
    return None

# ══════════════════════════════════════════════════════════════
#  МЕТОД 3: recaptcha.net bypass
# ══════════════════════════════════════════════════════════════

async def solve_via_recaptcha_net() -> Optional[str]:
    if not REQUESTS_AVAILABLE:
        return None
    
    try:
        co = base64.urlsafe_b64encode(b"https://proxy.webshare.io:443").decode().rstrip("=")
        base_url = "https://www.recaptcha.net"
        sitekey = WEBSHARE_SITEKEY
        
        resp = requests.get(
            f"{base_url}/recaptcha/api.js?render={sitekey}",
            headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
            timeout=10
        )
        version_match = re.search(r"releases/([^/]+)/recaptcha", resp.text)
        if not version_match:
            return None
        version = version_match.group(1)
        
        anchor_url = f"{base_url}/recaptcha/api2/anchor?ar=1&k={sitekey}&co={co}&hl=en&v={version}&size=invisible"
        resp = requests.get(anchor_url, headers={"Referer": WEBSHARE_REGISTER_URL}, timeout=10)
        anchor_match = re.search(r'id="recaptcha-token"\s+value="([^"]+)"', resp.text)
        if not anchor_match:
            return None
        anchor_token = anchor_match.group(1)
        
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
        rr_match = re.search(r'\["rresp","([^"]+)"', resp.text)
        if rr_match:
            token = rr_match.group(1)
            if len(token) > 30:
                return token
    except:
        pass
    return None

# ══════════════════════════════════════════════════════════════
#  ГЛАВНЫЙ СОЛВЕР
# ══════════════════════════════════════════════════════════════

async def solve_captcha() -> Optional[str]:
    methods = [
        ("Whisper", solve_with_whisper_playwright),
        ("Playwright", solve_with_playwright_recaptcha),
        ("recaptcha.net", solve_via_recaptcha_net),
    ]
    
    for name, method in methods:
        try:
            token = await method()
            if token and len(token) > 30:
                return token
        except:
            pass
        await asyncio.sleep(1)
    
    return None

# ══════════════════════════════════════════════════════════════
#  Регистрация на webshare.io
# ══════════════════════════════════════════════════════════════

def _api_headers(token: str = "") -> dict:
    return {
        "Accept": "application/json",
        "Content-Type": "application/json",
        "Origin": "https://proxy.webshare.io",
        "Referer": WEBSHARE_REGISTER_URL,
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Authorization": f"Token {token}" if token else "",
    }

def register_account() -> Optional[dict]:
    if not REQUESTS_AVAILABLE:
        return None
    
    cooldown = _reg_cooldown_until()
    if cooldown > time.time():
        return None

    for attempt in range(1, MAX_REG_TRIES + 1):
        email = find_valid_gmail()
        password = gen_password()
        
        captcha_token = asyncio.run(solve_captcha())
        if not captcha_token:
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
                timeout=25
            )
            
            if resp.status_code in (200, 201):
                data = resp.json()
                token = data.get("token") or data.get("api_key")
                if token:
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
                return None
            
        except:
            pass
        
        time.sleep(3 * attempt)
    
    return None

# ══════════════════════════════════════════════════════════════
#  Получение прокси
# ══════════════════════════════════════════════════════════════

def get_proxies(token: str, count: int = 10) -> list:
    if not REQUESTS_AVAILABLE:
        return []
    
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
    except:
        pass
    return []

def get_free_proxies(count: int = 10) -> list:
    accounts = load_accounts()
    user_accounts = accounts.get("user_accounts", {})
    
    if "default" in user_accounts:
        acc = user_accounts["default"]
        token = acc.get("token")
        if token:
            proxies = get_proxies(token, count)
            if proxies:
                return proxies
    
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
#  Telegram Bot
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

⚡ *Методы решения:*
• Whisper+Playwright (аудио+AI)
• Playwright Recaptcha
• recaptcha.net bypass

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
            "⚙️ *Методы решения:*\n"
            "1. Whisper+Playwright\n"
            "2. Playwright Recaptcha\n"
            "3. recaptcha.net",
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
                "• Все методы капчи не сработали\n\n"
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
    ║  Использует ВСЕ методы решения reCAPTCHA                   ║
    ║  БЕСПЛАТНО — БЕЗ API КЛЮЧЕЙ                               ║
    ╚══════════════════════════════════════════════════════════════╝
    """)
    
    if not TELEBOT_AVAILABLE:
        print("❌ Ошибка: telebot не установлен!")
        print("📦 Добавьте в requirements.txt: pyTelegramBotAPI")
        sys.exit(1)
    
    print("✅ Методы решения:")
    print("  1. Whisper+Playwright (аудио+AI)")
    print("  2. Playwright Recaptcha")
    print("  3. recaptcha.net bypass")
    print()
    print("🚀 Бот запущен!")
    
    try:
        bot.infinity_polling()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")
