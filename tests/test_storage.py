from kitsune.storage import ConversationStore


def test_history_keeps_the_last_turns_in_order(tmp_path):
    s = ConversationStore(str(tmp_path / "k.db"))
    for i in range(5):
        s.append("c", "u", {"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"})
    assert [m["content"] for m in s.history("c", "u", 2)] == ["q3", "a3", "q4", "a4"]


def test_history_is_per_user_and_channel():
    s = ConversationStore(":memory:")
    s.append("c1", "u1", {"role": "user", "content": "mine"})
    s.append("c1", "u2", {"role": "user", "content": "theirs"})
    s.append("c2", "u1", {"role": "user", "content": "elsewhere"})
    assert [m["content"] for m in s.history("c1", "u1", 5)] == ["mine"]
    assert s.forget("c1", "u1") == 1 and s.history("c1", "u1", 5) == []
    assert s.history("c2", "u1", 5)


def test_persists_across_reopen(tmp_path):
    path = str(tmp_path / "k.db")
    s = ConversationStore(path)
    s.append("c", "u", {"role": "user", "content": "remember me"})
    s.close()
    assert ConversationStore(path).history("c", "u", 1)[0]["content"] == "remember me"
