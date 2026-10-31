# Insights Analyst

A weekly written brief on the dashboard's figures, for the service desk manager.

## What it does

1. Loads tickets the same way the dashboard does: the CSV in `TICKETS_CSV` if set, otherwise generated synthetic tickets.
2. Computes aggregate figures with the dashboard's own functions in `metrics.py`: headline KPIs, the last 14 days against the 14 before, SLA by priority, open tickets past SLA, backlog by age, top issues, knowledge coverage by category, workload by group and channel mix.
3. Sends only those figures to Claude (`claude-sonnet-5-5` by default). No ticket rows, ticket IDs or assignee names leave the machine.
4. Claude returns a headline, 3 to 5 findings, 1 to 3 risks and 2 to 4 recommendations, each naming the group that should act.
5. Every number the brief quotes is checked against the figures. Any that cannot be found are listed under the brief as "Check these figures".
6. Writes `insights/brief.md` (and `brief.json` with figures and brief). The figures table is printed with the brief, so each claim can be checked.

A brief on synthetic data is labelled as such at the top.

## Running it

In GitHub Actions: the **Insights Analyst** workflow runs every Monday at 13:00 UTC and can be started from the Actions tab. The brief appears on the run's summary page and as the `insights-brief` artifact (kept 90 days). It needs the `ANTHROPIC_API_KEY` repository secret; without it the run fails with a clear message. Starting it with `dry_run` computes the figures without calling Claude.

Locally:

```bash
pip install -e .
sdd-insights --dry-run                     # figures only
ANTHROPIC_API_KEY=... sdd-insights         # full brief, insights/brief.md
TICKETS_CSV=data/private/tickets.csv sdd-insights --json insights/brief.json
```

Set `INSIGHTS_MODEL` or `--model` to use another Claude model.

## Cost

One Claude call per run, about 3,000 input tokens and at most 2,000 output tokens. The token counts are printed at the end of each brief.

## Limits

- The brief is advice. It does not change tickets, assignments or the dashboard.
- In GitHub Actions there is no real ticket export, so scheduled briefs use synthetic data. Do not commit real ticket data to this repository to change that; run `sdd-insights` locally against your export instead.
