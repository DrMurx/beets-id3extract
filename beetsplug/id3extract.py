"""A plugin that maps arbitrary ID3 tags to beets custom fields.

Each configured field is registered as a beets media field, so beets itself
keeps it in sync with the file: tag -> database on import and `beet update`,
database -> tag on `beet write` and `beet modify`.

Configuration:
    The plugin is configured through the beets config.yaml file. List the
    beets fields under `fields` in the 'id3extract' section and give each the
    tag it is stored in.

    Example config:
        plugins:
            - id3extract

        id3extract:
            fields:
                spotify_url: WOAS       # short form: <beets field>: <tag>
                mood: TMOO
                energy:                 # long form
                    tag: TDLY
                    type: int           # str (default), int, float or bool
                spotify_track_id:
                    tag: WOAS
                    url: spotify-track  # keep only the ID of the URL
                shop_id:
                    tag: WPAY
                    extract: '^https://shop[.]example/item/(?P<id>[0-9]+)'
                    format: 'https://shop.example/item/{id}'

    A tag is the ID of an ID3 text frame (T***) or URL frame (W***). TXXX and
    WXXX frames are not supported yet. On MP4 files the tag is stored as
    `----:com.apple.iTunes:<TAG>`, on Vorbis-style formats as `<TAG>`.

    A field or tag that beets already uses itself aborts beets. For a tag
    this can be overridden per field with `share_tag: yes`.

    `extract` is a regular expression with a named group `id`. A tag value it
    matches is reduced to that group; any other value is kept as it is.
    `format` is the reverse: a template in which `{id}` is replaced by the
    field value when the tag is written. Without `format` the field is
    read-only. `url` selects a built-in pair of the two (see `URL_PRESETS`).

    The former `mappings` option (`<tag>: <beets field>`) is deprecated but
    still read. A `WOAS` mapping is treated as `url: spotify-track`.
"""

import re

import confuse
import mutagen.id3
from beets.dbcore import types
from beets.library import Item
from beets.plugins import BeetsPlugin
from beets.ui import UserError
from mediafile import MediaField, MediaFile, MP3StorageStyle, MP4StorageStyle, StorageStyle

# Preset name -> (extract, format), selected with the `url` option.
URL_PRESETS = {
    'spotify-track': (
        r'^https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/(?P<id>[A-Za-z0-9]+)',
        'https://open.spotify.com/track/{id}',
    ),
}


class ConflictError(SystemExit):
    """A configured field or tag collides with one beets uses itself.

    beets catches every `Exception` raised while a plugin loads and carries on
    without the plugin. A conflict must stop beets instead, so this derives
    from `SystemExit`: the message is printed and beets exits with status 1.
    """
    def __init__(self, message):
        super(ConflictError, self).__init__(f'id3extract: error: {message}')


class NullBoolean(types.Boolean):
    """A boolean type that keeps `None`, so a missing tag is not written as false."""
    @property
    def null(self):
        return None


# Config name -> (MediaField out_type, beets type of the flexible field).
# The beets types keep `None` so that a file without the tag does not get one
# on the next write.
FIELD_TYPES = {
    'str': (str, None),
    'int': (int, types.NullInteger()),
    'float': (float, types.NULL_FLOAT),
    'bool': (bool, NullBoolean()),
}


def parse_tag_spec(spec):
    """Parse a tag spec from the config into `(kind, frame_id, desc)`.

    `kind` is 'text' or 'url'. Raise `ValueError` for specs that are invalid
    or not supported.
    """
    frame_id, has_desc, desc = spec.partition(':')
    frame_id = frame_id.strip().upper()
    if has_desc or frame_id in ('TXXX', 'WXXX'):
        raise ValueError(f'{frame_id} frames are not supported yet')
    frame_class = mutagen.id3.Frames.get(frame_id)
    if frame_class is None:
        raise ValueError(f"unknown ID3 frame '{spec}'")
    if frame_id.startswith('T') and issubclass(frame_class, mutagen.id3.TextFrame):
        return 'text', frame_id, None
    if frame_id.startswith('W') and issubclass(frame_class, mutagen.id3.UrlFrame):
        return 'url', frame_id, None
    raise ValueError(f'{frame_id} frames are not supported yet, only text (T***) and URL (W***) frames')


def beets_field_for_frame(frame_id):
    """Return the name of a MediaFile field that already uses the ID3 frame, if any."""
    for name, descriptor in vars(MediaFile).items():
        for style in getattr(descriptor, '_styles', ()):
            if isinstance(style, MP3StorageStyle) and style.key == frame_id:
                return name
    return None


class Transform:
    """Converts between a tag value (such as a URL) and the ID kept in the field."""
    def __init__(self, extract, format=None):
        """Raise `ValueError` if `extract` or `format` is unusable."""
        try:
            self.pattern = re.compile(extract)
        except re.error as exc:
            raise ValueError(f"'extract' is not a valid regular expression: {exc}") from None
        if 'id' not in self.pattern.groupindex:
            raise ValueError("'extract' needs a named group (?P<id>...)")
        if format is not None and '{id}' not in format:
            raise ValueError("'format' needs the placeholder {id}")
        self.template = format

    @property
    def read_only(self):
        return self.template is None

    def extract(self, value):
        """Return the ID in a tag value, or `None` if the value is something else."""
        match = self.pattern.search(value)
        return match.group('id') if match and match.group('id') else None

    def to_field(self, value):
        """Convert a tag value to the field value."""
        return self.extract(value) or value

    def to_tag(self, value):
        """Convert a field value to the tag value.

        A value that is neither an ID nor something an ID can be extracted
        from was read from the file as it is, and is written back as it is.
        """
        tag_id = self.extract(value)
        if tag_id is not None:
            return self.template.replace('{id}', tag_id)
        formatted = self.template.replace('{id}', value)
        if self.extract(formatted) == value:
            return formatted
        return value


class MP3URLStorageStyle(MP3StorageStyle):
    """Storage for ID3 URL frames (like WOAS)."""
    def fetch(self, mutagen_file):
        try:
            return mutagen_file[self.key].url
        except KeyError:
            return None

    def store(self, mutagen_file, value):
        frame = mutagen.id3.Frames[self.key](url=value)
        mutagen_file.tags.setall(self.key, [frame])


class TagField(MediaField):
    """A media field for one configured tag."""
    def __init__(self, kind, frame_id, out_type=str, transform=None):
        self.transform = transform
        self.read_only = transform is not None and transform.read_only
        mp3_style = MP3URLStorageStyle if kind == 'url' else MP3StorageStyle
        super(TagField, self).__init__(
            mp3_style(frame_id, read_only=self.read_only),
            MP4StorageStyle(f'----:com.apple.iTunes:{frame_id}', read_only=self.read_only),
            StorageStyle(frame_id, read_only=self.read_only),
            out_type=out_type
        )

    def __get__(self, mediafile, owner=None):
        value = super(TagField, self).__get__(mediafile, owner)
        if self.transform and value is not None:
            value = self.transform.to_field(value)
        return value

    def __set__(self, mediafile, value):
        # The storage styles round floats to two decimal places.
        if isinstance(value, float):
            value = repr(value)
        if self.transform and not self.read_only and value is not None:
            value = self.transform.to_tag(str(value))
        super(TagField, self).__set__(mediafile, value)

    def __delete__(self, mediafile):
        # The styles' `read_only` flag does not cover deletion.
        if not self.read_only:
            super(TagField, self).__delete__(mediafile)


class ID3ExtractPlugin(BeetsPlugin):
    def __init__(self):
        super(ID3ExtractPlugin, self).__init__()
        self.config.add({'fields': {}, 'mappings': {}})

        # Validate the whole configuration before registering anything.
        media_fields = {}
        self.item_types = {}
        fields_by_frame = {}
        for field, (key, options) in self._configured_fields().items():
            if field in vars(MediaFile) or field in Item._fields:
                raise ConflictError(
                    f"{key}: '{field}' is already a beets field; choose another field name"
                )

            unknown = set(options) - {'tag', 'type', 'share_tag', 'url', 'extract', 'format'}
            if unknown:
                raise UserError(f"{key}: unknown option '{sorted(unknown)[0]}'")
            tag = options.get('tag')
            if not isinstance(tag, str):
                raise UserError(f'{key}: a tag is required')
            try:
                kind, frame_id, _ = parse_tag_spec(tag)
            except ValueError as exc:
                raise UserError(f'{key}: {exc}') from None
            if frame_id in fields_by_frame:
                raise UserError(
                    f"{key}: tag {frame_id} is already mapped to '{fields_by_frame[frame_id]}'"
                )
            fields_by_frame[frame_id] = field

            type_name = options.get('type', 'str')
            if type_name not in FIELD_TYPES:
                raise UserError(
                    f"{key}: unknown type '{type_name}', expected one of {', '.join(FIELD_TYPES)}"
                )
            out_type, item_type = FIELD_TYPES[type_name]
            if item_type is not None:
                self.item_types[field] = item_type

            share_tag = options.get('share_tag', False)
            if not isinstance(share_tag, bool):
                raise UserError(f"{key}: 'share_tag' must be yes or no")
            owner = beets_field_for_frame(frame_id)
            if owner and not share_tag:
                raise ConflictError(
                    f"{key}: tag {frame_id} is already used by the beets field '{owner}'; "
                    f"use that field, or set 'share_tag: yes' under id3extract.fields.{field} "
                    'to map the tag a second time'
                )
            if owner:
                self._log.debug("{}: sharing tag {} with the beets field '{}'", key, frame_id, owner)

            transform = self._transform(key, options)
            if transform and out_type is not str:
                raise UserError(f"{key}: 'url', 'extract' and 'format' need type str, not {type_name}")
            if transform and transform.read_only:
                self._log.warning("{}: 'extract' without 'format' makes the field read-only", key)
            media_fields[field] = TagField(kind, frame_id, out_type, transform)

        for field, descriptor in media_fields.items():
            self._log.debug('Registering field {}', field)
            self.add_media_field(field, descriptor)

    def _transform(self, key, options):
        """Return the `Transform` configured by `url` or `extract`/`format`, if any."""
        preset = options.get('url')
        extract, template = options.get('extract'), options.get('format')
        if preset is not None:
            if extract is not None or template is not None:
                raise UserError(f"{key}: 'url' cannot be combined with 'extract' or 'format'")
            if preset not in URL_PRESETS:
                raise UserError(
                    f"{key}: unknown url preset '{preset}', expected one of {', '.join(URL_PRESETS)}"
                )
            extract, template = URL_PRESETS[preset]
        if extract is None and template is None:
            return None
        if extract is None:
            raise UserError(f"{key}: 'format' needs 'extract'")
        if not isinstance(extract, str) or not isinstance(template, (str, type(None))):
            raise UserError(f"{key}: 'extract' and 'format' must be strings")
        try:
            return Transform(extract, template)
        except ValueError as exc:
            raise UserError(f'{key}: {exc}') from None

    def _config_mapping(self, name):
        """Return the config section `name` as a dict."""
        try:
            return self.config[name].get(dict)
        except confuse.ConfigError as exc:
            raise UserError(str(exc)) from None

    def _configured_fields(self):
        """Return `{beets field: (config key, options)}` from `fields` and the legacy `mappings`."""
        fields = {}
        for field, value in self._config_mapping('fields').items():
            key = f'id3extract.fields.{field}'
            if isinstance(value, str):
                value = {'tag': value}
            if not isinstance(value, dict):
                raise UserError(f'{key}: expected a tag or a mapping of options')
            fields[str(field)] = (key, dict(value))

        mappings = self._config_mapping('mappings')
        if mappings:
            self._log.warning(
                "the 'mappings' option is deprecated; use 'fields' with '<beets field>: <tag>' entries instead"
            )
        for tag, field in mappings.items():
            key = f'id3extract.mappings.{tag}'
            tag, field = str(tag), str(field)
            if field in fields:
                raise UserError(f"{key}: field '{field}' is configured more than once")
            options = {'tag': tag}
            if tag.strip().upper() == 'WOAS':
                options['url'] = 'spotify-track'
            fields[field] = (key, options)
        return fields
