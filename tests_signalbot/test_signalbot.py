import pytest
from fastapi.testclient import TestClient

from signalbot import config
from signalbot.format import format_signal
from signalbot.parse import ParseError, parse_alert


def test_json_alert_and_format():
    sig = parse_alert('{"secret":"x","action":"BUY","symbol":"CAPITALCOM:US30","entry":39000,"sl":38900,"tp":39200}')
    assert (sig.action, sig.symbol, sig.entry, sig.sl, sig.tps) == ("buy", "US30", 39000.0, 38900.0, [39200.0])
    msg = format_signal(sig)
    assert "BUY US30" in msg and "Entry: 39,000" in msg and "R:R 2.0" in msg


def test_plain_text_alert():
    sig = parse_alert("secret=abc SELL NAS100 entry 18,500.5 sl 18600 tp1 18400 tp2 18300")
    assert (sig.action, sig.symbol, sig.entry) == ("sell", "US100", 18500.5)
    assert sig.tps == [18400.0, 18300.0]


def test_close_alert():
    assert format_signal(parse_alert('{"action":"close","symbol":"SPX"}')).startswith("⚪")


@pytest.mark.parametrize("body", ["", "hello", '{"action":"buy","symbol":"EURUSD"}', '{"action":"hodl","symbol":"US30"}'])
def test_rejects_bad_alerts(body):
    with pytest.raises(ParseError):
        parse_alert(body)


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "WEBHOOK_SECRET", "s3cret")
    monkeypatch.setattr(config, "DB_PATH", str(tmp_path / "t.db"))
    sent = []
    monkeypatch.setattr("signalbot.broadcast.send_detailed", lambda text: sent.append(text) or {"telegram": True})
    from signalbot.app import app
    c = TestClient(app)
    c.sent = sent
    return c


def test_webhook_flow(client):
    body = '{"secret":"s3cret","action":"buy","symbol":"US100","entry":18500,"sl":18450,"tp":18600}'
    assert client.post("/webhook", content=body).json() == {"status": "sent"}
    assert client.post("/webhook", content=body).json() == {"status": "duplicate"}
    assert len(client.sent) == 1


def test_webhook_rejects_bad_secret_and_bad_alert(client):
    assert client.post("/webhook", content='{"secret":"nope","action":"buy","symbol":"US30"}').status_code == 401
    assert client.post("/webhook", content='{"secret":"s3cret","action":"buy","symbol":"EURUSD"}').status_code == 422
    assert client.sent == []
