# folio-eureka

## Version Management
To get the versions of the modules for Eureka, select the appropriate flower release tag from [folio-org/platform-lsp](https://github.com/folio-org/platform-lsp). Find the app versions from the install-applications.json file and then select the versioned tag from the corresponding application name folio-org repository.

## Secrets
Add to [Vault](https://vault.sul.stanford.edu/) key-value pairs for db-credentials, eureka-common, eureka-edge, kafka-credentials, keycloak-credentials, kong-credentials, opensearch-credentials, and s3-credentials.
Create k8s VaultStaticSecrets by applying the secrets.yaml file:
```
envsubst < secrets.yaml | kubectl -n ${namespace} apply -f -
```

## Install Infrastructire in the cluster namespace (Kong, Keycloak, Elasticsearch, Postfix)
```
for I in `ls ${namespace}/infrastructure/*_application.yaml`; do kubectl -n ${namespace} apply -f $I; done
```

### keycloak helm install commands if there are issues with the ArgoCD app
```
helm upgrade --install -n folio-test --version v24.7.4 keycloak bitnami/keycloak -f folio-test/infrastructure/keycloak.yaml
```

## Install Vault in the cluster namespace
```
helm -n ${namespace} install -f folio-test/infrastructure/vault.yaml vault hashicorp/vault
```
Then create the folio-backend-admin-client secret in cluster namespace vault under `secret/folio/master`

## Deploy mgr-* modules
```
for M in `ls ${namespace}/modules/mgr-*/application.yaml`; do kubectl -n ${namespace} apply -f $M; done
```


## Get a token from the master realm
```
TOKEN=$(curl -sX POST -d client_id="folio-backend-admin-client" -d client_secret="$KC_ADMIN_CLIENT_SECRET" -d grant_type="client_credentials" "$KC_URL/realms/master/protocol/openid-connect/token" | jq -r '.access_token')
```

### Expand the access token lifespan
```
curl -sX PUT "$KC_URL/admin/realms/master" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d'{"accessTokenLifespan": "3600", "ssoSessionIdleTimeout": "3600"}'
```

## Post the applications
Get the application descriptors for app-platform-minimal from the repository [folio-org/app-platform-minimal](https://github.com/folio-org/app-platform-minimal) and select the version tag 1.0.43 for Ramsons R2-2024-csp-8. Copy the application-descriptor.json file from there and save as $namespace/application-descriptor-minimal.json.

Get the application descriptors for app-platform-complete from the repository [folio-org/app-platform-complete](https://github.com/folio-org/app-platform-complete) and select the version tag 1.1.89 for Ramsons R2-2024-csp-8. Copy the application-descriptor.json file from there and save as $namespace/application-descriptor-complete.json. 

Make sure the tag value for app-platform-minimal matches the version saved to application-descriptor-minimal.json (listed in the depencies array of the app-platform-complete descriptor).

Get the application descriptors for other required apps and repeat the process:
```
curl -X POST --location "$KONG_URL/applications" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d@"$APP_FILE"
```

Check the applications posted by logging into the folio-k8s-pod shell and doing:
```
curl "$KONG_URL/applications"
```

Delete any extra applications as needed, e.g.:
```
curl -X DELETE --location "$KONG_URL/applications/$APP_ID" -H "Authorization: Bearer $TOKEN"
```

## Deploy backend modules for each application
```
python ./create_module_values.py $APP_FILE -n $namespace
python ./create_applications.py $APP_FILE -n $namespace -x apply
```

## Register the applications
```
APP_ID=$APP_ID python3 ./discovery-modules.py
```

## Create the tenant
```
curl -X POST --location "$KONG_URL/tenants" --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' --data '{"name": "sul", "description": "Stanford University Libraries"}'
```

### Get the tenantUUID
```
tenantUUID=$(curl -sX GET "$KONG_URL/tenants" | jq -r '.tenants | .[] | .id')
```

## Check or create sul-application redirect URIs in Keycloak
### 1. Get Keycloak client UUID for the tenant application
```
CLIENT_UUID=$(curl -X GET  "$KC_URL/admin/realms/$TENANT_ID/clients?clientId=$TENANT_ID-application"   -H "Authorization: Bearer $TOKEN"   -H 'Content-Type: application/json' | jq -r '.[].id')
```
### 2. Update client to set tenant UI URLs and origins
```
curl -X PUT \
  "$KC_URL/admin/realms/$TENANT_ID/clients/$CLIENT_UUID" \
  -H "Authorization: Bearer $TOKEN" \
  -H 'Content-Type: application/json' \
  --data "{
    \"rootUrl\": \"https://${namespace}.stanford.edu\",
    \"baseUrl\": \"https://${namespace}.stanford.edu\",
    \"adminUrl\": \"https://${namespace}.stanford.edu\",
    \"redirectUris\": [\"https://${namespace}.stanford.edu/*\", \"http://localhost:3000/*\"],
    \"webOrigins\": [\"/*\"],
    \"authorizationServicesEnabled\": true,
    \"serviceAccountsEnabled\": true,
    \"attributes\": {\"post.logout.redirect.uris\": \"/*##https://${namespace}.stanford.edu/*\"}
  }"
```

## Create Entitlements

### Create entitlements for app-platform-minimal (Make sure all modules are up and running, may need to do multiple times due to timeouts)
```
curl -X POST --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_ID\"]}"
```

### Create keycloak system users - mod-users-keycloak and mod-login-keycloak
#### After entitling app-platform-minimal a keycloak user in the sul realm and a vault secret is created for mod-roles-keycloak only.

Create system users for mod-users-keycloak and mod-login-keycloak, example using the [sidecar-module-access-client](#sidecar-client-login)
```
curl -X POST --location "$KONG_URL/users-keycloak/users" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data-raw '{
    "username": "mod-users-keycloak",
    "active": true,
    "personal": {
        "lastName": "System"
    }
}'
```
Add a password to vault
```
vault kv patch secret/folio/sul mod-users-keycloak="<random 32 characters>"
```
Add the password to keycloak
```
curl -X POST --location "$KONG_URL/authn/credentials" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "username": "mod-users-keycloak",
    "userId": "<userId from users-keycloak/users POST response>",
    "password": "<random 32 character password from vault: secret/folio/sul>"
}'
```

Restart the mod-*-keycloak modules.

### Create entitlements for app-platform-complete (Make sure all modules are up and running, may need to repeat due to timeouts)
Use the [folio-backend-admin-client](#get-a-token-from-the-master-realm) id 
```
curl -X POST --location "$KONG_URL/entitlements?async=true&ignoreErrors=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_ID\"]}"
```
mod-entities-links system user is failing the entitlements process due to its user missing from keycloak. However, we don't migrate users to keycloak until after the entitlements process is completed. We will skip mod-entities-links by passing the ignoreErrors=true query parameter so that the rollback operation (when ignoreErrors=false, the default) does not uninstall modules, remove   routes, and remove Keycloak resources.
```
curl -X POST --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_ID\"]}"
```

### Monitor entitlements process
Using flowId (<flow-id> from POST respone)
```
flowId=$(curl -s "$KONG_URL/entitlement-flows/<flow-id>" | jq -r '.id')
```
```
appFlowId=$(curl -s "$KONG_URL/entitlement-flows/$flowId" | jq -r '.applicationFlows | .[].id')
```
Using application flow ID:
```
curl -s "$KONG_URL/application-flows/$appFlowId?includeStages=true" | jq
```

### Get applications entitled for tenant
```
curl -s "$KONG_URL/entitlements/sul/applications" -H "Authorization: Bearer $TOKEN" -H "x-okapi-tenant: sul" -H "x-okapi-token: $TOKEN"
```

### Get entitlements for tenant
```
curl -s "$KONG_URL/entitlements?includeModules=true&query=tenantId==$tenantUUID"
```

### Re-install entitlements/applications for tenant
```
curl -sX PUT --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN" -H "x-okapi-token: $TOKEN" -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_ID\"]}"
```
```
    curl -sX DELETE "$KONG_URL/entitlements" -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_ID\"]}" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

## Create the Admin User
Using the [sidecar-module-access-client](#sidecar-client-login)
```
curl -X POST --location "$KONG_URL/users-keycloak/users" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data-raw '{
    "username": "eureka_admin",
    "active": true,
    "personal": {
        "firstName": "Admin",
        "lastName": "Eureka",
        "email": "sul-unicorn-devs@lists.stanford.edu"
    }
}'
```

### Create User credentials
```
curl -X POST --location "$KONG_URL/authn/credentials" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "username": "eureka_admin",
    "userId": "<userId>",
    "password": "SecretPassword"
}'
```
### Create Admin Role
```
curl -X POST --location "$KONG_URL/roles" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "name": "adminRole",
    "description": "Admin role"
}'
```
```
adminRoleId=$(curl -s --location "$KONG_URL/roles?limit=500" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' | jq -r '.roles[] | select(.name == "adminRole") | .id')
```
### Get all of the capabilities
```
curl -s --location "$KONG_URL/capabilities?limit=3000" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' > json/all-capabilities.json
```
```
cat json/all-capabilities.json | jq '.capabilities[].id' > json/all-capability-ids.json
```
Construct a json file:
```
"{
    "roleId": "$adminRoleId",
    "capabilityIds": [
        \"Eureka-Capability-01-UUID\",
        \"Eureka-Capability-02-UUID\",
        \"Eureka-Capability-03-UUID\"
    ]
}"
```

### Assign Capabilities to Role
```
curl -X POST --location "$KONG_URL/roles/capabilities" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' -d@json/all-capability-ids.json
```
#### Check the role capabilities
```
curl -s --location "$KONG_URL/roles/$adminRoleId/capabilities?limit=5000" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul'
```

### Add Admin Role to Admin User
```
curl -X POST --location "$KONG_URL/roles/users" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' -d "{ \"userId\": \"<userId from Keycloak Attributes>\", \"roleIds\": [\"$adminRoleId\"]}"
```

## Sidecar Client Login
### Get the sidecar client vault secret from secret/folio/sul and set the sidecar secret as SIDECAR_SECRET
```
export SIDECAR_SECRET=$(kubectl -n $namespace exec -it vault-0 -- vault kv get secret/folio/sul | grep sidecar-module-access-client | awk '{print $2}')
```

### Get the sidecar token from the tenant (sul) keycloak realm
```
TOKEN=$(curl -sX POST -d client_id="sidecar-module-access-client" -d client_secret="$SIDECAR_SECRET" -d grant_type=client_credentials "$KC_URL/realms/sul/protocol/openid-connect/token" | jq -r  '.access_token')
```

## Notes
 - All modules must have all possible "SYSTEM_USER_ENABLED" vars set to false. This is handled in the `create_module_values.py` script by setting: `{"name": "FOLIO_SYSTEM_USER_ENABLED", "value": "false"}, {"name": "SYSTEM_USER_CREATED", "value": "false"}, {"name": "SYSTEM_USER_ENABLED", "value": "false"}`
 - In `platform-complete` the `stripes.config.js`, `module.exports["config"]["hasAllPerms"]` setting must be "true" in order for the user to be able to see the app settings.


## Upgrading to a new Flower Release
1. Fetch and save new application descriptors.
1. Update versions of mgr-apps, sidecar, kong and keycloak in yaml files.
1. Add any new env vars or configs as needed and specified in release notes for new modules.
1. Run the create_module_values.py script to update the override.yaml files with the new image tags. And create any new module folders for new apps.
1. Run the create_applications.py script with `-x dry-run` for each application descriptor to create ArgoCD application specs.
1. Commit all files to a flower release branch and open a pull request to merge to main.
1. After the PR is merged, upgrade modules by syncing in ArgoCD. ArgoCD should show which are now out of sync. For any new modules, an application will need to be created first using `kubectl -n ${namespace} apply -f path/to/module/application.yaml`.
1. Check the logs for the mgr modules to see that they upgraded themselves (or do we need to do something to upgrade them?).
1. [Post the new applications](#post-the-applications).
1. [Register the applications](#register-the-applications). You will probably need to use the update script if there are modules in the descriptor file that are the same as the currently registered module version. 
1. Upgrade existing applications:
    ```
    APP_IDS="\"app-platform-minimal-2.0.38\", \"app-platform-complete-2.2.13\""
    ```
    ```
    curl -X PUT --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [$APP_IDS]}"
    ```
1. [Create entitlements](#create-entitlements) for the new applications.
    ```
    APP_IDS="\"app-acquisitions-1.0.25\", \"app-bulk-edit-1.0.8\", \"app-erm-usage-2.0.4\", "app-fqm-1.0.14\", "app-linked-data-1.1.6\", "app-marc-migrations-2.0.4\", "app-reading-room-2.0.2\""
    ```
    ```
    curl -X POST --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [$APP_IDS]}"
    ```
1. [Get all of the capabilities](#get-all-of-the-capabilities)
1. [Assign capabilities to the adminRole](#assign-capabilities-to-role) using PUT instead of POST.
