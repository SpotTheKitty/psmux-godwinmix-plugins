"""The little bit of the GitHub API the index needs. Standard library only.

Set GITHUB_TOKEN to lift the limit of 60 calls an hour. The workflow does.
"""

import base64
import json
import os
import urllib.error
import urllib.request

API = "https://api.github.com"


def _request(url, data=None):
    headers = {"Accept": "application/vnd.github+json", "User-Agent": "godwinmix-plugins-index"}
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        headers["Authorization"] = f"Bearer {token}"
    body = json.dumps(data).encode() if data is not None else None
    return urllib.request.Request(url, data=body, headers=headers)


def get(path):
    """GET an API path. None for a 404, an exception for anything else."""
    try:
        with urllib.request.urlopen(_request(f"{API}{path}"), timeout=30) as r:
            return json.load(r)
    except urllib.error.HTTPError as e:
        if e.code == 404:
            return None
        raise RuntimeError(f"{path} answered {e.code}: {e.read()[:200]!r}") from e


def graphql(query, **variables):
    with urllib.request.urlopen(_request(f"{API}/graphql", {"query": query, "variables": variables}), timeout=30) as r:
        answer = json.load(r)
    if answer.get("errors"):
        raise RuntimeError(f"GraphQL said: {answer['errors']}")
    return answer["data"]


def repo(full):
    return get(f"/repos/{full}")


def text(full, path, ref):
    """A file's text at a ref, or None when it is not there."""
    found = get(f"/repos/{full}/contents/{path}?ref={ref}")
    if not found or found.get("type") != "file":
        return None
    return base64.b64decode(found["content"]).decode("utf-8", "replace")


def listing(full, path, ref):
    """The entries of a folder, or an empty list."""
    found = get(f"/repos/{full}/contents/{path}?ref={ref}")
    return found if isinstance(found, list) else []


def social_preview(full):
    owner, name = full.split("/", 1)
    data = graphql(
        "query($o:String!,$n:String!){repository(owner:$o,name:$n){openGraphImageUrl}}", o=owner, n=name
    )
    return (data.get("repository") or {}).get("openGraphImageUrl") or ""


def releases(full):
    """Every published release, newest first, drafts left out."""
    found = get(f"/repos/{full}/releases?per_page=100") or []
    return [r for r in found if not r.get("draft")]


def last_change(full, path):
    """When the last commit touching a folder was made, RFC 3339."""
    found = get(f"/repos/{full}/commits?path={path}&per_page=1") or []
    return found[0]["commit"]["committer"]["date"] if found else ""


def topic_search(topic):
    """Every public repository carrying a topic, as owner/repo."""
    found = get(f"/search/repositories?q=topic:{topic}&per_page=100") or {}
    return sorted(item["full_name"] for item in found.get("items", []))


def raw(full, ref, path):
    return f"https://raw.githubusercontent.com/{full}/{ref}/{path}"
