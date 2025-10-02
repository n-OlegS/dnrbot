import sqlite3
import os
import time
import datetime

from dateutil.relativedelta import relativedelta

import dotenv


def deduct():
    dotenv.load_dotenv()
    path = os.getenv('SQL_PATH')
    connection = sqlite3.connect(path)
    cursor = connection.cursor()

    gids = cursor.execute('SELECT id FROM chats').fetchall()

    for (gid,) in gids:
        # do deducting logic
        process_group(gid, in_cursor=cursor)

    connection.close()


def process_group(gid, in_cursor=None, check_date=True):
    if in_cursor is None:
        dotenv.load_dotenv()
        path = os.getenv('SQL_PATH')
        connection = sqlite3.connect(path)
        cursor = connection.cursor()
    else:
        cursor = in_cursor

    prices = {}

    # set prices
    prices_l = cursor.execute("SELECT id, price FROM prices").fetchall()
    for price in prices_l:
        prices[price[0]] = price[1]

    balance = cursor.execute("SELECT balance FROM chats WHERE id = ?", (gid,)).fetchone()[0]
    tier = cursor.execute("SELECT tier FROM chats WHERE id = ?", (gid,)).fetchone()[0]
    payed_date = cursor.execute("SELECT payed_date FROM chats WHERE id = ?", (gid,)).fetchone()[0]

    if check_date:
        payed_date = datetime.datetime.utcfromtimestamp(payed_date)
        expiry_dt = payed_date + relativedelta(months=1)
        expiry_dt = int(expiry_dt.timestamp())

        if expiry_dt > time.time():
            if in_cursor is None:
                cursor.connection.close()

            return

    due = prices[tier]
    balance -= due

    if balance >= 0:
        payed_date = int(time.time())
        cursor.execute(f'UPDATE chats SET payed_date = ?, balance = ? WHERE id = ?', (payed_date, balance, gid))
        cursor.connection.commit()
        out = True
        interval = cursor.execute('SELECT interval FROM prices WHERE id = ?', (tier,)).fetchone()[0]
    else:
        # Get default interval from database for fallback
        default_interval_result = cursor.execute('SELECT interval FROM prices WHERE id = 0').fetchone()
        interval = default_interval_result[0] if default_interval_result else 1440
        balance += due
        out = False

    cursor.execute('UPDATE chats SET active = ?, interval = ? WHERE id = ?', (int(out), interval * 60, gid))
    cursor.connection.commit()

    if in_cursor is None:
        cursor.connection.close()


def deductor_d():
    while 1:
        deduct()
        time.sleep(24 * 60 * 60)

