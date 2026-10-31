"""Service Desk Insights Analyst: a weekly written brief on the dashboard's figures.

The figures are computed here, deterministically, with the same functions the
dashboard uses (metrics.py). Only those aggregate figures are sent to Claude,
never ticket rows or assignee names. Claude writes the narrative: what changed,
what is at risk and what to do next. Every number the brief quotes is checked
against the figures, and any it cannot find is listed under the brief.

Run it with ``sdd-insights``; see docs/insights.md.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.request
from datetime import date
from pathlib import Path
from typing import Any

import pandas as pd

from . import metrics
from .data import load_tickets
from .generate import generate_tickets

API_URL = "https://api.anthropic.com/v1/messages"
DEFAULT_MODEL = "claude-sonnet-5-5"
MAX_TOKENS = 2000
TIMEOUT_SECONDS = 120

SYSTEM_PROMPT = """You are the Service Desk Insights Analyst for an IT service desk.
You receive aggregate figures computed from the desk's tickets. Write a short weekly
brief for the service desk manager.

Rules:
- Use only the figures you are given. Never invent, estimate or extrapolate a number.
- Quote numbers exactly as they appear in the figures.
- If a figure is null, say it is not available; do not guess it.
- Be specific: name the priority, category, issue or assignment group.
- Recommendations must follow from a finding and name the group that should act.
- Plain, direct sentences. No greetings, no filler.

Reply with JSON only, matching this shape:
{"headline": "one sentence",
 "findings": [{"title": "...", "detail": "one or two sentences citing figures"}],
 "risks": [{"title": "...", "detail": "..."}],
 "recommendations": [{"action": "...", "why": "...", "owner": "assignment group"}]}
Give 3 to 5 findings, 1 to 3 risks and 2 to 4 recommendations."""


class InsightsError(RuntimeError):
    """Raised when the brief cannot be produced."""


def _records(df: pd.DataFrame) -> list[dict[str, Any]]:
    return json.loads(df.to_json(orient="records"))


def build_facts(df: pd.DataFrame, as_of: pd.Timestamp, source: str) -> dict[str, Any]:
    """Aggregate figures for the brief. Contains no ticket rows and no assignee names."""
    k = metrics.kpis(df, as_of)
    flow = metrics.daily_flow(df, as_of)
    last_14 = flow.tail(14)
    prior_14 = flow.iloc[-28:-14] if len(flow) >= 28 else flow.iloc[0:0]
    ageing = metrics.backlog_ageing(df, as_of)
    breaches = metrics.open_sla_breaches(df, as_of)
    return {
        "source": source,
        "as_of": as_of.isoformat(),
        "period_days": len(flow),
        "kpis": {
            "opened": k.opened,
            "resolved": k.resolved,
            "open_backlog": k.open_backlog,
            "open_past_sla": k.open_breached,
            "sla_compliance_pct": k.sla_compliance_pct,
            "first_contact_resolution_pct": k.fcr_pct,
            "knowledge_coverage_pct": k.kb_coverage_pct,
            "median_resolve_hours": k.median_resolve_hours,
        },
        "last_14_days": {
            "opened": int(last_14["opened"].sum()),
            "resolved": int(last_14["resolved"].sum()),
            "backlog_start": int(last_14["backlog"].iloc[0]) if len(last_14) else None,
            "backlog_end": int(last_14["backlog"].iloc[-1]) if len(last_14) else None,
        },
        "prior_14_days": None
        if prior_14.empty
        else {
            "opened": int(prior_14["opened"].sum()),
            "resolved": int(prior_14["resolved"].sum()),
        },
        "sla_by_priority": _records(metrics.sla_by_priority(df)),
        "open_past_sla_by_priority": {
            str(p): int(n) for p, n in breaches.groupby("priority").size().items()
        },
        "backlog_by_age": {
            str(b): int(n)
            for b, n in ageing.groupby("age_bucket", sort=False)["tickets"].sum().items()
        },
        "top_issues": _records(metrics.top_issues(df, n=5)),
        "knowledge_coverage_by_category": _records(metrics.kb_coverage_by_category(df)),
        "workload_by_group": _records(metrics.workload(df, as_of, by="assignment_group")),
        "channel_mix": _records(metrics.channel_mix(df)),
    }


def ask_claude(
    facts: dict[str, Any], api_key: str, model: str = DEFAULT_MODEL, opener=urllib.request.urlopen
) -> dict[str, Any]:
    """Send the figures to Claude and return the parsed brief."""
    body = {
        "model": model,
        "max_tokens": MAX_TOKENS,
        "system": SYSTEM_PROMPT,
        "messages": [
            {
                "role": "user",
                "content": "Figures for this week's brief:\n" + json.dumps(facts, indent=1),
            }
        ],
    }
    request = urllib.request.Request(  # noqa: S310 - fixed https URL
        API_URL,
        data=json.dumps(body).encode(),
        headers={
            "content-type": "application/json",
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
        },
        method="POST",
    )
    try:
        with opener(request, timeout=TIMEOUT_SECONDS) as response:
            payload = json.loads(response.read())
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace")[:500]
        raise InsightsError(f"Anthropic API returned HTTP {exc.code}: {detail}") from exc
    except urllib.error.URLError as exc:
        raise InsightsError(f"Could not reach the Anthropic API: {exc.reason}") from exc

    text = "".join(b.get("text", "") for b in payload.get("content", []) if b.get("type") == "text")
    brief = parse_brief(text)
    brief["_usage"] = payload.get("usage", {})
    brief["_model"] = payload.get("model", model)
    return brief


def parse_brief(text: str) -> dict[str, Any]:
    """Parse Claude's JSON reply, tolerating a surrounding code fence."""
    match = re.search(r"\{.*\}", text, re.DOTALL)
    if not match:
        raise InsightsError("The model's reply contained no JSON brief.")
    try:
        brief = json.loads(match.group(0))
    except json.JSONDecodeError as exc:
        raise InsightsError(f"The model's brief was not valid JSON: {exc}") from exc
    if not isinstance(brief.get("headline"), str) or not isinstance(brief.get("findings"), list):
        raise InsightsError("The model's brief is missing a headline or findings.")
    for key in ("findings", "risks", "recommendations"):
        brief.setdefault(key, [])
    return brief


_NUMBER = re.compile(r"(?<![A-Za-z\d.])\d+(?:\.\d+)?")


def _numbers(value: Any) -> set[str]:
    if isinstance(value, bool) or value is None:
        return set()
    if isinstance(value, int | float):
        return {_norm(str(value))}
    if isinstance(value, str):
        return {_norm(n) for n in _NUMBER.findall(value)}
    if isinstance(value, dict):
        return set().union(*(_numbers(v) | _numbers(k) for k, v in value.items()), set())
    if isinstance(value, list):
        return set().union(*(_numbers(v) for v in value), set())
    return set()


def _norm(n: str) -> str:
    return str(float(n)).removesuffix(".0")


def unverified_numbers(brief: dict[str, Any], facts: dict[str, Any]) -> list[str]:
    """Numbers the brief quotes that do not appear anywhere in the figures."""
    known = _numbers(facts)
    quoted = _numbers({k: v for k, v in brief.items() if not k.startswith("_")})
    # Small counts ("two groups", "top 3") are wording, not figures.
    return sorted((n for n in quoted - known if float(n) > 10), key=float)


def render_markdown(facts: dict[str, Any], brief: dict[str, Any] | None) -> str:
    k = facts["kpis"]

    def fmt(v: Any, suffix: str = "") -> str:
        return "n/a" if v is None else f"{v}{suffix}"

    lines = [f"# Service desk insights, {facts['as_of'][:10]}", ""]
    if facts["source"].startswith("synthetic"):
        lines += [
            "> **Synthetic sample data.** These tickets are generated, not from a real desk.",
            "",
        ]
    else:
        lines += [f"Data: {facts['source']}", ""]
    if brief:
        lines += [f"**{brief['headline']}**", ""]
        for title, key in (("Findings", "findings"), ("Risks", "risks")):
            if brief[key]:
                lines += [f"## {title}", ""]
                lines += [f"- **{i.get('title', '')}.** {i.get('detail', '')}" for i in brief[key]]
                lines.append("")
        if brief["recommendations"]:
            lines += ["## Recommendations", ""]
            lines += [
                f"- **{r.get('action', '')}** ({r.get('owner') or 'owner not named'}). "
                f"{r.get('why', '')}"
                for r in brief["recommendations"]
            ]
            lines.append("")
        unverified = unverified_numbers(brief, facts)
        if unverified:
            lines += [
                "> **Check these figures.** The brief quotes "
                + ", ".join(unverified)
                + ", which do not appear in the computed figures below.",
                "",
            ]
    lines += [
        "## Figures",
        "",
        "| Figure | Value |",
        "| --- | --- |",
        f"| Opened | {k['opened']} |",
        f"| Resolved | {k['resolved']} |",
        f"| Open backlog | {k['open_backlog']} |",
        f"| Open past SLA | {k['open_past_sla']} |",
        f"| SLA compliance | {fmt(k['sla_compliance_pct'], '%')} |",
        f"| First contact resolution | {fmt(k['first_contact_resolution_pct'], '%')} |",
        f"| Knowledge coverage | {fmt(k['knowledge_coverage_pct'], '%')} |",
        f"| Median time to resolve | {fmt(k['median_resolve_hours'], ' h')} |",
        "",
    ]
    if brief:
        usage = brief.get("_usage", {})
        lines.append(
            f"Written by {brief.get('_model', 'Claude')} from the figures above "
            f"({usage.get('input_tokens', '?')} input, "
            f"{usage.get('output_tokens', '?')} output tokens)."
        )
    else:
        lines.append("Dry run: figures only, no brief written.")
    return "\n".join(lines) + "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Write the weekly service desk insights brief.")
    parser.add_argument("--out", type=Path, default=Path("insights/brief.md"), help="Markdown file")
    parser.add_argument(
        "--json", type=Path, default=None, help="also write figures + brief as JSON"
    )
    parser.add_argument("--model", default=os.environ.get("INSIGHTS_MODEL", DEFAULT_MODEL))
    parser.add_argument("--seed", type=int, default=42, help="seed for synthetic data")
    parser.add_argument("--days", type=int, default=120, help="days of synthetic data")
    parser.add_argument("--end", type=date.fromisoformat, default=None, help="synthetic as-of date")
    parser.add_argument("--dry-run", action="store_true", help="compute figures, skip Claude")
    args = parser.parse_args(argv)

    csv_path = os.environ.get("TICKETS_CSV", "").strip()
    if csv_path:
        df = load_tickets(csv_path)
        source = f"ticket export ({Path(csv_path).name})"
    else:
        df = generate_tickets(days=args.days, end=args.end, seed=args.seed)
        source = f"synthetic sample (seed {args.seed}, {args.days} days)"
    as_of = metrics.data_as_of(df)
    facts = build_facts(df, as_of, source)

    brief = None
    if not args.dry_run:
        api_key = os.environ.get("ANTHROPIC_API_KEY", "").strip()
        if not api_key:
            print(
                "ANTHROPIC_API_KEY is not set. Add it as a repository secret, "
                "or use --dry-run for figures only.",
                file=sys.stderr,
            )
            return 2
        try:
            brief = ask_claude(facts, api_key, args.model)
        except InsightsError as exc:
            print(f"Insights brief failed: {exc}", file=sys.stderr)
            return 1

    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_markdown(facts, brief))
    if args.json:
        args.json.parent.mkdir(parents=True, exist_ok=True)
        args.json.write_text(json.dumps({"facts": facts, "brief": brief}, indent=2))
    print(f"Wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
