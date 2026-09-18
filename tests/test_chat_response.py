from app.services.chat_response import new_assistant_messages, strip_speaker_prefix


def test_strip_speaker_prefix_removes_head_coach_label():
    assert (
        strip_speaker_prefix("Head Coach: Hey, I'm here.")
        == "Hey, I'm here."
    )


def test_new_assistant_messages_skips_prior_turns_and_duplicates():
    prior = [
        {"role": "user", "content": "hi"},
        {"role": "assistant", "name": "Head Coach", "content": "Head Coach: Hey, I'm here."},
    ]
    result = prior + [
        {"role": "user", "content": "i just wanna chat"},
        {
            "role": "assistant",
            "name": "Head Coach",
            "content": "Head Coach: Hey, I'm here.",
        },
        {
            "role": "assistant",
            "name": "Head Coach",
            "content": "Head Coach: What's going on today — gym, food, sleep, or you just want to vent?",
        },
    ]
    fresh = new_assistant_messages(prior, result)
    assert len(fresh) == 1
    assert fresh[0]["content"].startswith("What's going on today")
    assert "Head Coach:" not in fresh[0]["content"]


def test_new_assistant_messages_allows_repeated_identity_reply():
    identity = "I'm your Head Coach — Alex, Sam, and Jordan can help."
    prior = [
        {"role": "user", "content": "who are you"},
        {"role": "assistant", "content": identity},
    ]
    result = prior + [
        {"role": "user", "content": "who are you"},
        {"role": "assistant", "content": identity},
    ]
    fresh = new_assistant_messages(prior, result)
    assert len(fresh) == 1
    assert fresh[0]["content"] == identity
