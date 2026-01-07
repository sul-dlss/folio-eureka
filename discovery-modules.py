import httpx
import json
import os

def main():
    kong_url = os.getenv('KONG_URL', 'http://mgr-applications')
    app_id = os.getenv('APP_ID', 'applications')
    token = _token()
    request = httpx.get(f'{kong_url}/applications/{app_id}',)
    applications = json.loads(request.text)
    print(applications)
    discovery = { "discovery": [] }

    for module in applications['modules']:
        module_location = f"http://{module['name']}:8082"
        module['location'] = module_location
        discovery['discovery'].append(module)

    print("POSTING to /modules/discovery")
    print(discovery)
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.post(
                f"{kong_url}/modules/discovery",
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
    kc_url = os.getenv('KC_URL', 'http://keycloak:8080')
    kc_admin_client_secret = os.getenv('KC_ADMIN_CLIENT_SECRET')
    print(f'fetching new token from {kc_url}')
    response = httpx.post(f'{kc_url}/realms/master/protocol/openid-connect/token',
        data={
            "client_id": "folio-backend-admin-client",
            "grant_type": "client_credentials",
            "client_secret": kc_admin_client_secret,
        }
    )

    token = response.json()['access_token']
    return token


if __name__ == "__main__":
    main()
