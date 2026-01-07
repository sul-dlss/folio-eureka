import httpx
import json
import os

def main():
    global token
    kong_url = os.getenv('KONG_URL', 'http://mgr-applications')
    app_id = os.getenv('APP_ID', 'applications')
    token = _token()
    request = httpx.get(f'{kong_url}/applications/{app_id}',)
    applications = json.loads(request.text)
    discovery = { "discovery": [] }

    for module in applications['modules']:
        module_location = f"http://{module['name']}:8082"
        module['location'] = module_location
        discovery['discovery'].append(module)

    # print(discovery)
    for module in discovery['discovery']:
        print(f"UPDATING /modules/discovery/{module['id']}")
        try:
            discovery_put(module, token)
        except httpx.TimeoutException:
            print("Request timed out!")
            continue

def discovery_put(module, token):
    kong_url = os.getenv('KONG_URL', 'http://mgr-applications')
    with httpx.Client(timeout=20.0) as client:
        try:
            response = client.put(
                f"{kong_url}/modules/{module['id']}/discovery", 
                headers={
                    'content-type': 'application/json',
                    'Authorization': f'Bearer {token}'
                },
                data=json.dumps(module)
            )
            print(response)
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code == 401:
                token = _token()
                discovery_put(module, token)


def _token():
    global token
    kc_url = os.getenv('KC_URL', 'http://keycloak:8080')
    kc_admin_client_secret = os.getenv('KC_ADMIN_CLIENT_SECRET')
    print('fetching new token')
    response = httpx.post(f'{kc_url}/realms/master/protocol/openid-connect/token',
                         data={
                             "client_id": "folio-backend-admin-client",
                             "grant_type": "client_credentials",
                             "client_secret": f"{kc_admin_client_secret}",
                         }
                    )

    token = response.json()['access_token']
    return token


if __name__ == "__main__":
    main()
