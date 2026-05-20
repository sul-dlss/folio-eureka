psql -h localhost -U okapi okapi <<EOF
DO \$\$ DECLARE
  r RECORD;
BEGIN
  FOR r IN (SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'sul_%') LOOP
    EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.schema_name) || ' CASCADE';
  END LOOP;
END \$\$;
EOF