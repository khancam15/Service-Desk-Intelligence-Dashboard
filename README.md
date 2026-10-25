# Service Desk Intelligence Dashboard

A dashboard that turns service desk ticket data into actionable insight: volume and backlog trends, SLA health, recurring issues, and team workload.

> **Status: planning.** The repository holds its development and security baseline (CI, CodeQL, issue templates, contribution and security policies) and no application code yet. Everything below describes intent, not a working system.

## Purpose

Turn IT service desk activity into operational insight: ticket volume and trends, first contact resolution, backlog ageing and knowledge article coverage, presented on one dashboard. It builds on an internal, unpublished ITSM AI assistant used in the author's day to day service desk work and brings the reporting side of that work into a project that can be shown publicly.

**Audience:** service desk and IT operations leads, and reviewers assessing how the author approaches ITSM data and dashboard design. Part of [Khaneil Campbell's](https://github.com/khancam15) portfolio.

## Ground rules

- **No employer data.** The dashboard runs on synthetic or anonymised ticket data. Nothing from a production ITSM instance is committed.
- **No fabricated metrics.** A value appears only when it is computed from the data in the repository.
- **Secrets stay out of git.** Credentials live in a gitignored `.env`; `.env.example` lists the names only.

## Planned scope

To be confirmed once the first iteration is designed:

1. A documented data model for tickets, categories, priorities, SLA targets and knowledge articles
2. A synthetic data generator so the dashboard can be run by anyone
3. The dashboard itself, with each metric defined in the documentation before it is shown
4. Setup and verification instructions, and this README updated to match what exists

## Getting started

```bash
git clone https://github.com/khancam15/service-desk-dashboard.git
cd service-desk-dashboard
cp .env.example .env   # fill in local values; never commit .env
```

Setup and run instructions will be added here once the stack lands.

## Development workflow

- `main` is protected. All changes go through a pull request with passing checks.
- Branch names: `feat/...`, `fix/...`, `chore/...`, `docs/...`.
- Commit messages follow [Conventional Commits](https://www.conventionalcommits.org/) (for example `feat: add SLA breach chart`).
- See [CONTRIBUTING.md](CONTRIBUTING.md) for details.

## Security

Ticket data can contain personal information and internal system details. Use synthetic or anonymized data for development, keep credentials in environment variables or GitHub secrets, and report vulnerabilities privately as described in [SECURITY.md](SECURITY.md).

## Related work

- [Splunk Brute Force Detection Lab](https://github.com/khancam15/splunk-bruteforce-detection-lab): detection and case note automation
- [Multi-Agent Commerce Pipeline](https://github.com/khancam15/multi-agent-commerce-pipeline): agent orchestration with publish gates

## License

[MIT](LICENSE)
