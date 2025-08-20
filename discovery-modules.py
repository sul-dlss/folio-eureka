import httpx
import json
import os

def main():
    request = httpx.get('http://mgr-applications/applications')
    applications = json.loads(request.text)
    discovery = { "discovery": [] }

    for app in applications['applicationDescriptors']:
        for module in app['modules']:
            module_location = f"http://{module['name']}:8082"
            module['location'] = module_location
            discovery['discovery'].append(module)

    print(discovery)
    print("POSTING to /modules/discovery")
    post_response = httpx.post(
        'http://mgr-applications/modules/discovery', 
        headers={
            'content-type': 'application/json',
            'Authorization': f'Bearer {os.getenv("TOKEN")}'
        },
        data=json.dumps(discovery)
    )

    print(post_response)


if __name__ == "__main__":
    main()
