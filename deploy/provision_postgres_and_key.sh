#!/usr/bin/env bash
set -euo pipefail

DB_PASS="$(openssl rand -hex 16)"
API_KEY="$(openssl rand -hex 24)"
API_HASH="$(python3 -c "import hashlib,sys; print(hashlib.sha256(sys.argv[1].encode()).hexdigest())" "$API_KEY")"

sudo -u postgres psql -tAc "DO \$\$ BEGIN IF NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'jarvis_mcp') THEN CREATE ROLE jarvis_mcp LOGIN PASSWORD '$DB_PASS'; ELSE ALTER ROLE jarvis_mcp WITH PASSWORD '$DB_PASS'; END IF; END \$\$;"
if ! sudo -u postgres psql -tAc "SELECT 1 FROM pg_database WHERE datname = 'jarvis_mcp'" | grep -q 1; then
  sudo -u postgres createdb -O jarvis_mcp jarvis_mcp
fi

sudo -u postgres psql -d jarvis_mcp -c "CREATE TABLE IF NOT EXISTS api_keys (id BIGSERIAL PRIMARY KEY, key_hash TEXT UNIQUE NOT NULL, owner_name TEXT NOT NULL, scopes TEXT NOT NULL DEFAULT '*', is_active BOOLEAN NOT NULL DEFAULT TRUE, created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(), last_used_at TIMESTAMPTZ NULL);"
sudo -u postgres psql -d jarvis_mcp -c "INSERT INTO api_keys (key_hash, owner_name, scopes) VALUES ('$API_HASH', 'marionet1', '*') ON CONFLICT (key_hash) DO NOTHING;"

sed -i "s|^MCP_DATABASE_URL=.*|MCP_DATABASE_URL=postgresql://jarvis_mcp:$DB_PASS@127.0.0.1:5432/jarvis_mcp|" /home/jump/mcp-jarvis1net/.env
sed -i "s|^MCP_REQUIRE_API_KEY=.*|MCP_REQUIRE_API_KEY=true|" /home/jump/mcp-jarvis1net/.env

umask 077
printf "%s\n" "$API_KEY" > /home/jump/mcp-jarvis1net/.generated_api_key

systemctl --user restart jarvis1net-mcp.service
echo "API_KEY=$API_KEY"
