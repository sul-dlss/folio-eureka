import argparse
import httpx
import json
import os

from pathlib import Path

parser = argparse.ArgumentParser(
                    prog="EurekaDeploymentFlow",
                    formatter_class=argparse.RawDescriptionHelpFormatter,
                    description="""Register applications, register modules, create tenant, create entitlements
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
                    FLOW_STAGES=true""",
                    epilog="-------")

parser.add_argument("filename", nargs="*", help="The application descriptor JSON file or files to process. If not provided, all JSON files in the namespace directory will be processed.")
parser.add_argument("-n", "--namespace", required=True, help="the Kubernetes namespace for the applications.")
parser.add_argument("-a", "--register_apps", action="store_true", default=False, help="register applications, uses MGR_APP_URL")
parser.add_argument("-d", "--delete_apps", action="store_true", default=False, help="delete applications (for upgrading flower release), uses MGR_APP_URL")
parser.add_argument("-m", "--register_modules", action="store_true", default=False, help="register modules for discovery, uses MGR_APP_URL")
parser.add_argument("-u", "--reregister_modules", action="store_true", default=False, help="re-register modules for discovery, uses MGR_APP_URL")
parser.add_argument("-t", "--create_tenant", action="store_true", default=False, help="create tenant, uses MGR_TENANTS_URL")
parser.add_argument("-e", "--entitle", action="store_true", default=False, help="entitle applications, uses MGR_ENTITLE_URL, ASYNC, REF_DATA, SAMPLE_DATA")
parser.add_argument("-f", "--flow_id", help="FlowId to get entitlement-flow state, uses FLOW_STAGES")

args = parser.parse_args()

def main():
    global token
    token = _token()
    mgr_app_url = os.getenv("MGR_APP_URL", "http://mgr-applications")
    mgr_tenants_url = os.getenv("MGR_TENANTS_URL", "http://mgr-tenants")
    mgr_entitle_url = os.getenv("MGR_ENTITLE_URL", "http://mgr-tenant-entitlements")
    files: list = []
    if args.filename:
        for file in args.filename:
            files.append(file)
    else:
        for file in Path(args.namespace).glob("*.json"):
            files.append(file)
    if args.create_tenant:
            print("Creating tenant")
            tenant_uuid = create_tenant(token, mgr_tenants_url)
            print(f"Created tenant sul, uuid: {tenant_uuid}")
    if args.entitle:
        app_ids: list = []
        for file in files:
            with open(file, "r") as fo:
                data = json.load(fo)
                app_ids.append(data["id"])

        print(f"Entitling {app_ids}")
        tenant_uuid = tenant_id(token, mgr_tenants_url)
        entitle_applications(token, app_ids, tenant_uuid, mgr_entitle_url)
    if args.flow_id:
        entitlement_flow(token, args.flow_id, mgr_entitle_url)
    for file in files:
        with open(file, "r") as fo:
            data = json.load(fo)
            app_id = data["id"]
            if args.register_apps:
                print(f"Register {app_id}")
                register_applications(token, data, mgr_app_url)
                registered_apps(token, mgr_app_url)
            if args.delete_apps:
                print(f"Delete {app_id}")
                delete_applications(token, app_id, mgr_app_url)
                registered_apps(token, mgr_app_url)
            if args.register_modules:
                print(f"Registering modules for {app_id}")
                for module in data["modules"]:
                    updated_module = module_discovery_object(module)
                    register_module(token, updated_module, mgr_app_url)
            if args.reregister_modules:
                print(f"Re-registering modules for {app_id}")
                for module in data["modules"]:
                    updated_module = module_discovery_object(module)
                    re_register_module(token, updated_module, mgr_app_url)


def register_applications(token, data, mgr_app_url):
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{mgr_app_url}/applications", 
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data=json.dumps(data)
            )
            print(response.text)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def registered_apps(token, mgr_app_url):
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.get(
                f"{mgr_app_url}/applications?limit=50", 
                headers={
                    "Authorization": f"Bearer {token}"
                }
            )
            print(response.text)
            apps = json.loads(response.text).get("applicationDescriptors")
            if len(apps) == 0:
              print("No applications are registered")
            else:
                for i in apps:
                    app_id = i["id"]
                    print(f"{app_id} is registered")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def delete_applications(token, app_id, mgr_app_url):
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.delete(
                f"{mgr_app_url}/applications/{app_id}", 
                headers={
                    "Authorization": f"Bearer {token}"
                }
            )
            print(response.text)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def module_discovery_object(module) -> dict:
    module_location = f"http://{module['name']}:8082"
    module["location"] = module_location
    module.pop("url", None) #removes url key from module dict
    return module


def register_module(token, module, mgr_app_url):
    module_id = f"{module['name']}-{module['version']}"
    print(f"POSTING to /modules/{module_id}/discovery")
    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.post(
                f"{mgr_app_url}/modules/{module_id}/discovery",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data=json.dumps(module)
            )
            print(response.text)
            response.raise_for_status()
        except httpx.TimeoutException:
            print("Request timed out!")
            print("Retrying with a PUT")
            re_register_module(token, module, mgr_app_url)
        except httpx.HTTPStatusError as exc:
            print(exc)


def re_register_module(token, module, mgr_app_url):
    module_id = f"{module['name']}-{module['version']}"
    print(f"PUTTING to /modules/{module_id}/discovery")
    print(module)
    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.put(
                f"{mgr_app_url}/modules/{module_id}/discovery",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data=json.dumps(module)
            )
            print(response.text)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                token = _token()
                re_register_module(token, module, mgr_app_url)


def create_tenant(token, mgr_tenants_url) -> str:
    data = {
        "name": "sul",
        "description": "Stanford University Libraries"
    }
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{mgr_tenants_url}/tenants",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data=json.dumps(data)
            )
            print(response.text)
            tenant_uuid = json.loads(response.text).get("id")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)
    return tenant_uuid


def tenant_id(token, mgr_tenants_url) -> str:
    with httpx.Client() as client:
        try:
            response = client.get(
                f"{mgr_tenants_url}/tenants?query=name==sul",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                }
            )
            print(response.text)
            tenant_uuid = json.loads(response.text).get("id")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)
    return tenant_uuid


def entitle_applications(token, app_ids, tenant_uuid, mgr_entitle_url):
    data = {
        "tenantId": tenant_uuid,
        "applications": app_ids
    }
    async_entitlement: bool = json.dumps(os.getenv("ASYNC", True))
    load_ref: bool = json.dumps(os.getenv("REF_DATA", True))
    load_sample: bool = json.dumps(os.getenv("SAMPLE_DATA", False))
    print(f"Entitlement params: async={async_entitlement}&tenantParameters=loadReference={load_ref},loadSample={load_sample}")
    with httpx.Client(timeout=60.0) as client:
        try:
            response = client.post(
                f"{mgr_entitle_url}/entitlements?async={async_entitlement}&tenantParameters=loadReference={load_ref},loadSample={load_sample}",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-token": token
                },
                data=json.dumps(data)
            )
            print(response.text)
            flow_id = json.loads(response.text).get("flowId")
            print(f"Flow ID: {flow_id}")
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def entitlement_flow(flow_id, mgr_entitle_url):
    include_stages: bool = json.dumps(os.getenv("FLOW_STAGES", True))
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.get(f"{mgr_entitle_url}/entitlement-flows/{flow_id}?includeStages={include_stages}")
            print(response.text)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def _token():
    kc_url = os.getenv("KC_URL", "http://keycloak:8080")
    kc_admin_client_id = os.getenv("KC_ADMIN_CLIENT_ID", "folio-backend-admin-client")
    kc_admin_client_secret = os.getenv("KC_ADMIN_CLIENT_SECRET")
    print(f"fetching new token from {kc_url}")
    response = httpx.post(f"{kc_url}/realms/master/protocol/openid-connect/token",
        data={
            "client_id": kc_admin_client_id,
            "grant_type": "client_credentials",
            "client_secret": kc_admin_client_secret,
        }
    )

    print(response.text)
    token = response.json()["access_token"]
    return token


if __name__ == "__main__":
    main()
