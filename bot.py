from FilmParser import FilmParser, ParserState
from utils import BotStates, KEYS_TO_RU, PARSER_STATES_TO_RU
from config import API_TOKEN
# standard libraries
import os
import time
import threading
import logging
# external libraries
from aiogram.utils.exceptions import NetworkError as aiogramNetworkError
from aiogram import Bot, Dispatcher, executor, types
from aiogram.contrib.fsm_storage.memory import MemoryStorage
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

# Configure logging
logging.basicConfig(level=logging.INFO)

# Initialize bot and dispatcher
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot, storage=MemoryStorage())
dp.middleware.setup(LoggingMiddleware())

inline_btn_1 = InlineKeyboardButton('1', callback_data='1')
inline_btn_2 = InlineKeyboardButton('2', callback_data='2')
inline_btn_3 = InlineKeyboardButton('3', callback_data='3')
kb_list = [inline_btn_1, inline_btn_2, inline_btn_3]

fp = FilmParser()


# Скачивание фильма и индикация состояний парсера
@dp.callback_query_handler(lambda c: 1 <= int(c.data) <= 3, state=str(BotStates.DOWNLOADING))
async def process_download_choice(callback_query: types.CallbackQuery):
    await bot.send_message(callback_query.from_user.id, f"Вы выбрали фильм №{callback_query.data}")
    fp.set_film_by_index(int(callback_query.data) - 1)
    current_state = fp.get_state()
    x = threading.Thread(target=fp.start_download, args=(50,))
    x.start()
    state_msg = await bot.send_message(callback_query.from_user.id, PARSER_STATES_TO_RU[current_state.name])
    while fp.get_state() != ParserState.DONE:
        time.sleep(1)
        if fp.get_state() > current_state:
            await state_msg.delete()
            state_msg = await bot.send_message(callback_query.from_user.id,
                                               PARSER_STATES_TO_RU[(current_state := fp.get_state()).name])
    x.join()
    await state_msg.delete()
    try:
        await bot.send_document(callback_query.from_user.id, open(
            f'{fp.get_film_data().get("name").replace(".", "")}/{fp.get_film_data().get("name")}-final.mp4', 'rb'))
    except aiogramNetworkError:
        await bot.send_message(callback_query.from_user.id, "Ошибка! Файл весит более 50мб, отправляем частями...")
        os.chdir(fp.get_film_data().get("name").replace(".", ""))
        for p in list(os.walk("parts"))[0][-1]:
            os.chdir("parts")
            await bot.send_document(callback_query.from_user.id, open(p, 'rb'))
            os.chdir("..")
    except:
        await bot.send_message(callback_query.from_user.id, "Ошибка! Попробуйте еще раз прописав /start")
    finally:
        state = dp.current_state(user=callback_query.from_user.id)
        await state.reset_state()


# Поиск фильма и предоставление выбора
@dp.message_handler(state=str(BotStates.CHOOSING_FILM))
async def choose_film(message: types.Message):
    loader = await message.answer("Ищем лучшие совпадения...")
    fp.set_film_name_and_update_data(message.text)
    await loader.delete()
    msg_content = str()
    film_list = fp.get_film_list()
    for i, film_data in enumerate(fp.get_film_list()[0:min(3, len(film_list))], start=1):
        msg_content += f"{i}.\n"
        for key, value in film_data.items():
            if value is not None:
                msg_content += f"\t{KEYS_TO_RU[key]}: {value}\n"
        await message.answer(msg_content)
        msg_content = ''
    await message.answer("Выберите фильм", reply_markup=InlineKeyboardMarkup().row(*kb_list[0:min(3, len(film_list))]))
    state = dp.current_state(user=message.from_user.id)
    await state.set_state(BotStates.DOWNLOADING)


# Начало
@dp.message_handler(state='*', commands=['start'])
async def start_bot(message: types.Message):
    await message.answer("Напишите название фильма")
    state = dp.current_state(user=message.from_user.id)
    await state.set_state(BotStates.CHOOSING_FILM)


@dp.message_handler(state='*')
async def echo_message(message: types.Message):
    await message.answer("Чего?")


if __name__ == '__main__':
    executor.start_polling(dp, skip_updates=True)
