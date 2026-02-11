import argparse
import httpx
import json
import os
import sys


parser = argparse.ArgumentParser(
                    prog="BootstrapAdminRole",
                    description="Bootstrap admin role and user for FOLIO Eureka platform",
                    epilog="-------")

parser.add_argument("-c", "--create_user", required=False, action="store_true", default=False, help="create user, else just add new capabilities to admin role")
parser.add_argument("-e", "--email", required="--create_user" or "-c" in sys.argv, help="admin user email address, required if -c is used")
parser.add_argument("-f", "--first_name", required="--create_user" or "-c" in sys.argv, help="admin user first name, required if -c is used")
parser.add_argument("-l", "--last_name", required="--create_user" or "-c" in sys.argv, help="admin user last name, required if -c is used")
parser.add_argument("-p", "--password", required="--create_user" or "-c" in sys.argv, help="password for admin user, required if -c is used")
parser.add_argument("-u", "--username", required="--create_user" or "-c" in sys.argv, help="username for admin user, required if -c is used")

args = parser.parse_args()


def main():
    global token
    token = _token()
    create_user: bool = args.create_user
    if create_user:
        print("Creating admin user")
        user_id = create_user(token, args)
        print("Creating admin user credentials")
        create_credentials(token, user_id, args)
        print("Creating adminRole")
        create_role(token)
        role_id = admin_role_id(token)
        capabilities = all_capabilities(token)
        print("Adding all capabilities to adminRole")
        assign_capabilities(token, role_id, capabilities)
        print("Assigning admin user to adminRole")
        assign_role(token, user_id, role_id)
    else:
        print("Adding all capabilities to adminRole")
        role_id = admin_role_id(token)
        capabilities = all_capabilities(token)


def create_user(token, args):
    data = { "username": args.username,
             "active": True,
             "personal": {
                "firstName": args.first_name,
                "lastName": args.last_name,
                "email": args.email
              }
            }
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{kong_url}/users-keycloak/users", 
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            print(response)
            response = json.loads(response.text)
            user_id = response.get("id", None)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return user_id


def create_credentials(token, user_id, args):
    data = { "username": args.username,
             "userId": user_id,
             "password": args.password
           }
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{kong_url}/authn/credentials", 
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def create_role(token):
    data = { "name": "adminRole",
             "description": "Admin role"
           }
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{kong_url}/roles", 
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def admin_role_id(token):
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.get(
                f"{kong_url}/roles?query=name==\"adminRole\"",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                }
            )
            response = json.loads(response.text)
            role_id = response["roles"][0].get("id", None)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return role_id


def all_capabilities(token) -> list:
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    capabilities: list = []
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.get(
                f"{kong_url}/capabilities?limit=1",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                }
            )
            response = json.loads(response.text)
            total_recs = response["totalRecords"]
            rec_range = chunks(0, total_recs, 500)
            for range in rec_range:
                start, _ = range
                with httpx.Client(timeout=20.0) as client:
                    try:
                        response = client.get(
                            f"{kong_url}/capabilities?limit=500&offset={start}",
                            headers={
                                "content-type": "application/json",
                                "Authorization": f"Bearer {token}",
                                "x-okapi-tenant": "sul"
                            }
                        )
                        response = json.loads(response.text)
                        for i in response["capabilities"]:
                            capabilities.append(i["id"])
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        print(exc)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return capabilities
    

def assign_capabilities(token, role_id, capabilities):
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            data = {
                "roleId": role_id,
                "capabilityIds": capabilities
            }
            response = client.post(
                f"{kong_url}/roles/capablities",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            response.raise_for_status()
            if response.status_code != httpx.codes.OK:
                data = {capabilities}
                response = client.put(
                f"{kong_url}/roles/{role_id}/capablities",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def assign_role(token, user_id, role_id):
    data = {
        "userId": user_id,
        "roleIds": [role_id]
    }
    kong_url = os.getenv("KONG_URL", "http://kong:8001")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{kong_url}/roles/users",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def chunks(start, stop, step) -> list:
    return [(i, min(i + step - 1, stop)) for i in range(start, stop + 1, step)]


def _token():
    global token
    kc_url = os.getenv("KC_URL", "http://keycloak:8080")
    kc_client_id = "sidecar-module-access-client"
    kc_client_secret = os.popen(f"kubectl exec -it vault-0 -- vault kv get -format=json secret/folio/sul | jq -jrc '.data.data.\"sidecar-module-access-client\"'").read().strip()
    print('fetching new token')
    response = httpx.post(f'{kc_url}/realms/sul/protocol/openid-connect/token',
                         data={
                             "client_id": f"{kc_client_id}",
                             "grant_type": "client_credentials",
                             "client_secret": f"{kc_client_secret}",
                         }
                    )

    token = response.json()['access_token']
    return token


if __name__ == "__main__":
    main()
