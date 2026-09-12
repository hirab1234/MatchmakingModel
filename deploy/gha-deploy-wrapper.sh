#!/bin/bash
# Forced command for the GitHub Actions deploy key.
#
# Installed on the server as /usr/local/bin/gha-deploy-wrapper.sh and referenced
# from root's authorized_keys with command="...". The CI key therefore cannot run
# an arbitrary shell on this box - only a deploy of a specific commit.
set -euo pipefail

CMD=${SSH_ORIGINAL_COMMAND:-}

if [[ "$CMD" =~ ^deploy[[:space:]]+([0-9a-f]{40})$ ]]; then
  exec /usr/local/bin/deploy-matchmaking.sh "${BASH_REMATCH[1]}"
elif [[ "$CMD" == "deploy" || -z "$CMD" ]]; then
  exec /usr/local/bin/deploy-matchmaking.sh
else
  echo "refused: this key may only run 'deploy [sha]'" >&2
  exit 1
fi
