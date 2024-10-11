import os
import subprocess
import re
import time
import telebot
import json
import threading

TOKEN = '8164536485:AAHjwHcVkV5gdTZ86NCeJKCcNbI8nC56IQc'
bot = telebot.TeleBot(TOKEN)
DATA_FILE = 'hikka_data.json'

def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as file:
            return json.load(file)
    return {}

def save_data(data):
    with open(DATA_FILE, 'w') as file:
        json.dump(data, file, indent=4)

def find_link(output):
    url_pattern = r'https?://[^\s]+'
    links = re.findall(url_pattern, output)
    return links[-1] if links else None

def start_hikka_instances():
    data = load_data()
    for user_id, user_data in data.items():
        if user_data.get("running", False):
            start_hikka(user_id)

def animate_installation(message, stop_event):
    dots = ["", ".", "..", "..."]
    idx = 0

    while not stop_event.is_set():
        try:
            bot.edit_message_text(
                chat_id=message.chat.id,
                message_id=message.message_id,
                text=f"🔃 <b>Installing{dots[idx % len(dots)]}</b>",
                parse_mode="HTML"
            )
            idx += 1
            time.sleep(1.5)
        except telebot.apihelper.ApiException:
            break

def start_hikka(user_id, message=None, first_name=None):
    user_folder = f"./{user_id}"
    os.makedirs(user_folder, exist_ok=True)
    os.chdir(user_folder)

    wget_command = "wget -qO- https://hikariatama.ru/get_hikka | bash"
    process = subprocess.Popen(wget_command, shell=True, stdout=subprocess.PIPE, stderr=subprocess.STDOUT)

    stop_event = threading.Event()

    def monitor_process():
        lines_received = 0
        sent_initial_link = False

        while True:
            output = process.stdout.readline()
            if output == b"" and process.poll() is not None:
                break

            if output:
                decoded_line = output.decode('utf-8')
                print(decoded_line, end='', flush=True)
                lines_received += 1

                if not sent_initial_link:
                    link = find_link(decoded_line)
                    if link and message:
                        markup = telebot.types.InlineKeyboardMarkup()
                        web_app = telebot.types.WebAppInfo(link)
                        markup.add(telebot.types.InlineKeyboardButton("🔗 Open link", web_app=web_app))

                        bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=message.message_id,
                            text=f"👋 <a href='tg://user?id={user_id}'>{first_name}</a><b>, please open the site to continue installation!</b>",
                            reply_markup=markup,
                            parse_mode="HTML"
                        )
                        sent_initial_link = True
                        stop_event.set()

                if "hikka" in decoded_line.lower():
                    data = load_data()
                    data[user_id] = {"running": True, "installing": False}
                    save_data(data)

                    if message:
                        bot.edit_message_text(
                            chat_id=message.chat.id,
                            message_id=message.message_id,
                            text=f"🌸 <a href='tg://user?id={user_id}'>{first_name}</a><b>,</b> <code>Hikka</code><b> was successfully installed! To remove it, click the button below.</b>",
                            parse_mode="HTML",
                            reply_markup=create_keyboard(user_id)
                        )
                    break

            if "error" in decoded_line.lower():
                break

            time.sleep(1)

    threading.Thread(target=monitor_process, daemon=True).start()
    threading.Thread(target=animate_installation, args=(message, stop_event), daemon=True).start()

def stop_hikka(user_id, chat_id):
    user_folder = f"./{user_id}"
    if os.path.exists(user_folder):
        try:
            subprocess.run(["rm", "-rf", user_folder], check=True)
            bot.send_message(chat_id, "🗑️ Папка пользователя успешно удалена.")
            return True
        except subprocess.CalledProcessError as e:
            bot.send_message(chat_id, f"⚠️ Ошибка при удалении: {e}")
            return False
    bot.send_message(chat_id, "⚠️ Папка пользователя не найдена.")
    return False

def create_keyboard(user_id):
    data = load_data()
    markup = telebot.types.InlineKeyboardMarkup()
    if user_id in data:
        markup.add(telebot.types.InlineKeyboardButton("🗑️ Remove", callback_data='remove'))
    else:
        markup.add(telebot.types.InlineKeyboardButton("🌷 Install", callback_data='install'))
    return markup

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    user_id = str(call.from_user.id)
    first_name = call.from_user.first_name
    data = load_data()

    if call.data == 'install':
        if data.get(user_id, {}).get("installing", False):
            return
        
        data[user_id] = {"running": False, "installing": True}
        save_data(data)

        msg = bot.edit_message_text(
            chat_id=call.message.chat.id,
            message_id=call.message.message_id,
            text=f"🔃 <b>Installing...</b>",
            parse_mode="HTML"
        )
        
        start_hikka(user_id, msg, first_name)

    elif call.data == 'remove':
        chat_id = call.message.chat.id
        if stop_hikka(user_id, chat_id):
            data = load_data()
            if user_id in data:
                del data[user_id]
                save_data(data)
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"👋 <a href='tg://user?id={user_id}'>{first_name}</a><b>,</b><code> Hikka</code><b> was successfully removed. To reinstall it, click the button below!</b>",
                parse_mode="HTML",
                reply_markup=create_keyboard(user_id)
            )
        else:
            bot.send_message(chat_id, "⚠️ Error during removal!")

@bot.message_handler(commands=['start'])
def start(message):
    user_id = str(message.from_user.id)
    first_name = message.from_user.first_name
    data = load_data()

    if user_id in data and data[user_id].get("running", False):
        bot.send_message(
            message.chat.id,
            f"👋 <a href='tg://user?id={user_id}'>{first_name}</a><b>, you already have </b><code>Hikka</code> installed! <b>To remove it, click the button below!</b>",
            parse_mode="HTML",
            reply_markup=create_keyboard(user_id)
        )
    else:
        if user_id in data and data[user_id].get("installing", False):
            return
            
        msg = bot.send_message(
            message.chat.id,
            f"🌸 <a href='tg://user?id={user_id}'>{first_name}</a>, <b>to install</b> <code>Hikka</code><b>, click the button below!</b>",
            parse_mode="HTML",
            reply_markup=create_keyboard(user_id)
        )

if __name__ == "__main__":
    start_hikka_instances()
    bot.polling(none_stop=True)
                
