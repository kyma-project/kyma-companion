---
name: address-review-comments
description: Address review comments on GitHub pull requests using the gh CLI. Use when the user wants to respond to feedback, make changes, or update a pull request. Trigger keywords - address review comments, update PR, respond to feedback.
---

# Address Review Comments

Address review comments on GitHub pull requests using the `gh` CLI.

## Prerequisites

- There are not uncommitted changes in the working directory.
- There are no unpushed commits in the current branch.
- The branch is uptodate from remote (e.g., `git pull origin <branch>`).

## Instructions

### Pull Review Comments
There is a `hyperspace-insights` bot configured to auto review PRs and leave comments. Also, other reviewers may leave comments on the PR. To pull the review comments, use the `gh` CLI:

```bash
gh pr view <PR_NUMBER> --comments
```

### Understand the Comments

Go through each comment and understand the feedback provided by the reviewers. Check if the comment is a valid concern, suggestion, or question. If the comment is valid, plan how to address it in your code changes. Do not make any changes yet; just understand the feedback and plan your response.

### Output a summary for the PR author

Summarize the review comments in bullet points and potential plan to address or triage them. This summary will help the PR author understand the feedback and plan their next steps.

### Ask the user if they want to address the comments

Ask the user if they want to address the review comments. If they do, address the comments as per your plan. If not, you can provide guidance on how to respond to the comments without making changes.
