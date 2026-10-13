"""Offline tests for the gallery media and the release platforms. No network:
the folder listing and the webp fetch are stubbed.

    python -m unittest discover -s tools -p "test_*.py"
"""

import struct
import unittest
from unittest import mock

import build_index
import describe


def webp(*chunks):
    body = b"WEBP" + b"".join(c + struct.pack("<I", len(d)) + d + b"\0" * (len(d) & 1) for c, d in chunks)
    return b"RIFF" + struct.pack("<I", len(body)) + body


STILL = webp((b"VP8 ", b"\0" * 11))
MOVING = webp((b"VP8X", bytes([0x02]) + b"\0" * 9), (b"ANIM", b"\0" * 6), (b"ANMF", b"\0" * 20))
FLAG_ONLY = webp((b"VP8X", bytes([0x12]) + b"\0" * 9))
CHUNK_ONLY = webp((b"VP8X", b"\0" * 10), (b"ANIM", b"\0" * 6))


def gallery(names, heads=None):
    """Run pictures over a fake gallery folder; heads maps a file name to the
    bytes its webp fetch returns."""
    heads = heads or {}
    files = [{"name": n, "type": "file"} for n in names] + [{"name": "sub", "type": "dir"}]
    fetch = lambda url, limit=describe.WEBP_HEAD: heads.get(url.rsplit("/", 1)[-1], b"")  # noqa: E731
    with mock.patch.object(describe.gh, "listing", return_value=files), \
            mock.patch.object(describe.gh, "social_preview", return_value="https://example.com/social.png"), \
            mock.patch.object(describe, "fetch_head", side_effect=fetch):
        return describe.pictures("o/r", "main", "", own_repo=True)


def short(urls):
    return [u.rsplit("/", 1)[-1] for u in urls]


class NaturalOrder(unittest.TestCase):
    def test_numbers_sort_as_numbers(self):
        names = ["screenshot-10.png", "Screenshot-2.png", "screenshot-1.png", "demo.gif"]
        self.assertEqual(sorted(names, key=describe.natural_key),
                         ["demo.gif", "screenshot-1.png", "Screenshot-2.png", "screenshot-10.png"])

    def test_media_follows_natural_order(self):
        shown = gallery(["screenshot-10.png", "screenshot-2.png", "tour.mp4", "demo.gif"])
        self.assertEqual(short(m["url"] for m in shown["media"]),
                         ["demo.gif", "screenshot-2.png", "screenshot-10.png", "tour.mp4"])


class Types(unittest.TestCase):
    def test_by_extension(self):
        shown = gallery(["a.png", "b.JPG", "c.jpeg", "d.gif", "e.mp4", "f.webm", "g.txt", "README.md"])
        self.assertEqual([m["type"] for m in shown["media"]],
                         ["image", "image", "image", "animation", "video", "video"])

    def test_icon_and_thumbnail_are_not_media(self):
        shown = gallery(["icon.png", "thumbnail.jpg", "thumbnail.mp4", "shot.png"])
        self.assertEqual(short(m["url"] for m in shown["media"]), ["shot.png"])
        self.assertEqual(short([shown["icon"], shown["thumbnail"]]), ["icon.png", "thumbnail.jpg"])

    def test_webp_header(self):
        self.assertFalse(describe.webp_is_animated(STILL))
        self.assertTrue(describe.webp_is_animated(MOVING))
        self.assertTrue(describe.webp_is_animated(FLAG_ONLY))
        self.assertTrue(describe.webp_is_animated(CHUNK_ONLY))
        self.assertFalse(describe.webp_is_animated(b""))
        self.assertFalse(describe.webp_is_animated(b"GIF89a" + b"ANIM" * 4))

    def test_webp_fetched(self):
        shown = gallery(["a.webp", "b.webp", "c.webp"], {"a.webp": STILL, "b.webp": MOVING})
        self.assertEqual([m["type"] for m in shown["media"]], ["image", "animation", "image"])


class ScreenshotsAndMedia(unittest.TestCase):
    def test_split(self):
        shown = gallery(["tour.mp4", "screenshot-1.png", "demo.gif", "spin.webp"], {"spin.webp": MOVING})
        self.assertEqual(short(shown["screenshots"]), ["demo.gif", "screenshot-1.png", "spin.webp"])
        self.assertTrue(all(isinstance(s, str) for s in shown["screenshots"]))
        self.assertEqual(short([shown["preview"]]), ["demo.gif"])
        self.assertEqual(short([shown["thumbnail"]]), ["demo.gif"])

    def test_video_only(self):
        shown = gallery(["tour.webm"])
        self.assertEqual(shown["screenshots"], [])
        self.assertEqual(short([shown["preview"]]), ["tour.webm"])
        self.assertEqual(shown["thumbnail"], "https://example.com/social.png")

    def test_no_preview_for_stills(self):
        shown = gallery(["screenshot-1.png"])
        self.assertEqual(shown["preview"], "")


class AnyPlatform(unittest.TestCase):
    def platforms(self, *names):
        latest = {"tag_name": "v1.0.0", "assets": [{"name": n} for n in names]}
        return build_index.version_of({"api": 1}, latest, False)["platforms"]

    def test_any_names(self):
        for name in ("p-1.0.0-any.zip", "p-1.0.0-ANY-py3.tar.gz", "p_1.0.0_any.whl"):
            self.assertEqual(self.platforms(name), ["any"], name)

    def test_signature_alone_is_not_any(self):
        for name in ("p-any.zip.sigstore.json", "p-any.zip.sig", "p-any.zip.pem", "p-any.zip.bundle", "p-any.zip.sigstore"):
            self.assertEqual(self.platforms(name), [], name)

    def test_triples_then_any(self):
        self.assertEqual(self.platforms("p-any.zip", "p-windows-x86_64.zip", "p-linux-x86_64.tar.gz"),
                         ["linux-x86_64", "windows-x86_64", "any"])

    def test_no_any(self):
        self.assertEqual(self.platforms("p-1.0.0-windows-x86_64.zip", "company.zip"), ["windows-x86_64"])


if __name__ == "__main__":
    unittest.main()
