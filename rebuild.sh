#!/usr/bin/env bash
# Rebuild and restart this project's containers without re-pulling base images
# (mysql, redis, python base layers already on the machine).
#
# Usage:
#   ./rebuild.sh              # normal rebuild + up
#   ./rebuild.sh --force      # tear down / remove orphans, then rebuild (for ContainerConfig etc.)
#   ./rebuild.sh force        # same as --force

set -euo pipefail

cd "$(dirname "$0")"

FORCE=0
for arg in "$@"; do
  case "$arg" in
    --force|force|-f)
      FORCE=1
      ;;
    -h|--help)
      echo "Usage: $0 [--force]"
      echo "  Rebuild stocks-dashboard from local code."
      echo "  Does not pull mysql/redis/python template images from the registry."
      echo "  --force  Remove project containers/orphans first, then recreate."
      exit 0
      ;;
    *)
      echo "Unknown argument: $arg" >&2
      echo "Usage: $0 [--force]" >&2
      exit 1
      ;;
  esac
done

if docker compose version >/dev/null 2>&1; then
  COMPOSE=(docker compose)
  # Single-token flags so "false"/"never" are not treated as service names
  PULL_NEVER=(--pull=never)
  BUILD_NO_PULL=(--pull=false)
elif command -v docker-compose >/dev/null 2>&1; then
  COMPOSE=(docker-compose)
  # Compose v1 has no --pull=never on up; avoid "pull" and use build --pull=false
  PULL_NEVER=()
  BUILD_NO_PULL=(--pull=false)
else
  echo "Neither 'docker compose' nor 'docker-compose' found." >&2
  exit 1
fi

echo "==> Using: ${COMPOSE[*]}"

if [[ "$FORCE" -eq 1 ]]; then
  echo "==> Force clean: stopping project containers and removing orphans"
  "${COMPOSE[@]}" down --remove-orphans || true

  # Remove known stale container names from renames / failed recreates
  for name in stocks-dashboard stocks-app stocks-mysql stocks-redis; do
    docker rm -f "$name" 2>/dev/null || true
  done
  # Catch compose-generated names like stocks-volatility_app_1
  while IFS= read -r id; do
    [[ -n "$id" ]] && docker rm -f "$id" 2>/dev/null || true
  done < <(docker ps -aq --filter "name=stocks-volatility" 2>/dev/null || true)
  while IFS= read -r id; do
    [[ -n "$id" ]] && docker rm -f "$id" 2>/dev/null || true
  done < <(docker ps -aq --filter "name=stocks-dashboard" 2>/dev/null || true)
fi

echo "==> Building app image (no registry pull of base images)"
"${COMPOSE[@]}" build "${BUILD_NO_PULL[@]}" stocks-dashboard

echo "==> Starting services (no image pull)"
if [[ "${COMPOSE[*]}" == "docker compose" ]]; then
  if [[ "$FORCE" -eq 1 ]]; then
    "${COMPOSE[@]}" up -d --build --force-recreate --remove-orphans "${PULL_NEVER[@]}"
  else
    "${COMPOSE[@]}" up -d --build "${PULL_NEVER[@]}"
  fi
else
  # docker-compose v1: never run "pull"; build already used --pull=false
  if [[ "$FORCE" -eq 1 ]]; then
    "${COMPOSE[@]}" up -d --build --force-recreate --remove-orphans
  else
    "${COMPOSE[@]}" up -d --build
  fi
fi

echo "==> Status"
"${COMPOSE[@]}" ps
echo "Done. Dashboard: http://localhost:5000"
echo "Logs: ${COMPOSE[*]} logs -f stocks-dashboard"
echo "Wipe all DB data: ${COMPOSE[*]} down -v   # then ./rebuild.sh"
