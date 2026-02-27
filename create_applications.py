import argparse
import json
import os
import yaml

from pathlib import Path

parser = argparse.ArgumentParser(
                    prog="CreateApplications",
                    description="Create ArgoCD applications for FOLIO using application descriptors",
                    epilog="-------")

parser.add_argument("filename", nargs="*", help="The application descriptor JSON file or files to process. If not provided, all JSON files in the namespace directory will be processed.")
parser.add_argument("-m", "--modules", help="a list of modules to install, each with -m flag", nargs="+", action="extend")
parser.add_argument("-n", "--namespace", required=True, help="the Kubernetes namespace for the applications")
parser.add_argument("-p", "--prod_replicasets", action="store_true", default=False, help="use production-level replicaset counts, else replicaCount=1")
parser.add_argument("-r", "--helm_repo", default="folio-helm-v2-dlss", help="the Helm repository to use for the applications (folio-helm-v2-dlss by default)")
parser.add_argument("-v", "--values_branch", default="main", help="the branch in the values repository to use for the applications (main by default)")
parser.add_argument("-x", "--execute", required=False, default="dry-run", choices=["apply", "dry-run"], help="whether to apply the applications to ArgoCD or just do a dry-run (dry-run by default)")
parser.add_argument("--no_generate", required=False, default=False, action="store_true", help="whether to skip generating the applications")

args = parser.parse_args()

if args.no_generate and args.execute == "dry-run":
    parser.error("--no_generate is set, but --execute is 'dry-run'. No applications will be generated or applied.")

def application_manifest(name, version, namespace, repo_url, values_files):
    data = {
        "apiVersion": "argoproj.io/v1alpha1",
        "kind": "Application",
        "metadata": {
            "name": name,
            "namespace": namespace,
        },
        "spec": {
            "project": namespace,
            "destination": {
                "server": "https://kubernetes.default.svc",
                "namespace": namespace,
            },
            "sources": [
                {
                    "repoURL": repo_url,
                    "targetRevision": version,
                    "chart": name,
                    "helm": {
                        "valueFiles": values_files
                    }
                },
                {
                    "ref": "values",
                    "repoURL": "https://github.com/sul-dlss/folio-eureka",
                    "targetRevision": args.values_branch,
                }
            ]
        }
    }
    return yaml.dump(data)


def create_applications(filename):
    with open(filename, "r") as file:
        data = json.load(file)

    modules = data["modules"]
    if args.modules:
        modules = [obj for obj in data["modules"] if obj["name"] in args.modules]

    for module in modules:
        module_name = module["name"]
        dir = Path(f"{args.namespace}/modules/{module_name}")
        dir.mkdir(parents=True, exist_ok=True)
        values_files = []
        values_files.append(f"$values/{args.namespace}/modules/{module_name}/overrides.yaml")
        
        if Path(f"{args.namespace}/modules/{module_name}/resources.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/resources.yaml")
        else:
            values_files.append(f"$values/{args.namespace}/common/resources.yaml")

        if Path(f"{args.namespace}/modules/{module_name}/sidecar.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/sidecar.yaml")
        elif not module_name.startswith("edge-"):
                values_files.append(f"$values/{args.namespace}/common/sidecar.yaml")

        if Path(f"{args.namespace}/modules/{module_name}/probes.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/probes.yaml")
        else:
            values_files.append(f"$values/{args.namespace}/common/probes.yaml")

        if args.prod_replicasets and Path(f"{args.namespace}/modules/{module_name}/replicas.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/replicas.yaml")

        if Path(f"{args.namespace}/modules/{module_name}/service.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/service.yaml")
        
        if Path(f"{args.namespace}/modules/{module_name}/java_opts.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/java_opts.yaml")
        
        if Path(f"{args.namespace}/modules/{module_name}/extra_env.yaml").exists():
            values_files.append(f"$values/{args.namespace}/modules/{module_name}/extra_env.yaml")
        
        chart_version = os.popen(f"helm show chart {args.helm_repo}/{module_name} | grep \"^version\" | awk '{{print $2}}'").read().strip()
        
        repo_url = os.popen(f"helm repo list | grep {args.helm_repo} | awk '{{print $2}}'").read().strip()

        app_file = f"{args.namespace}/modules/{module_name}/application.yaml"
        
        if not args.no_generate:
            with open(app_file, "w") as file:
                file.write(application_manifest(
                    name=module_name,
                    version=chart_version,
                    namespace=args.namespace,
                    repo_url=repo_url,
                    values_files=values_files
                ))

            print(f"Generated application manifest for {module_name}")

        if args.execute == "apply":
            kubectl_command = f"kubectl -n {args.namespace} apply -f {app_file}"
            print(f"Applying application manifest for {module_name}")
            os.system(kubectl_command)


if args.filename:
    for file in args.filename:
        create_applications(file)
else:
    descriptor_files = Path(args.namespace).glob('*.json')
    for file in descriptor_files:
        create_applications(file)
