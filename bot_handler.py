from __future__ import annotations
import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Optional

from aiogram import Bot, Dispatcher, F
from aiogram.enums import ParseMode
from aiogram.filters import Command
from aiogram.client.default import DefaultBotProperties
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton, CallbackQuery, InlineKeyboardMarkup, InlineKeyboardButton, BufferedInputFile, ReplyKeyboardRemove

from database import Database
from models import ExpenseInput, parse_date_iso, format_amount, format_date, CATEGORIES
from calendar_kb import make_calendar_kb, parse_calendar_callback
from export_csv import export_to_csv


class AddStates(StatesGroup):
    waiting_purchase = State()
    waiting_category = State()
    waiting_date = State()
    waiting_amount = State()


class EditStates(StatesGroup):
    waiting_id = State()
    waiting_purchase = State()
    waiting_category = State()
    waiting_date = State()
    waiting_amount = State()


@dataclass
class BotApp:
    bot: Bot
    dp: Dispatcher
    db: Database

    @classmethod
    def create(cls, token: str, db: Database) -> "BotApp":
        bot = Bot(token=token, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
        dp = Dispatcher()
        app = cls(bot=bot, dp=dp, db=db)
        app._register_handlers()
        return app

    def _register_handlers(self) -> None:
        dp = self.dp

        def get_main_kb() -> ReplyKeyboardMarkup:
            return ReplyKeyboardMarkup(
                keyboard=[
                    [KeyboardButton(text="Добавить"), KeyboardButton(text="Список")],
                    [KeyboardButton(text="Посмотреть за месяц"), KeyboardButton(text="Редактировать")],
                ],
                resize_keyboard=True,
            )

        @dp.message(Command("start"))
        async def cmd_start(message: Message) -> None:
            await message.answer(
                "Бот учёта расходов\n\nИспользуйте кнопки меню:",
                reply_markup=get_main_kb(),
            )

        # ADD FLOW
        @dp.message(F.text == "Добавить")
        async def btn_add(message: Message, state: FSMContext) -> None:
            await state.set_state(AddStates.waiting_purchase)
            await message.answer("Покупка (до 40 символов):", reply_markup=ReplyKeyboardRemove())

        @dp.message(AddStates.waiting_purchase)
        async def add_purchase(message: Message, state: FSMContext) -> None:
            purchase = (message.text or "").strip()
            if not purchase:
                await message.answer("Покупка не может быть пустой. Попробуйте ещё раз:")
                return
            if len(purchase) > 40:
                await message.answer(f"Покупка слишком длинная ({len(purchase)} симв.). Максимум 40 символов:")
                return
            
            await state.update_data(purchase=purchase)
            await state.set_state(AddStates.waiting_category)
            
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"addcat:{cat}") for cat in CATEGORIES[i:i+2]]
                    for i in range(0, len(CATEGORIES), 2)
                ]
            )
            await message.answer("Выберите категорию:", reply_markup=kb)

        @dp.callback_query(AddStates.waiting_category, F.data.startswith("addcat:"))
        async def add_category_btn(callback: CallbackQuery, state: FSMContext) -> None:
            category = callback.data[7:]
            await state.update_data(category=category)
            await state.set_state(AddStates.waiting_date)
            
            now = datetime.now()
            await state.update_data(default_date=now.strftime("%d.%m.%Y"))
            
            kb = make_calendar_kb(now.year, now.month)
            await callback.message.answer(
                f"Дата (по умолчанию сегодня {now.strftime('%d.%m.%Y')}):",
                reply_markup=kb
            )
            await callback.answer()

        @dp.message(AddStates.waiting_date)
        async def add_date_text(message: Message, state: FSMContext) -> None:
            date_text = (message.text or "").strip()
            if not date_text or date_text.lower() in ["today", "сегодня"]:
                data = await state.get_data()
                date_text = data.get("default_date", datetime.now().strftime("%d.%m.%Y"))
            
            date_iso = parse_date_iso(date_text)
            if not date_iso:
                await message.answer("Неверный формат даты. Используйте dd.mm.yyyy или календарь выше:")
                return
            
            await state.update_data(date=date_iso)
            await state.set_state(AddStates.waiting_amount)
            await message.answer("Сумма (например 123.45):")

        @dp.callback_query(AddStates.waiting_date, F.data.startswith("calendar:"))
        async def add_date_calendar(callback: CallbackQuery, state: FSMContext) -> None:
            parsed = parse_calendar_callback(callback.data)
            if not parsed:
                await callback.answer()
                return
            
            if parsed[0] == "today":
                date_iso = datetime.now().strftime("%Y-%m-%d")
                await state.update_data(date=date_iso)
                await state.set_state(AddStates.waiting_amount)
                await callback.message.answer("Сумма (например 123.45):")
                await callback.answer()
            elif parsed[0] == "nav":
                _, year, month = parsed
                kb = make_calendar_kb(year, month)
                await callback.message.edit_reply_markup(reply_markup=kb)
                await callback.answer()
            elif parsed[0] == "day":
                _, year, month, day = parsed
                date_iso = f"{year:04d}-{month:02d}-{day:02d}"
                await state.update_data(date=date_iso)
                await state.set_state(AddStates.waiting_amount)
                await callback.message.answer("Сумма (например 123.45):")
                await callback.answer()

        @dp.message(AddStates.waiting_amount)
        async def add_amount(message: Message, state: FSMContext) -> None:
            data = await state.get_data()
            exp, error = ExpenseInput.from_strings(
                data.get("purchase", ""),
                data.get("category", ""),
                "",  # date already parsed
                message.text or ""
            )
            
            if error and "Дата" not in error:
                await message.answer(error)
                return
            
            # Create expense
            exp_id = app.db.add_expense(
                data.get("purchase", ""),
                data.get("category", ""),
                data.get("date", ""),
                exp.amount if exp else 0
            )
            
            from_db = app.db.get_expense(exp_id)
            await message.answer(
                f"✅ Добавлено #{exp_id}\n"
                f"Покупка: {from_db.purchase}\n"
                f"Категория: {from_db.category}\n"
                f"Дата: {format_date(from_db.date_iso)}\n"
                f"Сумма: {format_amount(from_db.amount)}",
                reply_markup=get_main_kb()
            )
            await state.clear()

        # LIST
        @dp.message(F.text == "Список")
        async def btn_list(message: Message) -> None:
            items = app.db.list_expenses(limit=100)
            if not items:
                await message.answer("Нет записей", reply_markup=get_main_kb())
                return
            
            lines = []
            for e in items:
                lines.append(
                    f"#{e.id}: {e.purchase} | {e.category} | {format_date(e.date_iso)} | {format_amount(e.amount)}"
                )
            
            # Split if too long
            text = "\n".join(lines)
            if len(text) > 4000:
                text = "\n".join(lines[:50]) + "\n\n... (показаны первые 50)"
            
            await message.answer(text, reply_markup=get_main_kb())

        # MONTH VIEW
        @dp.message(F.text == "Посмотреть за месяц")
        async def btn_month(message: Message) -> None:
            now = datetime.now()
            stats = app.db.get_monthly_stats(now.year, now.month)
            
            if stats["count"] == 0:
                await message.answer(
                    f"Нет данных за {now.strftime('%B %Y')}",
                    reply_markup=get_main_kb()
                )
                return
            
            lines = [
                f"📊 Отчёт за {now.strftime('%B %Y')}",
                f"Записей: {stats['count']}",
                f"<b>Общая сумма: {format_amount(stats['total'])}</b>",
                "",
                "По категориям:",
            ]
            for cat, amt in stats["by_category"].items():
                pct = (amt * 100) // stats["total"] if stats["total"] > 0 else 0
                lines.append(f"  {cat}: {format_amount(amt)} ({pct}%)")
            
            await message.answer("\n".join(lines), reply_markup=get_main_kb())

        # EDIT
        @dp.message(F.text == "Редактировать")
        async def btn_edit(message: Message, state: FSMContext) -> None:
            await state.set_state(EditStates.waiting_id)
            await message.answer("Введите ID записи для редактирования:", reply_markup=ReplyKeyboardRemove())

        @dp.message(EditStates.waiting_id)
        async def edit_get_id(message: Message, state: FSMContext) -> None:
            text = (message.text or "").strip()
            if not text.isdigit():
                await message.answer("ID должен быть числом. Попробуйте ещё раз:")
                return
            
            eid = int(text)
            exp = app.db.get_expense(eid)
            if not exp:
                await message.answer("Запись не найдена", reply_markup=get_main_kb())
                await state.clear()
                return
            
            await state.update_data(
                eid=eid,
                old_purchase=exp.purchase,
                old_category=exp.category,
                old_date=exp.date_iso,
                old_amount=exp.amount
            )
            await state.set_state(EditStates.waiting_purchase)
            
            await message.answer(
                f"Редактирование #{eid}\n\n"
                f"Текущие значения:\n"
                f"Покупка: {exp.purchase}\n"
                f"Категория: {exp.category}\n"
                f"Дата: {format_date(exp.date_iso)}\n"
                f"Сумма: {format_amount(exp.amount)}\n\n"
                f"Введите новое значение для <b>Покупки</b> (или '-' чтобы оставить текущее):"
            )

        @dp.message(EditStates.waiting_purchase)
        async def edit_purchase(message: Message, state: FSMContext) -> None:
            text = (message.text or "").strip()
            data = await state.get_data()
            
            if text == "-":
                purchase = data["old_purchase"]
            else:
                if len(text) > 40:
                    await message.answer("Покупка не более 40 символов. Попробуйте ещё раз:")
                    return
                purchase = text
            
            await state.update_data(new_purchase=purchase)
            await state.set_state(EditStates.waiting_category)
            
            kb = InlineKeyboardMarkup(
                inline_keyboard=[
                    [InlineKeyboardButton(text=cat.capitalize(), callback_data=f"editcat:{cat}") for cat in CATEGORIES[i:i+2]]
                    for i in range(0, len(CATEGORIES), 2)
                ] + [[InlineKeyboardButton(text="Оставить текущую", callback_data="editcat:-")]]
            )
            await message.answer(f"Выберите новую категорию (текущая: {data['old_category']}):", reply_markup=kb)

        @dp.callback_query(EditStates.waiting_category, F.data.startswith("editcat:"))
        async def edit_category(callback: CallbackQuery, state: FSMContext) -> None:
            cat = callback.data[8:]
            data = await state.get_data()
            
            if cat == "-":
                category = data["old_category"]
            else:
                category = cat
            
            await state.update_data(new_category=category)
            await state.set_state(EditStates.waiting_date)
            
            now = datetime.now()
            kb = make_calendar_kb(now.year, now.month)
            await callback.message.answer(
                f"Выберите новую дату (текущая: {format_date(data['old_date'])}) или введите dd.mm.yyyy или '-':",
                reply_markup=kb
            )
            await callback.answer()

        @dp.message(EditStates.waiting_date)
        async def edit_date_text(message: Message, state: FSMContext) -> None:
            text = (message.text or "").strip()
            data = await state.get_data()
            
            if text == "-":
                date_iso = data["old_date"]
            else:
                date_iso = parse_date_iso(text)
                if not date_iso:
                    await message.answer("Неверный формат даты. Попробуйте ещё раз (dd.mm.yyyy или '-'):")
                    return
            
            await state.update_data(new_date=date_iso)
            await state.set_state(EditStates.waiting_amount)
            await message.answer(f"Введите новую сумму (текущая: {format_amount(data['old_amount'])}) или '-':")

        @dp.callback_query(EditStates.waiting_date, F.data.startswith("calendar:"))
        async def edit_date_calendar(callback: CallbackQuery, state: FSMContext) -> None:
            parsed = parse_calendar_callback(callback.data)
            if not parsed:
                await callback.answer()
                return
            
            data = await state.get_data()
            
            if parsed[0] == "today":
                date_iso = datetime.now().strftime("%Y-%m-%d")
                await state.update_data(new_date=date_iso)
                await state.set_state(EditStates.waiting_amount)
                await callback.message.answer(f"Введите новую сумму (текущая: {format_amount(data['old_amount'])}) или '-':")
                await callback.answer()
            elif parsed[0] == "nav":
                _, year, month = parsed
                kb = make_calendar_kb(year, month)
                await callback.message.edit_reply_markup(reply_markup=kb)
                await callback.answer()
            elif parsed[0] == "day":
                _, year, month, day = parsed
                date_iso = f"{year:04d}-{month:02d}-{day:02d}"
                await state.update_data(new_date=date_iso)
                await state.set_state(EditStates.waiting_amount)
                await callback.message.answer(f"Введите новую сумму (текущая: {format_amount(data['old_amount'])}) или '-':")
                await callback.answer()

        @dp.message(EditStates.waiting_amount)
        async def edit_amount(message: Message, state: FSMContext) -> None:
            text = (message.text or "").strip()
            data = await state.get_data()
            
            if text == "-":
                amount = data["old_amount"]
            else:
                from models import parse_amount
                amount = parse_amount(text)
                if not amount:
                    await message.answer("Неверный формат суммы. Попробуйте ещё раз (или '-'):")
                    return
            
            # Update
            eid = data["eid"]
            app.db.update_expense(
                eid,
                purchase=data["new_purchase"],
                category=data["new_category"],
                date_iso=data["new_date"],
                amount=amount
            )
            
            exp = app.db.get_expense(eid)
            await message.answer(
                f"✅ Обновлено #{eid}\n"
                f"Покупка: {exp.purchase}\n"
                f"Категория: {exp.category}\n"
                f"Дата: {format_date(exp.date_iso)}\n"
                f"Сумма: {format_amount(exp.amount)}",
                reply_markup=get_main_kb()
            )
            await state.clear()

    async def run(self) -> None:
        await self.dp.start_polling(self.bot)


# keep a module-level reference for handler closures
app: BotApp


def build_app(token: str, db: Database) -> BotApp:
    global app
    app = BotApp.create(token, db)
    return app

