---
name: create-github-pr
description: Create GitHub pull requests using the gh CLI. Use when the user wants to create a new PR, submit code for review, or open a pull request. Trigger keywords - create PR, pull request, new PR, submit for review, code review.
---

# Create GitHub Pull Request

Create pull requests on GitHub using the `gh` CLI.

## Prerequisites

- The `gh` CLI must be authenticated (`gh auth status`).
- You must have commits on a branch that's pushed to the remote.
- Branch should be from forked repository.

## Before Creating a PR

### Verify Branch State

Before creating a PR, verify:

1. Check the current branch:

   ```bash
   git branch --show-current
   ```

2. **You're not on main or release-* ** - Never create PRs directly from main or release branches.

3. If the current branch is main or release-* or not a fork, stop and ask the user to create a new forked branch.

### Run Pre-commit Checks

Sync the poetry dependencies.

```bash
poetry install
poetry sync
```

Run the local pre-commit task before opening a PR:

```bash
poetry run poe pre-commit-check
```



### Check for uncommitted changes

If there are uncommitted changes, ask the user if they want to commit them before creating the PR. If no, continue with the committed changes. If yes, use the `commit-changes` skill to commit the changes before creating the PR.

## Create the PR

### Push Your Branch

Ensure your branch is pushed to the remote:

```bash
git push -u origin HEAD
```

### Generate PR title and description

Follow the skill `.agents/skills/pr-description/SKILL.md` guildelines to generate a PR title and description.
   
### Target a Different Branch

Default target is `main`. If the current branch was created from a different branch (e.g., `release-1.0`), ask the user to select the correct base branch for the PR: `main`, `release-1.0`, etc.

```bash
gh pr create --base "release-1.0"
```

### Create the PR

Use the gh cli to create the PR with the generated title, description, and target branch.

```bash
gh pr create --title "PR Title" --body "PR Description" --base "target-branch"
```

## After Creating

The command outputs the PR URL and number.

**Display the URL using markdown link syntax** so it's easily clickable:

```
Created PR [#123](https://github.com/OWNER/REPO/pull/123)
```

### Add a comment on the PR

There is a skill `address-review-comments` that can be used to address review comments on the pull requests.

Add a comment on the PR to suggest to use this skill to address review comments:

```bash
gh pr comment <PR_NUMBER> --body "You can use the `address-review-comments` skill locally to address review comments on this PR."
```
