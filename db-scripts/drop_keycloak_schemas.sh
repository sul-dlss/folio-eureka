psql -h localhost -U keycloak keycloak <<EOF
DO \$\$ 
DECLARE 
    r RECORD; 
BEGIN 
    FOR r IN (SELECT tablename FROM pg_tables WHERE schemaname = 'public') LOOP 
        EXECUTE 'DROP TABLE public.' || quote_ident(r.tablename) || ' CASCADE'; 
    END LOOP; 
END \$\$;
EOF