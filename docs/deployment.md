# Deployment

The app is a single Streamlit process with no database. It needs Python 3.11+ or Docker, port 8501, and optionally a tickets CSV.

## Docker

```bash
docker build -t service-desk-dashboard .
docker run --rm -p 8501:8501 service-desk-dashboard          # synthetic data
docker run --rm -p 8501:8501 \
  -v "$PWD/data/private:/data:ro" -e TICKETS_CSV=/data/tickets.csv \
  service-desk-dashboard                                     # your own export
```

The image runs as a non-root user and has a health check on `/_stcore/health`. CI builds the image and checks that endpoint on every pull request.

## Hosting options

Any host that runs a container or a Python process works. Two low-effort choices:

- **Streamlit Community Cloud** (free, public apps): connect the GitHub repository, set the main file to `src/service_desk_dashboard/app.py` and Python 3.12. Synthetic data only, since the app is public.
- **A container platform** (for example Google Cloud Run, Azure Container Apps, Fly.io, Render): deploy the Docker image, expose port 8501, and set `TICKETS_CSV` if you mount data.

## Before showing real ticket data

The dashboard has no login of its own. If it will ever show anything other than synthetic data:

- Put it behind an identity-aware proxy or the platform's built-in authentication (for example Cloud Run with IAP, Azure Easy Auth, or Cloudflare Access), and serve it over HTTPS only.
- Anonymise exports first: pseudonymous assignees, no requester names, emails or free-text descriptions.
- Keep the data file outside the image and the repository, mounted read-only.

## Configuration

| Variable | Default | Purpose |
| --- | --- | --- |
| `TICKETS_CSV` | empty | Path to a tickets CSV (see [data-model.md](data-model.md)). Empty means synthetic data. |
| `SYNTHETIC_DAYS` | `120` | Days of synthetic history. |
| `SYNTHETIC_SEED` | `42` | Seed for synthetic data. |

Streamlit server settings are in `.streamlit/config.toml` (headless, usage statistics off, XSRF protection on, error details hidden from viewers).
