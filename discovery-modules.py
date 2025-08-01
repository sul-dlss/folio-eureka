import httpx
import json

def main():
    request = httpx.get('http://mgr-applications/applications')
    applications = json.loads(request.text)
    discovery = { "discovery": [] }

    for module in applications['applicationDescriptors'][0]['modules']:
        module_location = f"http://{module['name']}:8082"
        module['location'] = module_location
        discovery['discovery'].append(module)

    post_response = httpx.post(
        'http://mgr-applications/modules/discovery', 
        headers={'content-type': 'application/json'},
        data=json.dumps(discovery)
    )

    print(post_response.status_code)


if __name__ == "__main__":
    main()
