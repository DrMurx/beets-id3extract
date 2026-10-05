# AGENTS.md

Guidance for AI agents working on `beets-id3extract`.

**Keep this file current.** It describes the project as it is right now. Whenever a change alters the layout, configuration, behaviour, tooling or known defects described here, update this file in the same change.

## What this is

A [beets](https://beets.io) plugin that connects file tags (mainly ID3 frames in MP3s) to beets item fields that beets does not handle itself, in both directions: tag → database on import, database → tag on write. The main use case is DJ/streaming metadata such as a Spotify track ID kept in the `WOAS` frame.

## Layout

| Path | Purpose |
| --- | --- |
| `beetsplug/id3extract.py` | The whole plugin (~120 lines) |
| `beetsplug/__init__.py` | `pkgutil` namespace package boilerplate. Do not add code here |
| `pyproject.toml`, `setup.py` | Packaging. Metadata is duplicated across both; keep them in sync |
| `README.md` | User documentation. Update it with every config or behaviour change |

There are no tests, CI or linter configuration.

## Environment

Nothing is installed globally. Use a virtualenv:

```bash
uv venv && uv pip install -e . pytest      # or: python3 -m venv .venv && .venv/bin/pip install -e . pytest
```

Last verified against Python 3.14, beets 2.14.1, mediafile 0.17.0, mutagen 1.48.1. `pyproject.toml` declares `beets>=1.6.0` and Python ≥ 3.8; neither lower bound has been tested.

Use the Context7 MCP (`/websites/beets_readthedocs_io_en_stable`) for beets API questions, or read the installed sources under `.venv/lib/python*/site-packages/{beets,mediafile,mutagen}`. The installed source is the authority.

## How the code works

Config (`config.yaml`):

```yaml
plugins: [id3extract]
id3extract:
    mappings:
        WOAS: track_id        # <tag>: <beets field>
```

For each mapping `TAG: field`, `ID3ExtractPlugin.__init__`:

1. Registers a MediaFile field named `tag.lower()` (for example `woas`) through `add_media_field`, backed by `CustomID3Field`:
   - MP3: `MP3URLStorageStyle(TAG)`
   - MP4: `----:com.apple.iTunes:TAG`
   - Vorbis and other formats: `TAG`
2. Listens to `item_imported` and `album_imported`. `process_item` reopens the file, reads the media field and copies it into the beets field. If the tag is exactly `WOAS` and the value starts with `https://open.spotify.com/track/`, only the track ID is kept.
3. Listens to `write` and puts the beets field value into `tags[tag.lower()]`.

## Known defects

All reproduced against the versions listed above.

- **Only URL frames can be read.** `MP3URLStorageStyle.get` returns `frame.url`, so text frames (`TKEY`, `TXXX:…`) always read as `None`.
- **Writing destroys non-URL frames.** `set` always builds a `WOAS` frame regardless of the key, and because the media field reads as `None`, any `item.write()` deletes the mapped text frame from the file, even if nothing changed.
- **The Spotify round trip is lossy.** The URL is reduced to an ID on import, and the next write stores the bare ID in `WOAS`, replacing the URL.
- **Shadow fields.** Each mapping also creates a flexible attribute named after the tag (`woas`, `txxx:foo`) next to the configured field.
- **Tag names are case-sensitive in some places.** `woas: track_id` registers fine but never matches a frame, and the Spotify check requires `WOAS` exactly.
- **A name collision crashes beets at startup.** A tag whose lowercase name is an existing MediaFile property (`TITLE`), or two tags differing only in case, raises `ValueError` from `MediaFile.add_field`.
- **Mapping to a built-in field is half-broken.** `WOAS: title` does not update the database, but the write hook still pushes the title into `WOAS`.
- **Only import is covered.** Existing library items are never processed; there is no command.
- A bare `except:` in `__init__` hides config errors.

## beets and mediafile facts worth knowing

- `BeetsPlugin.add_media_field(name, descriptor)` adds the descriptor to the `MediaFile` class and `name` to `Item._media_fields`. From then on `Item.read()` (import, `beet update`) and `Item.write()` (`beet write`, `beet modify`) sync `item[name]` with the tag without any listener.
- `MediaFile.add_field` is class-global and permanent for the process, and raises `ValueError` if the name exists. Tests must isolate or undo registrations.
- `Item.write()` builds `tags` from media fields only, sends the `write` event, then calls `MediaFile.update(tags)`. A value of `None` deletes the tag.
- In a `StorageStyle`, override `fetch`/`store` (raw mutagen access) and `serialize`/`deserialize` (value conversion), not `get`/`set`.
- Stock `MP3StorageStyle.fetch` reads `frame.text[0]` and does not catch `AttributeError`, so it cannot be pointed at `W***` frames. `MP3DescStorageStyle(desc, key="TXXX")` handles `TXXX:DESC`; with `key="WXXX", attr="url", multispec=False` it handles `WXXX:DESC`.
- `beets.test.helper` exists in the installed package, but its audio fixtures (`test/rsrc`) are not shipped in the wheel. Generate test files yourself: 20 repetitions of `b"\xff\xfb\x90\x00" + b"\x00" * 413` form a valid MP3 that mutagen and MediaFile accept.
- Every `item.write()` also adds beets' own default frames (`TRCK 0/0`, `TDRC 0000`, …). Assert on the frames under test, not on the whole tag.
- beets' own `spotify` plugin stores its ID in the flexible field `spotify_track_id`.

## Conventions

- Keep the plugin a single module unless it clearly outgrows that.
- Log through `self._log` with `{}` placeholders (beets style), never `print`.
- Report configuration mistakes as `beets.ui.UserError` naming the offending key; do not swallow them.
- Never write a file tag in a form that cannot be read back to the same database value. Add a round-trip test for every new tag kind.
- Config changes are user-facing: update `README.md` and the module docstring in the same change.
- Do not commit or push unless asked.
