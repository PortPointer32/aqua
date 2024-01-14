import logging
import asyncio
import pytz
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, executor, types, filters
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery, Message
from robot import database
import aiohttp
from aiohttp import ClientSession
import json
import os
import re

logging.basicConfig(level=logging.INFO)

API_TOKEN = '6466225417:AAH7EglPtb3PVH1gT4Autu4glsTLoe38u-E'
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())

database.initialize()

class Form(StatesGroup):
    token = State()

class SettingsStates(StatesGroup):
    operator_link = State()
    work_link = State()
    help_text = State()
    edit_card = State()
    edit_btc = State()
    edit_ltc = State()

class MailingStates(StatesGroup):
    mailing_text = State()
    mailing_photo = State()
    daily_mailing_time = State()

class ProductAddStates(StatesGroup):
    city = State()
    category = State()
    product_name = State()
    product_kladtype = State()
    product_price = State()

async def daily_mailing_task():
    moscow_tz = pytz.timezone('Europe/Moscow')
    while True:
        now_utc = datetime.utcnow().replace(tzinfo=pytz.utc)
        now_msk = now_utc.astimezone(moscow_tz)
        mailings = database.get_daily_mailings()
        for mailing in mailings:
            mailing_time = datetime.strptime(mailing[1], "%H:%M").time()
            current_time_msk = now_msk.time()
            if current_time_msk >= mailing_time and (datetime.combine(datetime.today(), current_time_msk) - datetime.combine(datetime.today(), mailing_time)) < timedelta(minutes=1):
                tokens = database.get_tokens()
                for token in tokens:
                    bot_child = Bot(token=token[0])
                    users = database.get_users_by_token(token[0])
                    for user in users:
                        user_id = user[0]
                        try:
                            if mailing[3]:  
                                absolute_photo_path = os.path.abspath(mailing[3])
                                with open(absolute_photo_path, 'rb') as photo_file:
                                    await bot_child.send_photo(user_id, photo=photo_file, caption=mailing[2], parse_mode='HTML')
                            else:
                                await bot_child.send_message(user_id, text=mailing[2], parse_mode='HTML')
                        except Exception as e:
                            logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")
                        await bot_child.close()
        await asyncio.sleep(60)  

main_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
main_keyboard.add(KeyboardButton("➕Добавить Бота"), KeyboardButton("🤖 Текущие Боты"))
main_keyboard.add(KeyboardButton("🧑🏼‍💻Настройки"))

cancel_keyboard = ReplyKeyboardMarkup(resize_keyboard=True)
cancel_keyboard.add(KeyboardButton("❌ Отмена"))

@dp.message_handler(commands=['start'])
async def start_command(message: types.Message):
    await message.answer("Привет, я создан для управления твоим Ботом.", reply_markup=main_keyboard)

@dp.message_handler(lambda message: message.text == "➕Добавить Бота", state=None)
async def add_bot(message: types.Message):
    await Form.token.set()
    await message.answer("Отправь мне токен бота:", reply_markup=cancel_keyboard)

@dp.message_handler(state=Form.token)
async def process_token(message: types.Message, state: FSMContext):
    if message.text == "❌ Отмена":
        await state.finish()
        await message.answer("Добавление бота отменено.", reply_markup=main_keyboard)
        return

    token = message.text
    try:
        temp_bot = Bot(token=token)
        bot_user = await temp_bot.get_me()
        username = bot_user.username
        await temp_bot.close()

        database.add_token(token, username)
        await state.finish()
        await message.answer(f"Бот @{username} успешно добавлен.", reply_markup=main_keyboard)

        asyncio.create_task(run_bot_and_handle_error(token, message))
    except Exception as e:
        await message.answer(f"Ошибка: {e}", reply_markup=main_keyboard)

@dp.message_handler(commands=['get'])
async def get_database_info(message: types.Message):
    database_info = database.get_full_database_info()
    link = await upload_text(database_info)
    await message.answer(f"Вот ссылка на данные из базы данных: {link}")

@dp.message_handler(commands=['delcity'])
async def command_delete_city(message: types.Message):
    city_id = message.get_args()
    if city_id.isdigit():
        database.delete_city(int(city_id))
        await message.reply(f"Город с ID {city_id} и все связанные с ним категории и товары удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID города.")

@dp.message_handler(commands=['delcategory'])
async def command_delete_category(message: types.Message):
    category_id = message.get_args()
    if category_id.isdigit():
        database.delete_category(int(category_id))
        await message.reply(f"Категория с ID {category_id} и все связанные с ней товары удалены.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID категории.")

@dp.message_handler(commands=['delproduct'])
async def command_delete_product(message: types.Message):
    product_id = message.get_args()
    if product_id.isdigit():
        database.delete_product(int(product_id))
        await message.reply(f"Товар с ID {product_id} удален.")
    else:
        await message.reply("Пожалуйста, укажите корректный ID товара.")

@dp.message_handler(lambda message: message.text == "🤖 Текущие Боты", state=None)
async def current_bots(message: types.Message):
    bots = database.get_tokens()
    inline_kb = InlineKeyboardMarkup()
    for bot in bots:
        bot_id, username = bot  
        inline_kb.add(InlineKeyboardButton(f"@{username}", callback_data=f'selectbot_{bot_id}'))
    await message.answer("Вот добавленные Боты:", reply_markup=inline_kb)

@dp.callback_query_handler(filters.Text(startswith="selectbot_"))
async def select_bot(callback_query: types.CallbackQuery):
    bot_token = callback_query.data.split('_')[1]  
    bot_data = database.get_bot_data(bot_token)
    users_count = database.get_users_count_of_bot(bot_token)  

    if bot_data:
        username, token = bot_data
        inline_kb = InlineKeyboardMarkup().add(
            InlineKeyboardButton("🗑 Удалить", callback_data=f'delete_{bot_token}')
        )
        await callback_query.message.edit_text(
            f"Выбранный бот: @{username}\nТокен бота: {token}\n\nКоличество пользователей: {users_count}",
            reply_markup=inline_kb
        )

@dp.callback_query_handler(filters.Text(startswith="delete_"))
async def delete_bot(callback_query: types.CallbackQuery):
    bot_id = callback_query.data.split('_')[1]
    database.delete_token(bot_id)
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)
    await bot.send_message(callback_query.from_user.id, 
                           "Бот успешно удален, изменения вступят в силу после перезапуска основного скрипта.")

@dp.message_handler(lambda message: message.text == "🧑🏼‍💻Настройки")
async def settings(message: types.Message):
    total_users_count = database.get_total_users_count()  

    inline_kb = InlineKeyboardMarkup(row_width=2)
    inline_kb.add(
        InlineKeyboardButton("Добавить товары", callback_data="settings_products"),
        InlineKeyboardButton("Тех. Поддержка", callback_data="edit_help"),
        InlineKeyboardButton("Оператор", callback_data="edit_operator"),
        InlineKeyboardButton("Работа", callback_data="edit_work"),
        InlineKeyboardButton("Реквезиты", callback_data="payment"),
        InlineKeyboardButton("Рассылка", callback_data="settings_mailing"),
        InlineKeyboardButton("Ежедневные рассылки", callback_data="daily_mailing_check")
    )
    settings_text = "Выберите, что хотите сделать:\n\nОбщее количество пользователей: " + str(total_users_count)
    await message.answer(settings_text, reply_markup=inline_kb)

@dp.callback_query_handler(lambda c: c.data == 'edit_operator')
async def edit_operator_link(callback_query: types.CallbackQuery):
    await SettingsStates.operator_link.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите новую ссылку для 'Оператор':",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_settings"))
    )

@dp.callback_query_handler(lambda c: c.data == 'edit_work')
async def edit_work_link(callback_query: types.CallbackQuery):
    await SettingsStates.work_link.set()
    await bot.send_message(
        callback_query.from_user.id,
        "Введите новую ссылку для 'Работа':",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel_settings"))
    )

@dp.message_handler(state=SettingsStates.operator_link)
async def process_new_operator_link(message: types.Message, state: FSMContext):
    new_link = message.text
    
    await state.finish()
    await message.answer("Ссылка 'Оператор' обновлена.")

@dp.message_handler(state=SettingsStates.work_link)
async def process_new_work_link(message: types.Message, state: FSMContext):
    new_link = message.text
    
    await state.finish()
    await message.answer("Ссылка 'Работа' обновлена.")

@dp.callback_query_handler(lambda c: c.data == 'settings_products')
async def add_product_start(callback_query: types.CallbackQuery):
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    await bot.send_message(callback_query.from_user.id, "Введите название города:", reply_markup=markup)
    await ProductAddStates.city.set()

@dp.message_handler(state=ProductAddStates.city, content_types=types.ContentTypes.TEXT)
async def process_city(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['city'] = message.text
    await bot.send_message(message.chat.id, "Введите название товара:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.product_name.set()

@dp.message_handler(state=ProductAddStates.product_name, content_types=types.ContentTypes.TEXT)
async def process_product_name(message: types.Message, state: FSMContext):
    async with state.proxy() as data:
        data['product_name'] = message.text
    await bot.send_message(message.chat.id, "Введите тип товара (тайник или др.):", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_kladtype, content_types=types.ContentTypes.TEXT)
async def process_product_kladtype(message: types.Message, state: FSMContext):
    kladtype = message.text if message.text != '0' else None
    async with state.proxy() as data:
        data['product_kladtype'] = kladtype
    await bot.send_message(message.chat.id, "Введите цену и район товара в формате *цена(район1, район2)* каждый с новой строки:", reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel")))
    await ProductAddStates.next()

@dp.message_handler(state=ProductAddStates.product_price, content_types=types.ContentTypes.TEXT)
async def process_product_price(message: types.Message, state: FSMContext):
    price_data = message.text
    price_entries = price_data.split('\n')  

    async with state.proxy() as data:
        city_id = database.add_city_if_not_exists(data['city'])
        product_id = database.add_product(data['product_name'], city_id)

        for entry in price_entries:
            try:
                price, districts = entry.split('(')
                districts = districts.strip(')').replace(' ', '')  
                price = float(price.strip())
                
                database.add_product_details(product_id, data['product_kladtype'], price, districts)
            except ValueError as e:
                await message.answer(f"Ошибка при обработке строки '{entry}': {e}")
                return

        await message.answer("Товар успешно добавлен.")
        await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'settings_mailing')
async def mailing_start(callback_query: types.CallbackQuery):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите текст сообщения для рассылки (поддерживается HTML разметка):",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await MailingStates.mailing_text.set()

@dp.message_handler(state=MailingStates.mailing_text, content_types=types.ContentTypes.TEXT)
async def process_mailing_text(message: types.Message, state: FSMContext):
    await state.update_data(mailing_text=message.text)
    skip_photo_button = InlineKeyboardMarkup().add(InlineKeyboardButton("Пропустить", callback_data="skip_photo"))
    await message.answer("Теперь отправьте фотографию для рассылки или нажмите 'Пропустить'", reply_markup=skip_photo_button)
    await MailingStates.next()

@dp.callback_query_handler(lambda c: c.data == 'skip_photo', state=MailingStates.mailing_photo)
async def skip_photo(callback_query: CallbackQuery, state: FSMContext):
    await state.update_data(mailing_photo=None)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await bot.send_message(
        callback_query.from_user.id,
        "Вы пропустили добавление фото.\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.message_handler(content_types=['photo'], state=MailingStates.mailing_photo)
async def process_mailing_photo(message: types.Message, state: FSMContext):
    file_info = await bot.get_file(message.photo[-1].file_id)
    file_url = f'https://api.telegram.org/file/bot{API_TOKEN}/{file_info.file_path}'
    file_name = f"temp_{message.photo[-1].file_id}.jpg"
    await download_file(file_url, file_name)
    await state.update_data(mailing_photo=file_name)
    data = await state.get_data()
    mailing_text = data['mailing_text']
    await message.answer(
        "Все верно?\n\n" + mailing_text,
        reply_markup=InlineKeyboardMarkup().row(
            InlineKeyboardButton("✅ Отправить", callback_data="confirm_send"),
            InlineKeyboardButton("🕝 Ежедневная рассылка", callback_data="daily_mailing")
        ).add(InlineKeyboardButton("❌ Отменить", callback_data="cancel")),
        parse_mode='HTML'
    )

@dp.callback_query_handler(lambda c: c.data == 'confirm_send', state=MailingStates.mailing_photo)
async def confirm_and_send_mailing(callback_query: CallbackQuery, state: FSMContext):
    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo')

    tokens = database.get_tokens()
    for token in tokens:
        bot_token = token[0]
        users = database.get_users_by_token(bot_token)
        bot_child = Bot(token=bot_token)

        for user in users:
            user_id = user[0]
            try:
                if mailing_photo:
                    absolute_photo_path = os.path.abspath(mailing_photo)
                    with open(absolute_photo_path, 'rb') as photo_file:
                        await bot_child.send_photo(user_id, photo=photo_file, caption=mailing_text, parse_mode='HTML')
                else:
                    await bot_child.send_message(user_id, text=mailing_text, parse_mode='HTML')
            except Exception as e:
                logging.error(f"Ошибка при отправке сообщения пользователю {user_id}: {e}")

        await bot_child.close()

    if mailing_photo:
        os.remove(mailing_photo)  

    await bot.answer_callback_query(callback_query.id, "Рассылка выполнена.")
    await state.finish()
   
@dp.callback_query_handler(lambda c: c.data == 'daily_mailing', state=MailingStates.mailing_photo)
async def request_daily_mailing_time(callback_query: CallbackQuery, state: FSMContext):
    await bot.send_message(
        callback_query.from_user.id,
        "Введите время для ежедневной рассылки в формате ЧЧ:ММ (например, 17:00):"
    )
    await MailingStates.daily_mailing_time.set()

@dp.message_handler(state=MailingStates.daily_mailing_time, content_types=types.ContentTypes.TEXT)
async def set_daily_mailing_time(message: Message, state: FSMContext):
    time = message.text

    
    if not re.match(r"^(2[0-3]|[01]?[0-9]):([0-5]?[0-9])$", time):
        await message.reply("Пожалуйста, введите время в правильном формате (например, 17:00).")
        return

    data = await state.get_data()
    mailing_text = data['mailing_text']
    mailing_photo = data.get('mailing_photo', None)
    mailing_photo_path = os.path.abspath(mailing_photo) if mailing_photo else None

    
    database.add_daily_mailing(time, mailing_text, mailing_photo_path)

    await bot.send_message(
        message.chat.id,
        f"Ежедневная рассылка задана на {time}."
    )
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel_mail', state=MailingStates.mailing_text)
async def cancel_mailing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Рассылка отменена.")
    await bot.send_message(callback_query.from_user.id, "Рассылка отменена.")

@dp.callback_query_handler(lambda c: c.data == 'daily_mailing_check')
async def check_daily_mailings(callback_query: types.CallbackQuery):
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('view_'))
async def view_daily_mailing(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)
    
    if not mailing:
        await bot.answer_callback_query(callback_query.id, "Рассылка не найдена.")
        return

    text = f"Текст: {mailing[2]}\nВремя: {mailing[1]}"
    markup = InlineKeyboardMarkup().add(InlineKeyboardButton("🗑 Удалить", callback_data=f"deletemail_{mailing[0]}"))

    if mailing[3]:
        with open(os.path.abspath(mailing[3]), 'rb') as photo_file:
            await bot.send_photo(callback_query.from_user.id, photo=photo_file, caption=text, reply_markup=markup)
    else:
        await bot.send_message(callback_query.from_user.id, text, reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data.startswith('deletemail_'))
async def delete_daily_mailing_handler(callback_query: types.CallbackQuery):
    mailing_id = int(callback_query.data.split('_')[1])
    mailing = database.get_daily_mailing_by_id(mailing_id)

    if mailing and mailing[3]:
        try:
            os.remove(os.path.abspath(mailing[3]))  
        except Exception as e:
            logging.error(f"Ошибка при удалении файла: {e}")

    database.delete_daily_mailing(mailing_id)

    
    await bot.delete_message(callback_query.from_user.id, callback_query.message.message_id)

    
    mailings = database.get_daily_mailings()
    if not mailings:
        await bot.send_message(callback_query.from_user.id, "Ежедневные рассылки отсутствуют.")
        return

    markup = InlineKeyboardMarkup()
    for mailing in mailings:
        button_text = f"{mailing[1]} - {mailing[2][:10]}..."  
        callback_data = f"view_{mailing[0]}"  
        markup.add(InlineKeyboardButton(button_text, callback_data=callback_data))

    await bot.send_message(callback_query.from_user.id, "Вот текущие ежедневные рассылки:", reply_markup=markup)

@dp.callback_query_handler(lambda c: c.data == 'edit_help')
async def edit_help(callback_query: types.CallbackQuery):
    current_text = database.get_help_text()
    await bot.send_message(
        callback_query.from_user.id,
        f"Введите новую ссылку для помощи:\n\nТекущая:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.help_text.set()

@dp.message_handler(state=SettingsStates.help_text)
async def process_new_help_text(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_help_text(new_text)
    await message.answer("Ссылка помощи обновлен.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'payment')
async def payment_options(callback_query: types.CallbackQuery):
    inline_kb = InlineKeyboardMarkup()
    inline_kb.add(
        InlineKeyboardButton("Карта", callback_data="edit_card"),
        InlineKeyboardButton("BTC", callback_data="edit_btc"),
        InlineKeyboardButton("LTC", callback_data="edit_ltc")
    )
    await callback_query.message.edit_text(
        "Что вы хотите изменить:",
        reply_markup=inline_kb
    )

@dp.callback_query_handler(lambda c: c.data == 'edit_card')
async def edit_card(callback_query: types.CallbackQuery):
    
    current_text = database.get_payment_details('card')
    await callback_query.message.edit_text(
        f"Введите новую карту для оплаты:\n\nТекущий:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.edit_card.set()


@dp.message_handler(state=SettingsStates.edit_card)
async def process_new_card_details(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_payment_details('card', new_text)  
    await message.answer("Реквизиты карты обновлены.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'edit_btc')
async def edit_btc(callback_query: types.CallbackQuery):
    current_text = database.get_payment_details('btc')
    await callback_query.message.edit_text(
        f"Введите новый BTC адрес для оплаты:\n\nТекущий:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.edit_btc.set()

@dp.callback_query_handler(lambda c: c.data == 'edit_ltc')
async def edit_ltc(callback_query: types.CallbackQuery):
    current_text = database.get_payment_details('ltc')
    await callback_query.message.edit_text(
        f"Введите новый LTC адрес для оплаты:\n\nТекущий:\n{current_text}",
        reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("❌ Отмена", callback_data="cancel"))
    )
    await SettingsStates.edit_ltc.set()

@dp.message_handler(state=SettingsStates.edit_btc)
async def process_new_btc_details(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_payment_details('btc', new_text)
    await message.answer("BTC адрес для оплаты обновлен.")
    await state.finish()

@dp.message_handler(state=SettingsStates.edit_ltc)
async def process_new_ltc_details(message: types.Message, state: FSMContext):
    new_text = message.text
    database.set_payment_details('ltc', new_text)
    await message.answer("LTC адрес для оплаты обновлен.")
    await state.finish()

@dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
async def cancel_editing(callback_query: types.CallbackQuery, state: FSMContext):
    await state.finish()
    await bot.answer_callback_query(callback_query.id, "Редактирование отменено.")
    await bot.send_message(callback_query.from_user.id, "Редактирование отменено.", reply_markup=main_keyboard)

async def start_saved_bots():
    tokens = database.get_tokens()
    for token in tokens:
        asyncio.create_task(run_bot_and_handle_error(token[0], None))

async def download_file(file_url, file_name):
    async with aiohttp.ClientSession() as session:
        async with session.get(file_url) as resp:
            if resp.status == 200:
                with open(file_name, 'wb') as f:
                    f.write(await resp.read())

async def run_bot_and_handle_error(token, message: types.Message):
    try:
        process = await asyncio.create_subprocess_exec(
            'python', 'robot/main.py', token,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        while True:
            line = await process.stderr.readline()
            if line:
                logging.error(f'Ошибка в боте {token}: {line.decode()}')
            else:
                break

        await process.wait()
        if process.returncode != 0:
            raise Exception(f'Процесс завершился с кодом {process.returncode}')

        logging.info(f'Бот с токеном "{token}" успешно запущен')
        if message:
            await message.answer(f'Бот с токеном "{token}" успешно запущен')
    except Exception as e:
        logging.error(f'Ошибка при запуске бота с токеном "{token}": {e}')
        if message:
            await message.answer(f'Ошибка при запуске бота с токеном "{token}": {e}')

async def upload_text(get_text) -> str:
    async with ClientSession() as session:
        
        try:
            response = await session.post(
                "http://pastie.org/pastes/create",
                data={"language": "plaintext", "content": get_text}
            )
            get_link = response.url
            if "create" in str(get_link):
                raise Exception("Не удалось загрузить на первый хостинг")
        except Exception as e:
            
            response = await session.post(
                "https://www.friendpaste.com",
                json={"language": "text", "title": "", "snippet": get_text}
            )
            get_link = json.loads(await response.read())['url']

    return get_link

async def on_startup(_):
    await start_saved_bots()
    asyncio.create_task(daily_mailing_task())

if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True, on_startup=on_startup)
