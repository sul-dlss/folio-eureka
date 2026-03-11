import argparse
import httpx
import json
import os


parser = argparse.ArgumentParser(
                    prog="BootstrapAdminRole",
                    description="Bootstrap libsys_role and user for FOLIO Eureka platform",
                    epilog="-------")

parser.add_argument("-c", "--create_user", action="store_true", default=False, help="create user, else just add new capabilities to libsys_role")
parser.add_argument("-e", "--email", help="admin user email address")
parser.add_argument("-f", "--first_name", help="admin user first name")
parser.add_argument("-l", "--last_name", help="admin user last name")
parser.add_argument("-p", "--password", help="password for admin user")
parser.add_argument("-u", "--username", help="username for admin user")

args = parser.parse_args()

if args.create_user and args.email is None:
    parser.error("<email> required with --create_user")
if args.create_user and args.first_name is None:
    parser.error("<first_name> required with --create_user")
if args.create_user and args.last_name is None:
    parser.error("<last_name> required with --create_user")
if args.create_user and args.password is None:
    parser.error("<password> required with --create_user")
if args.create_user and args.username is None:
    parser.error("<username> required with --create_user")
if os.getenv("SIDECAR_SECRET") is None or len(os.getenv("SIDECAR_SECRET")) == 0:
    parser.error("set SIDECAR_SECRET env var to get token")


def main():
    global token
    token = _token()
    create_user: bool = args.create_user
    if create_user:
        print("Creating admin user")
        user_id = create_kc_user(token, args)
        print("Creating admin user credentials")
        create_credentials(token, user_id, args)
        print("Creating libsys_role")
        create_role(token)
        role_id = admin_role_id(token)
        capabilities = all_capabilities(token)
        print("Adding all capabilities to libsys_role")
        assign_capabilities(token, role_id, capabilities)
        print("Assigning admin user to libsys_role")
        assign_role(token, user_id, role_id)
    else:
        print("Adding all capabilities to libsys_role")
        role_id = admin_role_id(token)
        capabilities = all_capabilities(token)
        assign_capabilities(token, role_id, capabilities)


def create_kc_user(token, args):
    data = { "username": args.username,
             "active": True,
             "personal": {
                "firstName": args.first_name,
                "lastName": args.last_name,
                "email": args.email
              }
            }
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
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
            print(response.status_code)
            user_data = json.loads(response.text)
            user_id = user_data.get("id", None)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return user_id


def create_credentials(token, user_id, args):
    data = { "username": args.username,
             "userId": user_id,
             "password": args.password
           }
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
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
            print(response.status_code)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def create_role(token):
    data = { "name": "libsys_role",
             "description": "Role for LibSys ONLY"
           }
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
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
            print(response.status_code)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def admin_role_id(token):
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.get(
                f"{kong_url}/roles?query=name==\"libsys_role\"",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                }
            )
            print(response.status_code)
            role_data = json.loads(response.text)
            role_id = role_data["roles"][0].get("id", None)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return role_id


def all_capabilities(token) -> list:
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
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
            print(response.status_code)
            response_text = json.loads(response.text)
            total_recs = response_text["totalRecords"]
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
                        print(response.status_code)
                        capabilities_dict = json.loads(response.text)
                        for i in capabilities_dict["capabilities"]:
                            capabilities.append(i["id"])
                        response.raise_for_status()
                    except httpx.HTTPStatusError as exc:
                        print(exc)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)

        return capabilities
    

def assign_capabilities(token, role_id, capabilities):
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
    with httpx.Client(timeout=None) as client:
        try:
            data = {
                "roleId": role_id,
                "capabilityIds": capabilities
            }
            response = client.post(
                f"{kong_url}/roles/capabilities",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}",
                    "x-okapi-tenant": "sul"
                },
                data=json.dumps(data)
            )
            print(response.status_code)
            if response.status_code != httpx.codes.OK:
                print("Capability assignment already exists; doing an update")
                data = {"capabilityIds": capabilities}
                response = client.put(
                    f"{kong_url}/roles/{role_id}/capabilities",
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
    kong_url = os.getenv("KONG_URL", "http://kong:8000")
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
            print(response.status_code)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def chunks(start, stop, step) -> list:
    return [(i, min(i + step - 1, stop)) for i in range(start, stop + 1, step)]


def _token():
    global token
    kc_url = os.getenv("KC_URL", "http://keycloak:8080")
    kc_client_id = "sidecar-module-access-client"
    kc_client_secret = os.getenv("SIDECAR_SECRET", "SecretPassword")
    print('fetching new token')
    response = httpx.post(f'{kc_url}/realms/sul/protocol/openid-connect/token',
                         data={
                             "client_id": f"{kc_client_id}",
                             "grant_type": "client_credentials",
                             "client_secret": f"{kc_client_secret}",
                         }
                    )

    print(response.status_code)
    token = response.json()['access_token']
    return token


if __name__ == "__main__":
    main()
