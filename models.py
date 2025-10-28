from __future__ import annotations
from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Optional, Tuple


DATE_FMT = "%d.%m.%Y"
DATE_FMT_ISO = "%Y-%m-%d"


def parse_amount(text: str) -> Optional[int]:
    """Parse human amount like '123' or '123.45' into minor units (cents).

    Returns integer number of cents, strictly > 0.
    """
    try:
        value = text.replace(",", ".").strip()
        if value.startswith("+"):
            value = value[1:]
        d = Decimal(value)
        d = d.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        cents = int(d * 100)
        return cents if cents > 0 else None
    except (InvalidOperation, ValueError):
        return None


def parse_date_iso(text: str) -> Optional[str]:
    """Parse human date like 'dd.mm.yyyy' or 'today' into ISO for DB storage."""
    text = text.strip()
    if text.lower() in {"", "today", "сегодня"}:
        return datetime.now().strftime(DATE_FMT_ISO)
    # Try dd.mm.yyyy
    try:
        dt = datetime.strptime(text, DATE_FMT)
        return dt.strftime(DATE_FMT_ISO)
    except Exception:
        pass
    # Fallback: try ISO
    try:
        dt = datetime.strptime(text, DATE_FMT_ISO)
        return dt.strftime(DATE_FMT_ISO)
    except Exception:
        return None


def format_date(date_iso: str) -> str:
    """Format ISO date from DB to dd.mm.yyyy for display."""
    try:
        dt = datetime.strptime(date_iso, DATE_FMT_ISO)
        return dt.strftime(DATE_FMT)
    except Exception:
        return date_iso


def format_amount(cents: int) -> str:
    """Format cents into string with dot as decimal separator."""
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    rub = cents // 100
    kop = cents % 100
    return f"{sign}{rub}.{kop:02d}"


CATEGORIES = ["еда", "авто", "быт", "животные"]


@dataclass(frozen=True)
class ExpenseInput:
    purchase: str
    category: str
    date_iso: str
    amount: int

    @staticmethod
    def from_strings(purchase_text: str, category_text: str, date_text: str, amount_text: str) -> Tuple[Optional["ExpenseInput"], Optional[str]]:
        purchase = purchase_text.strip()
        if not purchase:
            return None, "Покупка не должна быть пустой"
        if len(purchase) > 40:
            return None, "Покупка не более 40 символов"
        
        category = category_text.strip().lower()
        if category not in CATEGORIES:
            return None, f"Категория должна быть одной из: {', '.join(CATEGORIES)}"
        
        date_iso = parse_date_iso(date_text)
        if date_iso is None:
            return None, "Дата в формате dd.mm.yyyy или 'today'"
        
        amount = parse_amount(amount_text)
        if amount is None:
            return None, "Неверная сумма. Пример: 123 или 123.45"
        
        return ExpenseInput(purchase=purchase, category=category, date_iso=date_iso, amount=amount), None
