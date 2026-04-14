import psycopg2
import os
from datetime import datetime
from dotenv import load_dotenv
load_dotenv()

def get_conn():
    return psycopg2.connect(os.getenv("SUPABASE_DB_URL"))

class HistoryStore:

    def add(self, user_id,company_number, question, answer):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    "INSERT INTO history (user_id, company_number, question, answer, created_at) VALUES (%s, %s, %s, %s, %s)",
                    (user_id, company_number,question, answer, datetime.utcnow())
                )
            conn.commit()
        finally:
            conn.close()

    def get(self, user_id,company_number, limit=10):
        conn = get_conn()
        try:
            with conn.cursor() as cur:
                cur.execute(
                    """
                SELECT question, answer
                FROM history
                WHERE user_id = %s AND company_number = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                    (user_id, company_number, limit)
                )
                rows = cur.fetchall()
            return list(reversed(rows))
        finally:
            conn.close()

    def format(self, user_id, company_number, limit=10):
        rows = self.get(user_id, company_number, limit)

        return "".join(
            f"User: {q}\nAssistant: {a}\n"
            for q, a in rows
        )

history_store = HistoryStore()
