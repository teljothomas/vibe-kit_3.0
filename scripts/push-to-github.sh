#!/usr/bin/env sh
set -eu
REMOTE_URL="https://github.com/teljothomas/vibe-kit_3.0.git"
if git remote get-url origin >/dev/null 2>&1; then
  CURRENT="$(git remote get-url origin)"
  if [ "$CURRENT" != "$REMOTE_URL" ]; then
    echo "push blocked: origin is $CURRENT, expected $REMOTE_URL" >&2
    exit 2
  fi
else
  git remote add origin "$REMOTE_URL"
fi
git show-ref --verify --quiet refs/heads/main || { echo "push blocked: local main branch is missing" >&2; exit 2; }
git show-ref --verify --quiet refs/heads/phase/28-v3-foundation || { echo "push blocked: Phase 28 branch is missing" >&2; exit 2; }
git push -u origin main
git push -u origin phase/28-v3-foundation
