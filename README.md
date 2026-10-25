# Service Desk Intelligence Dashboard

A dashboard that turns service desk ticket data into actionable insight: volume and backlog trends, SLA health, recurring issues, and team workload.

> Status: early setup. The application stack has not been committed yet.

## Getting started

```bash
git clone https://github.com/khancam15/Service-Desk-Intelligence-Dashboard.git
cd Service-Desk-Intelligence-Dashboard
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

## License

[MIT](LICENSE)
