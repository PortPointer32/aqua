import os
import sys
from aiogram import Dispatcher, types
import keyboards
import database
from aiogram.dispatcher import FSMContext
from aiogram.dispatcher.filters.state import State, StatesGroup
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton, CallbackQuery
from aiogram.utils.callback_data import CallbackData
import aiohttp
import random
import logging
import time
import json

logging.basicConfig(level=logging.INFO)

class ReplenishBalanceStates(StatesGroup):
    enter_amount = State()
    choose_method = State()
    choose_payment_method = State()

class CaptchaState(StatesGroup):
    input = State()

async def update_crypto_rates():
    global btc_price, ltc_price
    url = 'https://api.coingecko.com/api/v3/simple/price?ids=bitcoin,litecoin&vs_currencies=rub'
    async with aiohttp.ClientSession() as session:
        async with session.get(url) as response:
            data = await response.json()
            btc_price = data['bitcoin']['rub']
            ltc_price = data['litecoin']['rub']

async def periodic_crypto_update():
    while True:
        await update_crypto_rates()
        await asyncio.sleep(900)  

async def show_categories(message: types.Message):
    await message.answer("Выберите категорию:", reply_markup=get_inline_keyboard())
    
def get_inline_keyboard():
    markup = InlineKeyboardMarkup(row_width=1)
    cities = database.get_cities()
    city_buttons = [InlineKeyboardButton(city[1], callback_data=f"city_{city[0]}") for city in cities]
    
    for i in range(0, len(city_buttons), 2):
        buttons_to_add = city_buttons[i:i+2]
        markup.row(*buttons_to_add)

    operator_url = database.get_operator_link()
    help_url = database.get_help_text()
    work_url = database.get_work_link()
    site_url = "https://telegram.org/"
    
    markup.add(InlineKeyboardButton("Баланс (0 руб.)", callback_data="balance"))
    markup.add(InlineKeyboardButton("Последний заказ", callback_data="last_order"))
    markup.add(InlineKeyboardButton("✨САПОРТ✨", url=help_url))
    markup.add(InlineKeyboardButton("💥ОПЕРАТОР", url=operator_url))
    markup.add(InlineKeyboardButton("🚀РАБОТА🚀", url=work_url))
    markup.add(InlineKeyboardButton("💥Наш сайт💥", url=site_url))
    return markup

def correct_minute_form(minutes):
    if 10 <= minutes % 100 <= 20:
        return 'минут'
    elif minutes % 10 == 1:
        return 'минуту'
    elif 2 <= minutes % 10 <= 4:
        return 'минуты'
    else:
        return 'минут'

async def send_random_captcha(message: types.Message, state: FSMContext):
    captcha_dir = 'captcha'
    captcha_files = [f for f in os.listdir(captcha_dir) if f.endswith('.jpg')]
    
    if not captcha_files:
        await message.answer("Ошибка: файлы капчи не найдены.")
        return
    
    captcha_file = random.choice(captcha_files)
    captcha_path = os.path.join(captcha_dir, captcha_file)

    with open(captcha_path, 'rb') as photo:
        await message.answer_photo(
            photo=photo, 
            caption=f"Привет {message.from_user.first_name}. Пожалуйста, решите капчу с цифрами на этом изображении, чтобы убедиться, что вы человек."
        )
        async with state.proxy() as data:
            data['captcha_answer'] = captcha_file.rstrip('.jpg')

btc_price = 0
ltc_price = 0

async def register_handlers(dp: Dispatcher, bot_token):
    @dp.message_handler(commands=['start'], state="*")
    async def cmd_start(message: types.Message, state: FSMContext):
        user_id = message.from_user.id
        if not database.check_user_exists(user_id, bot_token):
            await CaptchaState.input.set()
            await send_random_captcha(message, state)
        else:
            await state.finish()
            await message.answer("Привет", reply_markup=keyboards.main_keyboard())
            await show_categories(message)
    
    @dp.message_handler(state=CaptchaState.input)
    async def handle_captcha_input(message: types.Message, state: FSMContext):
        async with state.proxy() as data:
            correct_answer = data.get('captcha_answer')
        
        if message.text == correct_answer:
            user_id = message.from_user.id
            database.add_user(user_id, bot_token)  
            await state.finish()
            await message.answer("Привет", reply_markup=keyboards.main_keyboard())
            await show_categories(message)
        else:
            await send_random_captcha(message, state)

    @dp.message_handler(lambda message: message.text == "Главное меню", state="*")
    async def handle_main_menu(message: types.Message, state: FSMContext):
        await show_categories(message)

    @dp.callback_query_handler(lambda c: c.data == 'last_order')
    async def handle_last_order(callback_query: types.CallbackQuery):
        await callback_query.answer("У вас нет подтвержденных заказов", show_alert=True)
    
    @dp.callback_query_handler(lambda c: c.data == 'balance')
    async def initiate_replenish_balance(callback_query: types.CallbackQuery):
        await callback_query.answer()
        await ReplenishBalanceStates.enter_amount.set()
        await callback_query.message.answer("Введите сумму на которую вы хотите пополнить баланс:")
    
    
    @dp.message_handler(state=ReplenishBalanceStates.enter_amount)
    async def enter_replenish_amount(message: types.Message, state: FSMContext):
        if not message.text.isdigit() or int(message.text) < 1000:
            await message.reply("Введите корректную сумму (не менее 1000 рублей).")
        else:
            await state.update_data(amount=int(message.text))
            await ReplenishBalanceStates.choose_payment_method.set()
            inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оплата на карту💳", callback_data="method_card"))
            inline_kb.add(InlineKeyboardButton("Bitcoin", callback_data="method_btc"))
            inline_kb.add(InlineKeyboardButton("Litecoin", callback_data="method_ltc"))
            await message.answer("Чем вы будете оплачивать:", reply_markup=inline_kb)
    
    
    @dp.callback_query_handler(state=ReplenishBalanceStates.choose_payment_method)
    async def choose_payment_method(callback_query: types.CallbackQuery, state: FSMContext):
        payment_method = callback_query.data.split('_')[1]
        await state.update_data(payment_method=payment_method)
    
        user_data = await state.get_data()
        amount = int(user_data['amount'])
        order_number = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
        if payment_method in ['btc', 'ltc']:
            
            payment_details = database.get_payment_details(payment_method)
            final_amount = calculate_final_amount(amount, payment_method)
            currency = payment_method.upper()
            await callback_query.message.answer(
                f"Оплатите <b>{final_amount}</b> {currency} на адрес <b>{payment_details}</b>",
                parse_mode='HTML'
            )
        else:
            
            card_details = database.get_payment_details('card')
            await callback_query.message.answer(text=get_payment_instructions(order_number, amount), parse_mode='HTML')
            await callback_query.message.answer(
                f"Заявка на оплату № {order_number}. Переведите на банковскую карту <b>{amount}</b> рублей удобным для вас способом. Важно пополнить ровную сумму.\n<b>{card_details}</b>\n‼️ это <b>НЕ СБЕРБАНК!</b>\n‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n<b>‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ</b>",
                parse_mode='HTML'
            )
        current_time = time.time()
        payment_issue_callback_data = f"issue_{current_time}"
        await callback_query.message.answer(
            "Если в течение часа средства не выдались автоматически, то нажмите на кнопку - 'Проблема с оплатой'",
            reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Проблема с оплатой?", callback_data=payment_issue_callback_data))
        )
        await state.finish()
    @dp.callback_query_handler(lambda c: c.data.startswith('city_'))
    async def process_city_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        city_id = int(callback_query.data.split('_')[1])
    
        products = database.get_products_by_city(city_id)
        markup = InlineKeyboardMarkup(row_width=1)
        for product in products:
            product_name = product[1]
            product_id = product[0]
            price = int(database.get_product_price(product_id))
            markup.add(InlineKeyboardButton(f"{product_name} ({price} руб.)", callback_data=f"product_{product_id}_{city_id}"))
        await callback_query.message.answer("Выберите продукт", reply_markup=markup)
    
    @dp.callback_query_handler(lambda c: c.data.startswith('product_'))
    async def process_product_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        product_id, city_id = map(int, callback_query.data.split('_')[1:])
    
        product_details = database.get_product_details(product_id)
        markup = InlineKeyboardMarkup(row_width=1)
        for detail in product_details:
            districts = detail[2].split(',')
            for district in districts:
                markup.add(InlineKeyboardButton(district, callback_data=f"district_{product_id}_{city_id}_{district}"))
    
        await callback_query.message.answer("выберите район", reply_markup=markup)
    @dp.callback_query_handler(lambda c: c.data.startswith('district_'))
    async def process_district_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, product_id, city_id, district = callback_query.data.split('_')
    
        product_details = database.get_product_details(int(product_id))
        klad_types = set(detail[0] for detail in product_details)
        markup = InlineKeyboardMarkup(row_width=1)
        for klad_type in klad_types:
            markup.add(InlineKeyboardButton(klad_type, callback_data=f"kladtype_{product_id}_{city_id}_{district}_{klad_type}"))
    
        await callback_query.message.answer("Выберите тип", reply_markup=markup)
            
    @dp.callback_query_handler(lambda c: c.data.startswith('kladtype_'))
    async def process_kladtype_selection(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, product_id, city_id, district, klad_type = callback_query.data.split('_')
    
        
        product_id = int(product_id)
        city_id = int(city_id)
    
        
        product_name = database.get_product_name(product_id)
        city_name = database.get_city_name(city_id)
    
        
        order_number = ''.join([str(random.randint(0, 9)) for _ in range(8)])
    
        
        message_text = (
            f"Номер покупки № <b>{order_number}</b>\n"
            f"Город: {city_name}\n"
            f"Район(станция): <b>{district}</b>\n"
            f"Товар и объем: <b>{product_name} ({klad_type})</b>\n"
            "Для проведения оплаты нажмите на кнопку <b>ОПЛАТИТЬ</b>\n"
            "После того, как Вы нажмете кнопку оплаты, у вас есть 30 минут на оплату"
        )
    
        
        markup = InlineKeyboardMarkup(row_width=1)
        markup.add(InlineKeyboardButton("Оплатить", callback_data=f"pay_{order_number}_{product_id}"))
        markup.add(InlineKeyboardButton("Отмена", callback_data="cancel"))
    
        
        await callback_query.message.answer(message_text, reply_markup=markup, parse_mode="HTML")
    @dp.callback_query_handler(lambda c: c.data.startswith('pay_'))
    async def process_payment(callback_query: types.CallbackQuery):
        await callback_query.answer()
        _, order_number, product_id = callback_query.data.split('_')
        product_id = int(product_id)
        
        
        price = database.get_product_price(product_id)
    
        
        inline_kb = InlineKeyboardMarkup().add(InlineKeyboardButton("Оплата на карту💳", callback_data=f"method_card_{order_number}_{price}"))
        inline_kb.add(InlineKeyboardButton("Bitcoin", callback_data=f"method_btc_{order_number}_{price}"))
        inline_kb.add(InlineKeyboardButton("Litecoin", callback_data=f"method_ltc_{order_number}_{price}"))
    
        await callback_query.message.answer("Ваш актуальный баланс 0 руб..\nЧем вы будете оплачивать?", reply_markup=inline_kb)
    @dp.callback_query_handler(lambda c: c.data.startswith('method_'))
    async def choose_payment_method(callback_query: types.CallbackQuery):
        await callback_query.answer()
        parts = callback_query.data.split('_')
        method = parts[1]
        order_number = parts[2]
        price = parts[3]
    
        
        price = float(price)  
    
        if method in ['btc', 'ltc']:
            
            payment_details = database.get_payment_details(method)
            final_amount = calculate_final_amount(price, method)
            currency = method.upper()
            await callback_query.message.answer(
                f"Оплатите <b>{final_amount}</b> {currency} на адрес <b>{payment_details}</b>\n"
                f"Заявка на оплату № {order_number}.",
                parse_mode='HTML'
            )
        else:
            
            card_details = database.get_payment_details('card')

            price = int(float(price))

            
            payment_instructions = get_payment_instructions(order_number, price)
            await callback_query.message.answer(payment_instructions, parse_mode='HTML')
    
            
            await callback_query.message.answer(
                f"Заявка на оплату № {order_number}. Переведите на банковскую карту <b>{price}</b> рублей удобным для вас способом.\n"
                f"<b>{card_details}</b>\n‼️ это <b>НЕ СБЕРБАНК!</b>\n"
                f"‼️ у вас есть 30 мин на оплату, после чего платёж не будет зачислен\n"
                f"<b>‼️ ПЕРЕВЁЛ НЕТОЧНУЮ СУММУ - ОПЛАТИЛ ЧУЖОЙ ЗАКАЗ</b>",
                parse_mode='HTML'
            )
    
            
            current_time = time.time()
            payment_issue_callback_data = f"issue_{current_time}"
            await callback_query.message.answer(
                "Если в течение часа средства не выдались автоматически, то нажмите на кнопку - 'Проблема с оплатой'",
                reply_markup=InlineKeyboardMarkup().add(InlineKeyboardButton("Проблема с оплатой?", callback_data=payment_issue_callback_data))
            )
    @dp.callback_query_handler(lambda c: c.data == 'cancel', state="*")
    async def handle_cancel(callback_query: types.CallbackQuery, state: FSMContext):
        await callback_query.answer()
        await state.finish()
        
        await show_categories(callback_query.message)
    @dp.callback_query_handler(lambda c: c.data.startswith('issue_'))
    async def issue(callback_query: types.CallbackQuery):
        parts = callback_query.data.split('_')
        issue_time = float(parts[1])  
    
        current_time = time.time()
        if current_time - issue_time < 1800:  
            time_left = int((1800 - (current_time - issue_time)) / 60)  
            minute_form = correct_minute_form(time_left)
            await callback_query.answer(f"Подождите еще {time_left} {minute_form} и в случае неполучения средств нажмите на кнопку еще раз.", show_alert=True)
        else:
            await callback_query.message.answer("Отправьте мне скриншот произведенной оплаты")

 
def calculate_final_amount(amount, payment_method):
    amount = float(amount)
    if payment_method == 'card':
        return amount  
    elif payment_method == 'btc':
        return round(amount / btc_price, 8)  
    elif payment_method == 'ltc':
        return round(amount / ltc_price, 5)  

def get_payment_instructions(order_number, amount):
    instructions = (
        f"✅ ВЫДАННЫЕ РЕКВИЗИТЫ ДЕЙСТВУЮТ 30 МИНУТ\n"
        f"✅ ВЫ ПОТЕРЯЕТЕ ДЕНЬГИ, ЕСЛИ ОПЛАТИТЕ ПОЗЖЕ\n"
        f"✅ ПЕРЕВОДИТЕ ТОЧНУЮ СУММУ. НЕВЕРНАЯ СУММА НЕ БУДЕТ ЗАЧИСЛЕНА.\n"
        f"✅ ОПЛАТА ДОЛЖНА ПРОХОДИТЬ ОДНИМ ПЛАТЕЖОМ.\n"
        f"✅ ПРОБЛЕМЫ С ОПЛАТОЙ? ПЕРЕЙДИТЕ ПО ССЫЛКЕ : <a href='http://ut2.guru/doctor'>doctor</a>\n"
        f"Предоставить чек об оплате и\n"
        f"ID:  <b>{order_number}</b>\n"
        f"✅ С ПРОБЛЕМНОЙ ЗАЯВКОЙ ОБРАЩАЙТЕСЬ НЕ ПОЗДНЕЕ 24 ЧАСОВ С МОМЕНТА ОПЛАТЫ."
    )
    return instructions
