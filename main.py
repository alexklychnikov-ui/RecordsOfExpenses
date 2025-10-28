import asyncio
from config import get_settings
from database import Database
from bot_handler import build_app


async def main() -> None:
    settings = get_settings()
    db = Database(settings.db_path)
    app = build_app(settings.bot_token, db)
    try:
        # Delete webhook if exists (to use polling instead)
        await app.bot.delete_webhook(drop_pending_updates=True)
        print("Бот запущен! Нажмите Ctrl+C для остановки.")
        await app.run()
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
