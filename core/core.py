import redis
from core.llm_gateway import job
import rq
import dotenv
import sqlite3
import os
import time


class Core:
    def __init__(self, gid):
        print(f"[CORE] Initializing Core for chat {gid}")
        self.id = gid
        self.interval = 24 * 60 * 60
        self.last = 0
        self.balance = 0
        self.summary = "No summary yet... \nUse /summary to generate"

        self.redis_conn = redis.Redis()
        self.rq = rq.Queue(connection=self.redis_conn)

        dotenv.load_dotenv()
        path = os.getenv('SQL_PATH')

        self.conn = sqlite3.connect(path)
        self.cursor = self.conn.cursor()

        self._update()
        print(f"[CORE] Core initialized for chat {gid}")

    def _update(self):
        # pull from sql
        # set fields

        x = self.cursor.execute('SELECT summ, balance, interval, last FROM chats WHERE id = ?', (self.id,)).fetchall()

        if len(x) != 1:
            self._push(update=False)
            return

        x = x[0]

        if len(x) != 4:
            self._push(update=False)
            return

        self.summary, self.balance, self.interval, self.last = x

    def _push(self, update=True):
        print(f"[CORE] Pushing chat data to DB for chat {self.id}")
        if update:
            self.cursor.execute('UPDATE chats SET interval = ?, last = ?, summ = ?, balance = ? WHERE id = ?', (self.interval, self.last, self.summary, self.balance, self.id))
        else:
            self.cursor.execute('INSERT INTO chats (id, interval, last, summ, balance) VALUES (?, ?, ?, ?, ?)', (self.id, self.interval, self.last, self.summary, self.balance))
        self.conn.commit()

    def _do_checks(self, uid, req_interval) -> tuple[bool, str]:
        # check if group ok
        if req_interval is None:
            if time.time() >= self.last + self.interval:
                return True, "group"

        # check user ok
        print(f"[CORE] Checking user permissions for user {uid}")
        self.ensure_user(uid)
        print("Ensured user")
        user_data = self.cursor.execute('SELECT paying, last, interval FROM users WHERE id = ?', (uid,)).fetchone()
        paying, last, interval = user_data

        if not paying:
            return False, ""

        if time.time() >= last + interval:
            return True, "user"

        return False, ""

    def _get_messages(self, interval):
        # return a string in the format "user: text\n" for messages in the interval time window
        from_t = int(time.time()) - interval

        msgs = self.cursor.execute('SELECT user, text FROM messages WHERE chat_id = ? AND time > ?', (self.id, from_t)).fetchall()
        msgs = '\n'.join(f'{x[0]}: {x[1]}' for x in msgs)

        return msgs

    def summ(self, uid, interval=None) -> bool:
        print(f"[CORE] Summary request from user {uid} in chat {self.id}")
        ok, funder = self._do_checks(uid, interval)
        basic_interval = 0

        if not ok:
            print(f"[CORE] Summary request denied for user {uid} in chat {self.id}")
            return False

        # handle timeout logic
        if funder == "user":
            self.cursor.execute('UPDATE users SET last = ? WHERE id = ?', (int(time.time()), uid))
            basic_interval = self.cursor.execute('SELECT interval FROM users WHERE id = ?', (uid,)).fetchone()[0]
        elif funder == "group":
            self.last = int(time.time())
            interval = self.interval
        else:
            raise ValueError

        if interval is None:
            interval = basic_interval

        self._request_summ(interval)
        self._push()

        return True

    def _request_summ(self, interval):
        # get messages
        messages = self._get_messages(interval)
        print(f"[CORE] Enqueuing summary job for chat {self.id} with {len(messages)} chars")
        self.rq.enqueue(job, messages, self.id)

    def update_summary(self, summary):
        self.summary = summary
        self._push()

    def get_summary(self):
        return self.summary

    def new_message(self, mid, uid, timestamp, text, username, reply: int = 0):
        print(f"[CORE] Storing message from user {uid} in chat {self.id}")
        self.cursor.execute('INSERT INTO messages (id, uid, chat_id, text, time, user, reply) VALUES (?, ?, ?, ?, ?, ?, ?)', (mid, uid, self.id, text, timestamp, username, reply))
        self.conn.commit()

    @staticmethod
    def ensure_user(uid):
        dotenv.load_dotenv()
        path = os.getenv('SQL_PATH')

        new_conn = sqlite3.connect(path)
        new_cursor = new_conn.cursor()

        user_exists = new_cursor.execute("SELECT paying FROM users WHERE id = ?", (uid,)).fetchone() is not None

        if user_exists:
            new_conn.close()
            return

        print(f"[CORE] Creating new user {uid} with default settings")
        new_cursor.execute('INSERT INTO users (id, paying, last, interval) VALUES (?, ?, ?, ?)', (uid, 0, 0, 60 * 1440))
        new_conn.commit()
        new_conn.close()

    def close(self):
        if self.conn:
            self.conn.close()



