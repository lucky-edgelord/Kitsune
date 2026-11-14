from kitsune.storage import ConversationStore


def ex(store, user, i, channel="c"):
    store.append(user, {"role": "user", "content": f"q{i}"}, {"role": "assistant", "content": f"a{i}"}, channel=channel)


def test_context_is_per_user_across_channels():
    s = ConversationStore(":memory:")
    ex(s, "u1", 0, channel="c1")
    ex(s, "u1", 1, channel="c2")
    ex(s, "u2", 9)
    ctx = s.context("u1")
    assert [m["content"] for m in ctx.turns] == ["q0", "a0", "q1", "a1"] and ctx.exchanges == 2
    assert [m["content"] for m in s.context("u2").turns] == ["q9", "a9"]


def test_compact_keeps_logs_and_rolls_summary():
    s = ConversationStore(":memory:")
    for i in range(4):
        ex(s, "u", i)
    ids = [t["id"] for t in s.uncompacted("u")]
    assert s.compact("u", "likes Frieren", ids[3]) == 4
    ctx = s.context("u")
    assert ctx.summary == "likes Frieren" and [m["content"] for m in ctx.turns] == ["q2", "a2", "q3", "a3"]
    s.compact("u", "likes Frieren and Dandadan", ids[-1])
    assert s.memory("u") == "likes Frieren and Dandadan" and s.context("u").turns == []
    total = s._db.execute("SELECT COUNT(*) FROM turns").fetchone()[0]
    assert total == 8  # compacted turns are kept as logs


def test_forget_clears_context_and_memory():
    s = ConversationStore(":memory:")
    ex(s, "u", 0)
    s.compact("u", "notes", s.uncompacted("u")[-1]["id"])
    ex(s, "u", 1)
    assert s.forget("u") >= 3 and s.context("u").turns == [] and s.memory("u") == ""


def test_feedback_only_for_logged_replies_latest_vote_wins():
    s = ConversationStore(":memory:")
    assert not s.rate("m1", "r", 1)
    s.log_reply("m1", "u", "hi", "Hey kit!", "happy")
    assert s.rate("m1", "r", 1) and s.rate("m1", "r", -1)
    rows = s.feedback()
    assert len(rows) == 1 and rows[0]["rating"] == -1 and rows[0]["reply"] == "Hey kit!"
    s.unrate("m1", "r", -1)
    assert s.feedback() == []


def test_persists_across_reopen(tmp_path):
    path = str(tmp_path / "k.db")
    s = ConversationStore(path)
    ex(s, "u", 0)
    s.close()
    assert ConversationStore(path).context("u").turns[0]["content"] == "q0"


def test_migrates_old_turns_table(tmp_path):
    import sqlite3

    path = str(tmp_path / "old.db")
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE turns (chat TEXT, user TEXT, role TEXT, content TEXT, at REAL)")
    db.execute("INSERT INTO turns VALUES ('c', 'u', 'user', 'old hello', 1.0)")
    db.commit()
    db.close()
    s = ConversationStore(path)
    assert s.context("u").turns == [{"role": "user", "content": "old hello"}]
    ex(s, "u", 1)
    assert s.context("u").exchanges == 2
