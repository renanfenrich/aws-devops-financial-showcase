#!/bin/sh
set -eu
# Official postgres entrypoint runs this once, before application migrations.
# psql reads the password from the environment; it never enters shell-expanded SQL.
psql --username "${POSTGRES_USER:-postgres}" --dbname postgres --set ON_ERROR_STOP=1 <<'SQL'
\getenv app_password POSTGRES_APP_PASSWORD
SELECT format('CREATE ROLE app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE PASSWORD %L',
              :'app_password') \gexec
CREATE DATABASE showcase OWNER app;
REVOKE CONNECT ON DATABASE showcase FROM PUBLIC;
GRANT CONNECT ON DATABASE showcase TO app;
SQL
