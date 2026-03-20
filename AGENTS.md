# richtan/richtan

GitHub profile README auto-generator. Renders ASCII art pinned repo
cards, a contribution heatmap, and an activity timeline as text art.

## Setup as Profile README

When the user asks to set up this profile README, follow these steps.

### Step 1: Verify GitHub CLI

Run `gh auth status`. If `gh` is not installed or not authenticated,
direct the user to install it (https://cli.github.com) and run
`gh auth login`. If they can't install it, direct them to SETUP.md.

### Step 2: Detect username

```sh
USERNAME=$(gh api user --jq '.login')
```

### Step 3: Check for existing profile repo

```sh
gh repo view "$USERNAME/$USERNAME" 2>/dev/null
```

If it already exists, ask the user how to proceed before continuing.

### Step 4: Create repo from template

```sh
gh repo create "$USERNAME" --template richtan/richtan --public
```

### Step 5: Create Personal Access Token

The user must create a classic PAT with `read:user` scope. Direct them
to this URL (scopes pre-selected):

https://github.com/settings/tokens/new?scopes=read:user&description=Profile+README

Classic tokens are required — fine-grained tokens have limited GraphQL
support. Ask the user to paste the token.

### Step 6: Set secret and configure

```sh
gh secret set PROFILE_TOKEN --repo "$USERNAME/$USERNAME" --body "$TOKEN"
```

Ask the user for their timezone (default: America/New_York).

If non-default:
```sh
gh variable set PROFILE_TIMEZONE --repo "$USERNAME/$USERNAME" --body "$TIMEZONE"
```

### Step 7: Run workflow and verify

```sh
gh workflow run update-profile.yml --repo "$USERNAME/$USERNAME"
gh run watch --repo "$USERNAME/$USERNAME" --exit-status
```

If the run fails, show logs with:
```sh
gh run view --repo "$USERNAME/$USERNAME" --log-failed
```

Tell the user to visit github.com/$USERNAME. If GitHub shows a
"Share to Profile" banner, they should click it once.

The profile auto-updates every 6 hours.
