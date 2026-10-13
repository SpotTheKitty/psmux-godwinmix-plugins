"""What a gallery card shows that the manifest does not say: a sentence out
of the README, and the pictures in the plugin's `gallery/` folder."""

import re

import github as gh

PICTURE = r"\.(png|jpg|jpeg|webp|gif)$"
SKIP = ("#", "!", "<", "[!", "[![", "---", "|", "```", ">", "=")


def first_paragraph(markdown):
    """The README's first paragraph of prose, with the markdown taken out."""
    para = []
    for line in markdown.splitlines():
        text = line.strip()
        if not text:
            if para:
                break
            continue
        if not para and text.startswith(SKIP):
            continue
        para.append(text)
    joined = " ".join(para)
    joined = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", joined)
    joined = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", joined)
    joined = re.sub(r"[*_]{1,2}([^*_]+)[*_]{1,2}", r"\1", joined)
    return joined.strip()[:400]


def pictures(full, ref, path, own_repo):
    """The icon, the thumbnail and the screenshots, as URLs.

    `gallery/icon.png` is the icon. The thumbnail is `gallery/thumbnail.png`,
    else the first screenshot, else the repository's social preview, which is
    only used when the plugin has the repository to itself: a monorepo's
    preview is about the monorepo.
    """
    folder = f"{path}/gallery" if path else "gallery"
    files = sorted(e["name"] for e in gh.listing(full, folder, ref) if e.get("type") == "file")
    url = lambda name: gh.raw(full, ref, f"{folder}/{name}")  # noqa: E731
    icon = next((url(n) for n in files if re.match(r"icon" + PICTURE, n)), "")
    shots = [url(n) for n in files if re.match(r"screenshot-[\w.-]+" + PICTURE, n)]
    thumbnail = next((url(n) for n in files if re.match(r"thumbnail" + PICTURE, n)), "")
    if not thumbnail and shots:
        thumbnail = shots[0]
    if not thumbnail and own_repo:
        thumbnail = gh.social_preview(full)
    return icon, thumbnail, shots
