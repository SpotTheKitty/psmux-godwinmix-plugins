#!/usr/bin/env python3
"""Regenerate index.json from listings/*.toml by reading each plugin's own
GitHub repository. Standard library only; Python 3.11 or newer for tomllib.

    python tools/build_index.py            read every repository, write index.json
    python tools/build_index.py --offline  check the listing files and nothing else

A repository that cannot be read keeps the entry it had, so one bad day at
the GitHub API does not take a plugin out of every gallery. A new listing
that cannot be read fails the run, which is what a pull request wants.
"""

import json
import os
import pathlib
import re
import sys
import tomllib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
import github as gh  # noqa: E402
from describe import first_paragraph, pictures  # noqa: E402

ROOT = pathlib.Path(__file__).resolve().parent.parent
INDEX = ROOT / "index.json"
# Every listing. A mixer from 0.3.10 on reads this first; an older one never
# asks for it, so a listing that names `mixer` is only here.
INDEX2 = ROOT / "index2.json"
VERSION = re.compile(r"^\d+\.\d+\.\d+$")
TOPIC = "godwinmix-plugin"
TRIPLES = ["linux-x86_64", "linux-aarch64", "linux-armv7", "macos-aarch64", "macos-x86_64", "windows-x86_64", "windows-aarch64"]
SLUG = re.compile(r"^[a-z0-9][a-z0-9-]*$")
REPO = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
ANY = re.compile(r"-any[.-]|_any\.", re.I)
SIGNATURE = (".sigstore.json", ".sigstore", ".bundle", ".sig", ".pem")
HEADER = {
    "name": "godwinmix-plugins",
    "title": "GodwinMix plugins",
    "description": "Every listed GodwinMix plugin, read from its own repository once a day: what it does, its pictures, its stars and how often it was downloaded.",
    "owner": "psmux",
    "version": 1,
}


def listings():
    out = []
    for path in sorted((ROOT / "listings").glob("*.toml")):
        item = tomllib.loads(path.read_text(encoding="utf-8"))
        name, repo = item.get("name", ""), item.get("repo", "")
        if name != path.stem or not SLUG.match(name):
            raise SystemExit(f"{path.name}: `name` must be a lowercase slug and match the file name")
        if not REPO.match(repo):
            raise SystemExit(f"{path.name}: `repo` must be owner/repo")
        if item.get("path") and not item.get("bundled") and not item.get("source"):
            raise SystemExit(f"{path.name}: a plugin in a folder of a larger repository needs `source`, since a release or a git address names a whole repository")
        if not isinstance(item.get("featured", False), bool):
            raise SystemExit(f"{path.name}: `featured` is true or false")
        if "mixer" in item and not VERSION.match(str(item["mixer"])):
            raise SystemExit(f"{path.name}: `mixer` is the oldest GodwinMix that runs it, written 0.3.10")
        out.append(item)
    return out


def version_of(plugin, latest, bundled):
    api = int(plugin.get("api", 1))
    if latest and not bundled:
        names = [a["name"] for a in latest.get("assets", [])]
        platforms = [t for t in TRIPLES if any(t in n for n in names)]
        if any(ANY.search(n) and not n.lower().endswith(SIGNATURE) for n in names):
            platforms.append("any")
        return {"version": latest["tag_name"].lstrip("v"), "api": api, "platforms": platforms, "signed": False}
    if plugin.get("version"):
        return {"version": plugin["version"], "api": api, "platforms": plugin.get("platforms", []), "signed": False}
    return None


def entry(item, official):
    full, path = item["repo"], item.get("path", "").strip("/")
    bundled = bool(item.get("bundled"))
    info = gh.repo(full)
    if not info:
        raise RuntimeError(f"{full} is not a public repository")
    ref = info["default_branch"]
    at = lambda name: f"{path}/{name}" if path else name  # noqa: E731
    manifest = tomllib.loads(gh.text(full, at("gmx-plugin.toml"), ref) or "")
    plugin = manifest.get("plugin", {})
    if plugin and plugin.get("name") != item["name"]:
        raise RuntimeError(f"the manifest names `{plugin.get('name')}`, the listing `{item['name']}`")
    kinds = list(dict.fromkeys(p.get("kind", "") for p in manifest.get("provides", []) if p.get("kind")))
    readme = gh.text(full, at("README.md"), ref) or ""
    shown = pictures(full, ref, path, own_repo=not path)
    rels = [] if (bundled or path) else gh.releases(full)
    latest = next((r for r in rels if not r.get("prerelease")), rels[0] if rels else None)
    version = version_of(plugin, latest, bundled)
    has_assets = bool(version and version["platforms"])
    source = item.get("source") or (f"./{path}" if bundled else full if has_assets else f"https://github.com/{full}.git")
    spdx = ((info.get("license") or {}).get("spdx_id") or "").replace("NOASSERTION", "")
    out = {
        "name": item["name"],
        "source": source,
        "title": item.get("title", ""),
        "description": plugin.get("description") or first_paragraph(readme) or info.get("description") or "",
        "tier": official.get(item["name"], {}).get("tier", "custom") if bundled else "custom",
        "kinds": kinds,
        "license": plugin.get("license") or spdx,
        "repository": info["html_url"] + (f"/tree/{ref}/{path}" if path else ""),
        "homepage": info.get("homepage") or "",
        "author": item.get("author") or ", ".join(plugin.get("authors", [])) or info["owner"]["login"],
        "icon": shown["icon"],
        "thumbnail": shown["thumbnail"],
        "screenshots": shown["screenshots"],
        "media": shown["media"],
        "preview": shown["preview"],
        "stars": info.get("stargazers_count", 0),
        "downloads": None if bundled else sum(a.get("download_count", 0) for r in rels for a in r.get("assets", [])),
        "updated": (latest or {}).get("published_at") or (gh.last_change(full, path) if path else info.get("pushed_at")) or "",
        "tags": [t for t in info.get("topics", []) if t != TOPIC],
        "bundled": bundled,
        "featured": item.get("featured") is True,
        "mixer": item.get("mixer", ""),
        "versions": [version] if version else [],
    }
    return {k: v for k, v in out.items() if v is not None and v is not False and v != "" and v != []}


def main():
    items = listings()
    if "--offline" in sys.argv:
        print(f"{len(items)} listing files read")
        return 0
    previous = {}
    for path in (INDEX, INDEX2):
        if path.exists():
            previous.update({p["name"]: p for p in json.loads(path.read_text(encoding="utf-8")).get("plugins", [])})
    official_text = gh.text("psmux/GodwinMix", "godwinmix-marketplace.json", "main") or "{}"
    official = {p["name"]: p for p in json.loads(official_text).get("plugins", [])}
    plugins, refused = [], []
    for item in items:
        try:
            plugins.append(entry(item, official))
            print(f"read {item['name']} from {item['repo']}")
        except Exception as e:  # noqa: BLE001 one listing must not stop the rest
            print(f"::warning::{item['name']}: {e}")
            if item["name"] in previous:
                plugins.append(previous[item["name"]])
            else:
                refused.append(item["name"])
    for path, kept in ((INDEX2, plugins), (INDEX, for_old_mixers(plugins))):
        document = {**HEADER, "plugins": kept}
        path.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    report(items, plugins, len(for_old_mixers(plugins)))
    if refused:
        print(f"::error::not listed, because their repositories could not be read: {', '.join(refused)}")
        return 1
    return 0


def for_old_mixers(plugins):
    """index.json, for a mixer from before 0.3.10: every listing but those that
    name the oldest mixer they need, since that field arrived with 0.3.10."""
    return [p for p in plugins if not p.get("mixer")]


def report(items, plugins, old):
    """Say which repositories carry the topic and have no listing yet."""
    listed = {i["repo"].lower() for i in items}
    try:
        tagged = [r for r in gh.topic_search(TOPIC) if r.lower() not in listed]
    except Exception as e:  # noqa: BLE001 the search is a courtesy
        tagged, _ = [], print(f"::notice::the topic search did not answer: {e}")
    lines = [f"Wrote {len(plugins)} plugins to index2.json and {old} to index.json."]
    if tagged:
        lines.append(f"Carrying the `{TOPIC}` topic with no listing yet: {', '.join(tagged)}")
    print("\n".join(lines))
    summary = os.environ.get("GITHUB_STEP_SUMMARY")
    if summary:
        with open(summary, "a", encoding="utf-8") as f:
            f.write("\n\n".join(lines) + "\n")


if __name__ == "__main__":
    sys.exit(main())
