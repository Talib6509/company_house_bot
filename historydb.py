import sqlite3
from datetime import datetime

DB_PATH = "history.db"


class HistoryStore:

    def __init__(self):
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.create_table()

    # -------------------------
    # CREATE TABLE
    # -------------------------
    def create_table(self):
        query = """
        CREATE TABLE IF NOT EXISTS history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            question TEXT,
            answer TEXT,
            created_at TIMESTAMP
        )
        """
        self.conn.execute(query)
        self.conn.commit()

    # -------------------------
    # ADD MESSAGE
    # -------------------------
    def add(self, user_id, question, answer):
        query = """
        INSERT INTO history (user_id, question, answer, created_at)
        VALUES (?, ?, ?, ?)
        """
        self.conn.execute(query, (
            user_id,
            question,
            answer,
            datetime.utcnow()
        ))
        self.conn.commit()

    # -------------------------
    # GET HISTORY
    # -------------------------
    def get(self, user_id, limit=15):
        query = """
        SELECT question, answer FROM history
        WHERE user_id = ?
        ORDER BY id DESC
        LIMIT ?
        """
        cursor = self.conn.execute(query, (user_id, limit))
        rows = cursor.fetchall()

        return list(reversed(rows))

    # -------------------------
    # FORMAT FOR LLM
    # -------------------------
    def format(self, user_id, limit=6):
        rows = self.get(user_id, limit)

        text = ""
        for question, answer in rows:
            text += f"User: {question}\n"
            text += f"Assistant: {answer}\n"

        return text


# singleton
history_store = HistoryStore()
