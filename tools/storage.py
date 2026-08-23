import json
from datetime import UTC, datetime
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / "data"
DATA_FILE = DATA_DIR / "user_data.json"

DEFAULT_DATA = {
    "profile": {
        "name": "Athlete",
        "goal": "general fitness",
        "fitness_level": "beginner",
    },
    "workouts": [],
    "meals": [],
    "sleep_logs": [],
}


def _ensure_data_file() -> dict:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not DATA_FILE.exists():
        DATA_FILE.write_text(json.dumps(DEFAULT_DATA, indent=2), encoding="utf-8")
    return json.loads(DATA_FILE.read_text(encoding="utf-8"))


def load_data() -> dict:
    return _ensure_data_file()


def save_data(data: dict) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    DATA_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def reset_session_logs(profile: dict | None = None) -> None:
    """
    Clear workouts/meals/sleep for a fresh session. Keeps or updates profile.
    """
    data = load_data()
    if profile:
        data["profile"] = profile
    data["workouts"] = []
    data["meals"] = []
    data["sleep_logs"] = []
    save_data(data)


def today_str() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%d")
