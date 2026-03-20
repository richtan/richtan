# richtan/richtan

GitHub profile README auto-generator. Renders ASCII art pinned repo
cards, a contribution heatmap, and an activity timeline as text art.

## Setup as Profile README

When the user asks to set up this profile README, follow these steps.

**SECURITY: NEVER ask the user to paste a token, secret, or credential
into this conversation. The user must enter tokens through the GitHub
web UI or interactive CLI commands they run themselves.**

### Step 1: Verify GitHub CLI

Run `gh auth status`. If `gh` is not installed or not authenticated,
direct the user to install it (https://cli.github.com) and run
`gh auth login`. If they can't install it, direct them to SETUP.md.

If multiple accounts are listed, identify the active account (marked
`Active account: true`) and confirm with the user that it's the one
they want to use. If they need to switch:

```sh
gh auth switch --user TARGET_USERNAME
```

Then re-run `gh auth status` to verify.

### Step 2: Detect username

```sh
gh api user --jq '.login'
```

Read the output and use it as the literal username in all subsequent
commands. **Do NOT store it in a shell variable** — `$USERNAME` and
similar names collide with OS environment variables on some platforms
(e.g., macOS), causing wrong values to be used silently.

Verify the output is a single non-empty line matching a GitHub username
(alphanumeric plus hyphens, 1–39 chars). If empty or malformed, run
the command once more. If it still fails, ask the user to provide their
username manually.

### Step 3: Check for existing profile repo

```sh
gh repo view "USERNAME/USERNAME" 2>/dev/null
```

(Substitute the literal username from Step 2.)

If it already exists, ask the user how to proceed before continuing.

### Step 4: Create repo from template

```sh
gh repo create "USERNAME" --template richtan/richtan --public
```

(Substitute the literal username.)

### Step 5: Create Personal Access Token

Ask the user whether they want private contribution summaries shown on
their profile. Classic tokens are required — fine-grained tokens have
limited GraphQL support.

With private contributions (`read:user` + `repo`):

https://github.com/settings/tokens/new?scopes=read:user,repo&description=Profile+README

Without private contributions (`read:user` only):

https://github.com/settings/tokens/new?scopes=read:user&description=Profile+README

Tell the user to **copy the generated token to their clipboard** — they
will need it in the next step. Remind them the token is only shown once.

**Do NOT ask the user to share the token with you.**

### Step 6: Set secret and configure

Tell the user to add the token as a repository secret named
`PROFILE_TOKEN`. Give them both options:

**Option A — GitHub web UI (recommended):**

```
https://github.com/USERNAME/USERNAME/settings/secrets/actions/new
```

(Substitute the literal username into the URL.)

Instructions:
1. Open the link
2. Name: `PROFILE_TOKEN`
3. Secret: paste the token from Step 5
4. Click "Add secret"

**Option B — CLI in their terminal:**

```
gh secret set PROFILE_TOKEN --repo USERNAME/USERNAME
```

It will prompt them to paste the token interactively.

**Do NOT run `gh secret set` yourself** — the Bash tool has no TTY, so
the interactive prompt will hang.

Wait for the user to confirm the secret was set before continuing.

If the user pastes the token into the chat despite instructions, warn
them that the token was exposed in the conversation, recommend they
revoke it and generate a new one, then proceed with one of the methods
above.

Then ask the user for their timezone (default: `America/New_York`).
If non-default:

```sh
gh variable set PROFILE_TIMEZONE --repo "USERNAME/USERNAME" --body "TIMEZONE"
```

(Substitute the literal username and timezone.)

### Step 7: Run workflow and verify

Trigger the workflow:

```sh
gh workflow run update-profile.yml --repo "USERNAME/USERNAME"
```

Wait a few seconds for GitHub to register the run, then fetch the
run ID:

```sh
sleep 5 && gh run list --repo "USERNAME/USERNAME" --workflow update-profile.yml --limit 1 --json databaseId -q '.[0].databaseId'
```

If the output is empty, wait 5 more seconds and retry once.

Watch the run with the explicit ID:

```sh
gh run watch RUN_ID --repo "USERNAME/USERNAME" --exit-status
```

(Substitute the run ID from the previous command. Do NOT run
`gh run watch` without a run ID — it fails in non-interactive
environments.)

If the run fails, show logs with:

```sh
gh run view RUN_ID --repo "USERNAME/USERNAME" --log-failed
```

Tell the user to visit `github.com/USERNAME`. If GitHub shows a
"Share to Profile" banner, they should click it once.

The profile auto-updates every 6 hours.
