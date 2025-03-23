import telebot
import humanize
from telebot.types import ReplyKeyboardMarkup, KeyboardButton, InlineKeyboardButton, InlineKeyboardMarkup
import pymongo
import datetime
from bson.objectid import ObjectId

mongo_client = pymongo.MongoClient("mongodb://localhost:27017/")
database = mongo_client["task_manager"]
tasks_db = database["user_tasks"]

bot_token = '7788966144:AAH3S95XEOPDOCj7Cv9KGd5oDk4pvFPmqoM'
bot_instance = telebot.TeleBot(bot_token)
user_cache = {}

def generate_main_buttons():
    menu = ReplyKeyboardMarkup(row_width=2, resize_keyboard=True, one_time_keyboard=False)
    menu.add(
        KeyboardButton("➕ Создать задачу"),
        KeyboardButton("📋 Просмотр задач"),
        KeyboardButton("ℹ️ Информация"),
        KeyboardButton("🔙 Назад")
    )
    return menu

@bot_instance.message_handler(commands=['start'])
def start(message):
    bot_instance.reply_to(
        message,
        "🎉 SkatBot настроен! 🎉\n\nПожалуйста, выберите действие:",
        parse_mode="Markdown",
        reply_markup=generate_main_buttons()
    )

@bot_instance.message_handler(func=lambda msg: True)
def handle_menu(msg):
    if msg.text in ["➕ Создать задачу", "/create"]:
        bot_instance.reply_to(msg, "Введите название задачи:", parse_mode="Markdown")
        user_cache[msg.chat.id] = {}
        bot_instance.register_next_step_handler(msg, get_task_title)
    elif msg.text in ["📋 Просмотр задач", "/view"]:
        bot_instance.send_message(msg.chat.id, "Вот ваши задачи:", parse_mode="Markdown")
        display_tasks(msg)
    elif msg.text == "ℹ️ Информация":
        send_info(msg)
    elif msg.text == "🔙 Назад":
        go_back(msg)
    else:
        bot_instance.reply_to(msg, "❌ Неверный выбор.", reply_markup=generate_main_buttons())

@bot_instance.message_handler(commands=['create'])
def create_task(msg):
    chat_id = msg.chat.id
    user_cache[chat_id] = {}
    bot_instance.send_message(chat_id, "Введите название задачи:")
    bot_instance.register_next_step_handler(msg, get_task_title)

def get_task_title(msg):
    chat_id = msg.chat.id
    if msg.text == "🔙 Назад":
        go_back(msg)
        return
    user_cache[chat_id]['title'] = msg.text
    bot_instance.send_message(chat_id, "Добавьте описание задачи.")
    bot_instance.register_next_step_handler(msg, get_task_description)

def get_task_description(msg):
    chat_id = msg.chat.id
    if msg.text == "🔙 Назад":
        go_back(msg)
        return
    user_cache[chat_id]['description'] = msg.text
    bot_instance.send_message(chat_id, "Укажите дедлайн: дд мм гггг (через пробел)")
    bot_instance.register_next_step_handler(msg, get_task_deadline)

def get_task_deadline(msg):
    chat_id = msg.chat.id
    if msg.text == "🔙 Назад":
        go_back(msg)
        return
    try:
        deadline_date = datetime.datetime.strptime(msg.text, '%d %m %Y')
        user_cache[chat_id]['deadline'] = deadline_date
        task_data = {
            'user_id': msg.from_user.id,
            'chat_id': chat_id,
            'title': user_cache[chat_id]['title'],
            'description': user_cache[chat_id]['description'],
            'deadline': user_cache[chat_id]['deadline'],
            'status': False
        }
        tasks_db.insert_one(task_data)
        bot_instance.send_message(chat_id, "Задача успешно добавлена!")
    except ValueError:
        bot_instance.send_message(chat_id, "Неверный формат даты. Используйте дд мм гггг (через пробел).")
    finally:
        user_cache.pop(chat_id, None)

def display_tasks(msg):
    chat_id = msg.chat.id
    tasks = tasks_db.find({'chat_id': chat_id})
    if tasks_db.count_documents({'chat_id': chat_id}) == 0:
        bot_instance.send_message(chat_id, "У вас нет задач.")
    else:
        for task in tasks:
            keyboard = InlineKeyboardMarkup()
            task_id = task["_id"]
            title = task['title']
            description = task['description']
            status = task['status']
            deadline = task['deadline']
            response = (
                f"📌 *{title}*\n"
                f"📝 {description}\n"
                f"⏳ {humanize.naturalday(deadline).capitalize()}\n"
            )
            if not status:
                response += "❌ Не выполнено\n"
                button_done = InlineKeyboardButton(text="Выполнено", callback_data=f'done_{task_id}')
                button_edit = InlineKeyboardButton(text="Изменить", callback_data=f'edit_{task_id}')
                button_delete = InlineKeyboardButton(text="Удалить", callback_data=f'delete_{task_id}')
                keyboard.add(button_done, button_edit, button_delete)
            else:
                response += "✅ Выполнено!\n"
                button_undone = InlineKeyboardButton(text="Не выполнено", callback_data=f'undone_{task_id}')
                button_edit = InlineKeyboardButton(text="Изменить", callback_data=f'edit_{task_id}')
                button_delete = InlineKeyboardButton(text="Удалить", callback_data=f'delete_{task_id}')
                keyboard.add(button_undone, button_edit, button_delete)
            bot_instance.send_message(chat_id, response, parse_mode="Markdown", reply_markup=keyboard)

@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('done_'))
def completed(call):
    message = call.message
    task_id = call.data.split("_")[1]
    tasks_db.find_one_and_update({"_id": ObjectId(task_id)}, {'$set': {"status": True}})
    bot_instance.answer_callback_query(call.id, "Задача выполнена!")
    text = message.text[:-15]
    bot_instance.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text + "\n✅ Выполнено!",
        parse_mode="Markdown",
    )
@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('undone_'))
def uncompleted(call):
    message = call.message
    task_id = call.data.split("_")[1]
    tasks_db.find_one_and_update({"_id": ObjectId(task_id)}, {'$set': {"status": False}})
    bot_instance.answer_callback_query(call.id, "Задача невыполнена!")
    text = message.text[:-13]
    bot_instance.edit_message_text(
        chat_id=call.message.chat.id,
        message_id=call.message.message_id,
        text=text + "\n❌ Невыполнено!",
        parse_mode="Markdown",
    )
@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('edit_'))
def edit_task(call):
    task_id = call.data.split("_")[1]
    keyboard = InlineKeyboardMarkup()
    button_name = InlineKeyboardButton(text="Изменить название", callback_data=f'name_{task_id}')
    button_desc = InlineKeyboardButton(text="Изменить описание", callback_data=f'desc_{task_id}')
    button_deadline = InlineKeyboardButton(text="Изменить срок", callback_data=f'deadline_{task_id}')
    keyboard.add(button_name, button_desc, button_deadline)
    bot_instance.send_message(call.message.chat.id, "Что вы хотите изменить?", reply_markup=keyboard)

@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('name_'))
def update_title(call):
    task_id = call.data.split("_")[1]
    chat_id = call.message.chat.id
    bot_instance.send_message(chat_id, "Введите новое название:")
    bot_instance.register_next_step_handler(call.message, lambda msg: update_field(msg, task_id, 'title'))
@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('desc_'))
def update_description(call):
    task_id = call.data.split("_")[1]
    chat_id = call.message.chat.id
    bot_instance.send_message(chat_id, "Введите новое описание задачи:")
    # Передаем объект Message из CallbackQuery
    bot_instance.register_next_step_handler(call.message, lambda msg: update_field(msg, task_id, 'description'))
@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('deadline_'))
def update_deadline(call):
    task_id = call.data.split("_")[1]
    chat_id = call.message.chat.id
    bot_instance.send_message(chat_id, "Введите новый срок выполнения: дд мм гггг (через пробел)")
    bot_instance.register_next_step_handler(call.message, lambda msg: update_field(msg, task_id, 'deadline'))

def update_field(msg, task_id, field):
    new_value = msg.text
    tasks_db.find_one_and_update({"_id": ObjectId(task_id)}, {'$set': {field: new_value}})
    bot_instance.reply_to(msg, f"Поле обновлено: {new_value}")


@bot_instance.callback_query_handler(func=lambda call: call.data.startswith('delete_'))
def remove_task(call):
    task_id = call.data.split("_")[1]
    tasks_db.find_one_and_delete({"_id": ObjectId(task_id)})
    bot_instance.answer_callback_query(call.id, "Задача удалена!")
    bot_instance.delete_message(call.message.chat.id, call.message.message_id)

def send_info(msg):
    bot_instance.send_message(
        msg.chat.id,
        "С помощью SkatBot вы можете создавать и управлять своими задачами прямо через Telegram.\n\n"
        "Вы можете создавать простые задачи, используя естественный язык, к примеру: "
        "\"позвонить Джону\", \"проверить почту завтра \", \"оплатить счета 1 числа каждого месяца\" и т.д.\n\n"
        "Если вам нужен простой, но мощный инструмент для напоминаний, обязательно попробуйте SkatBot.\n\n"
        "Посмотрите исходный код на GitHub: [SkatBot GitHub](https://github.com/ArtyomProkopets/TGBot_DMLab)",
        parse_mode="Markdown"

    )

def go_back(msg):
    bot_instance.send_message(msg.chat.id, "Создание задачи отменено.", reply_markup=generate_main_buttons())

bot_instance.polling(none_stop=True)