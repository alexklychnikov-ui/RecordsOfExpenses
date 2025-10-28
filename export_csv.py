from __future__ import annotations
import csv
import io
from typing import List
from database import Expense
from models import format_amount, format_date


def export_to_csv(expenses: List[Expense]) -> str:
    """Export expenses to CSV format as string."""
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    
    # Header
    writer.writerow(["ID", "Покупка", "Категория", "Дата", "Сумма"])
    
    # Data
    for exp in expenses:
        writer.writerow([
            exp.id,
            exp.purchase,
            exp.category,
            format_date(exp.date_iso),
            format_amount(exp.amount),
        ])
    
    return output.getvalue()

