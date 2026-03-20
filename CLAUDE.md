# richtan/richtan

GitHub profile README auto-generator. Renders ASCII art pinned repo cards, a 52-week contribution heatmap, and a monthly activity timeline — all as text art inside a `<pre>` block.

## Architecture

Three components work together:

### 1. Cloudflare Worker (`worker/`)
Receives GitHub webhooks and dispatches profile updates.

- **HTTP handler** (`fetch`): POST only. Validates HMAC-SHA256 signature (timing-safe via `crypto.subtle.timingSafeEqual`). Filters events through allowlist: `push`, `repository:*` (all actions), `pull_request:opened/closed/reopened`, `pull_request_review:*` (all actions), `star:*`, `fork`, `issues:opened/closed`. Forwards accepted events to the `ProfileDebounce` Durable Object singleton.
- **Scheduled handler** (every 12h, configured in `wrangler.toml`): Generates GitHub App JWT → gets installation token → triggers workflow via `POST /repos/.../actions/workflows/update-profile.yml/dispatches` (`workflow_dispatch` API, `ref: "main"`).
- **Durable Object `ProfileDebounce`**: Uses SQLite storage (not KV). Three tables: `deliveries` (replay protection, 5-min TTL), `dispatches` (rate tracking), `state` (alarm flag). Replay protection rejects duplicate `X-GitHub-Delivery` IDs. Rate limit: max 30 dispatches/hour. First-event-wins debounce: sets a 60-second alarm, ignores subsequent events while alarm is pending. On alarm: gets installation token → dispatches via `POST /repos/.../dispatches` (`repository_dispatch` API, `event_type: "profile-update"`). Cleanup: removes records >24h old.

Note the two different dispatch APIs: scheduled handler uses `workflow_dispatch`, alarm uses `repository_dispatch`.

### 2. GitHub Actions (`.github/workflows/update-profile.yml`)
Triggers: `schedule` (every 6h), `repository_dispatch: profile-update` (from webhook), `workflow_dispatch` (from Worker scheduled + manual), `push` to `scripts/**` on main.

- Concurrency group `profile-update`, cancels in-progress runs
- Steps: checkout → Python 3.12 (pip cached) → install deps → run `generate.py` → commit as `github-actions[bot]` → push with 3-retry rebase loop

### 3. Python Pipeline (`scripts/`)
Fetches GitHub data via GraphQL, renders three sections, and atomically updates README.md.

## Key Files

```
scripts/
  generate.py          Orchestrator: fetch → render → validate → atomic write
  github_api.py        GraphQL client, fetches 366-day contribution window
  utils.py             Shared utilities: visual_len, visual_pad, visual_truncate, word_wrap, safe_href
  render_pinned.py     Box-drawn pinned repo cards (2-column layout, re-exports utils)
  render_graph.py      52-week contribution heatmap
  render_activity.py   Monthly activity timeline with tree formatting
requirements.txt       Single dependency: requests
requirements-dev.txt   Dev dependency: pytest

worker/
  src/index.js         Worker + Durable Object (all in one file)
  wrangler.toml        Worker config, DO binding, cron schedule
  package.json         Single dependency: jose

tests/                 pytest test suite

AGENTS.md              AI assistant setup runbook (auto-discovered by coding tools)

.github/
  workflows/update-profile.yml   CI workflow
  dependabot.yml                 Dependency updates
```

## Python Pipeline Details

### `generate.py`
- Fetches data, filters private repos from pinned items
- Sanitizes text: NFC normalization, strips null bytes/control chars
- Renders three sections: pinned → graph → activity
- Validates output is non-empty, warns if any line exceeds 80 visual chars
- SHA256 hash dedup: hashes the rendered `<pre>` block, compares to `<!-- hash:... -->` comment in existing README, skips write if unchanged
- Atomic write: writes to temp file then `os.replace()`
- Content lives between `<!-- PROFILE START -->` / `<!-- PROFILE END -->` markers

### `github_api.py`
- Fetches 366-day window via GraphQL: pinned repos (6), commits by repo (top 100, 100 nodes each), PRs by repo (top 50), reviews by repo (top 50), repos created (10), contribution calendar
- Username is passed as a proper GraphQL variable (`$login`), validated against GitHub's username regex
- Bearer token auth, 30s timeout

### `render_pinned.py`
- Re-exports `visual_len`, `visual_pad`, `visual_truncate`, `word_wrap`, `safe_href` from `utils.py` for backwards compatibility
- Cards are 39 chars wide (35 inner + 2 padding + 2 border). 2-column layout with 2-space gap
- Name truncated to 30 visual chars, description word-wrapped to 2 lines max
- Stats line: language left-aligned, stars/forks right-aligned with space fill

### `render_graph.py`
- Levels: `· ░ ▒ ▓ █`
- 7 rows (Sun=0 to Sat=6), day labels on Mon/Wed/Fri
- Month headers placed at first day of month with minimum 3-char spacing to avoid overlap

### `render_activity.py`
- Groups commits/PRs/reviews/repos-created by (year, month), sorted reverse chronological
- Tree formatting: `├─` / `└─` branches
- Dot-leader alignment at `LINE_WIDTH=72`
- Filters private repos independently (commits, PRs, reviews, and repos-created)
- Imports `visual_len`/`visual_pad`/`safe_href` from `utils`

## Secrets

| Secret | Where | Purpose |
|--------|-------|---------|
| `PROFILE_TOKEN` | GitHub Actions secret | PAT with `read:user` scope + repo write access for commit/push |
| `APP_ID` | Worker secret | GitHub App ID |
| `APP_PRIVATE_KEY` | Worker secret | PKCS8 PEM private key (imported via `jose`'s `importPKCS8`) |
| `WEBHOOK_SECRET` | Worker secret | HMAC-SHA256 webhook validation |
| `INSTALLATION_ID` | Worker secret (optional) | GitHub App installation ID; if unset, fetched from `/app/installations` |

### GitHub App JWT
RS256, issued at `now - 60s`, expires `now + 600s` (10 min), issuer = `APP_ID`.

### Installation token flow
If no `INSTALLATION_ID`, fetches from `GET /app/installations` (takes first result). Then exchanges JWT for token via `POST /app/installations/{id}/access_tokens`.

## Development

### Run locally
```sh
GITHUB_TOKEN=<pat> python scripts/generate.py
PROFILE_TIMEZONE=Europe/London GITHUB_TOKEN=<pat> python scripts/generate.py  # custom timezone
```
Scripts import each other as siblings — run from the repo root so Python finds them, or from `scripts/`.

### Dependencies
```sh
pip install -r requirements.txt       # just requests
pip install -r requirements-dev.txt   # pytest (for running tests)
```

### Run tests
```sh
pytest tests/ -v
```

### Worker dev
```sh
cd worker && npm install && npx wrangler dev
```

### Deploy worker
```sh
cd worker && npm install
```
Edit `wrangler.toml` and set `DISPATCH_REPO` to your `username/username`:
```toml
[vars]
DISPATCH_REPO = "yourusername/yourusername"
```
Then deploy:
```sh
npx wrangler deploy
wrangler secret put APP_ID
wrangler secret put APP_PRIVATE_KEY
wrangler secret put WEBHOOK_SECRET
wrangler secret put INSTALLATION_ID  # optional
```

## Git Workflow

README.md is auto-generated. Pushing script changes to `main` triggers CI to regenerate it. When working on rendering scripts:

1. Run `generate.py` locally to verify changes look correct
2. **Only commit script changes** — do not commit README.md. Discard local README changes with `git checkout README.md`
3. `git pull --rebase origin main && git push`

CI will regenerate and commit README.md automatically. This avoids rebase conflicts with automated profile updates (6h Actions cron, 12h Worker cron, webhook-triggered) that also modify README.md on `main`.

## Conventions / Gotchas

- All rendering targets max 80 visual chars per line
- `visual_len()` is the source of truth for display width — always use it, not `len()`
- Private repos are filtered in two places: `generate.py` (pinned items) and `render_activity.py` (commits, PRs, reviews, repos created)
- README content lives between `<!-- PROFILE START -->` / `<!-- PROFILE END -->` markers
- `<!-- hash:... -->` comment enables change detection to skip no-op updates
- Atomic writes prevent README corruption (temp file + `os.replace`)
- Use `safe_href()` from `utils.py` to validate URL schemes before embedding in HTML href attributes
- The Worker uses two different GitHub dispatch APIs: `workflow_dispatch` for scheduled runs, `repository_dispatch` for webhook-triggered runs

## Webhook Coverage

The worker's `ALLOWED_EVENTS` covers 7 event types: `push`, `repository` (all actions), `pull_request` (opened/closed/reopened), `pull_request_review` (all actions), `star`, `fork`, and `issues` (opened/closed). The debounce/rate-limiting infrastructure handles high-frequency events like `push` and `star`.

### Covered triggers

- **Webhook**: `push`, `repository:*` (all actions), `pull_request:opened/closed/reopened`, `pull_request_review:*`, `star:*`, `fork`, `issues:opened/closed`
- **Cron**: Actions schedule (every 6h), Worker scheduled handler (every 12h)
- **Code push**: `scripts/**` on main (triggers Actions workflow)

### Remaining gaps (no webhook exists)

- Pin/unpin repos on profile — **no webhook event exists**
- Profile bio/avatar/status changes (not rendered, but worth noting)
