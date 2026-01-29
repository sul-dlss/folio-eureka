import argparse
import json
import os
import yaml

from pathlib import Path

parser = argparse.ArgumentParser(
                    prog="CreateModuleValues",
                    description="Create FOLIO Eureka module values using application descriptors",
                    epilog="-------")

parser.add_argument("filename")
parser.add_argument("-m", "--modules", help="a list of modules to install, each with -m flag", nargs="+", action="extend")
parser.add_argument("-n", "--namespace", required=True, help="the Kubernetes namespace for the applications")
parser.add_argument("-p", "--prod_replicasets", action="store_true", help="use production-level replicaset counts, else replicaCount=1")

args = parser.parse_args()

S3_MODULES = [
    "mod-bulk-operations",
    "mod-data-export",
    "mod-data-export-worker",
    "mod-data-import",
    "mod-entities-links",
    "mod-lists",
    "mod-marc-migrations",
    "mod-oai-pmh",
    "mod-reporting",
    "mod-users",
]

ONE_REPLICASET = [
    "mod-data-export",
    "mod-data-export-spring",
    "mod-data-export-worker",
    "mod-data-import",
    "mod-erm-usage-harvester",
    "mod-quick-marc",
]

THREE_REPLICASET = [
    "mod-circulation",
    "mod-circulation-storage",
    "mod-configuration",
    "mod-finance",
    "mod-finance-storage",
    "mod-inventory",
    "mod-inventory-storage",
    "mod-orders",
    "mod-orders-storage",
    "mod-users",
    "mod-users-bl",
]

def base_override(name, version, prod_rs):
    data = {
        "image": {"repository": f"folioorg/{name}", "tag": f"{version}"},
        "podSecurityContext": {"fsGroup": 2000},
        "securityContext":{"capabilities": {"drop": ["ALL"]},
            "runAsNonRoot": True,
            "runAsUser": 1000,
            "allowPrivilegeEscalation": False
        },
        "eureka": {
            "enabled": True,
        },
        "integrations": {
            "db": {"enabled": True, "existingSecret": "db-credentials"},
            "kafka": {"enabled": True, "existingSecret": "kafka-credentials"},
            "okapi": {"enabled": False},
            "systemuser": {"enabled": False},
        },
        "deploymentStrategy": "RollingUpdate"
    }
    
    if name in S3_MODULES:
        data["integrations"]["s3"] = {"enabled": True, "existingSecret": "s3-credentials"}
    if not name.startswith("mod-pubsub"):
        data["eureka"]["extraEnvVars"] = [
            {"name": "FOLIO_SYSTEM_USER_ENABLED", "value": "false"},
            {"name": "SYSTEM_USER_CREATED", "value": "false"},
            {"name": "SYSTEM_USER_ENABLED", "value": "false"},
        ]
    if name.startswith("mod-reporting"):
        del data["securityContext"]["runAsUser"]
    if name.startswith("edge-"):
        del data["integrations"]["db"]
        del data["integrations"]["kafka"]
        data["integrations"]["eureka-edge"] = {"enabled": True, "existingSecret": "eureka-edge"}

    if prod_rs:
        data["replicaCount"] = 2
        if name in ONE_REPLICASET:
            data["replicaCount"] = 1
        if name in THREE_REPLICASET:
            data["replicaCount"] = 3

    return yaml.dump(data)


with open(args.filename, "r") as file:
    data = json.load(file)

modules = data["modules"]

if args.modules:
    modules = [obj for obj in data["modules"] if obj["name"] in args.modules]

for module in modules:
    name = module["name"]
    version = module["version"]
    dir = Path(f"{args.namespace}/modules/{name}")
    dir.mkdir(parents=True, exist_ok=True)
    prod_rs = args.prod_replicasets
    
    filename = f"{dir}/overrides.yaml"
    with open(filename, "w") as file:
        file.write(base_override(name, version, prod_rs))
