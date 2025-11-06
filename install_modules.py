import argparse
import json
import os
import yaml

from pathlib import Path

parser = argparse.ArgumentParser(
                    prog='InstallModules',
                    description='Install FOLIO Eureka modules using application descriptors',
                    epilog='-------')

parser.add_argument('filename')
parser.add_argument('-m', '--modules', help='a list of modules to install, each with -m flag', nargs="+", action='extend')
parser.add_argument('-n', '--namespace', required=True)
parser.add_argument('-p', '--prod_replicasets', action='store_true')
parser.add_argument('-r', '--helm_repo', default='folio-helm-v2')
parser.add_argument('-x', '--execute', required=True, default='dry-run', choices=['install', 'upgrade', 'dry-run'])

args = parser.parse_args()

def base_override(name, version):
    data = {
        "image": {"repository": f"folioorg/{name}", "tag": f"{version}"},
        "podSecurityContext": {"fsGroup": 2000},
        "securityContext":{"capabilities": {"drop": ['ALL']},
            "runAsNonRoot": True,
            "runAsUser": 1000,
            "allowPrivilegeEscalation": False
        },
        "eureka": {"enabled": True},
        "integrations": {
            "db": {"enabled": True, "existingSecret": "db-credentials"},
            "kafka": {"enabled": True, "existingSecret": "kafka-credentials"},
            "okapi": {"enabled": False},
        }
    }
    
    if name.startswith('edge-'):
        del data['integrations']['db']
        del data['integrations']['kafka']
        data['integrations']['eureka-edge'] = {"enabled": True, "existingSecret": "eureka-edge"}
    
    return yaml.dump(data)


def override_file(dir, name, version):
    filename = f"{dir}/overrides.yaml"
    with open(filename, 'w') as file:
        file.write(base_override(name, version))


def replicaset_override(name):
    if args.prod_replicasets:
        if Path(f"modules/{name}/replicaset-prod.yaml").exists():
            return f"-f modules/{name}/replicaset-prod.yaml"
    
    return ''


def resources_override(name):
    if Path(f"modules/{name}/resources.yaml").exists():
        return f"-f modules/{name}/resources.yaml"
    
    return f"-f modules/resources.yaml"


def extrafile_override(name, file):
    if Path(f"modules/{name}/{file}-{args.namespace}.yaml").exists():
        return f"-f modules/{name}/{file}.yaml"
    
    if Path(f"modules/{name}/{file}.yaml").exists():
        return f"-f modules/{name}/{file}.yaml"
    
    if Path(f"modules/{file}.yaml").exists():
        return f"-f modules/{file}.yaml"

    return ''


with open(args.filename, 'r') as file:
    data = json.load(file)

modules = data['modules']

if args.modules:
    modules = [obj for obj in data['modules'] if obj['name'] in args.modules]
        
for module in modules:
    name = module['name']
    version = module['version']
    dir = Path(f"modules/{name}")
    dir.mkdir(parents=True, exist_ok=True)
    
    override_file(dir, name, version)
    helm_command = f"helm -n {args.namespace} {args.execute} -f modules/{name}/overrides.yaml \
        {resources_override(name)} \
        {replicaset_override(name)} \
        {extrafile_override(name, 'extra_env')} \
        {extrafile_override(name, 'java_opts')} \
        {extrafile_override(name, 'probes')} \
        {extrafile_override(name, 'service')} \
        {extrafile_override(name, 'sidecar')} \
        {name} {args.helm_repo}/{name}"
    
    if args.execute == 'dry-run':
        command = " ".join(helm_command.replace('dry-run', 'install').strip().split())
        print(f"{command}\n")
    else:
        os.system(helm_command)
