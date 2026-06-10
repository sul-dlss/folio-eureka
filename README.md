# folio-eureka

## Version Management
To get the versions of the modules for Eureka, select the appropriate flower release tag from [folio-org/platform-lsp](https://github.com/folio-org/platform-lsp). Find the app versions from the install-applications.json file and then select the versioned tag from the corresponding application name folio-org repository. Update the deployment specification versions of folio-module-sidecar, keycloak, kong, mgr-applications, mgr-tenants, and mgr-tenant-entitlements based on the versions in platform-lsp/management-modules.json file for the flower release tag.

## Secrets
Add to [Vault](https://vault.sul.stanford.edu/) key-value pairs for db-credentials, eureka-common, eureka-edge, folio-eureka, folio-vault, kafka-credentials, keycloak-credentials, kong-credentials, mod-pubsub-system-user, opensearch-credentials, and s3-credentials.
Create k8s VaultStaticSecrets by applying the secrets.yaml file:
```
kubectl -n ${namespace} apply -f ${namespace}/infrastructure/secrets.yaml
```

## Install Infrastructure in the cluster namespace (Kong, Keycloak, Elasticsearch, Postfix)
```
for I in `ls ${namespace}/infrastructure/*_application.yaml`; do kubectl -n ${namespace} apply -f $I; done
```

### keycloak helm install commands if there are issues with the ArgoCD app
```
helm upgrade --install -n ${namespace} --version v24.7.4 keycloak bitnami/keycloak -f ${namespace}/infrastructure/keycloak.yaml
```

## Install Vault in the cluster namespace if there are issues with ArgoCD app
```
helm -n ${namespace} install --version v0.32.0 -f ${namespace}/infrastructure/vault.yaml vault hashicorp/vault
```
Initialize vault with secrets by first exec'ing into vault-0 pod:
```
vault operator init -key-shares=1 -key-threshold=1
vault operator unseal <Unseal Key 1>
vault login <Initial Root Token>
vault token create -id=<root id>
vault secrets enable -path=secret -version=2 kv
vault kv put secret/folio/master folio-backend-admin-client=<password> mgr-applications=<rand 32 char> mgr-tenant-entitlements=<rand 32 char> mgr-tenants=<rand 32 char>
```

## Module Deployment Specifications
Create the deployment specifications for the FOLIO backend and edge modules using the create_module_values.py script. Create the ArgoCD applications using the create_applications.py script. The default helm repo alias in the script is "folio-helm-v2-dlss", which should be set to https://sul-dlss.github.io/folio-helm-v2 in your local environment. The scripts will process all JSON files in the namespace directory if no filename is passed as first argument. Use the `-p, --prod_replicasets` flag when creating deployment specs and applications for folio-test and folio-prod namespaces. Commit all files and open a pull request.
```
python ./create_module_values.py -n ${namespace}
python ./create_applications.py -n ${namespace}
```

### Deploy backend and edge modules for each application
Use the `--no_generate` flag to apply ArgoCD applications as defined in the main branch of the repository. If deploying to folio-test or folio-prod namespaces, deploy modules without prod-level replicasets before entitling applications by excluding the `--no_generate` flag.
```
python ./create_applications.py -n $namespace -x apply
```
After creating applications, go to ArgoCD and sync apps (the applications do not auto-sync when applied).

## Deploy mgr-* modules
```
for M in `ls ${namespace}/modules/mgr-*/application.yaml`; do kubectl -n ${namespace} apply -f $M; done
```

## Deploy the folio-eureka-pod
Exec into the folio-eureka-pod once it is applied and do the rest of the process from there.
```
kubectl -n ${namespace} apply -f folio-eureka-pod.yaml
```

## Get a token from the master realm
```
TOKEN=$(curl -sX POST -d client_id="folio-backend-admin-client" -d client_secret="$KC_ADMIN_CLIENT_SECRET" -d grant_type="client_credentials" "$KC_URL/realms/master/protocol/openid-connect/token" | jq -r '.access_token')
```

### Expand the access token lifespan
```
curl -sX PUT "$KC_URL/admin/realms/master" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d'{"accessTokenLifespan": "3600", "ssoSessionIdleTimeout": "3600"}'
```

## Eureka Deployment and Entitlement Flow
In the folio-eureka-pod, run the eureka_deployment_flow.py script:
```
python eureka_deployment_flow.py -h

usage: EurekaDeploymentFlow [-h] -n NAMESPACE [-a] [-d] [-m] [-u] [-t] [-e] [-f FLOW_ID] [filename ...]

Register applications, register modules, create tenant, create entitlements
                    Default env vars:
                    MGR_APP_URL=http://mgr-applications
                    MGR_TENANTS_URL=http://mgr-tenants
                    MGR_ENTITLE_URL=http://mgr-tenant-entitlements
                    KC_URL=http://keycloak:8080
                    KC_ADMIN_CLIENT_ID=folio-backend-admin-client
                    KC_ADMIN_CLIENT_SECRET=<from folio-eureka k8s secret>
                    ASYNC=true
                    REF_DATA=true
                    SAMPLE_DATA=false
                    FLOW_STAGES=true

positional arguments:
  filename              The application descriptor JSON file or files to process. If not provided, all JSON files in the
                        namespace directory will be processed.

options:
  -h, --help            show this help message and exit
  -n NAMESPACE, --namespace NAMESPACE
                        the Kubernetes namespace for the applications.
  -a, --register_apps   register applications, uses MGR_APP_URL
  -d, --delete_apps     delete applications (for upgrading flower release), uses MGR_APP_URL
  -m, --register_modules
                        register modules for discovery, uses MGR_APP_URL
  -u, --reregister_modules
                        re-register modules for discovery, uses MGR_APP_URL
  -t, --create_tenant   create tenant, uses MGR_TENANTS_URL
  -e, --entitle         entitle applications, uses MGR_ENTITLE_URL, ASYNC, REF_DATA, SAMPLE_DATA
  -f FLOW_ID, --flow_id FLOW_ID
                        FlowId to get entitlement-flow state, uses FLOW_STAGES
```
### Register all the applications
```
python eureka_deployment_flow.py -n ${namespace} -a
```

Delete any extra applications as needed, e.g.:
```
python eureka_deployment_flow.py ${namespace}/application-descriptor-fqm.json ${namespace}/application-descriptor-linked-data.json -n ${namespace} -d
```

### Register all the modules for discovery
```
python eureka_deployment_flow.py -n ${namespace} -m
```

### Create the tenant
```
python eureka_deployment_flow.py -n ${namespace} -t
```

### Create Entitlements
#### Create entitlements for app-platform-minimal (Make sure all modules are up and running, may need to do multiple times due to timeouts)
```
python eureka_deployment_flow.py ${namespace}/application-descriptor-minimal.json -n ${namespace} -e
```

### Create entitlements for the rest of the applications
```
python eureka_deployment_flow.py ${namespace}/application-descriptor-acquisitions.json ${namespace}/application-descriptor-bulk-edit.json ${namespace}/application-descriptor-complete.json ${namespace}/application-descriptor-edge.json ${namespace}/application-descriptor-erm-usage.json ${namespace}/application-descriptor-fqm.json ${namespace}/application-descriptor-linked-data.json ${namespace}/application-descriptor-marc-migrations.json ${namespace}/application-descriptor-reading-room.json ${namespace}/application-descriptor-reporting.json ${namespace}/application-descriptor-z3950.json -n ${namespace} -e
```

### Monitor entitlements process
Use flow_id printed from entitlements step
```
python eureka_deployment_flow.py -n ${namespace} -f ${flow_id}
```
## Create sul-application redirect URIs in Keycloak
**Use curls or the UI**
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

## Bootstrap the Admin User
Using the [sidecar-module-access-client](#sidecar-client-login)

**Add the sidecar-module-access-client secret SIDECAR_SECRET to the folio-eureka secret, sync the VaultStaticSecret, restart the folio-eureka-pod and continue.**
From the folio-eureka-pod (has env vars needed), run:
```
python bootstrap_admin_user.py -c -e $LIBSYS_EMAIL -f Libsys -l Admin -p $LIBSYS_PASSWORD -u $LIBSYS_USER
```

## Curls for Eureka Deployment and Entitlement Flow
### Register the applications
Get the application descriptors for app-platform-minimal from the repository [folio-org/app-platform-minimal](https://github.com/folio-org/app-platform-minimal) and select the version tag 1.0.43 for Ramsons R2-2024-csp-8. Copy the application-descriptor.json file from there and save as $namespace/application-descriptor-minimal.json.

Get the application descriptors for app-platform-complete from the repository [folio-org/app-platform-complete](https://github.com/folio-org/app-platform-complete) and select the version tag 1.1.89 for Ramsons R2-2024-csp-8. Copy the application-descriptor.json file from there and save as $namespace/application-descriptor-complete.json. 

Make sure the tag value for app-platform-minimal matches the version saved to application-descriptor-minimal.json (listed in the depencies array of the app-platform-complete descriptor).

Get the application descriptors for other required apps and repeat the process:
```
curl -X POST --location "$KONG_URL/applications" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -d@"$APP_FILE"
```

Check the applications posted by exec'ing into the folio-eureka-pod shell and doing:
```
curl "$KONG_URL/applications"
```

Delete any extra applications as needed, e.g.:
```
curl -X DELETE --location "$KONG_URL/applications/$APP_ID" -H "Authorization: Bearer $TOKEN"
```
### Register the modules for discovery
```
APP_ID=$APP_ID python3 ./discovery-modules.py
```

### Create the tenant
```
curl -X POST --location "$KONG_URL/tenants" --header "Authorization: Bearer $TOKEN" --header 'Content-Type: application/json' --data '{"name": "sul", "description": "Stanford University Libraries"}'
```

### Get the tenantUUID
```
tenantUUID=$(curl -sX GET "$KONG_URL/tenants" | jq -r '.tenants | .[] | .id')
```

### Create entitlements for app-platform-complete (Make sure all modules are up and running, may need to repeat due to timeouts)
Use the [folio-backend-admin-client](#get-a-token-from-the-master-realm) id 
Set the APP_IDS to all except app-platform-minimal, e.g
```
APP_IDS="\"app-acquisitions-1.0.25\", \"app-bulk-edit-1.0.8\", \"app-platform-complete-2.2.13\", 
\"app-edge-complete-3.0.0\", \"app-erm-usage-2.0.4\", \"app-fqm-1.0.14\", \"app-linked-data-1.1.6\", \"app-marc-migrations-2.0.4\", \"app-reading-room-2.0.2\", \"app-reporting-1.4.0\", \"app-z3950-1.0.1\""
```
POST the entitlements
```
curl -X POST --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [\"$APP_IDS\"]}"
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
### Delete entitlements
```
curl -sX DELETE "$KONG_URL/entitlements" -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [$APP_IDS]}" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
```

### Reinstall a single module
```
curl -X POST --location "$KONG_URL/reinstall/modules?async=true&tenantParameters=loadReference=true,loadSample=false"  -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\": \"$tenantUUID\", \"applicationId\": \"$APP_ID\", \"modules\": [$MODULE_IDS]}"
```
### Reinstall many modules (up to 25 per API constraint)
```
curl -sX POST "http://mgr-tenant-entitlements/reinstall/modules?tenantParameters=loadReference=true,loadSampe=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" -d@reinstall.json
```

reinstall.json:
```
{
  "tenantId": "2d4c4f01-d4f0-437c-ab1c-a9fe19fd4c15",
  "applicationId": "app-platform-complete-2.2.13",
  "modules": [
    "mod-quick-marc-7.0.0",
    "mod-source-record-manager-3.10.9",
    "mod-di-converter-storage-2.4.2",
    "mod-source-record-storage-5.10.13",
    "mod-data-import-3.3.5",
    "mod-copycat-1.8.1"
  ]
}
```


### Commands for each step of the admin user-creation process
#### Create Admin User
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

#### Create User credentials
```
curl -X POST --location "$KONG_URL/authn/credentials" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "username": "eureka_admin",
    "userId": "<userId>",
    "password": "SecretPassword"
}'
```
#### Create Admin Role
```
curl -X POST --location "$KONG_URL/roles" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' --data '{
    "name": "adminRole",
    "description": "Admin role"
}'
```
```
adminRoleId=$(curl -s --location "$KONG_URL/roles?limit=500" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' | jq -r '.roles[] | select(.name == "adminRole") | .id')
```
#### Get all of the capabilities
```
curl -s --location "$KONG_URL/capabilities?limit=3000" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' > json/all-capabilities.json
curl -s --location "$KONG_URL/capabilities?limit=3000&offset=3000" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' >> json/all-capabilities.json
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

#### Assign Capabilities to Role
```
curl -X POST --location "$KONG_URL/roles/capabilities" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' -d@json/all-capability-ids.json
```
##### Check the role capabilities
```
curl -s --location "$KONG_URL/roles/$adminRoleId/capabilities?limit=5000" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul'
```

#### Add Admin Role to Admin User
```
curl -X POST --location "$KONG_URL/roles/users" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H 'x-okapi-tenant: sul' -d "{ \"userId\": \"<userId from Keycloak Attributes>\", \"roleIds\": [\"$adminRoleId\"]}"
```

## Sidecar Client Login
### Get the sidecar client vault secret from secret/folio/sul and set the sidecar secret as SIDECAR_SECRET
```
export SIDECAR_SECRET=$(kubectl -n $namespace exec -it vault-0 -- vault kv get -format=json secret/folio/sul | jq -jrc '.data.data."sidecar-module-access-client"')
```

### Get the sidecar token from the tenant (sul) keycloak realm
```
TOKEN=$(curl -sX POST -d client_id="sidecar-module-access-client" -d client_secret="$SIDECAR_SECRET" -d grant_type=client_credentials "$KC_URL/realms/sul/protocol/openid-connect/token" | jq -r  '.access_token')
```

## Notes
 - All modules must have all possible "SYSTEM_USER_ENABLED" vars set to false. This is handled in the `create_module_values.py` script by setting: `{"name": "FOLIO_SYSTEM_USER_ENABLED", "value": "false"}, {"name": "SYSTEM_USER_CREATED", "value": "false"}, {"name": "SYSTEM_USER_ENABLED", "value": "false"}`

## Build Stripes for Eureka
Follow the instructions on the [sul-dlss/folio-platform-lsp wiki page](https://github.com/sul-dlss/folio-platform-lsp/wiki)

## Upgrading to a new Flower Release
1. Fetch and save new application descriptors.
1. Update versions of mgr-apps, sidecar, kong and keycloak in yaml files.
1. Add any new env vars or configs as needed and specified in release notes for new modules.
1. Run the create_module_values.py script to update the override.yaml files with the new image tags. And create any new module folders for new apps.
1. Run the create_applications.py script with `-x dry-run` for each application descriptor to create ArgoCD application specs.
1. Commit all files to a flower release branch and open a pull request to merge to main.
1. After the PR is merged, upgrade modules by syncing in ArgoCD. ArgoCD should show which are now out of sync. For any new modules, an application will need to be created first using `kubectl -n ${namespace} apply -f path/to/module/application.yaml`.
1. Check the logs for the mgr modules to see that they upgraded themselves (or do we need to do something to upgrade them?).
1. Delete existing entitlements and applications in order to upgrade. The database schema keeps track of versions so any database migrations that need to happen for module upgrades will happen.
 - Get app IDs that were entitled:
    ```
    TOKEN=$(curl -sX POST -d client_id="folio-backend-admin-client" -d client_secret="$KC_ADMIN_CLIENT_SECRET" -d grant_type="client_credentials" "$KC_URL/realms/master/protocol/openid-connect/token" | jq -r '.access_token')
    curl -sX GET "$KONG_URL/entitlements" -H "Authorization: Bearer $TOKEN"
    ```
 - Delete the entitlements for those apps
    ```
    tenantUUID=$(curl -sX GET "$KONG_URL/tenants" | jq -r '.tenants | .[] | .id')
    APP_IDS=$(curl -sX GET "$KONG_URL/entitlements" -H "Authorization: Bearer $TOKEN" | jq -jr '.entitlements[] | "\"" + .applicationId + "\"" + "," ' | sed 's/.$//')
    curl -sX DELETE "$KONG_URL/entitlements" -d "{\"tenantId\":\"$tenantUUID\", \"applications\": [$APP_IDS]}" -H 'Content-Type: application/json' -H "Authorization: Bearer $TOKEN"
    ```
  - Delete the applications. Copy/paste application ID into $ID, e.g.:
    ```
    curl -sX DELETE "$KONG_URL/applications/$ID" -H "Authorization: Bearer $TOKEN"
1. [Post the new applications](#post-the-applications).
1. [Register the applications](#register-the-applications). You will probably need to use the update script if there are modules in the descriptor file that are the same as the currently registered module version. 
1. [Create entitlements](#create-entitlements) for the new applications.
    ```
    APP_IDS="\"app-acquisitions-1.0.25\", \"app-bulk-edit-1.0.8\", \"app-platform-complete-2.2.13\", \"app-edge-complete-3.0.0\", \"app-erm-usage-2.0.4\", \"app-fqm-1.0.14\", \"app-linked-data-1.1.6\", \"app-marc-migrations-2.0.4\", \"app-platform-minimal-2.0.38\", \"app-reading-room-2.0.2\", \"app-reporting-1.4.0\", \"app-z3950-1.0.1\""

    curl -X POST --location "$KONG_URL/entitlements?async=true&tenantParameters=loadReference=true,loadSample=false" -H "Authorization: Bearer $TOKEN" -H 'Content-Type: application/json' -H "x-okapi-token: $TOKEN" --data "{\"tenantId\":\"$tenantUUID\", \"applications\": [$APP_IDS]}"
    ```
1. Run the bootstrap_admin_user.py script without any flags to add all the capabilities to the adminRole.

## Elasticsearch Indexing
Use the rake tasks in sul-dlss/folio-tasks to index inventory data. [Inventory Indexing wiki page](https://github.com/sul-dlss/folio-tasks/wiki#inventory-indexing-using-mod-search-api)
