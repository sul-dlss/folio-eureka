# folio-eureka

## Version Management
The version tag of Ramsons is R2-2024. To get the versions of the modules for Eureka, select the appropriate tag from [folio-org/platform-lsp](https://github.com/folio-org/platform-lsp). The version for Rmasons CSP4 app-platform-minimal is 1.0.41 and for app-platform-complete it is 1.1.78.

## Secrets
Add to [Vault](https://vault.sul.stanford.edu/) key-value pairs for db-credentials, eureka-common, eureka-edge, kafka-credentials, keycloak-credentials, kong-credentials, opensearch-credentials, and s3-credentials.
Create k8s VaultStaticSecrets by applying the secrets.yaml file:
```
envsubst < secrets.yaml | kubectl -n ${namespace} apply -f -
```

## Kong, Keycloak, Vault
Ask Operations to install Kong provided the overrides in kong.yaml. Recommended chart version is 12.0.11.
Install Keycloak:
```
helm install -n folio-dev --version v21.0.4 keycloak bitnami/keycloak -f folio-keycloak.yaml
```

## Deploy mgr-* modules
```
helm install -n folio-dev mgr-applications -f mgr-applications.yaml folio-helm-v2/mgr-applications
helm install -n folio-dev mgr-tenant-entitlements -f mgr-tenant-entitlements.yaml folio-helm-v2/mgr-tenant-entitlements
helm install -n folio-dev mgr-tenants -f mgr-tenants.yaml folio-helm-v2/mgr-tenants
```

## Get a token 
From the folio-k8s-pod:

TOKEN=$(curl -sX POST -d client_id="folio-backend-admin-client" -d client_secret=SecretPassword -d grant_type=client_credentials http://keycloak-headless.folio-dev.svc.cluster.local:8080/realms/master/protocol/openid-connect/token | jq -r '.access_token')

### Expand the access token lifespan
```
curl -sX PUT http://keycloak-headless.folio-dev.svc.cluster.local:8080/admin/realms/master -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d'{"accessTokenLifespan": "3600", "ssoSessionIdleTimeout": "3600"}'
```

## Post the applications
Get the application descriptors for app-platform-minimal from the repository [folio-org/app-platform-minimal](https://github.com/folio-org/app-platform-minimal) and select the version tag 1.0.41. Copy the application-descriptor.json file from there and save as application-descriptor-minimal-ramsons.json.
```
curl -X POST --location 'http://mgr-applications/applications' -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d@application-descriptor-minimal-ramsons.json
```

Get the application descriptors for app-platform-complete from the repository [folio-org/app-platform-complete](https://github.com/folio-org/app-platform-complete) and select the version tag 1.1.78. Copy the application-descriptor.json file from there and save as application-descriptor-complete-ramsons.json. Make sure the tag value for app-platform-minimal matches the version saved to application-descriptor-minimal-ramsons.json (listed in the depencies array of the app-platform-complete descriptor).
```
curl -X POST --location 'http://mgr-applications/applications' -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d@application-descriptor-complete-ramsons.json
```

Check the applications posted by logging into the folio-k8s-pod shell and doing:
```
curl http://mgr-applications/applications
```

Delete any extra applications if desired:
```
curl -X DELETE --location 'http://mgr-applications/applications/app-platform-complete-1.1.83' -H "Authorization: Bearer $TOKEN"
```

## Register the applications
...with modules/discovery endpoint from the folio-k8s-pod shell:
```
python3 ./discovery-modules.py
```

## Create the tenant
curl -X POST --location http://mgr-tenants/tenants --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' --data '{"name": "sul", "description": "Stanford University Libraries"}'

### Get the tenantUUID
tenantUUID=$(curl -sX GET http://mgr-tenants/tenants | jq -r '.tenants | .[] | .id')

## Get the tenant attributes
curl -s http://mgr-tenants/tenants/$tenantUUID/tenant-attributes


## Deploy backend modules
```
python3 ./install_modules.py application-descriptor-minimal-ramsons.json -n folio-dev -x install
python3 ./install_modules.py application-descriptor-complete-ramsons.json -n folio-dev -x install
```

## Create entitlements (Make sure all modules are up and running, may need to do multiple times due to timeouts)
curl -X POST --location "http://mgr-tenant-entitlements/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"app-platform-minimal-1.0.41\"]}" 

curl -X POST --location "http://mgr-tenant-entitlements/entitlements?async=true&ignoreErrors=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"app-platform-complete-1.1.78\"]}"

mod-entities-links system user is failing the entitlements process due to its user missing from keycloak. However, we don't migrate users to keycloak until after the entitlements process is completed. We will skip mod-entities-links by passing the ignoreErrors=true query parameter so that the rollback operation (when ignoreErrors=false, the default) does not uninstall modules, remove Kong routes, and remove Keycloak resources.

curl -X POST --location "http://mgr-tenant-entitlements/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"app-platform-complete-1.1.78\"]}"

### Monitor entitlements process
Using flowId (<flow-id> from POST respone)

flowId=$(curl -s http://mgr-tenant-entitlements/entitlement-flows/<flow-id> | jq -r '.id')

appFlowId=$(curl -s http://mgr-tenant-entitlements/entitlement-flows/$flowId | jq -r '.applicationFlows | .[].id')

Using application flow ID:
curl -s http://mgr-tenant-entitlements/application-flows/$appFlowId?includeStages=true | jq

### Get applications entitled for tenant
curl -s http://mgr-tenant-entitlements/entitlements/sul/applications -H "Authorization: Bearer $TOKEN" -H "x-okapi-tenant: sul" -H "x-okapi-token: $TOKEN"

### Get entitlements for tenant
curl -s http://mgr-tenant-entitlements/entitlements?query=tenantId=="$tenantUUID"

### Re-install entitlements/applications for tenant
curl -sX PUT --location "http://mgr-tenant-entitlements/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -H "x-okapi-token: $TOKEN" -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"app-platform-minimal-1.0.41\"]}"

curl -sX DELETE http://mgr-tenant-entitlements/entitlements -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"app-platform-minimal-1.0.41\"]}" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"

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
## Get a sidecar token
### Find out the 
vault login with the root token

vault kv get secret/folio/sul

TOKEN=$(curl -sX POST -d client_id="sidecar-module-access-client" -d client_secret="<value for sidecar-module-access-client>" -d grant_type=client_credentials http://keycloak-headless.folio-dev.svc.cluster.local:8080/realms/sul/protocol/openid-connect/token | jq -r  '.access_token')

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