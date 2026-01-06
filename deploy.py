#!/usr/bin/env python3
"""
n8n Snippet Deployment Script

Syncs Python code snippets to n8n workflows via the REST API.
This script can update existing workflows that use registered snippets.

Usage:
    python deploy.py                    # Deploy all snippets
    python deploy.py --snippet <name>   # Deploy specific snippet
    python deploy.py --list             # List all snippets
    python deploy.py --dry-run          # Show what would be deployed

Environment variables required:
    N8N_HOST     - Your n8n instance URL (e.g., http://localhost:5678)
    N8N_API_KEY  - Your n8n API key
"""

import argparse
import json
import os
import sys
from pathlib import Path

import requests

SNIPPETS_DIR = Path(__file__).parent / "snippets"
REGISTRY_FILE = SNIPPETS_DIR / "snippet_registry.json"
N8N_CODE_NODE_TYPE = "n8n-nodes-base.code"
API_TIMEOUT = 30


def load_registry() -> dict:
    """Load the snippet registry."""
    with open(REGISTRY_FILE) as f:
        return json.load(f)


def load_snippet(filename: str) -> str:
    """Load a snippet file's contents."""
    snippet_path = SNIPPETS_DIR / filename
    with open(snippet_path) as f:
        return f.read()


def get_n8n_client() -> dict:
    """Create an n8n API client configuration."""
    host = os.environ.get("N8N_HOST")
    api_key = os.environ.get("N8N_API_KEY")

    if not host or not api_key:
        print("Error: N8N_HOST and N8N_API_KEY environment variables are required")
        sys.exit(1)

    return {
        "base_url": host.rstrip("/"),
        "headers": {"X-N8N-API-KEY": api_key, "Content-Type": "application/json"},
    }


def list_workflows(client: dict) -> list:
    """List all workflows from n8n."""
    url = f"{client['base_url']}/api/v1/workflows"
    response = requests.get(url, headers=client["headers"], timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json().get("data", [])


def get_workflow(client: dict, workflow_id: str) -> dict:
    """Get a specific workflow."""
    url = f"{client['base_url']}/api/v1/workflows/{workflow_id}"
    response = requests.get(url, headers=client["headers"], timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def update_workflow(client: dict, workflow_id: str, workflow: dict) -> dict:
    """Update a workflow."""
    url = f"{client['base_url']}/api/v1/workflows/{workflow_id}"
    response = requests.put(url, headers=client["headers"], json=workflow, timeout=API_TIMEOUT)
    response.raise_for_status()
    return response.json()


def find_python_nodes_with_snippet(workflow: dict, snippet_id: str) -> list:
    """Find Python Code nodes that reference a snippet."""
    matching_nodes = []
    for node in workflow.get("nodes", []):
        if node.get("type") == N8N_CODE_NODE_TYPE:
            params = node.get("parameters", {})
            # Check if node has a snippet marker in the code
            code = params.get("jsCode", "") or params.get("pythonCode", "")
            if f"# snippet: {snippet_id}" in code or f"# @snippet: {snippet_id}" in code:
                matching_nodes.append(node)
    return matching_nodes


def deploy_snippet(client: dict, snippet: dict, dry_run: bool = False) -> int:
    """Deploy a snippet to all workflows that use it."""
    snippet_id = snippet["id"]
    snippet_code = load_snippet(snippet["file"])

    # Add snippet marker if not present
    if f"# snippet: {snippet_id}" not in snippet_code:
        snippet_code = f"# snippet: {snippet_id}\n{snippet_code}"

    workflows = list_workflows(client)
    updated_count = 0

    for wf_summary in workflows:
        workflow = get_workflow(client, wf_summary["id"])
        matching_nodes = find_python_nodes_with_snippet(workflow, snippet_id)

        if matching_nodes:
            print(f"  Found {len(matching_nodes)} node(s) in workflow: {workflow['name']}")

            for node in matching_nodes:
                if "pythonCode" in node.get("parameters", {}):
                    node["parameters"]["pythonCode"] = snippet_code
                else:
                    node["parameters"]["jsCode"] = snippet_code

            if not dry_run:
                update_workflow(client, workflow["id"], workflow)
                print(f"    Updated workflow: {workflow['name']}")
            else:
                print(f"    [DRY RUN] Would update workflow: {workflow['name']}")

            updated_count += 1

    return updated_count


def main():
    parser = argparse.ArgumentParser(description="Deploy n8n Python snippets")
    parser.add_argument("--snippet", "-s", help="Deploy specific snippet by ID")
    parser.add_argument("--list", "-l", action="store_true", help="List all snippets")
    parser.add_argument("--dry-run", "-n", action="store_true", help="Show what would be deployed")
    args = parser.parse_args()

    registry = load_registry()

    if args.list:
        print("Available snippets:")
        for snippet in registry["snippets"]:
            print(f"  {snippet['id']}: {snippet['name']}")
            print(f"    {snippet['description']}")
        return

    client = get_n8n_client()

    snippets_to_deploy = registry["snippets"]
    if args.snippet:
        snippets_to_deploy = [s for s in snippets_to_deploy if s["id"] == args.snippet]
        if not snippets_to_deploy:
            print(f"Error: Snippet '{args.snippet}' not found")
            sys.exit(1)

    total_updated = 0
    for snippet in snippets_to_deploy:
        print(f"Deploying snippet: {snippet['name']}")
        updated = deploy_snippet(client, snippet, dry_run=args.dry_run)
        total_updated += updated

    print(f"\nDeployment complete: {total_updated} workflow(s) updated")


if __name__ == "__main__":
    main()
