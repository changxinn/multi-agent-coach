import os
import re
import textwrap

WIDTH = 72

AGENT_META = {
    "training_planner": {
        "short_name": "Alex",
        "title": "Training Planner",
        "color": "\033[94m",
        "icon": "[TRAIN]",
    },
    "nutrition_advisor": {
        "short_name": "Sam",
        "title": "Nutrition Advisor",
        "color": "\033[92m",
        "icon": "[FOOD]",
    },
    "recovery_coach": {
        "short_name": "Jordan",
        "title": "Recovery Coach",
        "color": "\033[95m",
        "icon": "[REST]",
    },
    "head_coach": {
        "short_name": "Head Coach",
        "title": "Orchestrator",
        "color": "\033[93m",
        "icon": "[ROUTE]",
    },
    "system": {
        "short_name": "System",
        "title": "System",
        "color": "\033[90m",
        "icon": "[SYS]",
    },
}

RESET = "\033[0m"
DIM = "\033[2m"
BOLD = "\033[1m"
CYAN = "\033[96m"


def _use_color() -> bool:
    if os.getenv("NO_COLOR"):
        return False
    return os.getenv("TERM", "dumb") != "dumb" or os.name == "nt"


def _c(text: str, color: str) -> str:
    if not _use_color():
        return text
    return f"{color}{text}{RESET}"


def print_banner():
    line = "=" * WIDTH
    print(_c(line, CYAN))
    print(_c("  FITNESS COACHING TEAM".center(WIDTH), BOLD + CYAN))
    print(_c(line, CYAN))
    print()
    print("  Coaches: Alex (training) | Sam (nutrition) | Jordan (recovery)")
    print("  The Head Coach routes each message to the right specialist.")
    print()
    print(_c("  Commands:", BOLD))
    print("    - Type your question and press Enter")
    print("    - Type  exit   to end session and see summary")
    print("    - Press  Ctrl+C  to quit immediately")
    print()


def print_profile_block(profile: dict):
    print(_c("-" * WIDTH, DIM))
    print(_c("  YOUR PROFILE", BOLD))
    print(f"  Name   : {profile.get('name', 'Athlete')}")
    print(f"  Goal   : {profile.get('goal', 'general fitness')}")
    print(f"  Level  : {profile.get('fitness_level', 'beginner')}")
    print(_c("-" * WIDTH, DIM))
    print()


def print_help_hints():
    print(_c("  Try asking:", BOLD))
    hints = [
        "Plan a 4-day program for my goal",
        "Log workout: DB squats 3x10, rows 3x12",
        "I ate McDonald's for lunch — log it",
        "I slept 6 hours and my knee hurts",
        "How am I doing this week?",
    ]
    for hint in hints:
        print(f"    > {hint}")
    print()


def print_user_line(text: str):
    print()
    print(_c("-" * WIDTH, DIM))
    print(_c("  YOU", BOLD))
    for line in textwrap.wrap(text, WIDTH - 4):
        print(f"  {line}")
    print(_c("-" * WIDTH, DIM))


def print_backend(event: str, detail: str = "", agent_key: str = "system"):
    """Always-visible backend trace (routing, tools, graph steps)."""
    meta = AGENT_META.get(agent_key, AGENT_META["system"])
    label = f"{meta['icon']} {meta['short_name']}"
    if detail:
        msg = (
            f"  {label}  {event}  {DIM}({detail}){RESET}"
            if _use_color()
            else f"  {label}  {event}  ({detail})"
        )
    else:
        msg = f"  {label}  {event}"
    print(_c(msg, meta["color"]) if _use_color() else msg)


def _to_bullets(text: str) -> list[str]:
    text = text.strip()
    if not text:
        return []

    # Normalize inline bullet characters to line-based bullets
    text = re.sub(r"\s*•\s*", "\n• ", text)
    text = re.sub(r"\s+-\s+", "\n- ", text)

    if re.search(r"^\s*[-•*]\s", text, re.MULTILINE):
        items = re.findall(r"^\s*[-•*]\s+(.+)$", text, re.MULTILINE)
        if items:
            return [item.strip() for item in items if item.strip()]

    sentences = re.split(r"(?<=[.!?])\s+", text)
    sentences = [s.strip() for s in sentences if s.strip()]

    if len(sentences) <= 2 and len(text) < 180:
        return sentences

    return sentences[:4]


def print_agent_response(agent_id: str, message: str):
    meta = AGENT_META.get(agent_id, AGENT_META["system"])
    header = f"  {meta['icon']} {meta['short_name']} -- {meta['title']}"
    print()
    print(_c(header, BOLD + meta["color"]))
    print(_c("  " + "-" * (WIDTH - 2), DIM))

    bullets = _to_bullets(message)
    for item in bullets:
        wrapped = textwrap.wrap(item, WIDTH - 6)
        print(f"  * {wrapped[0]}")
        for cont in wrapped[1:]:
            print(f"    {cont}")

    print(_c("  " + "-" * (WIDTH - 2), DIM))
    print()


def print_summary_block(summary: str):
    print()
    print(_c("=" * WIDTH, CYAN))
    print(_c("  SESSION SUMMARY", BOLD + CYAN))
    print(_c("=" * WIDTH, CYAN))

    body = summary
    for prefix in ("=== SESSION SUMMARY ===", "=== Progress Summary ==="):
        body = body.replace(prefix, "").strip()

    in_progress = False
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(("Goal:", "Today (")) and not in_progress:
            print()
            print(_c("  --- Logged This Session ---", BOLD))
            in_progress = True
        if stripped:
            print(f"  {line}")

    print(_c("=" * WIDTH, CYAN))
    print()
    print("  Session ended. Run again to start fresh, or review data/user_data.json")
    print()
