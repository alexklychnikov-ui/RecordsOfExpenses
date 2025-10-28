from __future__ import annotations
import calendar
from datetime import datetime, timedelta
from typing import Optional

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton


def make_calendar_kb(year: int, month: int) -> InlineKeyboardMarkup:
    """Build inline calendar keyboard for given year/month."""
    kb = []
    
    # Header with month/year
    month_name = calendar.month_name[month]
    kb.append([InlineKeyboardButton(text=f"{month_name} {year}", callback_data="calendar:ignore")])
    
    # Weekday headers
    weekdays = ["Пн", "Вт", "Ср", "Чт", "Пт", "Сб", "Вс"]
    kb.append([InlineKeyboardButton(text=d, callback_data="calendar:ignore") for d in weekdays])
    
    # Days grid
    cal = calendar.monthcalendar(year, month)
    for week in cal:
        row = []
        for day in week:
            if day == 0:
                row.append(InlineKeyboardButton(text=" ", callback_data="calendar:ignore"))
            else:
                row.append(InlineKeyboardButton(text=str(day), callback_data=f"calendar:day:{year}:{month}:{day}"))
        kb.append(row)
    
    # Navigation
    prev_month = month - 1
    prev_year = year
    if prev_month < 1:
        prev_month = 12
        prev_year -= 1
    
    next_month = month + 1
    next_year = year
    if next_month > 12:
        next_month = 1
        next_year += 1
    
    nav_row = [
        InlineKeyboardButton(text="<<", callback_data=f"calendar:nav:{prev_year}:{prev_month}"),
        InlineKeyboardButton(text="Сегодня", callback_data="calendar:today"),
        InlineKeyboardButton(text=">>", callback_data=f"calendar:nav:{next_year}:{next_month}"),
    ]
    kb.append(nav_row)
    
    return InlineKeyboardMarkup(inline_keyboard=kb)


def parse_calendar_callback(data: str) -> Optional[tuple]:
    """Parse calendar callback_data.
    
    Returns:
        ("day", year, month, day) for date selection
        ("nav", year, month) for navigation
        ("today",) for today button
        None for ignore
    """
    parts = data.split(":")
    if len(parts) < 2 or parts[0] != "calendar":
        return None
    
    action = parts[1]
    if action == "ignore":
        return None
    elif action == "today":
        return ("today",)
    elif action == "day" and len(parts) == 5:
        return ("day", int(parts[2]), int(parts[3]), int(parts[4]))
    elif action == "nav" and len(parts) == 4:
        return ("nav", int(parts[2]), int(parts[3]))
    return None

