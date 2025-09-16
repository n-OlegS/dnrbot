import datetime
import os
import time
import dotenv
import telebot
import redis
import json
import threading

from core.core import Core
from core.cleaner import clean
from core.command_parser import CommandParser
from bookkeeping.core import BKCore
from bookkeeping.deductor import deductor_d

dotenv.load_dotenv(dotenv_path='../.env')
TOKEN = os.getenv('BOT_TOKEN')
DEBUG = os.getenv('DEBUG') == 'True'

SLEEP_TIME = 1

if not TOKEN:
    quit("Token parsing failed")

bot = telebot.TeleBot(TOKEN, threaded=False)

cores = {}
command_parser = CommandParser(debug=DEBUG)
bkcore = BKCore()


def _get_core(gid) -> Core:
    if gid in cores:
        return cores[gid]

    else:
        core = Core(gid)
        cores[gid] = core

        return core


@bot.message_handler(commands=['start'])
def start_message(m: telebot.types.Message):
    print(f"[BOT] Start/help command from user {m.from_user.id} in chat {m.chat.id}")
    bot.reply_to(m, "👋 Welcome to SummaryBot!\n\nI help you generate concise summaries of your chat conversations. Use /help to see all available commands.")


@bot.message_handler(content_types=["text"])
def handle_message(m: telebot.types.Message):
    # Parse command
    result = command_parser.parse(m.text)
    
    if result.is_command:
        if not result.is_valid:
            bot.reply_to(m, f"❌ {result.error}")
            return
        
        # Route to appropriate handler
        if result.command == 'summary':
            summary(m)
        elif result.command == 'show':
            show(m)
        elif result.command == 'status':
            show_status(m)
        elif result.command == 'help':
            show_help(m)
        elif result.command == 'tier':
            change_tier(m)
        elif result.command == 'pay':
            initiate_payment(m)
        else:
            bot.reply_to(m, "❓ Unknown command. Use /help to see all available commands.")
        
        return

    # Handle regular message
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
        bot.set_message_reaction(m.chat.id, m.id, [telebot.types.ReactionTypeEmoji('⚡')])
        return

    print(f"[BOT] Summary request rejected for chat {gid}")
    bot.reply_to(m, "⏱️ Summary request is on cooldown. Use /show to view your last summary or check /status for timing details.")


def initiate_payment(m: telebot.types.Message):
    # Parse amount from command
    result = command_parser.parse(m.text)
    amount_str = result.params

    is_valid, error = command_parser._validate_amount(amount_str, debug=DEBUG)
    if not is_valid:
        bot.reply_to(m, f'❌ {error}')
        return

    amount = int(amount_str)

    payload = f"topup:{m.chat.id}"

    """prices = [
        # telebot.types.LabeledPrice(f'{amount} Stars', str(amount)),
        telebot.types.LabeledPrice('10 Star', '10'),
        telebot.types.LabeledPrice('50 Stars', '50'),
        telebot.types.LabeledPrice('100 Stars', '100'),
        telebot.types.LabeledPrice('250 Stars', '250'),
        telebot.types.LabeledPrice('500 Stars', '500'),
        telebot.types.LabeledPrice('1000 Stars', '1000')

    ]"""
    bot.send_invoice(chat_id=m.chat.id, title="Top up account", description='Top up your group balance!', invoice_payload=payload, provider_token='', currency='XTR', prices=[telebot.types.LabeledPrice(f'{amount} Stars', amount)])


@bot.pre_checkout_query_handler(func=lambda q: True)
def checkout(pre_q: telebot.types.PreCheckoutQuery):
    bot.answer_pre_checkout_query(pre_q.id, ok=True)


@bot.message_handler(content_types=['successful_payment'])
def got_payment(msg):
    sp = msg.successful_payment
    payload = sp.invoice_payload
    # sp.currency == 'XTR'
    stars_paid = sp.total_amount            # total Stars paid (integer)

    bot.reply_to(
        msg,
        f"✅ **Payment Successful**\n\n💫 {stars_paid} stars added to your balance\n\nThank you for your support!"
    )

    # TODO: add stars to balance
    _, gid = payload.split(':')
    if stars_paid == 1 and DEBUG:
        stars_paid = 100
    bkcore.group_payed(gid, stars_paid)


def show_help(m: telebot.types.Message):
    bot.reply_to(m, "📋 **Available Commands:**\n\n🔸 `/summary` - Generate chat summary\n🔸 `/show` - View last summary\n🔸 `/status` - Check account status\n🔸 `/pay X` - Purchase X stars\n🔸 `/tier X` - Switch to tier (free/basic/plus/pro/max/elite)\n\n💎 **Subscription Tiers:**\n\n```\n Tier  │ Price/Month │ Cooldown\n───────┼─────────────┼─────────\n FREE  │      0      │  24 hrs\n BASIC │  250 stars  │  3 hrs\n PLUS  │  500 stars  │  1 hr\n PRO   │ 1000 stars  │ 15 min\n MAX   │ 2000 stars  │ 15 min\n ELITE │ 2000 stars  │ 15 min\n```")


def change_tier(m: telebot.types.Message):
    gid = m.chat.id
    this_core = _get_core(gid)

    tier = m.text[6:]
    # Remove the numeric tier parsing since we now use names

    tier_names = {"free": 0, "basic": 1, "plus": 2, "pro": 3, "max": 4, "elite": 4}
    
    if tier.lower() not in tier_names:
        bot.reply_to(m, "❌ Invalid tier. Choose from: free, basic, plus, pro, max, elite")
        return
        
    tier = tier_names[tier.lower()]

    status = bkcore.handle_group_update(tier, gid)

    if not status:
        tier_names = ["FREE", "BASIC", "PLUS", "PRO", "MAX", "ELITE"]
        tier_name = tier_names[tier] if tier < len(tier_names) else f"TIER {tier}"
        bot.reply_to(m, f"ℹ️ You're already on {tier_name} tier.")
        return

    this_core.update()
    bot.reply_to(m, "✅ Tier updated successfully!")


def show_status(m: telebot.types.Message):
    gid = m.chat.id
    core = _get_core(gid)
    interval, balance, payed_date, active, tier = core.get_status()

    status_icon = "🟢" if active else "🔴"
    tier_names = ["FREE", "BASIC", "PLUS", "PRO", "MAX", "ELITE"]
    tier_name = tier_names[tier] if tier < len(tier_names) else f"TIER {tier}"
    out = f"📊 **Account Status**\n\n{status_icon} **Status:** {'Active' if active else 'Inactive'}\n💰 **Balance:** {balance} stars\n💎 **Tier:** {tier_name}\n⏱️ **Cooldown:** {int(interval / 60)} minutes\n📅 **Last Payment:** {datetime.datetime.fromtimestamp(payed_date).strftime('%d/%m/%y %H:%M')}"

    bot.reply_to(m, out)


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
    redis_conn = redis.Redis(host=os.getenv('REDIS_HOST'))

    while 1:
        pending = redis_conn.get('pending')
        if pending is None:
            redis_conn.set('pending', 0)
            pending = 0

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
        bot.send_message(gid, f"📄 **Summary Generated**\n🕒 {time.strftime('%H:%M', time.localtime())}\n\n{new_summary}")

        print(f"[BOT] Storing summary {new_summary[:10]} in group {gid}")
        core = Core(gid)
        core.update_summary(new_summary)
        core.close()


if __name__ == '__main__':
    print("[BOT] Starting Telegram bot...")
    
    # Start poll_summaries in a background thread
    print("[BOT] Starting summary polling thread...")
    polling_thread = threading.Thread(target=poll_summaries, daemon=True)
    polling_thread.start()

    print("[BOT] Starting database cleanup thread...")
    cleaning_thread = threading.Thread(target=cleaner, daemon=True)
    cleaning_thread.start()

    print("[BOT] Starting deductor thread...")
    deductor_thread = threading.Thread(target=deductor_d, daemon=True)
    deductor_thread.start()
    
    # Start the bot
    print("[BOT] Bot ready, starting infinity polling...")
    bot.infinity_polling()
