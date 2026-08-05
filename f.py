#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Telegram Proxy Bot — Бот для получения прокси с webshare.io и парсинга публичных прокси
100% бесплатно, асинхронная обработка
"""

import asyncio
import json
import os
import random
import re
import string
import time
from pathlib import Path
from typing import Optional, Dict, Any, List, Tuple
from io import BytesIO
import socket
import urllib.request
from collections import defaultdict

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
PROXY_CHECK_TIMEOUT = 5
MAX_PROXY_CHECK_THREADS = 30

# ─── ДОМЕНЫ ДЛЯ EMAIL ─────────────────────────────────────────

_EMAIL_DOMAINS = ["gmail.com", "outlook.com", "hotmail.com", "yahoo.com"]

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
    "nancy", "betty", "helen", "kimberly", "anna", "ruth", "joan", "frances", "judy", "victoria"
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

# ─── ФАЙЛЫ ────────────────────────────────────────────────────

BASE_DIR = Path(__file__).parent
ACCOUNTS_FILE = BASE_DIR / "webshare_accounts.json"
REG_COOLDOWN_FILE = BASE_DIR / "webshare_reg_cooldown.json"
USER_STATES_FILE = BASE_DIR / "user_states.json"

# ─── СОСТОЯНИЯ ПОЛЬЗОВАТЕЛЕЙ ────────────────────────────────

USER_STATES: Dict[int, Dict[str, Any]] = {}

def load_user_states() -> Dict[int, Dict[str, Any]]:
    if USER_STATES_FILE.exists():
        try:
            with open(USER_STATES_FILE, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return {int(k): v for k, v in data.items()}
        except Exception:
            return {}
    return {}

def save_user_states():
    try:
        with open(USER_STATES_FILE, 'w', encoding='utf-8') as f:
            json.dump(USER_STATES, f, indent=2, ensure_ascii=False)
    except Exception:
        pass

# ──────────────────────────────────────────────────────────────
#  ПАРСИНГ ПРОКСИ С САЙТОВ
# ──────────────────────────────────────────────────────────────

PROXY_SOURCES = {
    "http": [
        "https://free-proxy-list.net/",
        "https://www.sslproxies.org/",
        "https://www.us-proxy.org/",
        "https://api.proxyscrape.com/?request=getproxies&proxytype=http&timeout=1000",
        "https://raw.githubusercontent.com/proxifly/free-proxy-list/main/proxies/all/data.txt",
        "https://raw.githubusercontent.com/monosans/proxy-list/main/proxies/all.txt",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/http.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt",
        "https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-http.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxy-list/http.txt",
        "https://www.proxy-list.download/api/v1/get?type=http",
    ],
    "https": [
        "https://www.sslproxies.org/",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/https.txt",
        "https://raw.githubusercontent.com/roosterkid/openproxylist/main/HTTPS_RAW.txt",
        "https://raw.githubusercontent.com/mmpx12/proxy-list/master/https.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-https.txt",
        "https://raw.githubusercontent.com/Vann-Dev/proxy-list/main/proxy-list/https.txt",
        "https://www.proxy-list.download/api/v1/get?type=https",
    ],
    "socks4": [
        "https://www.socks-proxy.net/",
        "https://api.proxyscrape.com/?request=getproxies&proxytype=socks4&timeout=1000",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks4.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks4.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks4",
    ],
    "socks5": [
        "https://www.socks-proxy.net/",
        "https://api.proxyscrape.com/?request=getproxies&proxytype=socks5&timeout=1000",
        "https://raw.githubusercontent.com/zloi-user/hideip.me/main/socks5.txt",
        "https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt",
        "https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt",
        "https://raw.githubusercontent.com/Skillter/ProxyGather/refs/heads/master/proxies/working-proxies-socks5.txt",
        "https://www.proxy-list.download/api/v1/get?type=socks5",
    ]
}

async def scrape_proxies_from_source(client: httpx.AsyncClient, url: str, proxy_type: str, timeout: int = 10) -> List[Tuple[str, str]]:
    """Парсит прокси с одного источника и возвращает (ip:port, type)"""
    try:
        response = await client.get(url, timeout=timeout)
        if response.status_code != 200:
            return []
        
        text = response.text
        pattern = re.compile(r'\b\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}:\d{1,5}\b')
        proxies = pattern.findall(text)
        
        valid_proxies = []
        for p in proxies:
            parts = p.split(':')
            if len(parts) == 2:
                ip, port = parts
                ip_parts = ip.split('.')
                if all(0 <= int(x) <= 255 for x in ip_parts):
                    if 1 <= int(port) <= 65535:
                        valid_proxies.append((p, proxy_type))
        
        return valid_proxies
    except Exception:
        return []

async def scrape_all_proxies() -> Tuple[List[Tuple[str, str]], Dict[str, int]]:
    """Парсит все прокси со всех источников"""
    proxies = []
    stats = {}
    
    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as client:
        tasks = []
        for proxy_type, urls in PROXY_SOURCES.items():
            for url in urls:
                tasks.append(scrape_proxies_from_source(client, url, proxy_type))
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        for result in results:
            if isinstance(result, Exception):
                continue
            for proxy, ptype in result:
                proxies.append((proxy, ptype))
                stats[ptype] = stats.get(ptype, 0) + 1
    
    # Удаляем дубликаты
    seen = set()
    unique_proxies = []
    for proxy, ptype in proxies:
        if proxy not in seen:
            seen.add(proxy)
            unique_proxies.append((proxy, ptype))
    
    random.shuffle(unique_proxies)
    return unique_proxies, stats

# ──────────────────────────────────────────────────────────────
#  ПРОВЕРКА ПРОКСИ НА ВАЛИДНОСТЬ С ПИНГОМ И РЕГИОНОМ
# ──────────────────────────────────────────────────────────────

def get_country(ip: str) -> str:
    """Получить страну по IP"""
    try:
        import requests
        resp = requests.get(f"http://ip-api.com/json/{ip}", timeout=3)
        data = resp.json()
        if data.get('status') == 'success':
            return data.get('countryCode', '??')
        return '??'
    except Exception:
        return '??'

def check_proxy_with_details(proxy: str, proxy_type: str, timeout: int = 5) -> Optional[Dict]:
    """Проверяет прокси и возвращает детали (пинг, страна)"""
    try:
        ip, port = proxy.split(':')
        port = int(port)
        
        start_time = time.time()
        
        # Проверяем через socket
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        result = sock.connect_ex((ip, port))
        sock.close()
        
        if result != 0:
            return None
        
        ping = int((time.time() - start_time) * 1000)  # в миллисекундах
        
        # Проверяем через HTTP (только для http/https)
        if proxy_type in ['http', 'https']:
            try:
                proxy_support = urllib.request.ProxyHandler({
                    'http': f'http://{proxy}',
                    'https': f'http://{proxy}'
                })
                opener = urllib.request.build_opener(proxy_support)
                urllib.request.install_opener(opener)
                
                req = urllib.request.Request("http://httpbin.org/ip", method="GET")
                req.add_header("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
                req.add_header("Connection", "close")
                
                response = urllib.request.urlopen(req, timeout=timeout)
                response.read()
                response.close()
            except Exception:
                return None
        
        # Получаем страну
        country = get_country(ip)
        
        return {
            'proxy': proxy,
            'type': proxy_type,
            'ping': ping,
            'country': country
        }
        
    except Exception:
        return None

async def check_proxies_with_details_async(
    proxies: List[Tuple[str, str]], 
    timeout: int = 5, 
    max_concurrent: int = 30
) -> List[Dict]:
    """Асинхронная проверка прокси с деталями"""
    if not proxies:
        return []
    
    semaphore = asyncio.Semaphore(max_concurrent)
    valid_proxies = []
    
    async def check_one(proxy: str, ptype: str) -> Optional[Dict]:
        async with semaphore:
            return await asyncio.to_thread(check_proxy_with_details, proxy, ptype, timeout)
    
    tasks = [check_one(p, t) for p, t in proxies]
    results = await asyncio.gather(*tasks)
    
    valid_proxies = [r for r in results if r is not None]
    return valid_proxies

def format_proxy_details(proxy_data: Dict) -> str:
    """Форматирует прокси с деталями"""
    return f"{proxy_data['proxy']} | {proxy_data['type'].upper()} | 🌍{proxy_data['country']} | ⚡{proxy_data['ping']}ms"

# ──────────────────────────────────────────────────────────────
#  ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ДЛЯ WEBSHARE
# ──────────────────────────────────────────────────────────────

def gen_username() -> str:
    patterns = [
        lambda: f"{random.choice(_FIRST_NAMES)}.{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_FIRST_NAMES)}{random.randint(1, 9999)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}_{random.randint(1, 999)}",
        lambda: f"{random.choice(_FIRST_NAMES)[0]}{random.choice(_LAST_NAMES)}",
        lambda: f"{random.choice(_LAST_NAMES)}{random.randint(1, 9999)}",
        lambda: f"{random.choice(_FIRST_NAMES)}_{random.choice(_LAST_NAMES)}_{random.randint(2000, 2024)}",
        lambda: f"{random.choice(_FIRST_NAMES)}{random.choice(_LAST_NAMES)[:3]}{random.randint(100, 999)}",
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

def _smtp_check_outlook(email: str) -> bool | None:
    try:
        import smtplib
        with smtplib.SMTP("mx1.hotmail.com", 25, timeout=3) as smtp:
            smtp.ehlo("check.example.com")
            smtp.mail("")
            code, _ = smtp.rcpt(str(email))
            return code == 250
    except Exception:
        return None

def _smtp_check_yahoo(email: str) -> bool | None:
    try:
        import smtplib
        with smtplib.SMTP("mta6.am0.yahoodns.net", 25, timeout=3) as smtp:
            smtp.ehlo("check.example.com")
            smtp.mail("")
            code, _ = smtp.rcpt(str(email))
            return code == 250
    except Exception:
        return None

async def check_email_exists(email: str) -> bool:
    domain = email.split('@')[1].lower()
    
    if domain == "gmail.com":
        result = await asyncio.to_thread(_smtp_check_gmail, email)
        if result is not None:
            return result
    elif domain in ["outlook.com", "hotmail.com"]:
        result = await asyncio.to_thread(_smtp_check_outlook, email)
        if result is not None:
            return result
    elif domain == "yahoo.com":
        result = await asyncio.to_thread(_smtp_check_yahoo, email)
        if result is not None:
            return result
    
    return True

async def find_valid_email(max_tries: int = 30) -> tuple[str, str, str]:
    password = gen_password()
    
    for i in range(max_tries):
        email = gen_email()
        username = email.split('@')[0]
        if await check_email_exists(email):
            return email, username, password
        await asyncio.sleep(0.3)
    
    fallback = gen_email()
    return fallback, fallback.split('@')[0], password

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

class _RateLimitedError(Exception):
    pass

class _AlreadyRegisteredError(Exception):
    pass

async def _register_once(email: str, password: str, captcha_token: str) -> dict | None:
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
                elif "invalid" in body or "captcha" in body:
                    return None
            elif resp.status_code == 429:
                _set_reg_cooldown(700)
                raise _RateLimitedError()
    except Exception:
        pass
    return None

async def register_account_with_token(email: str, password: str, captcha_token: str) -> dict | None:
    try:
        account = await _register_once(email, password, captcha_token)
        if account:
            return account
    except _AlreadyRegisteredError:
        pass
    except _RateLimitedError:
        pass
    return None

# ──────────────────────────────────────────────────────────────
#  ТЕЛЕГРАМ БОТ
# ──────────────────────────────────────────────────────────────

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    global USER_STATES
    USER_STATES = load_user_states()
    if user_id not in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    keyboard = [
        [InlineKeyboardButton("📥 Получить прокси (webshare)", callback_data="get_proxies")],
        [InlineKeyboardButton("🌐 Спарсить прокси", callback_data="scrape_menu")],
        [InlineKeyboardButton("📊 Статистика", callback_data="stats")],
        [InlineKeyboardButton("❓ Помощь", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    welcome_text = (
        "🤖 *Добро пожаловать в Proxy Bot!*\n\n"
        "Я помогаю получать бесплатные прокси.\n\n"
        "📌 *Доступные функции:*\n"
        "1. Получить прокси с webshare.io\n"
        "2. Спарсить прокси (HTTP/HTTPS/SOCKS4/SOCKS5)\n"
        "3. Показать статистику\n\n"
        "⚠️ *Всё абсолютно бесплатно!*"
    )
    
    await update.message.reply_text(
        welcome_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    if query.data == "get_proxies":
        await get_proxies_start(update, context)
    elif query.data == "scrape_menu":
        await scrape_menu(update, context)
    elif query.data.startswith("scrape_"):
        proxy_type = query.data.replace("scrape_", "")
        await scrape_proxies_handler(update, context, proxy_type)
    elif query.data == "stats":
        await show_stats(update, context)
    elif query.data == "help":
        await show_help(update, context)
    elif query.data == "cancel":
        await cancel_operation(update, context)

async def scrape_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Меню выбора типа прокси для парсинга"""
    keyboard = [
        [InlineKeyboardButton("🌐 HTTP", callback_data="scrape_http")],
        [InlineKeyboardButton("🔒 HTTPS", callback_data="scrape_https")],
        [InlineKeyboardButton("🧦 SOCKS4", callback_data="scrape_socks4")],
        [InlineKeyboardButton("🧦 SOCKS5", callback_data="scrape_socks5")],
        [InlineKeyboardButton("📦 Все типы", callback_data="scrape_all")],
        [InlineKeyboardButton("🔙 Назад", callback_data="start_menu")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.callback_query.edit_message_text(
        "🌐 *Выберите тип прокси для парсинга:*\n\n"
        "Бот спарсит прокси с 25+ источников,\n"
        "проверит каждый на валидность,\n"
        "определит страну и пинг.\n\n"
        "⏳ Обычно занимает 1-3 минуты.",
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

async def scrape_proxies_handler(update: Update, context: ContextTypes.DEFAULT_TYPE, proxy_type: str = "all"):
    """Обработчик парсинга и проверки публичных прокси"""
    user_id = update.effective_user.id
    
    msg = await update.callback_query.edit_message_text(
        f"⏳ Начинаю парсинг {'всех типов' if proxy_type == 'all' else proxy_type.upper()} прокси...\n"
        "Шаг 1/3: Сбор прокси..."
    )
    
    try:
        # Шаг 1: Парсим прокси
        all_proxies, stats = await scrape_all_proxies()
        
        if not all_proxies:
            await msg.edit_text("❌ Не удалось спарсить прокси. Попробуйте позже.")
            return
        
        # Фильтруем по типу если нужно
        if proxy_type != "all":
            filtered_proxies = [(p, t) for p, t in all_proxies if t == proxy_type]
            if not filtered_proxies:
                await msg.edit_text(f"❌ Не найдено прокси типа {proxy_type.upper()}")
                return
        else:
            filtered_proxies = all_proxies
        
        total_raw = len(filtered_proxies)
        
        await msg.edit_text(
            f"⏳ Шаг 2/3: Проверка {total_raw} прокси на валидность...\n"
            "Это может занять до 2-3 минут..."
        )
        
        # Шаг 2: Проверяем прокси с деталями
        valid_proxies = await check_proxies_with_details_async(
            filtered_proxies, 
            timeout=PROXY_CHECK_TIMEOUT,
            max_concurrent=MAX_PROXY_CHECK_THREADS
        )
        
        total_valid = len(valid_proxies)
        
        if not valid_proxies:
            await msg.edit_text(
                f"❌ Не найдено валидных прокси!\n"
                f"📊 Спаршено всего: {total_raw}\n"
                f"❌ Все прокси невалидны\n\n"
                "Попробуйте позже или выберите другой тип."
            )
            return
        
        # Шаг 3: Анализируем результаты
        # Группировка по странам
        country_stats = defaultdict(int)
        ping_sum = 0
        type_stats = defaultdict(int)
        
        for p in valid_proxies:
            country_stats[p['country']] += 1
            type_stats[p['type']] += 1
            ping_sum += p['ping']
        
        avg_ping = ping_sum // total_valid if total_valid > 0 else 0
        
        # Формируем статистику
        country_text = "\n".join([f"  🌍 {country}: {count}" for country, count in sorted(country_stats.items(), key=lambda x: x[1], reverse=True)[:10]])
        type_text = "\n".join([f"  📦 {t.upper()}: {count}" for t, count in type_stats.items()])
        
        # Создаем файл с прокси
        proxy_lines = []
        for p in valid_proxies:
            proxy_lines.append(format_proxy_details(p))
        
        proxy_text = "\n".join(proxy_lines)
        file_data = BytesIO()
        file_data.write(proxy_text.encode('utf-8'))
        file_data.seek(0)
        
        # Отправляем файл
        await update.callback_query.message.reply_document(
            document=file_data,
            filename=f"proxies_{proxy_type}_{int(time.time())}.txt",
            caption=(
                f"✅ *Найдено {total_valid} валидных прокси!*\n\n"
                f"📊 Всего спаршено: {total_raw}\n"
                f"✅ Валидных: {total_valid}\n"
                f"❌ Невалидных: {total_raw - total_valid}\n"
                f"📈 Средний пинг: {avg_ping}ms\n\n"
                f"📦 *По типам:*\n{type_text}\n\n"
                f"🌍 *Топ-10 стран:*\n{country_text}\n\n"
                "💾 Формат: `IP:PORT | TYPE | 🌍COUNTRY | ⚡PING`"
            ),
            parse_mode="Markdown"
        )
        
        await msg.delete()
        
    except Exception as e:
        await msg.edit_text(f"❌ Ошибка при парсинге: {str(e)}")

async def get_proxies_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in USER_STATES and USER_STATES[user_id].get("waiting_for_token"):
        await update.callback_query.edit_message_text(
            "⏳ У вас уже есть активный процесс. Введите токен капчи."
        )
        return
    
    await update.callback_query.edit_message_text(
        "⏳ Генерирую данные аккаунта..."
    )
    
    email, username, password = await find_valid_email()
    
    USER_STATES[user_id] = {
        "waiting_for_token": True,
        "email": email,
        "password": password,
        "step": "waiting_token"
    }
    save_user_states()
    
    instruction = (
        f"🔐 *Сгенерированы данные аккаунта*\n\n"
        f"📧 *Email:* `{email}`\n"
        f"👤 *Username:* `{username}`\n"
        f"🔑 *Password:* `{password}`\n\n"
        "📋 *Инструкция:*\n"
        "1. Открой браузер и перейди по ссылке:\n"
        f"`{WEBSHARE_REGISTER_URL}`\n"
        "2. Введи email и пароль из данных выше\n"
        "3. Открой инструменты разработчика (F12)\n"
        "4. Перейди на вкладку Console\n"
        "5. Вставь команду и нажми Enter:\n"
        "`document.querySelector('[name=g-recaptcha-response]').value`\n"
        "6. Скопируй полученную длинную строку (токен)\n"
        "7. *Вставь токен в сообщение этому боту*\n\n"
        "⏳ Токен действителен ~2 минуты\n"
        "❌ Для отмены отправь /cancel"
    )
    
    await update.callback_query.message.edit_text(
        instruction,
        parse_mode="Markdown"
    )

async def handle_token(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    token_text = update.message.text.strip()
    
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
    
    await update.message.reply_text("⏳ Проверяю токен и регистрирую аккаунт...")
    
    email = USER_STATES[user_id].get("email")
    password = USER_STATES[user_id].get("password")
    
    if not email or not password:
        await update.message.reply_text("❌ Ошибка: данные аккаунта не найдены. Начни заново.")
        USER_STATES[user_id] = {}
        save_user_states()
        return
    
    account = await register_account_with_token(email, password, token_text)
    
    if account:
        await update.message.reply_text("✅ Аккаунт зарегистрирован! Получаю прокси...")
        await asyncio.sleep(2)
        
        proxies = await fetch_proxies(account["token"], count=10)
        
        if proxies:
            accounts_data = load_accounts()
            accounts_data["accounts"].append(account)
            save_accounts(accounts_data)
            
            USER_STATES[user_id] = {}
            save_user_states()
            
            proxy_text = "\n".join(proxies)
            
            if len(proxies) > 10:
                file_data = BytesIO()
                file_data.write(proxy_text.encode('utf-8'))
                file_data.seek(0)
                
                await update.message.reply_document(
                    document=file_data,
                    filename=f"proxies_webshare_{int(time.time())}.txt",
                    caption=f"✅ *Получено {len(proxies)} прокси с webshare.io!*\n\n"
                            "💾 Формат: `ip:port:username:password`"
                )
            else:
                await update.message.reply_text(
                    f"✅ *Получено {len(proxies)} прокси!*\n\n"
                    f"```\n{proxy_text}\n```\n\n"
                    "💾 Формат: `ip:port:username:password`",
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
    
    USER_STATES[user_id] = {}
    save_user_states()

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    help_text = (
        "❓ *Помощь*\n\n"
        "🤖 *Команды:*\n"
        "/start - Главное меню\n"
        "/cancel - Отменить текущую операцию\n"
        "/stats - Показать статистику\n\n"
        "📌 *Как получить прокси с webshare:*\n"
        "1. Нажми «Получить прокси»\n"
        "2. Бот сгенерирует email и пароль\n"
        "3. Введи данные на сайте webshare.io\n"
        "4. Скопируй токен из консоли браузера\n"
        "5. Вставь токен в бота\n"
        "6. Получи прокси (если >10 - файлом)\n\n"
        "🌐 *Как спарсить публичные прокси:*\n"
        "1. Нажми «Спарсить прокси»\n"
        "2. Выбери тип (HTTP/HTTPS/SOCKS4/SOCKS5/Все)\n"
        "3. Бот соберет прокси с 25+ источников\n"
        "4. Проверит каждый на валидность\n"
        "5. Определит страну и пинг\n"
        "6. Отправит файл со статистикой\n\n"
        "⚠️ *Бот работает полностью бесплатно!*"
    )
    
    await update.callback_query.edit_message_text(
        help_text,
        parse_mode="Markdown"
    )

async def cancel_operation(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    await update.callback_query.edit_message_text(
        "✅ Операция отменена.\n"
        "Используй /start для нового запроса."
    )

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    
    if user_id in USER_STATES:
        USER_STATES[user_id] = {}
        save_user_states()
    
    await update.message.reply_text(
        "✅ Операция отменена.\n"
        "Используй /start для нового запроса."
    )

async def stats_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
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
    application = Application.builder().token(TOKEN).build()
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("cancel", cancel))
    application.add_handler(CommandHandler("stats", stats_command))
    application.add_handler(CallbackQueryHandler(button_handler))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_token))
    
    global USER_STATES
    USER_STATES = load_user_states()
    
    print("🤖 Бот запущен!")
    print(f"📊 Загружено состояний: {len(USER_STATES)}")
    print(f"🌐 Источников прокси: {sum(len(urls) for urls in PROXY_SOURCES.values())}")
    print("🚀 Нажми Ctrl+C для остановки")
    
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n👋 Бот остановлен")