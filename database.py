import sqlite3
import os

DB_PATH = "data/casino.db"

class Database:
    def __init__(self):
        os.makedirs("data", exist_ok=True)
        self.conn = sqlite3.connect(DB_PATH, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self._create_tables()

    def _create_tables(self):
        c = self.conn.cursor()
        c.executescript("""
            CREATE TABLE IF NOT EXISTS users (
                user_id     INTEGER PRIMARY KEY,
                username    TEXT,
                balance     INTEGER DEFAULT 1000,
                total_won   INTEGER DEFAULT 0,
                total_lost  INTEGER DEFAULT 0,
                games_played INTEGER DEFAULT 0,
                last_daily  TEXT DEFAULT NULL,
                last_work   TEXT DEFAULT NULL
            );

            CREATE TABLE IF NOT EXISTS debts (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                lender_id   INTEGER,
                borrower_id INTEGER,
                amount      INTEGER,
                created_at  TEXT DEFAULT (datetime('now')),
                paid        INTEGER DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS transactions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id     INTEGER,
                amount      INTEGER,
                type        TEXT,
                description TEXT,
                created_at  TEXT DEFAULT (datetime('now'))
            );
        """)
        self.conn.commit()

    # ── USER ───────────────────────────────────────────────
    def get_user(self, user_id: int, username: str = None):
        c = self.conn.cursor()
        c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        if not row:
            c.execute(
                "INSERT INTO users (user_id, username) VALUES (?, ?)",
                (user_id, username or str(user_id))
            )
            self.conn.commit()
            c.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            row = c.fetchone()
        return dict(row)

    def update_balance(self, user_id: int, amount: int):
        """Add or subtract from balance. Returns new balance."""
        c = self.conn.cursor()
        c.execute("UPDATE users SET balance = balance + ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()
        c.execute("SELECT balance FROM users WHERE user_id = ?", (user_id,))
        return c.fetchone()["balance"]

    def set_balance(self, user_id: int, amount: int):
        c = self.conn.cursor()
        c.execute("UPDATE users SET balance = ? WHERE user_id = ?", (amount, user_id))
        self.conn.commit()

    def record_game(self, user_id: int, won: int, lost: int):
        c = self.conn.cursor()
        c.execute("""
            UPDATE users SET
                total_won = total_won + ?,
                total_lost = total_lost + ?,
                games_played = games_played + 1
            WHERE user_id = ?
        """, (won, lost, user_id))
        self.conn.commit()

    def get_leaderboard(self, limit: int = 10):
        c = self.conn.cursor()
        c.execute(
            "SELECT user_id, username, balance FROM users ORDER BY balance DESC LIMIT ?",
            (limit,)
        )
        return [dict(r) for r in c.fetchall()]

    def set_last_daily(self, user_id: int, dt_str: str):
        c = self.conn.cursor()
        c.execute("UPDATE users SET last_daily = ? WHERE user_id = ?", (dt_str, user_id))
        self.conn.commit()

    def set_last_work(self, user_id: int, dt_str: str):
        c = self.conn.cursor()
        c.execute("UPDATE users SET last_work = ? WHERE user_id = ?", (dt_str, user_id))
        self.conn.commit()

    # ── DEBTS ──────────────────────────────────────────────
    def add_debt(self, lender_id: int, borrower_id: int, amount: int):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO debts (lender_id, borrower_id, amount) VALUES (?, ?, ?)",
            (lender_id, borrower_id, amount)
        )
        self.conn.commit()
        return c.lastrowid

    def get_debts_owed_to(self, lender_id: int):
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM debts WHERE lender_id = ? AND paid = 0 ORDER BY created_at DESC",
            (lender_id,)
        )
        return [dict(r) for r in c.fetchall()]

    def get_debts_owed_by(self, borrower_id: int):
        c = self.conn.cursor()
        c.execute(
            "SELECT * FROM debts WHERE borrower_id = ? AND paid = 0 ORDER BY created_at DESC",
            (borrower_id,)
        )
        return [dict(r) for r in c.fetchall()]

    def pay_debt(self, debt_id: int):
        c = self.conn.cursor()
        c.execute("UPDATE debts SET paid = 1 WHERE id = ?", (debt_id,))
        self.conn.commit()

    def get_debt_by_id(self, debt_id: int):
        c = self.conn.cursor()
        c.execute("SELECT * FROM debts WHERE id = ?", (debt_id,))
        row = c.fetchone()
        return dict(row) if row else None

    # ── TRANSACTIONS ───────────────────────────────────────
    def log_transaction(self, user_id: int, amount: int, type_: str, desc: str):
        c = self.conn.cursor()
        c.execute(
            "INSERT INTO transactions (user_id, amount, type, description) VALUES (?, ?, ?, ?)",
            (user_id, amount, type_, desc)
        )
        self.conn.commit()
