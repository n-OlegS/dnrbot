import sqlite3
import dotenv
import os
import time


def clean():
    dotenv.load_dotenv()
    path = os.getenv('SQL_PATH')
    conn = sqlite3.connect(path)

    conn.cursor().execute("DELETE FROM messages WHERE time < ?", [int(time.time()) - 1440 * 60])
    conn.commit()
    conn.close()
