#!/usr/bin/env bash
# Installed by the operator, never auto-updated from a candidate release.
set -Eeuo pipefail
umask 077
: "${JOBEVENT_STACK_DIR:?}" "${JOBEVENT_REVISION_FILE:?}" "${JOBEVENT_HEALTH_URL:?}"
repo=https://github.com/ghdtjdwn/jobevent.git
state=${STATE_DIRECTORY:-/var/lib/jobevent-cd}
cd "$state"
exec 9>deploy.lock
flock -n 9 || exit 0
tip() { git ls-remote --exit-code "$repo" refs/heads/main | cut -f1; }
sha=$(tip)
[[ $sha =~ ^[a-f0-9]{40}$ ]]
[[ $(cat deployed 2>/dev/null || :) != "$sha" ]] || exit 0
[[ $(cat failed 2>/dev/null || :) != "$sha" ]] || exit 0
# Only a successful PUSH workflow for this exact main commit, not a PR/weekly job.
ci=$(curl -fsS --max-time 20 "https://api.github.com/repos/ghdtjdwn/jobevent/actions/workflows/ci.yml/runs?branch=main&event=push&head_sha=$sha&per_page=1")
jq -e --arg sha "$sha" '.workflow_runs[0] | .head_sha==$sha and .head_branch=="main" and .event=="push" and .conclusion=="success" and .head_repository.full_name=="ghdtjdwn/jobevent"' <<<"$ci" >/dev/null || exit 0
[[ -d source.git ]] || git init --bare -q source.git
git -C source.git fetch -q --depth=1 "$repo" refs/heads/main
[[ $(git -C source.git rev-parse FETCH_HEAD) == "$sha" ]] || exit 0
tmp=$(mktemp -d "$state/build.XXXXXXXX")
trap 'rm -r -- "$tmp"' EXIT
git -C source.git archive "$sha" | tar -x -C "$tmp"
# Keep host-owned Compose, reverse proxy, keys and persistent volume unchanged.
compose=(docker compose -p jobevent --project-directory "$JOBEVENT_STACK_DIR" -f "$JOBEVENT_STACK_DIR/compose.yaml" -f "$JOBEVENT_STACK_DIR/shared.yaml")
candidate=jobevent:cd-candidate
if ! if ! docker build --build-arg "JOBEVENT_REVISION=$sha" -t "$candidate" "$tmp"; then
  echo "$sha" > failed; echo "Candidate build failed; previous release remains active." >&2; exit 1
fi; then
  echo "$sha" > failed; echo "Candidate build failed; previous release remains active." >&2; exit 1
fi
printf 'services:\n  web:\n    image: %s\n' "$candidate" > "$tmp/preflight.yaml"
# Never apply a new schema to live data automatically.
if ! "${compose[@]}" -f "$tmp/preflight.yaml" run -T --rm --no-deps web sh -ec 'django-admin check --deploy --fail-level ERROR && django-admin migrate --check'; then
  echo "$sha" > failed; echo "Candidate preflight failed; previous release remains active; review migration/configuration." >&2; exit 1
fi
[[ $(tip) == "$sha" ]] || exit 0
previous=$(docker inspect --format '{{.Image}}' "$("${compose[@]}" ps -q web)")
docker tag "$previous" jobevent:previous
healthy() {
  [[ $(curl -fsS --max-time 5 "$JOBEVENT_HEALTH_URL" | jq -r '.revision') == "$sha" ]] &&
  [[ $(docker inspect -f '{{.State.Running}} {{.RestartCount}} {{.Image}}' "$("${compose[@]}" ps -q worker)") == "true 0 $(docker image inspect -f '{{.Id}}' "$candidate")" ]]
}
docker tag "$candidate" jobevent:local
if "${compose[@]}" up -d --no-build --no-deps web worker; then
  for _ in {1..18}; do
    if healthy && sleep 3 && healthy; then
      printf '%s\n' "$sha" > deployed.tmp; mv deployed.tmp deployed
      printf '%.12s\n' "$sha" > "$JOBEVENT_REVISION_FILE"
      echo "Activated $sha"; exit 0
    fi
    sleep 3
  done
fi
echo "$sha" > failed
docker tag "$previous" jobevent:local
"${compose[@]}" up -d --no-build --no-deps web worker
echo "Candidate failed readiness; restored prior image." >&2
exit 1
