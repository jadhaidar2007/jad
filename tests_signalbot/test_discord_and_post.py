import pytest

from signalbot import broadcast, config, discord, engine, post, trades
from signalbot.format import format_signal, to_discord, to_plain
from signalbot.parse import check_levels, parse_alert


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    monkeypatch.setattr(config, "TELEGRAM_BOT_TOKEN", "tok")
    monkeypatch.setattr(config, "TELEGRAM_CHAT_IDS", ["-1"])
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URLS", ["https://discord.test/hook"])


@pytest.fixture
def sent(monkeypatch):
    log = {"telegram": [], "discord": []}
    monkeypatch.setattr("signalbot.telegram.send_message", lambda text: log["telegram"].append(text) or True)
    monkeypatch.setattr("signalbot.discord.send_message", lambda text: log["discord"].append(text) or True)
    return log


# --- shorthand parsing ---------------------------------------------------------
@pytest.mark.parametrize("text,entry,sl,tps", [
    ("buy us30 39000 sl 38900 tp 39200", 39000, 38900, [39200]),
    ("sell nas100 18,500.5 sl 18550 tp1 18400 tp2 18300", 18500.5, 18550, [18400, 18300]),
    ("SELL SPX500 entry 5000 sl 5010", 5000, 5010, []),
    ("buy spx 5000 sl 4990 tp 5020", 5000, 4990, [5020]),
])
def test_shorthand(text, entry, sl, tps):
    sig = parse_alert(text)
    assert (sig.entry, sig.sl, sig.tps) == (entry, sl, tps)


def test_symbol_digits_are_not_mistaken_for_entry():
    assert parse_alert("buy us30").entry is None
    assert parse_alert("close us100 18450").entry == 18450


def test_level_warnings():
    assert check_levels(parse_alert("buy us30 39000 sl 38900 tp 39200")) == []
    assert any("SL" in w for w in check_levels(parse_alert("buy us30 39000 sl 39100 tp 39200")))
    assert any("TP1" in w for w in check_levels(parse_alert("sell us30 39000 sl 39100 tp 39200")))
    assert "not be tracked" in check_levels(parse_alert("buy us30"))[0]
    assert check_levels(parse_alert("close us30 39000")) == []


# --- formatting ------------------------------------------------------------------
def test_discord_and_plain_conversion():
    sig = parse_alert("buy us30 39000 sl 38900")
    sig.note = "Fed <speech> & 'risk'"
    msg = format_signal(sig)
    assert to_discord(msg).startswith("🟢 **BUY US30**")
    assert "Fed <speech> & 'risk'" in to_discord(msg)
    assert "**" not in to_plain(msg) and "<b>" not in to_plain(msg)


# --- discord transport ---------------------------------------------------------------
class Resp:
    def __init__(self, status, body=None):
        self.status_code, self.ok, self._b, self.text = status, status < 400, body or {}, ""

    def json(self):
        return self._b


def test_discord_post_disables_mentions_and_truncates(monkeypatch):
    calls = []
    monkeypatch.setattr("requests.post", lambda url, json, timeout: calls.append(json) or Resp(204))
    assert discord.send_message("@everyone " + "x" * 5000)
    assert calls[0]["allowed_mentions"] == {"parse": []} and len(calls[0]["content"]) == 2000


def test_discord_retries_rate_limit_then_succeeds(monkeypatch):
    seq = iter([Resp(429, {"retry_after": 0}), Resp(204)])
    monkeypatch.setattr("requests.post", lambda *a, **k: next(seq))
    monkeypatch.setattr("time.sleep", lambda s: None)
    assert discord.send_message("hi")


def test_discord_client_error_fails_without_retry(monkeypatch):
    n = []
    monkeypatch.setattr("requests.post", lambda *a, **k: n.append(1) or Resp(404))
    assert discord.send_message("hi") is False and len(n) == 1


# --- broadcast -------------------------------------------------------------------------
def test_broadcast_goes_to_both_and_reports_partial_failure(sent, monkeypatch):
    assert broadcast.send_detailed("<b>x</b>") == {"telegram": True, "discord": True}
    assert sent["telegram"] == ["<b>x</b>"] and sent["discord"] == ["**x**"]
    monkeypatch.setattr("signalbot.discord.send_message", lambda text: False)
    assert broadcast.send_detailed("y") == {"telegram": True, "discord": False}
    assert broadcast.send("y") is False


def test_broadcast_skips_unconfigured_platforms(sent, monkeypatch):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URLS", [])
    assert list(broadcast.send_detailed("x")) == ["telegram"]
    monkeypatch.setattr(config, "TELEGRAM_CHAT_IDS", [])
    assert broadcast.send_detailed("x") == {} and broadcast.send("x") is False


# --- manual CLI -------------------------------------------------------------------------
def run(args, answer="y"):
    return post.main(args, input_fn=lambda q: answer)


def test_post_flow_open_then_close(sent, capsys):
    assert run(["buy", "us30", "39000", "sl", "38900", "tp", "39200"]) == 0
    assert "BUY US30" in sent["telegram"][0] and "BUY US30" in sent["discord"][0]
    assert trades.open_trade_for("US30")["entry"] == 39000
    assert run(["close", "us30", "39150"]) == 0
    assert "✅ **US30 BUY** closed @ 39,150" in sent["discord"][1]
    assert trades.stats()["points"] == 150
    assert "✓ telegram" in capsys.readouterr().out


def test_post_cancel_and_dry_run_change_nothing(sent):
    assert run(["buy", "us30", "39000", "sl", "38900"], answer="n") == 1
    assert run(["buy", "us30", "39000", "sl", "38900", "--dry-run"]) == 0
    assert sent == {"telegram": [], "discord": []} and trades.open_trade_for("US30") is None


def test_post_preview_of_close_does_not_close_trade(sent):
    run(["buy", "us30", "39000", "sl", "38900"])
    run(["close", "us30", "39100", "--dry-run"])
    assert trades.open_trade_for("US30") is not None


def test_post_duplicate_guard_and_force(sent, capsys):
    assert run(["buy", "us30", "39000", "-y"]) == 0
    assert run(["buy", "us30", "39000", "-y"]) == 1
    assert "--force" in capsys.readouterr().out
    assert run(["buy", "us30", "39000", "-y", "--force"]) == 0


def test_post_bad_input_and_say(sent, capsys):
    assert run(["buy", "eurusd", "1.1"]) == 2
    assert run(["--say", "No more <trades> today", "-y"]) == 0
    assert sent["telegram"] == ["No more &lt;trades&gt; today"] and sent["discord"] == ["No more <trades> today"]
    assert run(["--open"]) == 0


def test_post_reports_partial_failure(sent, monkeypatch, capsys):
    monkeypatch.setattr("signalbot.discord.send_message", lambda text: False)
    assert run(["buy", "us30", "39000", "-y"]) == 1
    out = capsys.readouterr().out
    assert "✓ telegram" in out and "✗ FAILED discord" in out


def test_post_requires_a_destination(monkeypatch, capsys):
    monkeypatch.setattr(config, "DISCORD_WEBHOOK_URLS", [])
    monkeypatch.setattr(config, "TELEGRAM_CHAT_IDS", [])
    assert run(["buy", "us30", "39000"]) == 2
    assert "No destination" in capsys.readouterr().out


def test_engine_logs_failed_delivery(monkeypatch):
    monkeypatch.setattr("signalbot.broadcast.send_detailed", lambda t: {"telegram": False})
    assert engine.publish(parse_alert("buy us30 39000")).status == "failed"
