#!/bin/bash
# Mini SOC - PostgreSQL 16 bootstrap (idempotent).
#
# Installs PostgreSQL 16 from the PGDG apt repo, pins it to localhost, and
# creates the application role + database using the credentials embedded in
# DATABASE_URL (from /etc/mini-soc/.env).  Safe to re-run.
set -euo pipefail

ENV_FILE="${ENV_FILE:-/etc/mini-soc/.env}"
VENV_DIR="${VENV_DIR:-/home/ubuntu/mini-soc/.venv}"
PG_VERSION="${PG_VERSION:-16}"

log() { echo "[postgres] $*"; }

if [ ! -f "$ENV_FILE" ]; then
  echo "[postgres] missing $ENV_FILE" >&2
  exit 1
fi

# shellcheck disable=SC1090
set -a; . "$ENV_FILE"; set +a

if [ -z "${DATABASE_URL:-}" ]; then
  echo "[postgres] DATABASE_URL is not set in $ENV_FILE" >&2
  exit 1
fi

# Parse credentials out of DATABASE_URL with the venv interpreter.
read -r DB_USER DB_PASSWORD DB_NAME DB_HOST < <(
  "$VENV_DIR/bin/python" -c '
import sys, urllib.parse as u
p = u.urlparse(sys.argv[1])
print(p.username or "mini_soc", p.password or "",
      (p.path or "/mini_soc").lstrip("/") or "mini_soc",
      p.hostname or "localhost")
' "$DATABASE_URL"
)

log "Database=$DB_NAME User=$DB_USER Host=$DB_HOST"

# --- Install PostgreSQL 16 from PGDG ---------------------------------------
if ! command -v psql >/dev/null 2>&1 || ! dpkg -s "postgresql-${PG_VERSION}" >/dev/null 2>&1; then
  log "Adding PGDG apt repository"
  apt-get update -y
  apt-get install -y --no-install-recommends ca-certificates curl gnupg lsb-release
  install -d /usr/share/postgresql-common/pgdg
  curl -fsSL https://www.postgresql.org/media/keys/ACCC4CF8.asc \
    -o /usr/share/postgresql-common/pgdg/apt.postgresql.org.asc
  . /etc/os-release
  echo "deb [signed-by=/usr/share/postgresql-common/pgdg/apt.postgresql.org.asc] https://apt.postgresql.org/pub/repos/apt ${VERSION_CODENAME}-pgdg main" \
    > /etc/apt/sources.list.d/pgdg.list
  apt-get update -y
  log "Installing postgresql-${PG_VERSION}"
  DEBIAN_FRONTEND=noninteractive apt-get install -y "postgresql-${PG_VERSION}"
else
  log "postgresql-${PG_VERSION} already installed"
fi

# --- Listen on localhost only ----------------------------------------------
PG_CONF_DIR="/etc/postgresql/${PG_VERSION}/main"
mkdir -p "$PG_CONF_DIR/conf.d"
cat > "$PG_CONF_DIR/conf.d/mini-soc.conf" <<'CONF'
# Managed by mini-soc deploy/postgres.sh
listen_addresses = 'localhost'
port = 5432
CONF
chown -R postgres:postgres "$PG_CONF_DIR/conf.d" 2>/dev/null || true

systemctl enable --now postgresql >/dev/null 2>&1 || true
systemctl restart postgresql

# --- Role + database --------------------------------------------------------
log "Ensuring role and database exist"
# psql does not interpolate :'var' inside a dollar-quoted DO block, so build
# the statements with format() and execute them with \gexec instead.
sudo -u postgres psql -v ON_ERROR_STOP=1 \
  -v user="$DB_USER" -v pass="$DB_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE %I LOGIN PASSWORD %L', :'user', :'pass')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = :'user')\gexec
SELECT format('ALTER ROLE %I WITH LOGIN PASSWORD %L', :'user', :'pass')\gexec
SQL

if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname='${DB_NAME}'" | grep -q 1; then
  log "Creating database ${DB_NAME}"
  sudo -u postgres createdb -O "$DB_USER" "$DB_NAME"
else
  log "Database ${DB_NAME} already exists"
fi

log "PostgreSQL ready on ${DB_HOST}:5432"
