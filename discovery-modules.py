import httpx
import json
import os

def main():
    token = _token()
    request = httpx.get('http://kong-folio-dev.stanford.edu/applications')
    applications = json.loads(request.text)
    discovery = { "discovery": [] }

    for app in applications['applicationDescriptors']:
        for module in app['modules']:
            module_location = f"http://{module['name']}:8082"
            module['location'] = module_location
            discovery['discovery'].append(module)

    print(discovery)
    print("POSTING to /modules/discovery")
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                "http://kong-folio-dev.stanford.edu/modules/discovery",
                headers={
                    "content-type": "application/json",
                    "Authorization": f"Bearer {token}"
                },
                data=json.dumps(discovery)
            )
            print(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            print(exc)


def _token():
    print('fetching new token')
    response = httpx.post('http://keycloak-folio-dev.stanford.edu/realms/master/protocol/openid-connect/token',
        data={
            "client_id": "folio-backend-admin-client",
            "grant_type": "client_credentials",
            "client_secret": f"{os.getenv('KC_ADMIN_CLIENT_SECRET')}",
        }
    )

    token = response.json()['access_token']
    return token


if __name__ == "__main__":
    main()
