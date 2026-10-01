import time
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from signalbot import bot, config, post, trades
from signalbot.db import db

ADMIN, CHAT = 42, 4242


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "ADMIN_TELEGRAM_IDS", [str(ADMIN)])
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_IDS", ["-1"])
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URLS", ["https://discord.test/h"])
    monkeypatch.setattr(config, "TELEGRAM_WEBHOOK_SECRET", "tgsecret")


@pytest.fixture
def tg(monkeypatch):
    log = SimpleNamespace(replies=[], edits=[], answers=[], posted=[])
    monkeypatch.setattr("signalbot.telegram.reply", lambda chat_id, text, keyboard=None: log.replies.append((chat_id, text, keyboard)) or True)
    monkeypatch.setattr("signalbot.telegram.edit_message", lambda chat_id, mid, text, keyboard=None: log.edits.append((chat_id, mid, text, keyboard)) or True)
    monkeypatch.setattr("signalbot.telegram.answer_callback", lambda cid, text="": log.answers.append((cid, text)) or True)
    monkeypatch.setattr("signalbot.broadcast.send_detailed", lambda text: log.posted.append(text) or {"telegram": True, "discord": True})
    return log


def say(text, user=ADMIN, chat_type="private"):
    bot.handle_update({"update_id": 1, "message": {"text": text, "from": {"id": user}, "chat": {"id": CHAT, "type": chat_type}}})


def tap(data, user=ADMIN, chat_type="private"):
    bot.handle_update({"update_id": 2, "callback_query": {"id": "cb1", "data": data, "from": {"id": user},
                       "message": {"message_id": 9, "chat": {"id": CHAT, "type": chat_type}}}})


def button(tg, index=0):
    return tg.replies[-1][2][0][index]["callback_data"]


def test_signal_needs_confirmation_then_posts_everywhere(tg):
    say("buy us30 39000 sl 38900 tp 39200")
    preview = tg.replies[-1][1]
    assert "BUY US30" in preview and "Post to telegram + discord?" in preview
    assert tg.posted == [] and trades.open_trade_for("US30") is None  # nothing happens before the tap

    tap(button(tg))
    assert len(tg.posted) == 1 and "BUY US30" in tg.posted[0]
    assert trades.open_trade_for("US30")["entry"] == 39000
    assert "✅ Posted" in tg.edits[-1][2] and "✓ telegram" in tg.edits[-1][2] and "✓ discord" in tg.edits[-1][2]
    assert tg.edits[-1][3] is None  # buttons removed


def test_close_preview_shows_result_without_closing(tg):
    say("buy us30 39000 sl 38900"); tap(button(tg))
    say("close us30 39150")
    assert "+150 pts (+1.5R)" in tg.replies[-1][1]
    assert trades.open_trade_for("US30") is not None
    tap(button(tg))
    assert trades.open_trade_for("US30") is None and trades.stats()["points"] == 150


def test_strangers_and_groups_are_ignored(tg):
    say("buy us30 39000", user=999)
    say("buy us30 39000", chat_type="group")
    say("/open", user=999)
    assert tg.replies == [] and tg.posted == []
    say("/id", user=999)
    assert tg.replies[-1][1] == "Your Telegram user id is 999"


def test_other_user_cannot_press_my_button(tg):
    say("buy us30 39000"); data = button(tg)
    tap(data, user=999)
    assert tg.posted == []
    tap(data, user=ADMIN, chat_type="group")
    assert tg.posted == []


def test_double_tap_posts_once(tg):
    say("buy us30 39000"); data = button(tg)
    tap(data); tap(data)
    assert len(tg.posted) == 1
    assert tg.answers[-1][1] == "Already handled"


def test_cancel_posts_nothing(tg):
    say("buy us30 39000"); tap(button(tg, 1))
    assert tg.posted == [] and tg.edits[-1][2] == "Cancelled." and trades.open_trade_for("US30") is None
    tap(f"post:{1}")  # a cancelled preview can't be revived
    assert tg.posted == []


def test_expired_preview_does_not_post(tg):
    say("buy us30 39000"); data = button(tg)
    with db() as c:
        c.execute("UPDATE pending SET created_ts = ?", (time.time() - bot.CONFIRM_TTL_SECONDS - 5,))
    tap(data)
    assert tg.posted == [] and "Expired" in tg.edits[-1][2]


def test_duplicate_offers_post_anyway(tg):
    say("buy us30 39000"); tap(button(tg))
    say("buy us30 39000"); tap(button(tg))
    assert len(tg.posted) == 1 and "again?" in tg.edits[-1][2]
    tap(tg.edits[-1][3][0][0]["callback_data"])  # "Post anyway"
    assert len(tg.posted) == 2


def test_unreadable_input_and_warnings(tg):
    say("buy eurusd 1.1")
    assert "Couldn't read that" in tg.replies[-1][1] and tg.replies[-1][2] is None
    say("buy us30 39000 sl 39100")
    assert "⚠️ SL 39100 is on the wrong side" in tg.replies[-1][1]
    with db() as c:
        assert c.execute("SELECT COUNT(*) FROM pending").fetchone()[0] == 1  # the unreadable one made none


def test_note_after_pipe(tg):
    say("buy us30 39000 sl 38900 | NFP in 1h")
    assert "NFP in 1h" in tg.replies[-1][1]
    tap(button(tg))
    assert "NFP in 1h" in tg.posted[0]


def test_say_announcement_is_escaped_and_confirmed(tg):
    say("/say No more <trades> today")
    assert tg.posted == []
    tap(button(tg))
    assert tg.posted == ["No more &lt;trades&gt; today"]


def test_helpers_open_stats_drop_help(tg):
    say("/open"); assert tg.replies[-1][1] == "No open trades."
    say("buy us30 39000 sl 38900"); tap(button(tg))
    say("/open"); assert "BUY US30 @ 39000" in tg.replies[-1][1]
    say("/drop us30"); assert "Dropped" in tg.replies[-1][1] and trades.open_trade_for("US30") is None
    say("/drop us30"); assert "No open US30 trade" in tg.replies[-1][1]
    say("/stats"); assert "closed trades" in tg.replies[-1][1]
    say("/help"); assert "plain text" in tg.replies[-1][1]
    say("/bogus"); assert "plain text" in tg.replies[-1][1]


def test_no_destination_configured(tg, monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URLS", [])
    monkeypatch.setattr(config, "TELEGRAM_CHAT_IDS", [])
    say("buy us30 39000")
    assert "No destination configured" in tg.replies[-1][1]


def test_failed_delivery_is_reported(tg, monkeypatch):
    monkeypatch.setattr("signalbot.broadcast.send_detailed", lambda t: {"telegram": True, "discord": False})
    say("buy us30 39000"); tap(button(tg))
    assert "⚠️ Delivery problem" in tg.edits[-1][2] and "✗ FAILED discord" in tg.edits[-1][2]


def test_handler_errors_never_escape(tg, monkeypatch):
    monkeypatch.setattr("signalbot.engine.build_messages", lambda *a, **k: 1 / 0)
    say("buy us30 39000")  # must not raise


# --- transports ------------------------------------------------------------------------------------
def test_webhook_routes_messages_and_checks_secret(tg):
    from signalbot.app import app

    c = TestClient(app)
    upd = {"update_id": 1, "message": {"text": "/id", "from": {"id": 7}, "chat": {"id": 7, "type": "private"}}}
    assert c.post("/telegram/webhook", json=upd).status_code == 401
    assert c.post("/telegram/webhook", json=upd, headers={"X-Telegram-Bot-Api-Secret-Token": "tgsecret"}).status_code == 200
    assert tg.replies[-1][1] == "Your Telegram user id is 7"


def test_poll_once_advances_offset_and_survives_failures(tg, monkeypatch):
    batch = [{"update_id": 10, "message": {"text": "/id", "from": {"id": 1}, "chat": {"id": 1, "type": "private"}}},
             {"update_id": 11, "message": {"text": "/id", "from": {"id": 2}, "chat": {"id": 2, "type": "private"}}}]
    monkeypatch.setattr("signalbot.telegram.get_updates", lambda offset: batch)
    assert bot.poll_once(None) == 12 and len(tg.replies) == 2
    monkeypatch.setattr("signalbot.telegram.get_updates", lambda offset: None)
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert bot.poll_once(12) == 12


def test_cli_drop(tg, capsys):
    post.main(["buy", "us30", "39000", "-y"])
    assert post.main(["--drop", "us30"]) == 0 and "Dropped open US30" in capsys.readouterr().out
    assert trades.open_trade_for("US30") is None


def test_get_updates_request_shape(monkeypatch):
    from signalbot import telegram

    seen = {}

    class R:
        ok, status_code, text = True, 200, ""
        def json(self): return {"ok": True, "result": [{"update_id": 5}]}

    def fake_post(url, json, timeout):
        seen.update(url=url, json=json, timeout=timeout)
        return R()

    monkeypatch.setattr("requests.post", fake_post)
    assert telegram.get_updates(7) == [{"update_id": 5}]
    assert seen["url"].endswith("/bottok/getUpdates") and seen["json"]["offset"] == 7
    assert "callback_query" in seen["json"]["allowed_updates"] and seen["timeout"] > seen["json"]["timeout"]
    monkeypatch.setattr("requests.post", lambda *a, **k: type("E", (), {"ok": True, "json": lambda s: {"ok": True, "result": []}})())
    assert telegram.get_updates(None) == []
