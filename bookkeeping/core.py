import sqlite3
import dotenv
import os

from deductor import process_group


class BKCore:
    def __init__(self):
        dotenv.load_dotenv()
        path = os.getenv('SQL_PATH')
        self.connection = sqlite3.connect(path)
        self.cursor = self.connection.cursor()

    def handle_group_update(self, tier_id, gid):
        # 0 - free | 6h
        # 1 - 250 | 3h
        # 2 - 500 | 1h
        # 3 - 1000 | 15m
        # 4 - 2000 | 15m / custom length / message len

        if tier_id not in range(5):
            return False

        # set tier to new tier
        # call deductor with check_date=False

        old_tier = self.cursor.execute("SELECT tier FROM chats WHERE id = ?", (gid,)).fetchone()[0]

        if old_tier == tier_id:
            return False

        self.cursor.execute('UPDATE chats SET tier = ? WHERE id = ?', (tier_id, gid))
        self.connection.commit()
        process_group(gid, in_cursor=self.cursor, check_date=False)

        return True


