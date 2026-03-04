# Hooked

Hooked reduces PR cycle time by pushing pull request context, CI failures, and review nudges into team chat.

## What it does

- Posts a PR Brief when a pull request is opened, reopened, synchronized, or marked ready for review.
- Posts CI Failure triage when GitHub check runs or workflow runs fail for an associated PR.
- Runs a scheduled overdue-review scan and posts review nudges with reviewer suggestions.
- Keeps the core adapter-agnostic while isolating Runbear delivery behind a notifier port.
- Supports multi-repo routing with exact repo names, globs like `my-org/*`, and a catch-all `*` rule.

## Stack

- Python 3.13
- FastAPI
- SQLite + SQLAlchemy
- APScheduler
- GitHub API
- Optional OpenAI summaries
- Runbear adapter boundary for chat delivery

## Quick start

1. Create `.env` from `.env.example`.
2. Update `config.yaml` for the repos and destinations you want to track.
3. Install dependencies: `pip install -e .[dev]`
4. Start the service: `uvicorn app.api.main:app --reload`
5. Point your GitHub webhook at `POST /webhooks/github`

## Endpoints

- `POST /webhooks/github`
- `GET /healthz`
- `GET /readyz`
- `GET /debug/weekly-report`

## Config

Secrets are read from env vars. Non-secret configuration lives in `config.yaml`.

- GitHub: PAT for local demo or GitHub App credentials for production shape
- Runbear: API key plus either `RUNBEAR_WEBHOOK_URL` or workspace/destination config
- OpenAI: optional; the service falls back to deterministic content if unavailable
- Repository routing:
  - `github.repository_scope: configured` scans only explicitly configured repos
  - `github.repository_scope: all_accessible` scans every repo visible to the PAT or installed GitHub App
  - `repos[].full_name` can be an exact repo, a glob like `my-org/*`, or `*` as a fallback route

Example:

```yaml
github:
  mode: app
  repository_scope: all_accessible

repos:
  - full_name: "my-org/payments-api"
    destinations:
      pr_brief: payments-prs
      ci_failure: payments-ci
      review_nudge: payments-reviews

  - full_name: "my-org/frontend-*"
    destinations:
      pr_brief: frontend-prs
      ci_failure: frontend-ci
      review_nudge: frontend-reviews

  - full_name: "*"
    destinations:
      pr_brief: engineering-prs
      ci_failure: engineering-ci
      review_nudge: engineering-reviews
```

## Demo flow

1. Open a PR in the demo repo and show the PR Brief.
2. Push a failing commit and show the CI failure triage message.
3. Run the overdue scan or lower the threshold and show the review nudge.
4. Show `/debug/weekly-report` as the demo stub.

## ROI framing

- Reduce PR cycle time by pushing context into Slack.
- Fewer review stalls, fewer CI mysteries, fewer pings.

## Screenshots and video

- Add chat screenshots under `docs/` or directly in the repo.
- Add your Loom link here after recording the demo.

## Tests

Run:

```bash
pytest
```

## Limitations

- The Runbear adapter is isolated behind `NotifierPort`, but exact vendor payloads may need adjustment for your workspace.
- SQLite is the default v1 store.
- The weekly report is a demo stub, not a production reporting feature.

# Temp Changes for Webhook Test
