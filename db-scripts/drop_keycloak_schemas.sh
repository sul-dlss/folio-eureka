psql -h localhost -U keycloak keycloak <<EOF
DO \$\$ DECLARE
  r RECORD;
BEGIN
  FOR r IN (SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'public_%') LOOP
    EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.schema_name) || ' CASCADE';
  END LOOP;
END \$\$;
EOF