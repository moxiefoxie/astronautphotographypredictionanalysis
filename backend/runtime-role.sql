DO $$
DECLARE password text := replace(gen_random_uuid()::text || gen_random_uuid()::text, '-', '');
BEGIN
 IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname='appa_runtime') THEN RAISE EXCEPTION 'appa_runtime already exists; refusing to rotate'; END IF;
 EXECUTE format('CREATE ROLE appa_runtime LOGIN PASSWORD %L NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS CONNECTION LIMIT 20', password);
 PERFORM vault.create_secret(password, 'appa_runtime_connection_password', 'APPA runtime login, restricted to private appa schema');
END $$;
GRANT CONNECT ON DATABASE postgres TO appa_runtime;
GRANT USAGE ON SCHEMA appa TO appa_runtime;
GRANT SELECT, INSERT, UPDATE ON ALL TABLES IN SCHEMA appa TO appa_runtime;
DO $$
DECLARE t record;
BEGIN
 FOR t IN SELECT tablename FROM pg_tables WHERE schemaname='appa' LOOP
  EXECUTE format('CREATE POLICY appa_runtime_access ON appa.%I TO appa_runtime USING (true) WITH CHECK (true)',t.tablename);
 END LOOP;
END $$;
ALTER ROLE appa_runtime SET statement_timeout = '60s';
ALTER ROLE appa_runtime SET idle_in_transaction_session_timeout = '60s';
