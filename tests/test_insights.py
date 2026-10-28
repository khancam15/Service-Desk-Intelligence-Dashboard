import io
import json

import pandas as pd
import pytest

from service_desk_dashboard import insights, metrics


@pytest.fixture(scope="module")
def facts(synthetic):
    return insights.build_facts(synthetic, metrics.data_as_of(synthetic), "synthetic sample")


def test_facts_hold_aggregates_only(facts, synthetic):
    text = json.dumps(facts)
    assert "INC0" not in text
    for name in synthetic["assignee"].dropna().unique():
        assert name not in text
    assert facts["kpis"]["opened"] == len(synthetic)
    assert sum(facts["backlog_by_age"].values()) == facts["kpis"]["open_backlog"]
    assert sum(facts["open_past_sla_by_priority"].values()) == facts["kpis"]["open_past_sla"]


def test_facts_on_empty_data_have_no_made_up_rates(synthetic):
    empty = synthetic.iloc[0:0]
    f = insights.build_facts(empty, pd.Timestamp("2026-01-31"), "synthetic sample")
    assert f["kpis"]["sla_compliance_pct"] is None
    assert f["prior_14_days"] is None


BRIEF = {
    "headline": "Backlog is steady.",
    "findings": [{"title": "Volume", "detail": "Opened {opened} tickets."}],
    "risks": [],
    "recommendations": [
        {"action": "Write KB articles", "why": "Coverage", "owner": "Service Desk"}
    ],
}


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_ask_claude_sends_figures_and_parses_brief(facts):
    sent = {}

    def opener(request, timeout):
        sent["body"] = json.loads(request.data)
        sent["headers"] = dict(request.header_items())
        reply = "```json\n" + json.dumps(BRIEF) + "\n```"
        return _Response(
            json.dumps(
                {"model": "m", "content": [{"type": "text", "text": reply}], "usage": {}}
            ).encode()
        )

    brief = insights.ask_claude(facts, "key", "m", opener=opener)
    assert brief["headline"] == "Backlog is steady."
    assert sent["headers"]["X-api-key"] == "key"
    assert str(facts["kpis"]["opened"]) in sent["body"]["messages"][0]["content"]


def test_parse_brief_rejects_non_json():
    with pytest.raises(insights.InsightsError):
        insights.parse_brief("no brief today")


def test_unverified_numbers_flags_invented_figures(facts):
    opened = facts["kpis"]["opened"]
    good = json.loads(json.dumps(BRIEF).replace("{opened}", str(opened)))
    assert insights.unverified_numbers(good, facts) == []
    bad = json.loads(json.dumps(BRIEF).replace("{opened}", "987654"))
    assert insights.unverified_numbers(bad, facts) == ["987654"]


def test_markdown_labels_synthetic_data_and_flags(facts):
    bad = json.loads(json.dumps(BRIEF).replace("{opened}", "987654"))
    md = insights.render_markdown(facts, bad)
    assert "Synthetic sample data" in md
    assert "Check these figures" in md and "987654" in md
    assert "Dry run" in insights.render_markdown(facts, None)


def test_main_dry_run_and_missing_key(tmp_path, monkeypatch):
    monkeypatch.delenv("TICKETS_CSV", raising=False)
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    out = tmp_path / "brief.md"
    args = ["--out", str(out), "--days", "30", "--end", "2026-01-31"]
    assert insights.main([*args, "--dry-run", "--json", str(tmp_path / "b.json")]) == 0
    assert "Figures" in out.read_text()
    assert json.loads((tmp_path / "b.json").read_text())["brief"] is None
    assert insights.main(args) == 2
