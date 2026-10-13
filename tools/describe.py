"""What a gallery card shows that the manifest does not say: a sentence out
of the README, and the pictures, animations and videos in the plugin's
`gallery/` folder."""

import re
import struct
import urllib.request

import github as gh

PICTURE = r"\.(png|jpg|jpeg|webp|gif)$"
KINDS = {"png": "image", "jpg": "image", "jpeg": "image", "gif": "animation", "webp": "image", "mp4": "video", "webm": "video"}
SPECIAL = re.compile(r"^(icon|thumbnail)\.", re.I)
WEBP_HEAD = 65536
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


def natural_key(name):
    """Sort key that puts screenshot-2 before screenshot-10, ignoring case."""
    return [int(part) if part.isdecimal() else part for part in re.split(r"(\d+)", name.lower())]


def extension(name):
    return name.rsplit(".", 1)[-1].lower() if "." in name else ""


def fetch_head(url, limit=WEBP_HEAD):
    """The first `limit` bytes of a file, or nothing when it cannot be read."""
    request = urllib.request.Request(url, headers={"Range": f"bytes=0-{limit - 1}", "User-Agent": "godwinmix-plugins-index"})
    try:
        with urllib.request.urlopen(request, timeout=30) as r:
            return r.read(limit)
    except Exception:  # noqa: BLE001 an unreadable webp is called a still picture
        return b""


def webp_is_animated(data):
    """True when a WebP's header says it is animated: an ANIM chunk, or the
    animation bit in the VP8X flags."""
    if len(data) < 12 or data[:4] != b"RIFF" or data[8:12] != b"WEBP":
        return False
    at = 12
    while at + 8 <= len(data):
        fourcc, size = data[at:at + 4], struct.unpack("<I", data[at + 4:at + 8])[0]
        if fourcc == b"ANIM":
            return True
        if fourcc == b"VP8X" and at + 8 < len(data) and data[at + 8] & 0x02:
            return True
        at += 8 + size + (size & 1)
    return False


def media_kind(name, url):
    """image, animation or video, or None for a file the gallery does not show."""
    kind = KINDS.get(extension(name))
    if extension(name) == "webp" and webp_is_animated(fetch_head(url)):
        return "animation"
    return kind


def gallery_media(names, url):
    """Every gallery file but the icon and the thumbnail, in natural order,
    as {url, type}."""
    media = []
    for name in sorted(names, key=natural_key):
        if SPECIAL.match(name) or extension(name) not in KINDS:
            continue
        media.append({"url": url(name), "type": media_kind(name, url(name))})
    return media


def pictures(full, ref, path, own_repo):
    """The icon, the thumbnail, the screenshots, the media and the preview.

    `gallery/icon.png` is the icon. The thumbnail is `gallery/thumbnail.png`,
    else the first screenshot, else the repository's social preview, which is
    only used when the plugin has the repository to itself: a monorepo's
    preview is about the monorepo. `screenshots` is every media entry an img
    tag can show, never a video, for mixers that only read that field. The
    preview is the first animation or video, for a card that plays on hover.
    """
    folder = f"{path}/gallery" if path else "gallery"
    files = [e["name"] for e in gh.listing(full, folder, ref) if e.get("type") == "file"]
    url = lambda name: gh.raw(full, ref, f"{folder}/{name}")  # noqa: E731
    named = lambda stem: next((url(n) for n in sorted(files, key=natural_key) if re.match(stem + PICTURE, n, re.I)), "")  # noqa: E731
    media = gallery_media(files, url)
    shots = [m["url"] for m in media if m["type"] != "video"]
    preview = next((m["url"] for m in media if m["type"] in ("animation", "video")), "")
    thumbnail = named("thumbnail") or (shots[0] if shots else "")
    if not thumbnail and own_repo:
        thumbnail = gh.social_preview(full)
    return {"icon": named("icon"), "thumbnail": thumbnail, "screenshots": shots, "media": media, "preview": preview}
