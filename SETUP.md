# Setup

## Quick Start (5 minutes)

1. **Fork this repo** — Click "Fork" and change the **Repository name** to your GitHub username (e.g., `alice` for `alice/alice`). This is required for GitHub to display it as your profile README.

2. **Create a Personal Access Token (classic)** — Go to [Settings → Developer settings → Personal access tokens → Tokens (classic)](https://github.com/settings/tokens/new). Select the `read:user` scope. Classic tokens are recommended because fine-grained tokens have limited GraphQL API support.

3. **Add the token as a repository secret** — In your forked repo, go to Settings → Secrets and variables → Actions → New repository secret. Name it `PROFILE_TOKEN` and paste your token.

4. **Enable the workflow** — Go to the Actions tab in your fork, select "Update Profile" from the left sidebar, and click "Enable workflow".

5. **Run the workflow** — Click "Run workflow" → "Run workflow". Your profile README will be generated in about 15 seconds.

6. **Share to Profile** — GitHub may prompt you to share the README to your profile. Click "Share to Profile" once the workflow has finished running, so your profile displays your own data instead of the template.

The workflow runs automatically every 6 hours to keep your profile updated.

## Optional: Real-time updates with Cloudflare Worker

The `worker/` directory contains a Cloudflare Worker that triggers profile updates immediately when you create repos, open PRs, or submit reviews — instead of waiting for the 6-hour schedule.

<details>
<summary>Worker setup instructions</summary>

**Prerequisites**: Cloudflare account, GitHub App

1. **Create a GitHub App** at [Settings → Developer settings → GitHub Apps](https://github.com/settings/apps/new):
   - Set a Homepage URL (can be your profile)
   - Set a Webhook URL (your worker URL, added after deploy)
   - Webhook secret: generate a random string
   - Permissions: Contents (read & write), Issues (read), Metadata (read)
   - Subscribe to events: Forks, Issues, Pull requests, Pull request reviews, Pushes, Repositories, Stars
     - Note: The Issues event only appears after enabling the Issues permission above
   - Install the app on your profile repo

2. **Deploy the worker**:
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
   wrangler secret put APP_ID              # Your GitHub App's ID
   wrangler secret put APP_PRIVATE_KEY < path/to/private-key.pem  # Pipe from file to preserve newlines
   wrangler secret put WEBHOOK_SECRET     # The webhook secret you chose
   wrangler secret put INSTALLATION_ID    # Optional: find in app installation URL
   ```

3. **Update the GitHub App** webhook URL to your deployed worker URL.

</details>

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `GITHUB_TOKEN` | (required) | PAT with `read:user` scope |
| `GITHUB_USERNAME` | auto-detected | Override the username to render |
| `PROFILE_TIMEZONE` | `America/New_York` | Timezone for timestamps and date grouping (any IANA timezone, e.g., `Europe/London`, `Asia/Tokyo`) |

To set `PROFILE_TIMEZONE` in GitHub Actions, add it to the workflow env block or as a repository variable.

## Notes

- **Python version**: 3.9 or later required (3.12 recommended). The workflow uses 3.12.
- **Scheduled workflows on forks**: GitHub automatically disables scheduled workflows on forked repos after 60 days of inactivity. If your profile stops updating, go to Actions → "Update Profile" and re-enable it, or push any commit.
- **Dependabot**: This repo includes `.github/dependabot.yml` which creates automated dependency update PRs. Delete it if you don't want these.
- **Local development**: Run `GITHUB_TOKEN=<your-pat> python scripts/generate.py` from the repo root to preview changes locally.
- **Running tests**: `pip install -r requirements-dev.txt && pytest`
- **Syncing with upstream**: When your fork falls behind, click **Sync fork** on your repo's main page. If there are conflicts (from automated README updates), click **Discard N commits** — this is safe because the Action will regenerate README.md on its next run. Your `PROFILE_TOKEN` secret is preserved since secrets live in GitHub settings, not in the repo.

## Troubleshooting

- **"GITHUB_TOKEN not set"** — Make sure `PROFILE_TOKEN` is set in Settings → Secrets and variables → Actions.
- **"Could not fetch user"** — Your token may be expired or missing the `read:user` scope. Generate a new one.
- **"Rate limited"** — GitHub's GraphQL API rate-limits at 5,000 points/hour. Wait and retry, or use a less-scoped token.
- **Workflow shows as disabled** — GitHub disables scheduled workflows after 60 days of fork inactivity. Re-enable it in the Actions tab.
- **Webhook secret** — Use a random string of 32+ characters (e.g., `openssl rand -hex 32`).
- **INSTALLATION_ID** — This is auto-detected from the GitHub App's first installation. Only set it manually if you have multiple installations.
