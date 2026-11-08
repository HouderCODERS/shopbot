import asyncio
import re
import sqlite3
import datetime
import os
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

# ===== НАСТРОЙКИ =====
BOT_TOKEN = "9232358495:AAHAAXXqACqM4-RIDuS1Yxkb2PHOmVH9ZN0"
ADMIN_ID = 8808258682 # Твой ID
SELLER_TG = "s3rp3ntcoders"
SUPPORT_TG = "iserpentt"
# ======================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class KeyState(StatesGroup):
    waiting_for_key = State()

# === БАЗА ДАННЫХ ===
data_dir = Path(os.environ.get("DATA_DIR", "."))
data_dir.mkdir(parents=True, exist_ok=True)
db_path = data_dir / "shop.db"

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
    notify_msg TEXT DEFAULT NULL
)
""")
cur.execute("""
CREATE TABLE IF NOT EXISTS keys (
    key_code TEXT PRIMARY KEY,
    date_until TEXT
)
""")
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
        [InlineKeyboardButton(text="🛒 Купить", callback_data="buy")],
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
    await message.answer("👋 Добро пожаловать в магазин!\n\nВыберите действие:", reply_markup=main_menu())

# === СЕКРЕТНАЯ КОМАНДА ДЛЯ АДМИНА ===
@dp.message(Command("code"))
async def secret_code(message: types.Message):
    args = message.text.split()
    if len(args) < 2: return
    
    # Если ввели секретный код и это админ
    if args[1] == "hoholadmin" and message.from_user.id == ADMIN_ID:
        await message.answer("👑 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_menu())
        return

    # Если это обычный ключ, активируем его
    if message.from_user.id != ADMIN_ID:
        pass # логика для юзеров ниже

# === АДМИН-ПАНЕЛЬ (ВНУТРИ ШОПА) ===
def admin_menu():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="👥 Список юзеров", callback_data="admin_users")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")]
    ])

@dp.callback_query(F.data == "admin_menu")
async def admin_to_main(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    await callback.message.edit_text("👑 <b>Админ-панель</b>\n\nВыберите действие:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_users")
async def admin_users(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    
    cur.execute("SELECT user_id, username, full_name, sub_until FROM users ORDER BY sub_until DESC")
    users = cur.fetchall()

    if not users:
        await callback.message.edit_text("❌ Пользователей пока нет.", reply_markup=admin_menu())
        return

    text = "👥 <b>Все юзеры:</b>\n\n"
    kb = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")

    for u in users:
        sub = u['sub_until']
        status = "✅" if sub and sub >= today else "❌"
        text += f"{status} {u['full_name']} (@{u['username']})\n"
        kb.append([InlineKeyboardButton(text=f"{status} {u['full_name']}", callback_data=f"admin_user_{u['user_id']}")])

    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")])
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user_info(callback: types.CallbackQuery):
    await callback.answer()
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    cur.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cur.fetchone()

    if not user:
        await callback.message.edit_text("❌ Пользователь не найден.", reply_markup=admin_menu())
        return

    today = datetime.datetime.now().strftime("%Y-%m-%d")
    sub = user['sub_until']
    status = "✅ Активна" if sub and sub >= today else "❌ Истекла"
    sub_text = sub if sub else "Нет"

    text = (
        f"👤 <b>Инфо о юзере</b>\n\n"
        f"Имя: {user['full_name']}\n"
        f"Юзер: @{user['username']}\n"
        f"ID: <code>{user['user_id']}</code>\n"
        f"Подписка: {sub_text} ({status})"
    )

    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Продлить (30 дней)", callback_data=f"admin_extend_{user_id}")],
        [InlineKeyboardButton(text="❌ Забрать подписку", callback_data=f"admin_revoke_{user_id}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users")]
    ])

    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data.startswith("admin_extend_"))
async def admin_extend(callback: types.CallbackQuery):
    await callback.answer("Продлеваю...")
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    today = datetime.datetime.now()

    if row and row['sub_until'] and row['sub_until'] > today.strftime("%Y-%m-%d"):
        base = datetime.datetime.strptime(row['sub_until'], "%Y-%m-%d")
        new_date = base + datetime.timedelta(days=30)
    else:
        new_date = today + datetime.timedelta(days=30)
    
    new_date_str = new_date.strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (new_date_str, user_id))
    conn.commit()

    await admin_user_info(callback)

@dp.callback_query(F.data.startswith("admin_revoke_"))
async def admin_revoke(callback: types.CallbackQuery):
    await callback.answer("Забираю...")
    if callback.from_user.id != ADMIN_ID: return
    user_id = int(callback.data.split("_")[2])
    
    cur.execute("UPDATE users SET sub_until = NULL WHERE user_id = ?", (user_id,))
    conn.commit()

    await admin_user_info(callback)

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
        f"📊 <b>Статистика:</b>\n\n"
        f"Всего юзеров: {total}\n"
        f"С активной подпиской: {active}\n"
        f"Без подписки: {total - active}"
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)


# === ОСТАЛЬНЫЕ КНОПКИ ШОПА ===
@dp.callback_query(F.data == "main_menu")
async def to_main(callback: types.CallbackQuery):
    await callback.answer()
    await callback.message.edit_text("👋 Выберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "tutorial")
async def tutorial(callback: types.CallbackQuery):
    await callback.answer()
    text = (
        "📖 <b>Как сделать оффер:</b>\n\n"
        "1. Зайдите в личный чат.\n"
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
    await callback.message.edit_text("🔑 <b>Введите ключ</b>:", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Отмена", callback_data="buy")]]))
    await state.set_state(KeyState.waiting_for_key)

@dp.message(KeyState.waiting_for_key)
async def process_key(message: types.Message, state: FSMContext):
    user_key = message.text.strip()
    await state.clear()
    save_user(message.from_user)

    if user_key == "serpentcoders" and message.from_user.id == ADMIN_ID:
        cur.execute("UPDATE users SET sub_until = '2099-12-31' WHERE user_id = ?", (message.from_user.id,))
        conn.commit()
        await message.answer("✅ Админ-код принят! Подписка навсегда.", reply_markup=main_menu())
        return

    cur.execute("SELECT date_until FROM keys WHERE key_code = ?", (user_key,))
    row = cur.fetchone()
    if not row:
        await message.answer("❌ Неверный ключ!", reply_markup=buy_menu())
        return

    cur.execute("UPDATE users SET sub_until = ? WHERE user_id = ?", (row[0], message.from_user.id))
    conn.commit()
    await message.answer(f"✅ <b>Ключ активирован!</b>\nДействует до: <b>{row[0]}</b>", reply_markup=main_menu())

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
    buyer_id = callback.from_user.id
    buyer_username = callback.from_user.username or str(buyer_id)
    await change_message(callback.message, "⏳ <b>Ожидайте подтверждения от продавца...</b>")
    
    admin_text = f"🔔 <b>Покупатель отправил подарок!</b>\n\nПокупатель: @{buyer_username} (ID: <code>{buyer_id}</code>)\nПодарок: {gift_name}\nЦена: {price} ⭐"
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{buyer_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{buyer_id}")]
    ])
    try: await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
    except: pass

@dp.callback_query(F.data.startswith("approve_"))
async def approve_gift(callback: types.CallbackQuery):
    await callback.answer()
    buyer_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(f"✅ Сделка подтверждена.")
    try: await bot.send_message(buyer_id, "✅ <b>Продавец подтвердил получение подарка!</b>")
    except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_gift(callback: types.CallbackQuery):
    await callback.answer()
    buyer_id = int(callback.data.split("_")[1])
    await callback.message.edit_text(f"❌ Сделка отклонена.")
    try: await bot.send_message(buyer_id, "❌ <b>Продавец не получил подарок.</b>")
    except: pass

@dp.callback_query(F.data == "decline_offer")
async def decline(callback: types.CallbackQuery):
    await callback.answer()
    await change_message(callback.message, "❌ <b>Оффер отклонен.</b>")

async def main():
    print("Бот запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "business_message"])

if __name__ == "__main__":
    asyncio.run(main())
