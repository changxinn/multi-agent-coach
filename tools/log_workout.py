from tools.storage import load_data, save_data, today_str


def log_workout(description: str) -> str:
    """
    Log a completed or planned workout entry.
    Format: free text, e.g. '30 min run, easy pace' or 'legs: squats 3x10'.
    """
    data = load_data()
    entry = {
        "date": today_str(),
        "description": description.strip(),
    }
    data["workouts"].append(entry)
    save_data(data)
    return f"Workout logged for {entry['date']}: {description.strip()}"


def exercise_lookup(exercise_name: str) -> str:
    """
    Return basic guidance for a named exercise.
    """
    exercises = {
        "squat": "Bodyweight or barbell squat: keep chest up, knees track over toes, depth to parallel or below.",
        "goblet squat": "Goblet squat: hold DB at chest, elbows inside knees, sit between hips, knee-friendly depth.",
        "push-up": "Push-up: straight line head to heels, lower chest near floor, full lockout at top.",
        "deadlift": "Deadlift: hinge at hips, neutral spine, bar close to shins, drive through floor.",
        "rdl": "Romanian deadlift (RDL): soft knee bend, hinge hips back, bar stays close to legs, feel hamstring stretch.",
        "plank": "Plank: elbows under shoulders, brace core, avoid sagging hips.",
        "run": "Easy run: conversational pace; increase weekly mileage by no more than ~10%.",
        "bench press": "Bench press: retract scapula, feet planted, controlled bar path to mid-chest.",
        "row": "Row (barbell/dumbbell): hinge slightly, pull to lower ribs, squeeze shoulder blades.",
        "lunge": "Lunge: step long, front knee over ankle, torso upright, alternate legs.",
        "hip hinge": "Hip hinge: soft knees, push hips back, neutral spine — foundation for deadlifts and RDLs.",
        "hip mobility": "Hip mobility: 90/90 switches, couch stretch, and hip CARs — 2–3 rounds daily for flexibility goals.",
        "stretch": "General stretching: hold 30–45s, breathe steadily, no bouncing; focus on tight areas post-workout.",
        "hamstring stretch": "Hamstring stretch: hinge at hips with flat back, or supine band stretch — hold 30–45s each side.",
        "hip flexor": "Hip flexor stretch: half-kneeling, tuck pelvis, lean forward gently — 30–45s per side.",
        "shoulder mobility": "Shoulder mobility: wall slides, band pull-aparts, and dead hangs — controlled range, no pain.",
        "knee-friendly": "Knee-friendly legs: box squats, step-ups, RDLs, glute bridges, and cycling/swimming over running.",
        "knee-friendly leg": "Knee-friendly legs: box squats, step-ups, RDLs, glute bridges, and cycling/swimming over running.",
        "flexibility": "Flexibility training: 10–15 min daily mobility + 2 full stretch sessions/week; progress gradually, no pain.",
    }

    key = exercise_name.strip().lower()
    for name, tip in exercises.items():
        if name in key or key in name:
            return f"{name.title()} — {tip}"

    return (
        f"No detailed entry for '{exercise_name}'. "
        "General tip: start light, focus on form, and progress gradually."
    )
