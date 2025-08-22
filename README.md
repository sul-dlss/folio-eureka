# folio-eureka

## Get a token 

TOKEN=$(curl -sX POST -d client_id="folio-backend-admin-client" -d client_secret=SecretPassword -d grant_type=client_credentials http://keycloak-headless.folio-dev.svc.cluster.local:8080/realms/master/protocol/openid-connect/token | jq -r '.access_token')

## Post the applications
curl -X POST --location 'http://mgr-applications/applications' -H "Authorization: Bearer $TOKEN” -H 'Content-Type: application/json' -d@application-descriptor-minimal-ramsons.json

curl -X POST --location 'http://mgr-applications/applications' -H "Authorization: Bearer $TOKEN” -H 'Content-Type: application/json' -d@application-descriptor-complete-ramsons.json

curl http://mgr-applications/applications

## Create the tenant
curl -X POST --location http://mgr-tenants/tenants --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' --data '{"name": "sul", "description": "Stanford University Libraries"}

### Get the tenantUUID
curl -s http://mgr-tenants/tenants

## Create entitlements (Make sure all modules are up and running, may need to do multiple times due to timeouts)
curl -X POST --location "http://mgr-tenant-entitlements/entitlements" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $token" --data '{"tenantId": "$tenantUUID", "applications": ["app-platform-minimal-1.0.41"]}'

curl -X POST --location "http://mgr-tenant-entitlements/entitlements" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data '{"tenantId": "$tenantUUID", "applications": ["app-platform-complete-1.1.83"]}'

## Create Admin User

### Get the sidecar token from the tenant keycloak realm (sul)
TOKEN=$(curl -sX POST -d client_id="sidecar-module-access-client" -d client_secret="p11qYvTbNp0JCkOO8BIcONI2uXtKoPiJ" -d grant_type=client_credentials http://keycloak-headless:8080/realms/sul/protocol/openid-connect/token | jq -r  '.access_token')

## Create the User
curl -X POST --location 'http://mod-users-keycloak:8082/users-keycloak/users' -H "Authorization: Bearer $TOKEN” -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data-raw '{
    "username": "eureka_admin",
    "active": true,
    "personal": {
        "firstName": "Admin",
        "lastName": "Eureka",
        "email": "sul-unicorn-devs@lists.stanford.edu"
    }
}'

## ...
curl -X GET -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' 'http://mod-users-keycloak:8082/users-keycloak/users/e38b316e-a83d-45b9-8cd5-1c5e3eec3582'

{"username":"eureka_admin","id":"e38b316e-a83d-45b9-8cd5-1c5e3eec3582","active":true,"departments":[],"proxyFor":[],"personal":{"lastName":"Eureka","firstName":"Admin","email":"sul-unicorn-devs@lists.stanford.edu","addresses":[]},"createdDate":"2025-08-08T17:29:06.147+00:00","updatedDate":"2025-08-08T17:29:06.147+00:00","metadata":{"createdDate":"2025-08-08T17:29:06.143+00:00","updatedDate":"2025-08-08T17:29:06.143+00:00"},"customFields":{}}

curl -X POST --location 'http://mod-login-keycloak:8082/authn/credentials' -H "Authorization: Bearer $TOKEN” -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "username": "eureka_admin",
    "userId": "e38b316e-a83d-45b9-8cd5-1c5e3eec3582",
    "password": "SecretPassword"
}'

curl -X POST --location 'http://mod-roles-keycloak:8082/roles' -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "name": "adminRole",
    "description": "Admin role"
}'
{"id":"c2803b2c-f357-441f-a603-22cc46f38dd3","name":"adminRole","description":"Admin role","type":"REGULAR","metadata":{"createdDate":"2025-08-08T19:39:12.140+00:00","updatedDate":"2025-08-08T19:39:12.140+00:00"}}