# richtan/richtan

GitHub profile README auto-generator. Renders ASCII art pinned repo cards, a 52-week contribution heatmap, and a monthly activity timeline — all as text art inside a `<pre>` block.

## Architecture

Three components work together:

### 1. Cloudflare Worker (`worker/`)
Receives GitHub webhooks and dispatches profile updates.

- **HTTP handler** (`fetch`): POST only. Validates HMAC-SHA256 signature (timing-safe via `crypto.subtle.timingSafeEqual`). Filters events through allowlist: `repository:created`, `pull_request:opened/closed/reopened`, `pull_request_review:*` (all actions). Forwards accepted events to the `ProfileDebounce` Durable Object singleton.
- **Scheduled handler** (every 12h, configured in `wrangler.toml`): Generates GitHub App JWT → gets installation token → triggers workflow via `POST /repos/.../actions/workflows/update-profile.yml/dispatches` (`workflow_dispatch` API, `ref: "main"`).
- **Durable Object `ProfileDebounce`**: Uses SQLite storage (not KV). Three tables: `deliveries` (replay protection, 5-min TTL), `dispatches` (rate tracking), `state` (alarm flag). Replay protection rejects duplicate `X-GitHub-Delivery` IDs. Rate limit: max 30 dispatches/hour. First-event-wins debounce: sets a 60-second alarm, ignores subsequent events while alarm is pending. On alarm: gets installation token → dispatches via `POST /repos/.../dispatches` (`repository_dispatch` API, `event_type: "profile-update"`). Cleanup: removes records >24h old.

Note the two different dispatch APIs: scheduled handler uses `workflow_dispatch`, alarm uses `repository_dispatch`.

### 2. GitHub Actions (`.github/workflows/update-profile.yml`)
Triggers: `schedule` (every 6h), `repository_dispatch: profile-update` (from webhook), `workflow_dispatch` (from Worker scheduled + manual), `push` to `scripts/**` on main.

- Concurrency group `profile-update`, cancels in-progress runs
- Guard: `if: github.repository == 'richtan/richtan'`
- Steps: checkout → Python 3.12 (pip cached) → install deps → run `generate.py` → commit as `github-actions[bot]` → push with 3-retry rebase loop

### 3. Python Pipeline (`scripts/`)
Fetches GitHub data via GraphQL, renders three sections, and atomically updates README.md.

## Key Files

```
scripts/
  generate.py          Orchestrator: fetch → render → validate → atomic write
  github_api.py        GraphQL client, fetches 366-day contribution window
  render_pinned.py     Box-drawn pinned repo cards (2-column layout)
  render_graph.py      52-week contribution heatmap
  render_activity.py   Monthly activity timeline with tree formatting
requirements.txt       Single dependency: requests

worker/
  src/index.js         Worker + Durable Object (all in one file)
  wrangler.toml        Worker config, DO binding, cron schedule
  package.json         Single dependency: jose

.github/
  workflows/update-profile.yml   CI workflow
  dependabot.yml                 Dependency updates
```

## Python Pipeline Details

### `generate.py`
- Fetches data, filters private repos from pinned items
- Sanitizes text: NFC normalization, strips null bytes/control chars, escapes markdown metacharacters (backticks, brackets)
- Renders three sections: pinned → graph → activity
- Validates output is non-empty, warns if any line exceeds 80 visual chars
- SHA256 hash dedup: hashes the rendered `<pre>` block, compares to `<!-- hash:... -->` comment in existing README, skips write if unchanged
- Atomic write: writes to temp file then `os.rename()`
- Content lives between `<!-- PROFILE START -->` / `<!-- PROFILE END -->` markers

### `github_api.py`
- Fetches 366-day window via GraphQL: pinned repos (6), commits by repo (top 10, 100 nodes each), PRs by repo (top 5), reviews by repo (top 5), repos created (10), contribution calendar
- Username is string-interpolated into the query (not parameterized) via `.format(username=username)`
- Bearer token auth, 30s timeout

### `render_pinned.py`
- `visual_len()`: Display width calculator. Strips HTML tags, unescapes entities, handles East Asian wide chars (W/F = 2), skips combining marks (Mn/Me/Cf) and zero-width chars
- `visual_pad()`: Pads text to target visual width
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
- Filters private repos independently (commits and repos-created)
- Imports `visual_len`/`visual_pad` from `render_pinned`

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
```
Scripts import each other as siblings — run from the repo root so Python finds them, or from `scripts/`.

### Dependencies
```sh
pip install -r requirements.txt   # just requests
```

### Worker dev
```sh
cd worker && npm install && npx wrangler dev
```

### Deploy worker
```sh
cd worker && npx wrangler deploy
wrangler secret put APP_ID
wrangler secret put APP_PRIVATE_KEY
wrangler secret put WEBHOOK_SECRET
wrangler secret put INSTALLATION_ID  # optional
```

## Conventions / Gotchas

- All rendering targets max 80 visual chars per line
- `visual_len()` is the source of truth for display width — always use it, not `len()`
- Private repos are filtered in two places: `generate.py` (pinned items) and `render_activity.py` (commits, repos created)
- README content lives between `<!-- PROFILE START -->` / `<!-- PROFILE END -->` markers
- `<!-- hash:... -->` comment enables change detection to skip no-op updates
- Atomic writes prevent README corruption (temp file + `os.rename`)
- GraphQL username is string-interpolated, not parameterized — this is intentional (it's the authenticated user's own username)
- The Worker uses two different GitHub dispatch APIs: `workflow_dispatch` for scheduled runs, `repository_dispatch` for webhook-triggered runs
