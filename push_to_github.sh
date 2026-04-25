#!/bin/bash
set -e

echo "=== Pushing to GitHub ==="

# 1. Download GitHub CLI binary directly (avoids Xcode sudo prompt)
if ! command -v gh &> /dev/null; then
    echo "Downloading GitHub CLI..."
    curl -L https://github.com/cli/cli/releases/download/v2.47.0/gh_2.47.0_macOS_arm64.tar.gz -o gh.tar.gz
    tar -xzf gh.tar.gz
    export PATH="$PWD/gh_2.47.0_macOS_arm64/bin:$PATH"
fi

# 2. Check auth
if ! gh auth status &> /dev/null; then
    echo "You need to log in to GitHub. Running 'gh auth login'..."
    echo "Please select 'GitHub.com', 'HTTPS', and 'Login with a web browser'."
    gh auth login
fi

# 3. Rename current branch to main
git branch -M main

# 4. Create the repository
echo "Creating repository rksingh95/DecisionLedger..."
gh repo create rksingh95/DecisionLedger --public --source=. --remote=origin --push

echo "Done! Code pushed to https://github.com/rksingh95/DecisionLedger"
