# ID3Extract Plugin for beets

A [beets](https://beets.io) plugin that maps ID3 text and URL frames to beets custom fields, in both directions. This plugin is particularly useful for preserving tags that beets ignores during your music library management with beets.

## Use Cases

- Keep the Spotify track ID from a `WOAS` (official audio source) URL in your beets database
- Keep any other streaming or store URL, or just the ID inside it
- Preserve ID3 text frames that beets ignores, such as `TMOO` (mood)
- Edit those values with `beet modify` and have them written back to the files

## Installation

### Using pip (recommended)

```bash
pip install beets-id3extract
```

### Manual Installation

1. Clone this repository or copy `id3extract.py` to your beets plugin directory:
```bash
cp id3extract.py ~/.config/beets/beetsplug/
```

2. Enable the plugin in your beets config file (`config.yaml`):
```yaml
plugins:
    - id3extract
```

## Configuration

Add an `id3extract` section to your `config.yaml` and list the beets fields you want, each with the tag it is stored in:

```yaml
id3extract:
    fields:
        mood: TMOO              # short form: <beets field>: <tag>
        energy:                 # long form
            tag: TDLY
            type: int
        spotify_track_id:
            tag: WOAS
            url: spotify-track
```

Each entry consists of:
- Key: the beets field. It must not be a field beets already has (`title`, `initial_key`, ...); see [Conflicts with beets](#conflicts-with-beets).
- Value: either the tag, or a mapping with these options:

| Option | Meaning |
| --- | --- |
| `tag` | The tag to read and write. Required. |
| `type` | `str` (default), `int`, `float` or `bool`. Typed fields can be queried and sorted numerically, for example `beet ls energy:5..`. |
| `url` | A built-in URL preset; see [URLs and IDs](#urls-and-ids). |
| `extract`, `format` | A custom URL pattern; see [URLs and IDs](#urls-and-ids). |
| `share_tag` | `yes` to map a tag that beets already uses for a field of its own. Default `no`. See [Conflicts with beets](#conflicts-with-beets). |

### Tags

A tag is the ID of an ID3 frame, in upper or lower case:

- text frames (`T***`, for example `TMOO`), except `TXXX`
- URL frames (`W***`, for example `WOAS`), except `WXXX`

Other frames, including `TXXX:<description>`, are not supported yet. Each tag can be mapped to one field only.

On MP4 files the tag is stored as the freeform atom `----:com.apple.iTunes:<TAG>`, and on Vorbis-style formats (FLAC, Ogg, APE, ...) as a comment named `<TAG>`.

### URLs and IDs

A tag often holds a URL when all you want in beets is the ID inside it. The `url` option selects a built-in preset that does the conversion in both directions:

```yaml
id3extract:
    fields:
        spotify_track_id:
            tag: WOAS
            url: spotify-track
```

```
WOAS: "https://open.spotify.com/track/2BOUrjXoRIo2YHVAyZyXVX?si=abc123"
↓ import, update
spotify_track_id: "2BOUrjXoRIo2YHVAyZyXVX"
↓ write, modify
WOAS: "https://open.spotify.com/track/2BOUrjXoRIo2YHVAyZyXVX"
```

| Preset | Recognised URLs | Written as |
| --- | --- | --- |
| `spotify-track` | `http(s)://open.spotify.com/track/<id>`, also with a language prefix such as `/intl-de/` and with a query string | `https://open.spotify.com/track/<id>` |

`spotify_track_id` is the field beets' own `spotify` plugin uses, so the two work together; any other field name is fine too.

For other services, give the two directions yourself:

```yaml
id3extract:
    fields:
        shop_id:
            tag: WPAY
            extract: '^https?://(?:www\.)?shop\.example/item/(?P<id>\d+)'
            format: 'https://www.shop.example/item/{id}'
```

- `extract` is a [regular expression](https://docs.python.org/3/library/re.html#regular-expression-syntax) with a named group `id`. When a tag value matches, the field gets the content of that group.
- `format` is the URL to write, with `{id}` in place of the ID. It should be a URL that `extract` matches.

How values are converted:

- **The tag is rewritten in the `format` form.** The original URL is not kept: a query string or any other part outside the ID is gone after the next write.
- **A value that does not match is left alone.** If the tag holds something `extract` does not match, such as a URL of another service, the field gets the whole value, and the same value is written back unchanged.
- You can set the field to a full URL (`beet modify spotify_track_id=https://open.spotify.com/track/...`). The tag is written in the `format` form, and the field shows the ID after the next `beet update`.
- `extract` without `format` makes the field read-only: the ID is read, but the plugin never changes or removes the tag. A warning is logged at startup.
- These options work with any supported tag, not only URL frames, but only with `type: str`.

### Conflicts with beets

beets refuses to start, with an error naming the config key, if

- a configured field is a field beets already has, or
- a configured tag is one beets already uses for a field of its own, such as `TKEY` (`initial_key`) or `TBPM` (`bpm`).

This also protects you when a new beets release starts using a field name or tag that you have mapped: beets stops before it touches any file, and you can rename your field or switch to the new beets field.

For a tag, you can override the check per field:

```yaml
id3extract:
    fields:
        initial_key_raw:
            tag: TKEY
            share_tag: yes
```

Both fields are then read from the same frame and both are written to it. If their values differ, for example after `beet modify` changed only one of them, the field whose name comes later in the alphabet ends up in the file, and an empty value in that field removes the frame. Only use `share_tag` for fields you do not edit.

There is no override for a field name that beets already has.

### Migrating from `mappings`

Earlier versions were configured the other way round, with `<tag>: <beets field>` entries under `mappings`:

```yaml
id3extract:
    mappings:
        WOAS: track_id
```

This still works but is deprecated and logs a warning. Move each entry to `fields` with key and value swapped:

```yaml
id3extract:
    fields:
        track_id: WOAS
```

Differences to be aware of:

- A `WOAS` entry under `mappings` is treated as `url: spotify-track` (see [URLs and IDs](#urls-and-ids)), as before. Under `fields` you have to add that option yourself, otherwise the URL is stored unchanged.
- Earlier versions wrote the bare Spotify ID back into `WOAS`, replacing the URL. The URL is now written. Files that already hold a bare ID are repaired by the next `beet write`.
- Tags that are not ID3 text or URL frame IDs are now rejected.
- Tags that beets uses itself are now rejected, and `mappings` has no way to allow them. Move the entry to `fields` and set `share_tag: yes`.
- Earlier versions also created a field named after the tag (for example `woas`). It is no longer filled; remove leftovers with `beet modify 'woas!'`.

## Operation

Each configured field becomes a regular beets media field, so beets keeps it in sync with the file like its built-in fields:

- **`beet import`** reads the tag into the field.
- **`beet update`** re-reads the tag from files that changed on disk. Use it to pick up tags edited with another program. Files whose modification time has not changed are skipped, so items imported before a field was configured only get it once their file changes.
- **`beet modify mood=calm`** changes the field and writes the tag.
- **`beet write`** writes the field to the tag.
- **`beet modify 'mood!'`** removes the field from the database only; the tag stays in the file.

## Debugging

A configuration mistake is reported when beets starts, naming the offending key, for example `id3extract.fields.mood: unknown ID3 frame 'TMOX'`. Recent beets versions then continue without the plugin. A [conflict with beets](#conflicts-with-beets) always stops beets.

Run beets with the verbose flag to see which fields are registered:

```bash
beet -v ls
```

## Requirements

- beets 1.6.0 or later
- mediafile
- mutagen (for ID3 tag handling)

## Development

To set up a development environment:

```bash
git clone https://github.com/your-username/beets-id3extract.git
cd beets-id3extract
pip install -e ".[dev]"
pytest
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.
