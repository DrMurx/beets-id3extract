"""The `url`, `extract` and `format` options."""

import pytest
from beets.ui import UserError
from helpers import SPOTIFY_ID, SPOTIFY_URL, import_item, read_frames, write_item
from mutagen.id3 import TMOO, WOAS, WPAY

from beetsplug.id3extract import URL_PRESETS, Transform

SHOP = {
    "tag": "WPAY",
    "extract": r"^https?://(?:www\.)?shop\.example/item/[^/]+/(?P<id>\d+)",
    "format": "https://www.shop.example/item/-/{id}",
}

# Preset name -> [(URL in the file, ID in the database, URL written back)]
PRESET_CASES = {
    "spotify-track": [
        (SPOTIFY_URL, SPOTIFY_ID, SPOTIFY_URL),
        (f"{SPOTIFY_URL}?si=abc123", SPOTIFY_ID, SPOTIFY_URL),
        (f"http://open.spotify.com/track/{SPOTIFY_ID}", SPOTIFY_ID, SPOTIFY_URL),
        (f"https://open.spotify.com/intl-de/track/{SPOTIFY_ID}?si=abc123", SPOTIFY_ID, SPOTIFY_URL),
    ],
    "deezer-track": [
        ("https://www.deezer.com/track/3135556", "3135556", "https://www.deezer.com/track/3135556"),
        ("https://www.deezer.com/de/track/3135556?utm_source=x", "3135556", "https://www.deezer.com/track/3135556"),
        ("http://deezer.com/track/3135556", "3135556", "https://www.deezer.com/track/3135556"),
    ],
    "tidal-track": [
        ("https://tidal.com/track/234834560", "234834560", "https://tidal.com/track/234834560"),
        ("https://tidal.com/track/234834560/u", "234834560", "https://tidal.com/track/234834560"),
        ("https://tidal.com/browse/track/79930135", "79930135", "https://tidal.com/track/79930135"),
        ("https://listen.tidal.com/track/79930135", "79930135", "https://tidal.com/track/79930135"),
    ],
    "qobuz-track": [
        ("https://open.qobuz.com/track/49282452", "49282452", "https://open.qobuz.com/track/49282452"),
        ("https://play.qobuz.com/track/49282452", "49282452", "https://open.qobuz.com/track/49282452"),
    ],
    "youtube-video": [
        ("https://www.youtube.com/watch?v=dQw4w9WgXcQ", "dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://youtube.com/watch?v=dQw4w9WgXcQ&t=42s", "dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://www.youtube.com/watch?list=PL1&v=a_b-c1d2e3F", "a_b-c1d2e3F", "https://www.youtube.com/watch?v=a_b-c1d2e3F"),
        ("https://music.youtube.com/watch?v=dQw4w9WgXcQ&si=x", "dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
        ("https://youtu.be/dQw4w9WgXcQ?si=x", "dQw4w9WgXcQ", "https://www.youtube.com/watch?v=dQw4w9WgXcQ"),
    ],
    "soundcloud-track": [
        ("https://soundcloud.com/forss/flickermood", "forss/flickermood", "https://soundcloud.com/forss/flickermood"),
        ("https://soundcloud.com/forss/flickermood?si=abc&utm_source=clipboard", "forss/flickermood", "https://soundcloud.com/forss/flickermood"),
        ("https://m.soundcloud.com/forss/flickermood/", "forss/flickermood", "https://soundcloud.com/forss/flickermood"),
        ("http://www.soundcloud.com/some-user_1/a-track-2#t=1:00", "some-user_1/a-track-2", "https://soundcloud.com/some-user_1/a-track-2"),
    ],
}

# Preset name -> tag values the preset must leave alone
PRESET_FOREIGN = {
    "spotify-track": [
        "https://open.spotify.com/album/4aawyAB9vmqN3uQ7FjRGTy",
        "https://example.com/track/42",
        "spotify:track:2BOUrjXoRIo2YHVAyZyXVX",
    ],
    "deezer-track": ["https://www.deezer.com/album/302127", "https://www.deezer.com/track/abc", "https://example.com/track/1"],
    "tidal-track": ["https://tidal.com/album/77646168", "https://tidal.com/browse/album/1", "https://example.com/track/1"],
    "qobuz-track": ["https://open.qobuz.com/album/0060254788359", "https://www.qobuz.com/track/1"],
    "youtube-video": [
        "https://www.youtube.com/playlist?list=PL1234567890",
        "https://www.youtube.com/watch?v=tooshort",
        "https://www.youtube.com/watch?v=dQw4w9WgXcQtoolong",
        "https://www.youtube.com/watch?vv=dQw4w9WgXcQ",
        "https://www.youtube.com/@channel",
    ],
    "soundcloud-track": [
        "https://soundcloud.com/forss",
        "https://soundcloud.com/forss/sets/soulhack",
        "https://soundcloud.com/forss/tracks",
        "https://soundcloud.com/forss/flickermood/s-AbCdEf",
        "https://on.soundcloud.com/AbCdEf",
    ],
}

# Presets


def test_every_preset_has_cases():
    assert set(PRESET_CASES) == set(URL_PRESETS)
    assert set(PRESET_FOREIGN) == set(URL_PRESETS)


@pytest.mark.parametrize(
    "preset, url, tag_id, canonical",
    [(preset, *case) for preset, cases in PRESET_CASES.items() for case in cases],
)
def test_preset_round_trip(plugin, lib, mp3_factory, preset, url, tag_id, canonical):
    plugin({"fields": {"link_id": {"tag": "WOAS", "url": preset}}})
    path = mp3_factory(WOAS(url=url))

    item = import_item(lib, path)
    assert item["link_id"] == tag_id

    write_item(item)
    assert read_frames(path)["WOAS"].url == canonical

    item.read()
    assert item["link_id"] == tag_id


@pytest.mark.parametrize(
    "preset, url",
    [(preset, url) for preset, urls in PRESET_FOREIGN.items() for url in urls],
)
def test_preset_keeps_foreign_value_unchanged(plugin, lib, mp3_factory, preset, url):
    plugin({"fields": {"link_id": {"tag": "WOAS", "url": preset}}})
    path = mp3_factory(WOAS(url=url))

    item = import_item(lib, path)
    assert item["link_id"] == url

    write_item(item)
    assert read_frames(path)["WOAS"].url == url


@pytest.mark.parametrize(
    "preset, tag_id, canonical",
    sorted({(preset, tag_id, canonical) for preset, cases in PRESET_CASES.items() for _, tag_id, canonical in cases}),
)
def test_preset_writes_id_as_url(plugin, lib, mp3_factory, preset, tag_id, canonical):
    plugin({"fields": {"link_id": {"tag": "WOAS", "url": preset}}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["link_id"] = tag_id
    write_item(item)

    assert read_frames(path)["WOAS"].url == canonical


# extract and format


def test_extract_and_format_round_trip(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory(WPAY(url="http://shop.example/item/some-title/12345"))

    item = import_item(lib, path)
    assert item["shop_id"] == "12345"

    write_item(item)
    assert read_frames(path)["WPAY"].url == "https://www.shop.example/item/-/12345"


def test_changed_id_is_written_as_url(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory(WPAY(url="https://www.shop.example/item/-/12345"))

    item = import_item(lib, path)
    item["shop_id"] = "678"
    write_item(item)

    assert read_frames(path)["WPAY"].url == "https://www.shop.example/item/-/678"


def test_url_in_field_is_written_in_canonical_form(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["shop_id"] = "http://shop.example/item/some-title/678"
    write_item(item)

    assert read_frames(path)["WPAY"].url == "https://www.shop.example/item/-/678"


def test_value_that_is_not_an_id_is_written_unchanged(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["shop_id"] = "not-a-number"
    write_item(item)

    assert read_frames(path)["WPAY"].url == "not-a-number"


def test_transform_applies_to_text_frames(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": {"tag": "TMOO", "extract": "^mood=(?P<id>.+)$", "format": "mood={id}"}}})
    path = mp3_factory(TMOO(encoding=3, text=["mood=calm"]))

    item = import_item(lib, path)
    assert item["mood"] == "calm"

    item["mood"] = "tense"
    write_item(item)
    assert read_frames(path)["TMOO"].text == ["mood=tense"]


def test_absent_tag_stays_absent(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory()

    item = import_item(lib, path)
    assert item["shop_id"] is None

    write_item(item)
    assert "WPAY" not in read_frames(path)


def test_clearing_field_deletes_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"shop_id": SHOP}})
    path = mp3_factory(WPAY(url="https://www.shop.example/item/-/12345"))

    item = import_item(lib, path)
    item["shop_id"] = None
    write_item(item)

    assert "WPAY" not in read_frames(path)


# The write rule


@pytest.mark.parametrize(
    "value, tag",
    [
        ("12345", "https://www.shop.example/item/-/12345"),
        ("http://shop.example/item/title/12345", "https://www.shop.example/item/-/12345"),
        ("https://www.shop.example/item/-/12345", "https://www.shop.example/item/-/12345"),
        ("https://other.example/12345", "https://other.example/12345"),
        ("12a", "12a"),
        ("", ""),
    ],
)
def test_to_tag(value, tag):
    transform = Transform(SHOP["extract"], SHOP["format"])

    assert transform.to_tag(value) == tag
    assert transform.to_field(tag) == transform.to_field(value)


# Read-only fields


def test_extract_without_format_logs_a_warning(plugin, caplog):
    plugin({"fields": {"shop_id": {"tag": "WPAY", "extract": SHOP["extract"]}}})

    assert "id3extract.fields.shop_id: 'extract' without 'format' makes the field read-only" in caplog.text


@pytest.mark.parametrize("value", ["678", None])
def test_extract_without_format_never_changes_the_file(plugin, lib, mp3_factory, value):
    plugin({"fields": {"shop_id": {"tag": "WPAY", "extract": SHOP["extract"]}}})
    url = "http://shop.example/item/some-title/12345"
    path = mp3_factory(WPAY(url=url))

    item = import_item(lib, path)
    assert item["shop_id"] == "12345"

    item["shop_id"] = value
    write_item(item)
    assert read_frames(path)["WPAY"].url == url


# Validation


@pytest.mark.parametrize(
    "options, message",
    [
        ({"url": "nope"}, r"unknown url preset 'nope', expected one of spotify-track, deezer-track"),
        ({"url": "spotify-track", "extract": "(?P<id>.+)"}, r"'url' cannot be combined"),
        ({"url": "spotify-track", "format": "{id}"}, r"'url' cannot be combined"),
        ({"format": "x/{id}"}, r"'format' needs 'extract'"),
        ({"extract": "(?P<id>.+"}, r"'extract' is not a valid regular expression"),
        ({"extract": "x/(.+)"}, r"'extract' needs a named group"),
        ({"extract": "x/(?P<id>.+)", "format": "x/"}, r"'format' needs the placeholder \{id\}"),
        ({"extract": 5}, r"'extract' and 'format' must be strings"),
        ({"extract": "x/(?P<id>.+)", "format": 5}, r"'extract' and 'format' must be strings"),
        ({"url": "spotify-track", "type": "int"}, r".* need type str, not int"),
    ],
)
def test_invalid_transform_is_a_user_error(plugin, options, message):
    with pytest.raises(UserError, match=r"id3extract\.fields\.link_id: " + message):
        plugin({"fields": {"link_id": {"tag": "WOAS", **options}}})
