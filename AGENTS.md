# AGENTS.md

Guidance for AI agents working on `beets-id3extract`.

**Keep this file current.** It describes the project as it is right now. Whenever a change alters the layout, configuration, behaviour, tooling or known defects described here, update this file in the same change.

## What this is

A [beets](https://beets.io) plugin that connects file tags (ID3 text and URL frames in MP3s) to beets item fields that beets does not handle itself, in both directions: tag → database on import and update, database → tag on write. The main use case is DJ/streaming metadata such as a Spotify track ID kept in the `WOAS` frame.

## Layout

| Path | Purpose |
| --- | --- |
| `beetsplug/id3extract.py` | The whole plugin (~200 lines) |
| `beetsplug/__init__.py` | `pkgutil` namespace package boilerplate. Do not add code here |
| `tests/conftest.py` | Shared fixtures: `mp3_factory`, `plugin`, `lib` (see "Tests") |
| `tests/helpers.py` | Test helpers: `import_item`, `import_album`, `write_item`, `read_frames` |
| `tests/test_smoke.py` | Smoke tests for the plugin and the fixtures |
| `tests/test_fields.py` | The `fields` option: round trips per tag kind and type, native sync, validation |
| `tests/test_legacy_mappings.py` | The deprecated `mappings` option, including Spotify ID extraction |
| `tests/test_defects.py` | Remaining known defects as strict xfail tests against the desired behaviour |
| `pyproject.toml`, `setup.py` | Packaging and pytest configuration. Metadata (including the `dev` extra) is duplicated across both; keep them in sync |
| `README.md` | User documentation. Update it with every config or behaviour change |

There is no CI or linter configuration.

## Environment

Nothing is installed globally. Use a virtualenv:

```bash
uv venv && uv pip install -e ".[dev]"      # or: python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pytest
```

Last verified against Python 3.13 and 3.14, beets 2.14.1, mediafile 0.17.0, mutagen 1.48.1. `pyproject.toml` declares `beets>=1.6.0` and Python ≥ 3.8; neither lower bound has been tested.

Use the Context7 MCP (`/websites/beets_readthedocs_io_en_stable`) for beets API questions, or read the installed sources under `.venv/lib/python*/site-packages/{beets,mediafile,mutagen}`. The installed source is the authority.

## How the code works

Config (`config.yaml`):

```yaml
plugins: [id3extract]
id3extract:
    fields:
        mood: TMOO                # short form: <beets field>: <tag>
        energy:                   # long form
            tag: TDLY
            type: int             # str (default), int, float, bool
    mappings:                     # deprecated: <tag>: <beets field>
        WOAS: track_id
```

`ID3ExtractPlugin.__init__` does everything; the plugin has no listeners and no commands.

1. `_configured_fields` merges `fields` and the legacy `mappings` into `{field: (config key, options)}`. The config key (`id3extract.fields.mood`, `id3extract.mappings.WOAS`) prefixes every error message. Any use of `mappings` logs a deprecation warning. A legacy entry whose tag is `WOAS` gets the internal option `spotify_id`, which users cannot set through `fields`.
2. Every entry is validated before anything is registered, so a bad config registers nothing. All failures are `UserError`:
   - the field is an attribute of `MediaFile` or a fixed `Item` field (`title`, `bitrate`, `path`, ...);
   - unknown option, missing `tag`, unknown `type`;
   - the tag does not parse (`parse_tag_spec`), or is already mapped to another field.
3. `parse_tag_spec` upper-cases the frame ID, looks it up in `mutagen.id3.Frames` and returns `(kind, frame_id, desc)`. `kind` is `text` for `T***` frames that are `TextFrame` subclasses and `url` for `W***` frames that are `UrlFrame` subclasses. `TXXX`, `WXXX`, anything with a `:` and every other frame (`COMM`, `TIPL`, `APIC`, ...) is rejected as not supported yet.
4. Each field is registered under the **beets field name** through `add_media_field` with a `TagField`:
   - MP3: stock `MP3StorageStyle(frame_id)` for text, `MP3URLStorageStyle(frame_id)` for URL frames (overrides `fetch`/`store`);
   - MP4: `----:com.apple.iTunes:<FRAME_ID>`;
   - Vorbis and other formats: `<FRAME_ID>`.

   From then on beets syncs the field in `Item.read()` and `Item.write()`.
5. `type` sets the `MediaField` `out_type` and, for anything but `str`, an entry in `item_types` so queries and sorting are numeric. The beets types are the null-preserving ones (`NullInteger`, `NULL_FLOAT`, the plugin's own `NullBoolean`): a file without the tag reads as `None`, and `None` is not written back. With `INTEGER` or `BOOLEAN` every such file would get a `0` tag on the next write.
6. `TagField.__get__` implements the legacy Spotify behaviour (`spotify_id`): a value starting with `https://open.spotify.com/track/` is reduced to its last path segment without the query string. `TagField.__set__` turns floats into `repr()` strings, because the storage styles would round them to two decimals.

## Tests

Run `.venv/bin/pytest`. It must be green before and after every change. Only MP3 files are covered; the MP4 and Vorbis storage styles are untested.

- `tests/test_fields.py` covers the `fields` option: read, unchanged write and changed write per tag kind and per `type`, `item.read()` after an edit outside beets, numeric queries, the warning for tags beets uses itself, and one parametrised case per validation error.
- `tests/test_legacy_mappings.py` covers `mappings`: the deprecation warning, combination with `fields`, and Spotify ID extraction from `WOAS` (including query strings, and not for other frames).
- `tests/test_defects.py` holds the entries of "Known defects" that have a planned fix, written against the *desired* behaviour and marked `@pytest.mark.xfail(strict=True, reason="fixed in step N")`. Because the marker is strict, the test fails as soon as the defect is fixed; in the change that fixes it, remove the marker and move the test to the regular suite. `pytest --runxfail tests/test_defects.py` shows how each one fails today.
- Tests import, write and inspect files through `tests/helpers.py` (`import_item`, `write_item`, `read_frames`) rather than calling beets themselves.
- Use frames beets does not own (`TMOO`, `TDLY`, `WOAS`, `WOAF`) unless the test is about the overlap; see "Known defects".

Fixtures in `tests/conftest.py`:

- `mp3_factory(*frames, name="test.mp3")` writes a synthetic MP3 into `tmp_path`, tagged with the given `mutagen.id3` frames, and returns its `Path`. Pass `bytes(path)` to `Item.from_path`.
- `plugin(config=None)` resets `beets.config`, sets `beets.config["id3extract"]` to the given dict, instantiates `ID3ExtractPlugin` and installs it as the only loaded plugin. On teardown it removes the MediaFile properties, `Item._media_fields` entries and event listeners the plugin registered, and clears beets' `cached_classproperty` cache. Always create the plugin through this fixture, or registrations leak into other tests.
- `lib` is a `Library(":memory:")` with the working directory switched to `tmp_path`, because the library drops `:memory:-before-*.bak` files into the working directory.

## Known defects

All reproduced against the versions listed above.

- **The legacy Spotify round trip is lossy.** With `mappings: {WOAS: field}` the URL is reduced to an ID on read, and the next write stores the bare ID in `WOAS`, replacing the URL. The bare ID reads back as the same ID, so database and file stay consistent. (xfail test)
- **`TXXX:<DESC>` and `WXXX:<DESC>` are rejected** as not supported yet. (xfail tests)
- **A tag that beets also uses is fought over.** Mapping, say, `TKEY` creates a second field next to beets' `initial_key`, and both are written to the same frame. `MediaFile.update` writes fields in alphabetical order, so the later name wins: with differing values, a field sorting before the beets field is overwritten by the stale beets value, and one sorting after it overwrites a `beet modify` of the beets field. A `None` in the later field deletes the frame. The plugin only logs a warning (`beets_field_for_frame`).
- **Existing items are not backfilled.** `beet update` skips files whose mtime has not changed, so items imported before a field was configured keep it unset until the file changes. There is no command to force a re-read.
- **No field name validation.** A field name that beets cannot query (containing `:` or spaces) is accepted.
- `beet modify 'field!'` removes the field from the database but not the tag from the file (the key is absent from `tags`, so the tag is left alone). This is how beets treats every plugin media field.

## beets and mediafile facts worth knowing

- `BeetsPlugin.add_media_field(name, descriptor)` adds the descriptor to the `MediaFile` class and `name` to `Item._media_fields`. From then on `Item.read()` (import, `beet update`) and `Item.write()` (`beet write`, `beet modify`) sync `item[name]` with the tag without any listener.
- `MediaFile.add_field` is class-global and permanent for the process, and raises `ValueError` if the name exists. Tests must isolate or undo registrations.
- Event listeners live in the class-level dicts `BeetsPlugin.listeners` and `BeetsPlugin._raw_listeners`, and `plugins.send` dispatches to them whether or not the plugin is in `plugins._instances`. A plugin instance that is merely dropped keeps receiving events.
- `beets.util.cached_classproperty` caches per class in `cached_classproperty.cache` (for example `Item._types`, `Item._queries`); clear it after changing the set of loaded plugins.
- `Item.write()` builds `tags` from media fields only, sends the `write` event, then calls `MediaFile.update(tags)`. A value of `None` deletes the tag; a key missing from the item leaves the tag untouched. `MediaFile.update` goes through the fields in alphabetical order.
- `Item.read()` assigns every media field, so a missing tag sets the field to the null value of its beets type: `None` for untyped flexible fields, `NullInteger` and `NULL_FLOAT`, but `0`, `False` and `""` for `INTEGER`, `BOOLEAN` and `STRING`.
- `MediaField.__get__` returns `None` for a missing tag whatever the `out_type`. `StorageStyle.serialize` formats floats with `float_places=2`.
- beets 2.14 catches every exception from a plugin's `__init__`, logs it with a traceback as `** error loading plugin` and carries on without the plugin, exit code 0. A `UserError` from the plugin therefore does not abort the command.
- `mutagen.id3.COMM` and other non-`T***` frames are `TextFrame` subclasses too, and `TIPL`/`TMCL` are not; check the frame ID prefix as well as the class.
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
