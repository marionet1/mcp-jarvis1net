ALTER TABLE api_keys OWNER TO jarvis_mcp;
GRANT ALL PRIVILEGES ON TABLE api_keys TO jarvis_mcp;
GRANT USAGE, SELECT ON SEQUENCE api_keys_id_seq TO jarvis_mcp;
