from __future__ import annotations
import sqlite3
from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable, List, Optional, Tuple


@dataclass
class Expense:
    id: Optional[int]
    purchase: str
    category: str
    date_iso: str  # YYYY-MM-DD
    amount: int


class Database:
    def __init__(self, db_path: str) -> None:
        self._db_path = db_path
        self._conn = sqlite3.connect(db_path, check_same_thread=False)
        self._conn.execute("PRAGMA foreign_keys = ON;")
        self._conn.execute("PRAGMA journal_mode = WAL;")
        self._conn.execute("PRAGMA synchronous = NORMAL;")
        self._init_schema()

    def _init_schema(self) -> None:
        # Check if old schema exists and migrate
        cur = self._conn.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='expenses'")
        table_exists = cur.fetchone() is not None
        
        if table_exists:
            # Check if purchase column exists
            cur = self._conn.execute("PRAGMA table_info(expenses)")
            columns = {row[1] for row in cur.fetchall()}
            if "purchase" not in columns:
                # Migrate old schema
                self._conn.execute("ALTER TABLE expenses ADD COLUMN purchase TEXT DEFAULT ''")
                self._conn.commit()
        else:
            # Create new schema
            self._conn.execute(
                """
                CREATE TABLE expenses (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    purchase TEXT NOT NULL,
                    category TEXT NOT NULL,
                    date_iso TEXT NOT NULL CHECK(length(date_iso)=10),
                    amount INTEGER NOT NULL CHECK(amount > 0)
                );
                """
            )
            self._conn.commit()

    def close(self) -> None:
        try:
            self._conn.commit()
        finally:
            self._conn.close()

    # CRUD
    def add_expense(self, purchase: str, category: str, date_iso: str, amount: int) -> int:
        cur = self._conn.cursor()
        cur.execute(
            "INSERT INTO expenses(purchase, category, date_iso, amount) VALUES (?, ?, ?, ?)",
            (purchase, category, date_iso, amount),
        )
        self._conn.commit()
        return int(cur.lastrowid)

    def list_expenses(
        self,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
    ) -> List[Expense]:
        where: List[str] = []
        params: List[object] = []
        if category:
            where.append("category = ?")
            params.append(category)
        if date_from:
            where.append("date_iso >= ?")
            params.append(date_from)
        if date_to:
            where.append("date_iso <= ?")
            params.append(date_to)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        sql = (
            "SELECT id, purchase, category, date_iso, amount FROM expenses"
            + where_sql
            + " ORDER BY date_iso DESC, id DESC LIMIT ? OFFSET ?"
        )
        params.extend([limit, offset])
        cur = self._conn.execute(sql, params)
        rows = cur.fetchall()
        return [Expense(id=r[0], purchase=r[1], category=r[2], date_iso=r[3], amount=r[4]) for r in rows]

    def total_amount(
        self,
        category: Optional[str] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
    ) -> int:
        where: List[str] = []
        params: List[object] = []
        if category:
            where.append("category = ?")
            params.append(category)
        if date_from:
            where.append("date_iso >= ?")
            params.append(date_from)
        if date_to:
            where.append("date_iso <= ?")
            params.append(date_to)
        where_sql = (" WHERE " + " AND ".join(where)) if where else ""
        cur = self._conn.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM expenses" + where_sql,
            params,
        )
        (total,) = cur.fetchone()
        return int(total or 0)

    def get_expense(self, expense_id: int) -> Optional[Expense]:
        cur = self._conn.execute(
            "SELECT id, purchase, category, date_iso, amount FROM expenses WHERE id = ?",
            (expense_id,),
        )
        row = cur.fetchone()
        if not row:
            return None
        return Expense(id=row[0], purchase=row[1], category=row[2], date_iso=row[3], amount=row[4])

    def update_expense(
        self, expense_id: int, *, purchase: Optional[str] = None, category: Optional[str] = None, date_iso: Optional[str] = None, amount: Optional[int] = None
    ) -> bool:
        parts: List[str] = []
        params: List[object] = []
        if purchase is not None:
            parts.append("purchase = ?")
            params.append(purchase)
        if category is not None:
            parts.append("category = ?")
            params.append(category)
        if date_iso is not None:
            parts.append("date_iso = ?")
            params.append(date_iso)
        if amount is not None:
            parts.append("amount = ?")
            params.append(amount)
        if not parts:
            return False
        params.append(expense_id)
        cur = self._conn.execute(
            "UPDATE expenses SET " + ", ".join(parts) + " WHERE id = ?",
            params,
        )
        self._conn.commit()
        return cur.rowcount > 0

    def delete_expense(self, expense_id: int) -> bool:
        cur = self._conn.execute("DELETE FROM expenses WHERE id = ?", (expense_id,))
        self._conn.commit()
        return cur.rowcount > 0

    def get_categories(self) -> List[str]:
        """Return fixed list of categories."""
        return ["еда", "авто", "быт", "животные"]

    def get_monthly_stats(self, year: int, month: int) -> dict:
        """Get statistics for a specific month."""
        # First and last day of month
        import calendar
        _, last_day = calendar.monthrange(year, month)
        date_from = f"{year:04d}-{month:02d}-01"
        date_to = f"{year:04d}-{month:02d}-{last_day:02d}"
        
        # Total
        total = self.total_amount(date_from=date_from, date_to=date_to)
        
        # By category
        cur = self._conn.execute(
            """
            SELECT category, SUM(amount) as total
            FROM expenses
            WHERE date_iso >= ? AND date_iso <= ?
            GROUP BY category
            ORDER BY total DESC
            """,
            (date_from, date_to),
        )
        by_category = {row[0]: int(row[1]) for row in cur.fetchall()}
        
        # Count
        cur = self._conn.execute(
            "SELECT COUNT(*) FROM expenses WHERE date_iso >= ? AND date_iso <= ?",
            (date_from, date_to),
        )
        (count,) = cur.fetchone()
        
        return {
            "total": total,
            "count": int(count),
            "by_category": by_category,
            "date_from": date_from,
            "date_to": date_to,
        }
