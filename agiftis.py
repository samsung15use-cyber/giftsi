import os
import random
import sqlite3
import asyncio
from datetime import datetime

from aiogram import Bot, Dispatcher, F, types
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.fsm.state import State, StatesGroup
from aiogram.fsm.context import FSMContext
from aiogram.fsm.storage.memory import MemoryStorage

# ========== ⚙️ НАСТРОЙКИ ==========
TOKEN = os.getenv("8559247892:AAEYcK5RM9onRAS_COy0XzwW7gbWiinU6u4")  # Используем переменную окружения
ADMINS = [1417003901, 7146601753] 
EXCLUDED_CHANNEL = -1003638036761  # Канал, который исключаем из рассылки

from aiogram.client.default import DefaultBotProperties

bot = Bot(token=TOKEN, default=DefaultBotProperties(parse_mode="HTML"))
dp = Dispatcher(storage=MemoryStorage())

# ========== 📂 СОСТОЯНИЯ (FSM) ==========
class AdminStates(StatesGroup):
    broadcast_msg = State()
    broadcast_channels_msg = State()
    add_multiple_channels = State()

# ========== 🗃️ БАЗА ДАННЫХ ==========
def init_db():
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute("CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY)")
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN joined_at TIMESTAMP")
    except: pass
    try:
        cursor.execute("ALTER TABLE users ADD COLUMN last_launch TIMESTAMP")
    except: pass
    cursor.execute("CREATE TABLE IF NOT EXISTS channels (id INTEGER PRIMARY KEY AUTOINCREMENT, channel_id INTEGER, name TEXT, url TEXT)")
    cursor.execute("CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value INTEGER)")
    cursor.execute("INSERT OR IGNORE INTO settings VALUES ('total_launches', 0)")
    conn.commit()
    conn.close()

def db_query(query, params=(), fetchone=False, fetchall=False, commit=False):
    conn = sqlite3.connect("bot.db")
    cursor = conn.cursor()
    cursor.execute(query, params)
    res = None
    if fetchone: 
        res = cursor.fetchone()
    if fetchall: 
        res = cursor.fetchall()
    if commit: 
        conn.commit()
    conn.close()
    return res

async def check_subscriptions(user_id):
    """Проверяет подписку на все каналы и возвращает список неподписанных"""
    channels = db_query("SELECT channel_id, name, url FROM channels", fetchall=True)
    if not channels:
        return []
    
    not_subscribed = []
    for ch_id, name, url in channels:
        try:
            if not ch_id:
                continue
            chat_member = await bot.get_chat_member(int(ch_id), user_id)
            if chat_member.status in ['left', 'kicked']:
                not_subscribed.append((ch_id, name, url))
        except Exception as e:
            print(f"Ошибка проверки подписки на канал {ch_id}: {e}")
            not_subscribed.append((ch_id, name, url))
    
    return not_subscribed

async def is_subscribed_all(user_id):
    """Проверяет подписан ли пользователь на ВСЕ каналы"""
    not_subscribed = await check_subscriptions(user_id)
    return len(not_subscribed) == 0

# ========== 💎 ПОЛЬЗОВАТЕЛЬСКАЯ ЧАСТЬ ==========

@dp.message(Command("start"))
async def start_cmd(message: types.Message):
    user_id = message.from_user.id
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    
    db_query("INSERT OR IGNORE INTO users (user_id, joined_at) VALUES (?, ?)", (user_id, now), commit=True)
    db_query("UPDATE users SET last_launch = ? WHERE user_id = ?", (now, user_id), commit=True)
    db_query("UPDATE settings SET value = value + 1 WHERE key = 'total_launches'", commit=True)
    
    kb = InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text="Получить подарок!", callback_data="gift")]])
    await message.answer(
        "👋 <b>Привет! Хочешь бесплатный подарок?</b>\n\n"
        "Мы раздаем звезды и крутые NFT подарки всем новым пользователям. "
        "Это твой шанс получить приз прямо сейчас!\n\n"
        "⚡️ <b>Подарок уже ждет тебя. Нажми на кнопку ниже, чтобы забрать его.</b>", 
        reply_markup=kb
    )

@dp.callback_query(F.data == "gift")
async def gift_call(cb: CallbackQuery):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, я хочу забрать!", callback_data="check_subscription")],
        [InlineKeyboardButton(text="❌ Нет, мне не нужно", callback_data="cancel")]
    ])
    await cb.message.edit_text(
        "💎 <b>Почти готово!</b>\n\n"
        "Твой подарочный бокс забронирован за твоим ID. "
        "Осталось подтвердить, что ты человек, и забрать награду.\n\n"
        "<b>Ты готов подтвердить получение?</b>", 
        reply_markup=kb
    )
    await cb.answer()

@dp.callback_query(F.data == "check_subscription")
async def check_subscription(cb: CallbackQuery):
    """Проверяет подписку и показывает только неподписанные каналы"""
    user_id = cb.from_user.id
    
    not_subscribed = await check_subscriptions(user_id)
    
    if not not_subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Забрать NFT", callback_data="finish")],
            [InlineKeyboardButton(text="⭐ Забрать 700 Звезд", callback_data="finish")]
        ])
        await cb.message.edit_text(
            "🎉 <b>ПОДПИСКА ПОДТВЕРЖДЕНА!</b>\n\n"
            "Все супер! Теперь выбери, какой подарок ты хочешь получить первым:", 
            reply_markup=kb
        )
    else:
        text = (
            "📩 <b>Последнее условие:</b>\n\n"
            "Чтобы забрать подарок, подпишись на эти каналы. Это нужно, чтобы активировать твой личный кабинет:\n\n"
        )
        
        buttons = []
        for ch_id, name, url in not_subscribed:
            text += f" <b>{name}</b>\n"
            buttons.append([InlineKeyboardButton(text=f" {name}", url=url)])
        
        text += "\nКак только подпишешься — жми кнопку <b>«Я ПОДПИСАЛСЯ»</b>!"
        
        buttons.append([InlineKeyboardButton(text="✅ Я ПОДПИСАЛСЯ", callback_data="verify_subscription")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
    
    await cb.answer()

@dp.callback_query(F.data == "verify_subscription")
async def verify_subscription(cb: CallbackQuery):
    """Проверяет подписку после нажатия кнопки"""
    user_id = cb.from_user.id
    
    not_subscribed = await check_subscriptions(user_id)
    
    if not not_subscribed:
        kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="🖼 Забрать NFT", callback_data="finish")],
            [InlineKeyboardButton(text="⭐ Забрать 700 Звезд", callback_data="finish")]
        ])
        await cb.message.edit_text(
            "🎉 <b>ПОДПИСКА ПОДТВЕРЖДЕНА!</b>\n\n"
            "Все супер! Теперь выбери, какой подарок ты хочешь получить первым:", 
            reply_markup=kb
        )
    else:
        text = (
            "❌ <b>Вы не подписаны на все каналы!</b>\n\n"
            "Пожалуйста, подпишитесь на эти каналы:\n\n"
        )
        
        buttons = []
        for ch_id, name, url in not_subscribed:
            text += f" <b>{name}</b>\n"
            buttons.append([InlineKeyboardButton(text=f" {name}", url=url)])
        
        text += "\nПосле подписки нажмите кнопку ниже!"
        
        buttons.append([InlineKeyboardButton(text="✅ Я ПОДПИСАЛСЯ", callback_data="verify_subscription")])
        
        kb = InlineKeyboardMarkup(inline_keyboard=buttons)
        await cb.message.edit_text(text, reply_markup=kb, disable_web_page_preview=True)
        await cb.answer("❌ Вы не подписаны на все каналы! Подпишитесь и нажмите кнопку снова.", show_alert=True)

@dp.callback_query(F.data == "finish")
async def finish_gift(cb: CallbackQuery):
    await cb.message.edit_text(
        "🚀 <b>УСПЕШНО!</b>\n\n"
        "Твоя заявка на получение подарка отправлена в систему.\n\n"
        f"⏳ Проверка займет примерно: <b>{random.randint(2, 8)} часов.</b>\n\n"
        "Не отписывайся от каналов, иначе система отменит выдачу! Жди уведомления. ✅"
    )
    await cb.answer()

@dp.callback_query(F.data == "cancel")
async def cancel_call(cb: CallbackQuery):
    await cb.message.edit_text("Окей, если передумаешь — пиши /start")
    await cb.answer()

# ========== 👑 АДМИН ПАНЕЛЬ ==========

@dp.message(Command("admin"), F.from_user.id.in_(ADMINS))
async def admin_main(message: types.Message):
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Добавить ТГК", callback_data="adm_add"), 
         InlineKeyboardButton(text="❌ Удалить ТГК", callback_data="adm_del")],
        [InlineKeyboardButton(text="📊 Статистика", callback_data="adm_stats")],
        [InlineKeyboardButton(text="📢 Рассылка юзерам", callback_data="adm_send_users"),
         InlineKeyboardButton(text="📢 Пост в каналы", callback_data="adm_send_channels")]
    ])
    await message.answer("<b>🛠 АДМИН-ПАНЕЛЬ</b>", reply_markup=kb)

@dp.callback_query(F.data == "adm_add", F.from_user.id.in_(ADMINS))
async def add_ch_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.add_multiple_channels)
    await cb.message.answer(
        "📝 <b>Массовое добавление каналов</b>\n\n"
        "Пришли список каналов, где каждый канал с новой строки в формате:\n"
        "<code>ID, Название, Ссылка</code>\n\n"
        "<b>Пример:</b>\n"
        "<code>-100123, Мой Канал, https://t.me/link</code>\n\n"
        "<b>Важно:</b> Для получения ID канала отправьте любое сообщение в канал и перешлите его боту @getmyid_bot"
    )
    await cb.answer()

@dp.message(AdminStates.add_multiple_channels)
async def add_multiple_exec(msg: types.Message, state: FSMContext):
    lines = msg.text.split('\n')
    added_count = 0
    error_count = 0
    for line in lines:
        try:
            parts = [p.strip() for p in line.split(',')]
            if len(parts) == 3:
                ch_id, name, url = parts
                int(ch_id)
                db_query("INSERT INTO channels (channel_id, name, url) VALUES (?, ?, ?)", (ch_id, name, url), commit=True)
                added_count += 1
            else: 
                error_count += 1
        except Exception as e:
            error_count += 1
            print(f"Ошибка добавления канала: {e}")
    await state.clear()
    await msg.answer(f"✅ Добавлено: {added_count}\n❌ Ошибок: {error_count}")

@dp.callback_query(F.data == "adm_del", F.from_user.id.in_(ADMINS))
async def del_ch_list(cb: CallbackQuery):
    channels = db_query("SELECT id, name FROM channels", fetchall=True)
    if not channels: 
        return await cb.answer("Список пуст!", show_alert=True)
    
    buttons = []
    for cid, name in channels:
        buttons.append([InlineKeyboardButton(text=f"❌ {name}", callback_data=f"del_{cid}")])
    
    kb = InlineKeyboardMarkup(inline_keyboard=buttons)
    await cb.message.answer("Выберите канал для удаления:", reply_markup=kb)
    await cb.answer()

@dp.callback_query(F.data.startswith("del_"), F.from_user.id.in_(ADMINS))
async def del_exec(cb: CallbackQuery):
    chid = cb.data.split("_")[1]
    db_query("DELETE FROM channels WHERE id=?", (chid,), commit=True)
    await cb.message.edit_text("✅ Канал удален!")
    await cb.answer()

@dp.callback_query(F.data == "adm_stats", F.from_user.id.in_(ADMINS))
async def adm_stats(cb: CallbackQuery):
    total_u = db_query("SELECT COUNT(*) FROM users", fetchone=True)[0]
    total_l = db_query("SELECT value FROM settings WHERE key = 'total_launches'", fetchone=True)[0]
    total_channels = db_query("SELECT COUNT(*) FROM channels", fetchone=True)[0]
    await cb.message.answer(
        f"📊 <b>СТАТИСТИКА:</b>\n\n"
        f"🚀 Запусков: {total_l}\n"
        f"👥 Юзеров: {total_u}\n"
        f"📢 Каналов: {total_channels}"
    )
    await cb.answer()

# ========== РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ ==========
@dp.callback_query(F.data == "adm_send_users", F.from_user.id.in_(ADMINS))
async def broadcast_users_start(cb: CallbackQuery, state: FSMContext):
    await state.set_state(AdminStates.broadcast_msg)
    await cb.message.answer(
        "📢 <b>РАССЫЛКА ПОЛЬЗОВАТЕЛЯМ</b>\n\n"
        "Введите текст для рассылки всем пользователям.\n"
        "Можно использовать HTML разметку.\n\n"
        "Для отмены отправьте /cancel"
    )
    await cb.answer()

@dp.message(AdminStates.broadcast_msg)
async def broadcast_users_exec(msg: types.Message, state: FSMContext):
    if msg.text == "/cancel":
        await state.clear()
        await msg.answer("❌ Рассылка отменена!")
        return
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, отправить", callback_data="confirm_users_broadcast"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    
    await state.update_data(broadcast_text=msg.text)
    await msg.answer(
        f"📝 <b>ПРЕДПРОСМОТР:</b>\n\n{msg.text}\n\n"
        f"<b>Отправить это сообщение всем пользователям?</b>",
        reply_markup=kb
    )

@dp.callback_query(F.data == "confirm_users_broadcast", F.from_user.id.in_(ADMINS))
async def confirm_users_broadcast(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")
    
    if not text:
        await cb.answer("Ошибка: текст не найден!")
        await state.clear()
        return
    
    status_msg = await cb.message.answer("🔄 <b>Начинаю рассылку пользователям...</b>")
    
    users = db_query("SELECT user_id FROM users", fetchall=True)
    success_count = 0
    fail_count = 0
    
    for (uid,) in users:
        try:
            await bot.send_message(uid, text)
            success_count += 1
            await asyncio.sleep(0.05)
        except Exception as e:
            fail_count += 1
            print(f"Не удалось отправить пользователю {uid}: {e}")
    
    await status_msg.delete()
    await cb.message.edit_text(
        f"✅ <b>РАССЫЛКА ЗАВЕРШЕНА!</b>\n\n"
        f"📨 Отправлено: {success_count}\n"
        f"❌ Ошибок: {fail_count}\n"
        f"👥 Всего пользователей: {len(users)}"
    )
    await state.clear()
    await cb.answer()

# ========== РАССЫЛКА В КАНАЛЫ ==========
@dp.callback_query(F.data == "adm_send_channels", F.from_user.id.in_(ADMINS))
async def broadcast_channels_start(cb: CallbackQuery, state: FSMContext):
    channels_raw = db_query("SELECT name, channel_id FROM channels", fetchall=True)
    channels = [(name, ch_id) for name, ch_id in channels_raw if ch_id != EXCLUDED_CHANNEL]
    
    if not channels:
        await cb.answer("❌ Нет добавленных каналов для рассылки! (канал исключен)", show_alert=True)
        return
    
    channels_list = "\n".join([f"📢 {name}" for name, _ in channels])
    
    await state.set_state(AdminStates.broadcast_channels_msg)
    await cb.message.answer(
        f"📢 <b>РАССЫЛКА В КАНАЛЫ-СПОНСОРЫ</b>\n\n"
        f"<b>Каналы для отправки:</b>\n{channels_list}\n\n"
        f"<b>⚠️ Канал {EXCLUDED_CHANNEL} исключен из рассылки!</b>\n\n"
        f"Введите текст для публикации во все эти каналы.\n"
        f"Можно использовать HTML разметку.\n\n"
        f"Для отмены отправьте /cancel"
    )
    await cb.answer()

@dp.message(AdminStates.broadcast_channels_msg)
async def broadcast_channels_exec(msg: types.Message, state: FSMContext):
    if msg.text == "/cancel":
        await state.clear()
        await msg.answer("❌ Рассылка отменена!")
        return
    
    channels_raw = db_query("SELECT channel_id, name FROM channels", fetchall=True)
    channels = [(ch_id, name) for ch_id, name in channels_raw if ch_id != EXCLUDED_CHANNEL]
    
    if not channels:
        await msg.answer(f"❌ Нет добавленных каналов для рассылки! (канал {EXCLUDED_CHANNEL} исключен)")
        await state.clear()
        return
    
    channels_list = "\n".join([f"📢 {name}" for _, name in channels])
    
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="✅ Да, опубликовать", callback_data="confirm_channels_broadcast"),
         InlineKeyboardButton(text="❌ Отмена", callback_data="cancel_broadcast")]
    ])
    
    await state.update_data(broadcast_text=msg.text)
    await msg.answer(
        f"📝 <b>ПРЕДПРОСМОТР ПОСТА:</b>\n\n{msg.text}\n\n"
        f"<b>Каналы для публикации:</b>\n{channels_list}\n\n"
        f"<b>⚠️ Канал {EXCLUDED_CHANNEL} исключен из рассылки!</b>\n\n"
        f"<b>Опубликовать это сообщение во все каналы?</b>",
        reply_markup=kb,
        disable_web_page_preview=True
    )

@dp.callback_query(F.data == "confirm_channels_broadcast", F.from_user.id.in_(ADMINS))
async def confirm_channels_broadcast(cb: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    text = data.get("broadcast_text")
    
    if not text:
        await cb.answer("Ошибка: текст не найден!")
        await state.clear()
        return
    
    channels_raw = db_query("SELECT channel_id, name FROM channels", fetchall=True)
    channels = [(ch_id, name) for ch_id, name in channels_raw if ch_id != EXCLUDED_CHANNEL]
    
    if not channels:
        await cb.answer("❌ Нет добавленных каналов для рассылки!")
        await state.clear()
        return
    
    status_msg = await cb.message.answer("🔄 <b>Начинаю публикацию в каналы...</b>")
    
    success_count = 0
    fail_count = 0
    results = []
    
    for ch_id, ch_name in channels:
        try:
            sent_msg = await bot.send_message(int(ch_id), text)
            success_count += 1
            results.append(f"✅ {ch_name} - успешно")
            
            try:
                post_link = f"https://t.me/c/{str(ch_id)[4:]}/{sent_msg.message_id}"
                results.append(f"   🔗 {post_link}")
            except:
                pass
                
            await asyncio.sleep(0.5)
            
        except Exception as e:
            fail_count += 1
            error_text = str(e)
            results.append(f"❌ {ch_name} - ошибка: {error_text[:50]}")
            print(f"Не удалось отправить в канал {ch_name} ({ch_id}): {e}")
    
    await status_msg.delete()
    
    report = f"✅ <b>ПУБЛИКАЦИЯ ЗАВЕРШЕНА!</b>\n\n"
    report += f"📨 Успешно: {success_count}\n"
    report += f"❌ Ошибок: {fail_count}\n"
    report += f"📢 Всего каналов: {len(channels)}\n\n"
    report += f"<b>Подробности:</b>\n"
    report += "\n".join(results[:20])
    
    if len(results) > 20:
        report += f"\n\n... и еще {len(results) - 20} каналов"
    
    await cb.message.edit_text(report, disable_web_page_preview=True)
    await state.clear()
    await cb.answer()

@dp.callback_query(F.data == "cancel_broadcast", F.from_user.id.in_(ADMINS))
async def cancel_broadcast(cb: CallbackQuery, state: FSMContext):
    await state.clear()
    await cb.message.edit_text("❌ Рассылка отменена!")
    await cb.answer()

# ========== ЗАПУСК БОТА ==========
async def main():
    init_db()
    print("💎 NFT Бот запущен!")
    print("👑 Админ панель: /admin")
    print(f"⚠️ Канал {EXCLUDED_CHANNEL} исключен из рассылки!")
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())