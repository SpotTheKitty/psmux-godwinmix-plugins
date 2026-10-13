# GodwinMix plugins

The list of plugins for [GodwinMix](https://github.com/psmux/GodwinMix), the
live video mixer. The Plugins page in the mixer reads `index.json` from here,
and so do `gmx plugin search` and `gmx plugin add <name>`. A fresh mixer
knows about this list already; nobody has to add it.

There is no server behind it. Each plugin lives in its own repository. This
one holds a small file per plugin saying where that repository is, and a
workflow that reads every one of them once a day and writes what it found
into `index.json`: the description, the pictures, the stars, the download
count and the latest release.

## Getting your plugin listed

1. Put `gmx-plugin.toml` at the root of your repository. `gmx plugin new`
   writes one. The `description` in it is what the gallery shows, so write
   it for somebody deciding whether this is the plugin they want.
2. Add the topic `godwinmix-plugin` to the repository, so people can find it
   on GitHub too.
3. Add pictures if you have them, in a `gallery` folder at the root:
   * `gallery/icon.png`, square, 256 by 256 is plenty.
   * `gallery/thumbnail.png`, the card's picture, 16 by 9, 1280 by 720.
   * `gallery/screenshot-1.png`, `gallery/screenshot-2.png` and so on, for
     the detail view, in name order.

   With no thumbnail the first screenshot is used, and with no screenshots
   the repository's social preview.
4. Publish a GitHub release with one asset per platform, each name carrying
   the platform: `myplugin-1.0.0-windows-x86_64.zip`,
   `myplugin-1.0.0-linux-x86_64.tar.gz`. With no release assets the listing
   points at your git repository instead, and the mixer builds the plugin
   with the `[build]` section of your manifest.
5. Open a pull request adding `listings/<name>.toml`:

   ```toml
   name = "clock"
   repo = "yourname/gmx-clock"
   ```

   `name` is the plugin's name from its manifest and the file's name. You can
   add `title = "Clock"` for a nicer name on the card, and `author` if it is
   not the repository owner.

The workflow runs on the pull request and tells you if it could not read your
repository or your manifest. Once it is merged, your plugin is in the next
`index.json`, usually within a minute.

A plugin that lives in a folder of a larger repository can be listed with
`path = "the/folder"`, but it also needs `source`, the way the mixer installs
it (`cargo:`, `npm:`, `pypi:` or a release of its own), because a release or a
git address names a whole repository.

## Ratings

A card shows two numbers: the repository's GitHub stars and how many times its
release assets have been downloaded, every release added together. Both are
read from GitHub by the workflow. There is no rating server and nothing is
collected from the mixers that install a plugin.

## What is checked, and what is not

The workflow checks that your repository is public, that the manifest names
the same plugin as the listing, and that `index.json` matches `schema.json`.
It does not build your plugin, run it, or review its code.

**Nothing in this index is signed.** GodwinMix can verify a sigstore signature
against an identity named in a marketplace's `signing` block, but this
repository does not build or sign anyone's release assets yet, so the block is
left out and every version says `"signed": false` rather than pretending. A
plugin you list here is marked `custom`, which the mixer shows as unreviewed,
and it runs with the permissions you give it. A mixer configured with
`[plugins] allow_unsigned = false` will not install it.

## The plugins that ship with GodwinMix

The files whose `repo` is `psmux/GodwinMix` are the plugins in the mixer's own
`plugins/` folder. They are marked `"bundled": true`, the gallery shows them
as included, and installing one copies it from beside the mixer with no
download. Their tier is the one the official marketplace in the GodwinMix
repository gives them, and their star count is the GodwinMix repository's.

## The files here

| File | What it is |
|---|---|
| `index.json` | the list the mixer reads. Written by the workflow, never by hand |
| `schema.json` | a JSON Schema for it |
| `listings/*.toml` | one per plugin, added by pull request |
| `tools/build_index.py` | reads every listed repository and writes `index.json` |
| `tools/validate.py` | checks `index.json` against the schema |
| `.github/workflows/index.yml` | runs both on every change and once a day |

The tools need Python 3.11 or newer and nothing else, except `validate.py`,
which needs `pip install jsonschema`. To try a listing before you open the
pull request:

```
GITHUB_TOKEN=$(gh auth token) python tools/build_index.py
python tools/validate.py
```

## Running your own list

Fork this repository, change `HEADER` in `tools/build_index.py` so `name` is
yours, replace the files in `listings/`, and point your mixers at it with
`gmx marketplace add your-org/your-list`. Set `[marketplaces] only` in
`godwinmix.toml` to pin them to your list and nothing else.

## Licence

The tools and the index are MIT. Each plugin carries its own licence, named in
its entry.
