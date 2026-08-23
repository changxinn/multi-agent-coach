from tools.storage import load_data, today_str


def get_progress_summary() -> str:
    """
    Return a summary of recent workouts, meals, and sleep logs.
    """
    data = load_data()
    profile = data.get("profile", {})
    workouts = data.get("workouts", [])
    meals = data.get("meals", [])
    sleep_logs = data.get("sleep_logs", [])

    today = today_str()
    today_workouts = [w for w in workouts if w.get("date") == today]
    today_meals = [m for m in meals if m.get("date") == today]
    today_sleep = [s for s in sleep_logs if s.get("date") == today]

    lines = [
        "=== Progress Summary ===",
        f"Goal: {profile.get('goal', 'general fitness')}",
        f"Fitness level: {profile.get('fitness_level', 'beginner')}",
        "",
        f"Today ({today}):",
        f"  Workouts logged: {len(today_workouts)}",
        f"  Meals logged: {len(today_meals)}",
        f"  Sleep logs: {len(today_sleep)}",
        "",
        f"All-time totals: {len(workouts)} workouts, {len(meals)} meals, {len(sleep_logs)} sleep entries",
    ]

    if today_workouts:
        lines.append("")
        lines.append("Today's workouts:")
        for w in today_workouts[-3:]:
            lines.append(f"  - {w.get('description', '')}")

    if today_meals:
        lines.append("")
        lines.append("Today's meals:")
        for m in today_meals[-3:]:
            lines.append(f"  - {m.get('description', '')}")

    if today_sleep:
        lines.append("")
        lines.append("Today's sleep:")
        for s in today_sleep[-2:]:
            lines.append(
                f"  - {s.get('hours', '?')}h, quality: {s.get('quality', '?')}"
            )

    recent_workouts = workouts[-5:]
    if recent_workouts:
        lines.append("")
        lines.append("Recent workouts:")
        for w in recent_workouts:
            lines.append(f"  [{w.get('date', '?')}] {w.get('description', '')}")

    return "\n".join(lines)
