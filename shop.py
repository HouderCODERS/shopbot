import asyncio
import re
import sqlite3
import datetime
import os
import random
import string
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, FSInputFile
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "8692336245:AAFKoqW0L4sXWf6dTjXYA8vMO3ariK-L_hc"
ADMIN_ID = 8808258682
SELLER_TG = "s3rp3ntcoders"
SUPPORT_TG = "iserpentt"
# ======================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class AdminState(StatesGroup):
    waiting_days = State()
    waiting_keygen_days = State()
    waiting_gift_id = State()
    waiting_broadcast = State()
    waiting_key = State()
    waiting_promocode = State()
    waiting_promo_days = State()
    waiting_promo_limit = State()
    waiting_direct_msg = State()
    waiting_user_promo = State()

# === ТОНКИЙ ШРИФТ ДЛЯ КНОПОК ===
def thin(text: str) -> str:
    mapping = str.maketrans(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789",
        "𝗔𝗕𝗖𝗗𝗘𝗙𝗚𝗛𝗜𝗝𝗞𝗟𝗠𝗡𝗢𝗣𝗤𝗥𝗦𝗧𝗨𝗩𝗪𝗫𝗬𝗭𝗮𝗯𝗰𝗱𝗲𝗳𝗴𝗵𝗶𝗷𝗸𝗹𝗺𝗻𝗼𝗽𝗾𝗿𝘀𝘁𝘂𝘃𝘄𝘅𝘆𝘇𝟬𝟭𝟮𝟯𝟰𝟱𝟲𝟳𝟴𝟵"
    )
    return text.translate(mapping)

# === БАЗА ДАННЫХ ===
data_dir = Path(os.environ.get("DATA_DIR", "."))
try:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "shop.db"
    test_file = data_dir / ".test_write"
    test_file.touch()
    test_file.unlink()
except Exception:
    db_path = Path("shop.db")

def get_db():
    conn = sqlite3.connect(db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn

conn = get_db()
cur = conn.cursor()

cur.execute("""
CREATE TABLE IF NOT EXISTS users (
    user_id INTEGER PRIMARY KEY,
    username TEXT DEFAULT NULL,
    full_name TEXT DEFAULT NULL,
    sub_until TEXT DEFAULT NULL,
    is_blocked INTEGER DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY,
    days INTEGER,
    max_uses INTEGER DEFAULT 0,
    used_count INTEGER DEFAULT 0
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS promo_uses (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    code TEXT,
    user_id INTEGER,
    date TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    action TEXT,
    date TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT
)
""")

# АВТОМИГРАЦИЯ
def ensure_column(table, column, coltype):
    cur.execute(f"PRAGMA table_info({table})")
    cols = [row[1] for row in cur.fetchall()]
    if column not in cols:
        cur.execute(f"ALTER TABLE {table} ADD COLUMN {column} {coltype}")
        conn.commit()

ensure_column("users", "username", "TEXT")
ensure_column("users", "full_name", "TEXT")
ensure_column("users", "is_blocked", "INTEGER DEFAULT 0")
ensure_column("promos", "max_uses", "INTEGER DEFAULT 0")
ensure_column("promos", "used_count", "INTEGER DEFAULT 0")

conn.commit()

def log_action(user_id, action):
    date = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    cur.execute("INSERT INTO logs (user_id, action, date) VALUES (?, ?, ?)", (user_id, action, date))
    conn.commit()

def get_setting(key, default=None):
    cur.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cur.fetchone()
    return row[0] if row else default

def set_setting(key, value):
    cur.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()

def save_user(user):
    cur.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user.id,))
    row = cur.fetchone()
    is_blocked = row['is_blocked'] if row else 0
    cur.execute("""
        INSERT INTO users (user_id, username, full_name, is_blocked) 
        VALUES (?, ?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET 
        username=excluded.username, full_name=excluded.full_name
    """, (user.id, user.username, user.full_name, is_blocked))
    conn.commit()
    return is_blocked

def check_sub(user_id):
    cur.execute("SELECT sub_until, is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] is None or row[1] == 1: return False
    return datetime.datetime.now().strftime("%Y-%m-%d") <= row[0]

# === ЦЕНЫ ===
STARS_PRICES = {"2 недели": 15, "1 месяц": 30, "6 месяцев": 100, "1 год": 200, "Навсегда": 500}
STARS_DAYS = {"2 недели": 14, "1 месяц": 30, "6 месяцев": 180, "1 год": 365, "Навсегда": 36500}

# === МЕНЮ ===
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=thin("Купить за звезды"), callback_data="buy_stars")],
        [InlineKeyboardButton(text=thin("Ввести промокод"), callback_data="enter_promo")],
        [InlineKeyboardButton(text=thin("Туториал"), callback_data="tutorial")],
        [InlineKeyboardButton(text=thin("Мой профиль"), callback_data="profile")],
        [InlineKeyboardButton(text=thin("Поддержка"), url=f"https://t.me/{SUPPORT_TG}")]
    ])

def stars_shop_menu():
    kb = []
    for name, stars in STARS_PRICES.items():
        kb.append([InlineKeyboardButton(text=thin(f"{name} - {stars}"), callback_data=f"stars_buy_{name}")])
    kb.append([InlineKeyboardButton(text=thin("Назад"), callback_data="main_menu")])
    return InlineKeyboardMarkup(inline_keyboard=kb)

async def safe_edit_or_send(message: types.Message, text: str, keyboard: InlineKeyboardMarkup = None, link: str = None):
    kwargs = {}
    if keyboard: kwargs['reply_markup'] = keyboard
    if link: kwargs['link_preview_options'] = LinkPreviewOptions(url=link, prefer_large_media=True)
    try: await message.edit_text(text=text, **kwargs)
    except Exception:
        try: await message.delete()
        except: pass
        await message.answer(text=text, **kwargs)

# === СТАРТ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    is_blocked = save_user(message.from_user)
    if is_blocked: return 
    log_action(message.from_user.id, "start")
    if message.from_user.id != ADMIN_ID and get_setting("notify_new_users", "1") == "1":
        try:
            await bot.send_message(ADMIN_ID, f"<b>Новый юзер!</b>\n\n👤 {message.from_user.full_name}\n🔗 @{message.from_user.username}\nID: <code>{message.from_user.id}</code>")
        except: pass
    await message.answer("👋 <b>Добро пожаловать в магазин!</b>\n\n🎁 Чтобы получить <b>3 дня бесплатной подписки</b>, напишите @s3rp3ntcoders\n\nВыберите действие:", reply_markup=main_menu())

# === ВВОД ПРОМОКОДА (ПОЛЬЗОВАТЕЛЬ) ===
@dp.callback_query(F.data == "enter_promo")
async def enter_promo_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await safe_edit_or_send(callback.message, "<b>🎟 Введите промокод:</b>", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data="main_menu")]]))
    await state.set_state(AdminState.waiting_user_promo)

@dp.message(AdminState.waiting_user_promo)
async def process_user_promo(message: types.Message, state: FSMContext):
    code = message.text.strip()
    await state.clear()
    save_user(message.from_user)
    
    cur.execute("SELECT days, max_uses, used_count FROM promos WHERE code = ?", (code,))
    row = cur.fetchone()
    if not row:
        return await message.answer("<b>❌ Промокод не найден.</b>", reply_markup=main_menu())
    
    days, max_uses, used_count = row['days'], row['max_uses'], row['used_count']
    if max_uses > 0 and used_count >= max_uses:
        return await message.answer("<b>❌ Промокод больше не действителен (лимит исчерпан).</b>", reply_markup=main_menu())
    
    cur.execute("SELECT id FROM promo_uses WHERE code = ? AND user_id = ?", (code, message.from_user.id))
    if cur.fetchone():
        return await message.answer("<b>❌ Вы уже активировали этот промокод.</b>", reply_markup=main_menu())

    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (message.from_user.id,))
    u_row = cur.fetchone()
    today = datetime.datetime.now()
    if u_row and u_row['sub_until'] and u_row['sub_until'] > today.strftime("%Y-%m-%d"):
        base = datetime.datetime.strptime(u_row['sub_until'], "%Y-%m-%d")
        new_date = base + datetime.timedelta(days=days)
    else:
        new_date = today + datetime.timedelta(days=days)
    new_date_str = new_date.strftime("%Y-%m-%d")
    
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date_str, message.from_user.id))
    cur.execute("UPDATE promos SET used_count = used_count + 1 WHERE code = ?", (code,))
    cur.execute("INSERT INTO promo_uses (code, user_id, date) VALUES (?, ?, ?)", (code, message.from_user.id, today.strftime("%Y-%m-%d %H:%M")))
    conn.commit()
    
    await message.answer(f"<b>✅ Промокод активирован!</b>\n\nПодписка продлена до: <b>{new_date_str}</b>", reply_markup=main_menu())

# === АДМИН МЕНЮ ===
@dp.message(Command("menu"))
async def admin_menu_command(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("<b>👑 Главное меню админа</b>\n\nВыберите действие:", reply_markup=admin_main_menu())

def admin_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=thin("Список юзеров"), callback_data="admin_users")],
        [InlineKeyboardButton(text=thin("Статистика"), callback_data="admin_stats")],
        [InlineKeyboardButton(text=thin("Кейген"), callback_data="admin_keygen")],
        [InlineKeyboardButton(text=thin("Выдать по ID"), callback_data="admin_gift")],
        [InlineKeyboardButton(text=thin("Рассылка"), callback_data="admin_broadcast")],
        [InlineKeyboardButton(text=thin("Промокоды"), callback_data="admin_promo_menu")],
        [InlineKeyboardButton(text=thin("Логи"), callback_data="admin_logs")],
        [InlineKeyboardButton(text=thin("Уведомления"), callback_data="admin_notify_toggle")]
    ])

@dp.callback_query(F.data == "admin_main")
async def admin_to_main(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await safe_edit_or_send(callback.message, "<b>👑 Главное меню админа</b>\n\nВыберите действие:", admin_main_menu())

@dp.callback_query(F.data == "admin_notify_toggle")
async def admin_notify_toggle(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    current = get_setting("notify_new_users", "1")
    new_val = "0" if current == "1" else "1"
    set_setting("notify_new_users", new_val)
    status = "ВКЛ" if new_val == "1" else "ВЫКЛ"
    await safe_edit_or_send(callback.message, f"<b>🔔 Уведомления: {status}</b>", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Переключить"), callback_data="admin_notify_toggle")],[InlineKeyboardButton(text=thin("Назад"), callback_data="admin_main")]]))

@dp.callback_query(F.data == "buy_stars")
async def buy_stars(callback: types.CallbackQuery):
    await callback.answer()
    await safe_edit_or_send(callback.message, "<b>💎 Покупка подписки за Telegram Stars</b>\n\nВыберите тариф. После выбора вам нужно будет отправить звезды в ЛС продавцу.\n\n⚠️ <i>Ключ выдается вручную в течение часа.</i>", stars_shop_menu())

@dp.callback_query(F.data.startswith("stars_buy_"))
async def stars_buy(callback: types.CallbackQuery):
    await callback.answer()
    tariff = callback.data.replace("stars_buy_", "")
    if tariff not in STARS_PRICES: return
    stars = STARS_PRICES[tariff]; days = STARS_DAYS[tariff]
    text = f"<b>💎 Вы выбрали тариф: {tariff}</b>\n\n📤 Отправьте <b>{stars} ⭐</b> в ЛС @{SELLER_TG}\n\nВ течение часа он выдаст вам ключ на <b>{days} дней</b>."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin(f"Написать @{SELLER_TG}"), url=f"https://t.me/{SELLER_TG}")],[InlineKeyboardButton(text=thin("Назад"), callback_data="buy_stars")]])
    await safe_edit_or_send(callback.message, text, kb)

# === ПРОМОКОДЫ (АДМИН) ===
@dp.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT code, days, max_uses, used_count FROM promos")
    promos = cur.fetchall()
    
    text = "<b>🎟 Управление промокодами:</b>\n\n"
    if not promos:
        text += "❌ Промокодов нет."
    else:
        for p in promos:
            limit = "безлимит" if p['max_uses'] == 0 else str(p['max_uses'])
            text += f"<code>{p['code']}</code> (+{p['days']} дн.) [{p['used_count']}/{limit}]\n"
    
    kb = [
        [InlineKeyboardButton(text=thin("Создать промокод"), callback_data="admin_newpromo")],
        [InlineKeyboardButton(text=thin("Статистика активаций"), callback_data="admin_promo_stats")],
        [InlineKeyboardButton(text=thin("Назад"), callback_data="admin_main")]
    ]
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "admin_newpromo")
async def admin_newpromo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await safe_edit_or_send(callback.message, "<b>🎟 Введите текст промокода (например: FREE3):</b>", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data="admin_promo_menu")]]))
    await state.set_state(AdminState.waiting_promocode)

@dp.message(AdminState.waiting_promocode)
async def process_promocode(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    await state.update_data(code=message.text.strip())
    await state.set_state(AdminState.waiting_promo_days)
    await message.answer("Сколько дней дает этот промокод?")

@dp.message(AdminState.waiting_promo_days)
async def process_promo_days(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    days = int(message.text)
    await state.update_data(days=days)
    await state.set_state(AdminState.waiting_promo_limit)
    await message.answer("<b>Сколько раз можно активировать?</b>\n\nОтправь число (например: <code>10</code>), или напиши <code>0</code> для безлимита.")

@dp.message(AdminState.waiting_promo_limit)
async def process_promo_limit(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    limit = int(message.text)
    data = await state.get_data()
    code, days = data['code'], data['days']
    await state.clear()
    
    cur.execute("INSERT OR REPLACE INTO promos (code, days, max_uses, used_count) VALUES (?, ?, ?, 0)", (code, days, limit))
    conn.commit()
    await message.answer(f"<b>✅ Промокод <code>{code}</code> создан!</b>\nДает: {days} дней\nЛимит: {'безлимит' if limit == 0 else limit}", reply_markup=admin_main_menu())

@dp.callback_query(F.data == "admin_promo_stats")
async def admin_promo_stats(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT code, user_id, date FROM promo_uses ORDER BY id DESC LIMIT 50")
    uses = cur.fetchall()
    
    text = "<b>📊 Последние 50 активаций:</b>\n\n"
    if not uses:
        text += "Пока никто не активировал промокоды."
    else:
        for u in uses:
            text += f"<code>{u['code']}</code> — ID <code>{u['user_id']}</code> ({u['date']})\n"
            
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Назад"), callback_data="admin_promo_menu")]]))

# === ОСТАЛЬНЫЕ АДМИН ФУНКЦИИ ===
@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT user_id, username, full_name, sub_until, is_blocked FROM users ORDER BY sub_until DESC")
    users = cur.fetchall()
    if not users: return await safe_edit_or_send(callback.message, "❌ Пользователей нет.", admin_main_menu())
    text = "<b>👥 Все юзеры:</b>\n\n"
    kb = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    for u in users:
        sub = u['sub_until']
        status = "✅" if sub and sub >= today else "❌"
        if u['is_blocked']: status = "🚫"
        text += f"{status} {u['full_name']} (@{u['username']})\n"
        kb.append([InlineKeyboardButton(text=thin(f"{u['full_name']}"), callback_data=f"admin_user_{u['user_id']}")])
    kb.append([InlineKeyboardButton(text=thin("Назад"), callback_data="admin_main")])
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user_info(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    if not user: return await safe_edit_or_send(callback.message, "❌ Не найден.", admin_main_menu())
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    sub = user['sub_until']
    status = "✅ Активна" if sub and sub >= today else "❌ Истекла"
    if user['is_blocked']: status = "🚫 Заблокирован"
    text = f"<b>👤 Инфо о юзере</b>\n\n🔹 <b>Имя:</b> {user['full_name']}\n🔹 <b>Юзер:</b> @{user['username']}\n🔹 <b>ID:</b> <code>{user['user_id']}</code>\n🔹 <b>Подписка:</b> {sub if sub else 'Нет'} ({status})"
    block_btn = InlineKeyboardButton(text=thin("Разбанить" if user['is_blocked'] else "Забанить"), callback_data=f"admin_toggleblock_{user_id}")
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=thin("Продлить"), callback_data=f"admin_extend_{user_id}")],
        [InlineKeyboardButton(text=thin("Забрать"), callback_data=f"admin_revoke_{user_id}")],
        [block_btn, InlineKeyboardButton(text=thin("Написать"), callback_data=f"admin_writeto_{user_id}")],
        [InlineKeyboardButton(text=thin("Назад"), callback_data="admin_users")]
    ])
    await safe_edit_or_send(callback.message, text, kb)

@dp.callback_query(F.data.startswith("admin_toggleblock_"))
async def admin_toggleblock(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    cur.execute("SELECT is_blocked FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if row:
        new_val = 0 if row['is_blocked'] else 1
        cur.execute("UPDATE users SET is_blocked = ? WHERE user_id = ?", (new_val, user_id))
        conn.commit()
        await callback.answer("Забанен" if new_val else "Разбанен", show_alert=True)
    await admin_user_info(callback)

@dp.callback_query(F.data.startswith("admin_writeto_"))
async def admin_writeto(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    await state.update_data(target_user=user_id)
    await state.set_state(AdminState.waiting_direct_msg)
    await safe_edit_or_send(callback.message, f"<b>✉️ Написать юзеру</b>\n\nВведите текст сообщения для ID <code>{user_id}</code>:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data=f"admin_user_{user_id}")]]))

@dp.message(AdminState.waiting_direct_msg)
async def process_direct_msg(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    data = await state.get_data()
    user_id = data.get("target_user")
    text = message.text
    await state.clear()
    try:
        await bot.send_message(user_id, f"<b>Сообщение от администратора:</b>\n\n{text}")
        await message.answer("✅ Сообщение отправлено.", reply_markup=admin_main_menu())
    except Exception as e:
        await message.answer(f"❌ Ошибка: {e}", reply_markup=admin_main_menu())

@dp.callback_query(F.data.startswith("admin_extend_"))
async def admin_extend(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    await state.update_data(target_user=user_id)
    await state.set_state(AdminState.waiting_days)
    await safe_edit_or_send(callback.message, "<b>➕ Продление</b>\n\nВведите количество дней:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data=f"admin_user_{user_id}")]]))

@dp.message(AdminState.waiting_days)
async def process_extend_days(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    days = int(message.text)
    data = await state.get_data(); user_id = data.get("target_user"); await state.clear()
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,)); row = cur.fetchone()
    today = datetime.datetime.now()
    if row and row['sub_until'] and row['sub_until'] > today.strftime("%Y-%m-%d"):
        base = datetime.datetime.strptime(row['sub_until'], "%Y-%m-%d")
        new_date = base + datetime.timedelta(days=days)
    else: new_date = today + datetime.timedelta(days=days)
    new_date_str = new_date.strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date_str, user_id)); conn.commit()
    try: await bot.send_message(user_id, f"<b>👑 Администратор продлил вашу подписку!</b>\n\nДо: <b>{new_date_str}</b>")
    except: pass
    await message.answer(f"✅ Продлено до {new_date_str}.", reply_markup=admin_main_menu())

@dp.callback_query(F.data.startswith("admin_revoke_"))
async def admin_revoke(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    cur.execute("UPDATE users SET sub_until = NULL WHERE user_id = ?", (user_id,)); conn.commit()
    try: await bot.send_message(user_id, "<b>❌ Подписка отменена администратором.</b>")
    except: pass
    await callback.answer("Забрано.", show_alert=True)
    await admin_user_info(callback)

@dp.callback_query(F.data == "admin_keygen")
async def admin_keygen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await safe_edit_or_send(callback.message, "<b>🛠 Кейген</b>\n\nВведите количество дней:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data="admin_main")]]))
    await state.set_state(AdminState.waiting_keygen_days)

@dp.message(AdminState.waiting_keygen_days)
async def keygen_process(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID or not message.text.isdigit(): return
    days = int(message.text); await state.clear()
    chars = string.ascii_letters + string.digits
    key = "key-" + "".join(random.choice(chars) for _ in range(12))
    until = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute("CREATE TABLE IF NOT EXISTS keys (key_code TEXT PRIMARY KEY, date_until TEXT)")
    cur.execute("INSERT INTO keys (key_code, date_until) VALUES (?, ?)", (key, until)); conn.commit()
    await message.answer(f"<b>✅ Ключ создан!</b>\n\n🔑 <code>{key}</code>\n📅 До: <b>{until}</b> ({days} дней)", reply_markup=admin_main_menu())

@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT COUNT(*) FROM users"); total = cur.fetchone()[0]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM users WHERE sub_until >= ?", (today,)); active = cur.fetchone()[0]
    await safe_edit_or_send(callback.message, f"<b>📊 Статистика:</b>\n\n👥 Всего: <b>{total}</b>\n✅ С подпиской: <b>{active}</b>\n❌ Без: <b>{total - active}</b>", admin_main_menu())

@dp.callback_query(F.data == "admin_gift")
async def admin_gift(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await safe_edit_or_send(callback.message, "<b>🎁 Выдать по ID</b>\n\nВведите ID и дни (например: <code>123456789 30</code>):", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data="admin_main")]]))
    await state.set_state(AdminState.waiting_gift_id)

@dp.message(AdminState.waiting_gift_id)
async def process_gift(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit(): return await message.answer("❌ Введите: ID и дни")
    user_id, days = int(args[0]), int(args[1]); await state.clear()
    new_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date, user_id)); conn.commit()
    try: await bot.send_message(user_id, f"<b>👑 Администратор выдал вам подписку!</b>\n\nДо: <b>{new_date}</b>")
    except: pass
    await message.answer(f"✅ Выдано до {new_date}.", reply_markup=admin_main_menu())

@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await safe_edit_or_send(callback.message, "<b>📢 Рассылка</b>\n\nВведите текст для всех юзеров:", InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Отмена"), callback_data="admin_main")]]))
    await state.set_state(AdminState.waiting_broadcast)

@dp.message(AdminState.waiting_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text; await state.clear()
    cur.execute("SELECT user_id FROM users WHERE is_blocked = 0"); users = cur.fetchall()
    success = failed = 0
    for u in users:
        try: await bot.send_message(u['user_id'], text); success += 1; await asyncio.sleep(0.05)
        except Exception: failed += 1
    await message.answer(f"<b>✅ Рассылка завершена!</b>\n\n📤 Отправлено: {success}\n❌ Ошибок: {failed}", reply_markup=admin_main_menu())

@dp.callback_query(F.data == "admin_logs")
async def admin_logs(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT user_id, action, date FROM logs ORDER BY id DESC LIMIT 30"); logs = cur.fetchall()
    text = "<b>📝 Логи:</b>\n\n" + "\n".join(f"{l['date']} | {l['user_id']} | {l['action']}" for l in logs) if logs else "Пусто"
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Назад"), callback_data="admin_main")]]))

@dp.callback_query(F.data == "main_menu")
async def to_main(callback: types.CallbackQuery):
    await callback.answer()
    await safe_edit_or_send(callback.message, "<b>👋 Выберите действие:</b>", main_menu())

@dp.callback_query(F.data == "tutorial")
async def tutorial(callback: types.CallbackQuery):
    await callback.answer()
    text = "<b>📖 Как сделать оффер:</b>\n\n1. Зайдите в личный чат с человеком.\n2. Напишите:\n<code>/h [ссылка] [цена] [stars] [ru]</code>\n\n📌 <b>Пример:</b>\n<code>/h https://t.me/nft/CloverPin-193200 1200 stars ru</code>"
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Назад"), callback_data="main_menu")]]))

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    await callback.answer()
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (callback.from_user.id,)); row = cur.fetchone()
    text = "<b>👤 Ваш профиль</b>\n\n❌ У вас нет активной подписки." if not row or not row[0] or row[0] < datetime.datetime.now().strftime("%Y-%m-%d") else f"<b>👤 Ваш профиль</b>\n\n✅ Подписка активна до: <b>{row[0]}</b>"
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Назад"), callback_data="main_menu")]]))

# === ОФФЕР ===
@dp.business_message(F.text.startswith("/h"))
async def make_offer(message: types.Message):
    save_user(message.from_user)
    if not check_sub(message.from_user.id):
        try: await message.delete()
        except: pass
        return await message.answer("⛔ У вас нет подписки!")
    args = message.text.split()
    if len(args) < 5: return
    link, price, lang = args[1], args[2], args[4].lower()
    link = link.strip()
    match = re.search(r'/nft/([^-]+)-(\d+)', link)
    gift_name = f"{match.group(1)} #{match.group(2)}" if match else "Collectible"
    sender_id = message.from_user.id
    if lang == "ru":
        text = f"<b>Пользователь предлагает вам {price} ⭐ Stars за подарок 💎 {gift_name}.</b>\n\n<b>Оффер действителен ещё 6 ч. 0 мин..</b>"
        btn_accept, btn_decline = "Принять", "Отклонить"
    else:
        text = f"<b>User offers you {price} ⭐ Stars for the gift 💎 {gift_name}.</b>\n\n<b>Offer is valid for 6 hours.</b>"
        btn_accept, btn_decline = "Accept", "Decline"
    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=thin(f"❌ {btn_decline}"), callback_data="decline_offer"),
        InlineKeyboardButton(text=thin(f"✅ {btn_accept}"), callback_data=f"accept_{price}_{gift_name}_{sender_id}")
    ]])
    kwargs = {}
    if link.startswith("https://t.me/nft/"): kwargs['link_preview_options'] = LinkPreviewOptions(url=link, prefer_large_media=True)
    else: kwargs['link_preview_options'] = LinkPreviewOptions(is_disabled=True)
    try: await message.edit_text(text=text, reply_markup=keyboard, **kwargs)
    except:
        try: await message.delete()
        except: pass
        await message.answer(text=text, reply_markup=keyboard, **kwargs)

@dp.callback_query(F.data.startswith("accept_"))
async def accept(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_", 3); price, gift_name, sender_id = parts[1], parts[2], parts[3]
    text_accepted = f"<b>🎁 Подарок: {gift_name} успешно продан!</b>\n\n<b>Передайте подарок покупателю для зачисления звёзд.</b>\n\n<i>Сделка защищена Telegram. После передачи подарка звезды поступят на ваш баланс.</i>"
    try:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Передать NFT"), url=f"tg://user?id={sender_id}")], [InlineKeyboardButton(text=thin("Как передать?"), callback_data=f"how_to_send_{price}_{gift_name}_{sender_id}")]])
        await safe_edit_or_send(callback.message, text_accepted, keyboard)
    except:
        keyboard = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Как передать?"), callback_data=f"how_to_send_{price}_{gift_name}_{sender_id}")]])
        await safe_edit_or_send(callback.message, text_accepted, keyboard)

@dp.callback_query(F.data.startswith("how_to_send_"))
async def how_to_send(callback: types.CallbackQuery):
    await callback.answer()
    text = "<b>📖 Как передать подарок?</b>\n\n1. Откройте профиль покупателя по кнопке выше.\n2. Нажмите на три точки (⋮) в правом верхнем углу.\n3. Выберите «Отправить подарок».\n4. Выберите подарок из вашего списка.\n5. Подтвердите отправку.\n\n<b>После этого звезды поступят на ваш баланс автоматически.</b>"
    parts = callback.data.split("_"); price, gift_name, sender_id = parts[2], parts[3], parts[4]
    await safe_edit_or_send(callback.message, text, InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=thin("Назад"), callback_data=f"accept_{price}_{gift_name}_{sender_id}")]]))

@dp.callback_query(F.data == "decline_offer")
async def decline(callback: types.CallbackQuery):
    await callback.answer()
    await safe_edit_or_send(callback.message, "<b>❌ Оффер отклонен.</b>")

async def main():
    print("Бот запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "business_message"], drop_pending_updates=True)

if __name__ == "__main__":
    asyncio.run(main())
