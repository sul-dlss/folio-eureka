psql -h localhost -U okapi okapi <<EOF
DO \$\$ DECLARE
  r RECORD;
BEGIN
  FOR r IN (
    SELECT schema_name FROM information_schema.schemata
    WHERE schema_name LIKE 'sul_%'
       OR schema_name LIKE 'mod_%'
       OR schema_name LIKE 'supertenant_mod_%'
  ) LOOP
    EXECUTE 'DROP SCHEMA IF EXISTS ' || quote_ident(r.schema_name) || ' CASCADE';
  END LOOP;

BEGIN 
  FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP 
      EXECUTE 'DROP TABLE public.' || quote_ident(r.tablename) || ' CASCADE'; 
  END LOOP; 

  EXECUTE 'DROP SCHEMA IF EXISTS data_import_global CASCADE';
  EXECUTE 'DROP SCHEMA IF EXISTS id_dbz CASCADE';
  EXECUTE 'DROP SCHEMA IF EXISTS pubsub_config CASCADE';
  EXECUTE 'DROP SCHEMA IF EXISTS sys_quartz_mod_scheduler CASCADE';
END \$\$;
EOF