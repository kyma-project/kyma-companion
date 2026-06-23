---
name: commit-changes
description: Commit changes to the repository using git. Use when the user wants to save their work before creating a pull request. Trigger keywords - commit, save changes, git commit.
---

# Skill: commit-changes

Commit changes to the repository using git.

## Usage

```
/commit-changes
```

## Instructions

When this skill is invoked, follow these steps:

### 1. Analyze the current branch

Check the current changes in the working directory.

### 2. Select files to commit

Ask the user if they want to commit all changes or select which files they want to include in the commit. If there are untracked files.

### 3. Check for any secrets in the files.

Check if there is any sensitive information in the files to be committed. If any secrets are found, warn the user and ask if they want to proceed with the commit.

### 4. Generate the commit message

Generate a concise commit message based on the changes.

### 5. Commit the changes

Use the `git commit` command to commit the changes with the generated commit message.
