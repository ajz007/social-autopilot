#!/usr/bin/env bash
# The publishing history (state/*.json) lives on the autopilot-state branch, not on
# main, so main can stay protected while the daily job records what it posted.
#
#   state-branch.sh load            copy the history into ./state (no-op on first run)
#   state-branch.sh save "message"  commit ./state/*.json to the autopilot-state branch
set -euo pipefail
BRANCH=autopilot-state

case "${1:-}" in
  load)
    if git fetch -q origin "$BRANCH" 2>/dev/null; then
      git checkout FETCH_HEAD -- state/
      git reset -q -- state/
      echo "Loaded publishing history from $BRANCH."
    else
      echo "No $BRANCH branch yet; starting with an empty history."
    fi
    ;;
  save)
    shopt -s nullglob
    files=(state/*.json)
    [ ${#files[@]} -gt 0 ] || { echo "No history to save."; exit 0; }
    wt=$(mktemp -d)
    if git fetch -q origin "$BRANCH" 2>/dev/null; then
      git worktree add -q --detach "$wt" FETCH_HEAD
    else
      git worktree add -q --detach "$wt"
      git -C "$wt" checkout -q --orphan "$BRANCH-new"
      git -C "$wt" rm -rqf .
    fi
    mkdir -p "$wt/state"
    cp "${files[@]}" "$wt/state/"
    git -C "$wt" add state
    if git -C "$wt" diff --cached --quiet; then
      echo "History unchanged."
    else
      git -C "$wt" -c user.name="social-autopilot" -c user.email="social-autopilot@users.noreply.github.com" \
        commit -q -m "${2:-Record publishing history}"
      git -C "$wt" push -q origin "HEAD:refs/heads/$BRANCH"
      echo "Saved publishing history to $BRANCH."
    fi
    git worktree remove --force "$wt"
    ;;
  *)
    echo "usage: $0 load | save \"message\"" >&2; exit 2 ;;
esac
