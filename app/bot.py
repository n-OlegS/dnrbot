import os
import time
import dotenv
import telebot
import redis
import json
import threading

from core.core import Core
from core.cleaner import clean

dotenv.load_dotenv(dotenv_path='../.env')
TOKEN = os.getenv('BOT_TOKEN')

SLEEP_TIME = 1

if not TOKEN:
    quit("Token parsing failed")

bot = telebot.TeleBot(TOKEN, threaded=False)

cores = {}


def _get_core(gid) -> Core:
    if gid in cores:
        return cores[gid]

    else:
        core = Core(gid)
        cores[gid] = core

        return core


@bot.message_handler(commands=['start', 'help'])
def start_message(m: telebot.types.Message):
    print(f"[BOT] Start/help command from user {m.from_user.id} in chat {m.chat.id}")
    bot.reply_to(m, "Hello world!")


@bot.message_handler(content_types=["text"])
def handle_message(m: telebot.types.Message):
    if m.text[0] == '/':
        if m.text[1:] in ['summ', 'summary']:
            summary(m)
        elif m.text[1:] == 'show':
            show(m)
        else:
            bot.reply_to(m, "Unknown command")

        return

    gid = m.chat.id
    core = _get_core(gid)
    print(f"[BOT] Message from user {m.from_user.id} in chat {gid}: {m.text[:50]}...")

    core.new_message(m.id, m.from_user.id, int(time.time()), m.text, " ".join([x for x in [m.from_user.first_name, m.from_user.last_name] if x is not None]))


def summary(m: telebot.types.Message):
    gid = m.chat.id
    core = _get_core(gid)
    print(f"[BOT] Summary request from user {m.from_user.id} in chat {gid}")

    interval = None

    status = core.summ(m.from_user.id, interval=interval)

    if status:
        print(f"[BOT] Summary request accepted for chat {gid}")
        return

    print(f"[BOT] Summary request rejected for chat {gid}")
    bot.reply_to(m, "Timeout! Use /show to show the previous summary.")


def show(m: telebot.types.Message):
    gid = m.chat.id
    core = _get_core(gid)
    print(f"[BOT] Show summary request from user {m.from_user.id} in chat {gid}")

    old_summary = core.get_summary()
    bot.reply_to(m, old_summary)


def cleaner():
    while True:
        print("[BOT] Running database cleanup...")
        clean()
        time.sleep(3600)


def poll_summaries():
    redis_conn = redis.Redis()

    while 1:
        pending = redis_conn.get('pending')
        if pending is None:
            raise ValueError

        if int(pending) == 0:
            time.sleep(SLEEP_TIME)
            continue

        redis_conn.incrby('pending', -1)
        summs_bytes = redis_conn.get('summaries')
        
        if summs_bytes is None:
            raise ValueError

        summs = json.loads(summs_bytes.decode('utf-8'))
        new_summary, gid = summs.pop(0)

        redis_conn.set('summaries', json.dumps(summs))

        print(f"[BOT] Sending summary to chat {gid}")
        bot.send_message(gid, f"#summary\n{time.strftime('%H:%M', time.localtime())}\n\n" + new_summary)

        print(f"[BOT] Storing summary {new_summary[:10]} in group {gid}")
        core = _get_core(gid)
        core.update_summary(new_summary)


if __name__ == '__main__':
    print("[BOT] Starting Telegram bot...")
    
    # Start poll_summaries in a background thread
    print("[BOT] Starting summary polling thread...")
    polling_thread = threading.Thread(target=poll_summaries, daemon=True)
    polling_thread.start()

    print("[BOT] Starting database cleanup thread...")
    cleaning_thread = threading.Thread(target=cleaner, daemon=True)
    cleaning_thread.start()
    
    # Start the bot
    print("[BOT] Bot ready, starting infinity polling...")
    bot.infinity_polling()
