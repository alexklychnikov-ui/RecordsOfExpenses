import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    bot_token: str
    db_path: str = "expenses.db"


def load_env_file() -> None:
    # Get absolute path to .env file in the script directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    env_path = os.path.join(script_dir, ".env")
    
    if not os.path.exists(env_path):
        # Try current working directory as fallback
        env_path = ".env"
    
    if os.path.exists(env_path):
        try:
            # Try UTF-8 first, then UTF-16
            for encoding in ["utf-8", "utf-8-sig", "utf-16"]:
                try:
                    with open(env_path, "r", encoding=encoding) as f:
                        for line in f:
                            # Remove BOM if present
                            line = line.lstrip('\ufeff').strip()
                            if not line or line.startswith("#"):
                                continue
                            if "=" not in line:
                                continue
                            key, value = line.split("=", 1)
                            key = key.strip().lstrip('\ufeff')  # Extra BOM protection
                            value = value.strip()
                            if key and value:
                                os.environ[key] = value
                    break
                except (UnicodeDecodeError, UnicodeError):
                    continue
        except Exception:
            pass


def get_settings() -> Settings:
    load_env_file()
    token = os.environ.get("BOT_TOKEN", "").strip()
    if not token:
        raise RuntimeError("BOT_TOKEN is not set. Put it into .env or environment.")
    db_path = os.environ.get("DB_PATH", "expenses.db").strip() or "expenses.db"
    return Settings(bot_token=token, db_path=db_path)
