from pathlib import Path

from streamlit.testing.v1 import AppTest

APP = str(Path(__file__).parents[1] / "src" / "service_desk_dashboard" / "app.py")


def test_app_runs_on_synthetic_data(monkeypatch):
    monkeypatch.delenv("TICKETS_CSV", raising=False)
    monkeypatch.setenv("SYNTHETIC_DAYS", "30")
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.title[0].value == "Service Desk Intelligence"
    assert len(at.metric) == 8
    assert "Synthetic data" in at.caption[0].value


def test_app_loads_csv(monkeypatch, synthetic, tmp_path):
    path = tmp_path / "tickets.csv"
    synthetic.to_csv(path, index=False)
    monkeypatch.setenv("TICKETS_CSV", str(path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert at.metric[0].value == f"{len(synthetic):,}"


def test_app_reports_bad_csv(monkeypatch, tmp_path):
    path = tmp_path / "tickets.csv"
    path.write_text("ticket_id\nINC1\n")
    monkeypatch.setenv("TICKETS_CSV", str(path))
    at = AppTest.from_file(APP, default_timeout=60).run()
    assert not at.exception
    assert "Missing required columns" in at.error[0].value
