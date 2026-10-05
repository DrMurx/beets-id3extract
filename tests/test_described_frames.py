"""`TXXX:<description>` and `WXXX:<description>` tags."""

import pytest
from beets.ui import UserError
from helpers import import_item, read_frames, write_item
from mutagen.id3 import TXXX, WXXX

from beetsplug.id3extract import ConflictError, parse_tag_spec


def txxx(desc, text):
    return TXXX(encoding=3, desc=desc, text=[text])


def wxxx(desc, url):
    return WXXX(encoding=3, desc=desc, url=url)


# Tag specs


@pytest.mark.parametrize(
    "spec, parsed",
    [
        ("TMOO", ("text", "TMOO", None)),
        ("woas", ("url", "WOAS", None)),
        ("TXXX:ENERGY", ("text", "TXXX", "ENERGY")),
        ("txxx:Energy Level", ("text", "TXXX", "Energy Level")),
        ("TXXX: ENERGY ", ("text", "TXXX", "ENERGY")),
        ("TXXX:a:b", ("text", "TXXX", "a:b")),
        ("WXXX:SHOP", ("url", "WXXX", "SHOP")),
    ],
)
def test_parse_tag_spec(spec, parsed):
    assert parse_tag_spec(spec) == parsed


# TXXX


def test_txxx_frame_is_read(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("FOO", "bar"), txxx("OTHER", "x"))

    assert import_item(lib, path)["foo"] == "bar"


def test_unchanged_write_keeps_txxx_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("FOO", "bar"), txxx("OTHER", "x"))

    write_item(import_item(lib, path))

    frames = read_frames(path)
    assert frames.getall("TXXX:FOO") == [txxx("FOO", "bar")]
    assert frames["TXXX:OTHER"].text == ["x"]


def test_changed_write_updates_txxx_frame_in_place(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("FOO", "bar"), txxx("OTHER", "x"))

    item = import_item(lib, path)
    item["foo"] = "baz"
    write_item(item)

    frames = read_frames(path)
    assert sorted(frame.desc for frame in frames.getall("TXXX")) == ["FOO", "OTHER"]
    assert frames["TXXX:FOO"].text == ["baz"]
    assert frames["TXXX:OTHER"].text == ["x"]


def test_write_creates_missing_txxx_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:Foo"}})
    path = mp3_factory()

    item = import_item(lib, path)
    assert item["foo"] is None

    item["foo"] = "bar"
    write_item(item)
    assert read_frames(path)["TXXX:Foo"].text == ["bar"]


def test_write_without_value_adds_no_txxx_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory()

    write_item(import_item(lib, path))

    assert read_frames(path).getall("TXXX") == []


def test_clearing_field_deletes_txxx_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("FOO", "bar"), txxx("OTHER", "x"))

    item = import_item(lib, path)
    item["foo"] = None
    write_item(item)

    assert [frame.desc for frame in read_frames(path).getall("TXXX")] == ["OTHER"]


def test_description_matches_case_insensitively(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("foo", "bar"))

    item = import_item(lib, path)
    assert item["foo"] == "bar"

    item["foo"] = "baz"
    write_item(item)
    # The existing frame is updated and keeps its spelling.
    assert read_frames(path).getall("TXXX") == [txxx("foo", "baz")]


def test_description_may_contain_colons_and_spaces(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:My Tool: Energy"}})
    path = mp3_factory(txxx("My Tool: Energy", "7"))

    item = import_item(lib, path)
    assert item["foo"] == "7"

    item["foo"] = "8"
    write_item(item)
    assert read_frames(path).getall("TXXX") == [txxx("My Tool: Energy", "8")]


def test_txxx_round_trip_with_id3v23(plugin, lib, mp3_factory):
    plugin({"fields": {"foo": "TXXX:FOO"}})
    path = mp3_factory(txxx("FOO", "bar"))

    item = import_item(lib, path)
    item["foo"] = "baz"
    item.write(id3v23=True)

    frames = read_frames(path)
    assert frames.version == (2, 3, 0)
    assert frames["TXXX:FOO"].text == ["baz"]
    item.read()
    assert item["foo"] == "baz"


def test_typed_txxx_field(plugin, lib, mp3_factory):
    plugin({"fields": {"energy": {"tag": "TXXX:ENERGY", "type": "int"}}})
    path = mp3_factory(txxx("ENERGY", "7"))

    item = import_item(lib, path)
    assert item["energy"] == 7

    item["energy"] = 8
    write_item(item)
    assert read_frames(path)["TXXX:ENERGY"].text == ["8"]


def test_transform_on_txxx_field(plugin, lib, mp3_factory):
    plugin({"fields": {"spotify_track_id": {"tag": "TXXX:SPOTIFY", "url": "spotify-track"}}})
    path = mp3_factory(txxx("SPOTIFY", "https://open.spotify.com/track/abc?si=1"))

    item = import_item(lib, path)
    assert item["spotify_track_id"] == "abc"

    write_item(item)
    assert read_frames(path)["TXXX:SPOTIFY"].text == ["https://open.spotify.com/track/abc"]


# WXXX


def test_wxxx_frame_round_trip(plugin, lib, mp3_factory):
    plugin({"fields": {"shop": "WXXX:SHOP"}})
    path = mp3_factory(wxxx("SHOP", "https://example.com/a"), wxxx("OTHER", "https://example.com/x"))

    item = import_item(lib, path)
    assert item["shop"] == "https://example.com/a"

    write_item(item)
    assert read_frames(path)["WXXX:SHOP"].url == "https://example.com/a"

    item["shop"] = "https://example.com/b"
    write_item(item)
    frames = read_frames(path)
    assert sorted(frame.desc for frame in frames.getall("WXXX")) == ["OTHER", "SHOP"]
    assert frames["WXXX:SHOP"].url == "https://example.com/b"
    assert frames["WXXX:OTHER"].url == "https://example.com/x"


def test_wxxx_frame_is_created_and_deleted(plugin, lib, mp3_factory):
    plugin({"fields": {"shop": "WXXX:SHOP"}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["shop"] = "https://example.com/a"
    write_item(item)
    assert read_frames(path)["WXXX:SHOP"].url == "https://example.com/a"

    item["shop"] = None
    write_item(item)
    assert read_frames(path).getall("WXXX") == []


def test_transform_on_wxxx_field(plugin, lib, mp3_factory):
    plugin({"fields": {"spotify_track_id": {"tag": "WXXX:SPOTIFY", "url": "spotify-track"}}})
    path = mp3_factory(wxxx("SPOTIFY", "https://open.spotify.com/track/abc?si=1"))

    item = import_item(lib, path)
    assert item["spotify_track_id"] == "abc"

    item["spotify_track_id"] = "def"
    write_item(item)
    assert read_frames(path)["WXXX:SPOTIFY"].url == "https://open.spotify.com/track/def"


def test_txxx_and_wxxx_with_plain_frames(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO", "energy": "TXXX:ENERGY", "link": "WOAS", "shop": "WXXX:SHOP"}})
    path = mp3_factory()

    item = import_item(lib, path)
    item.update({"mood": "calm", "energy": "7", "link": "https://example.com/l", "shop": "https://example.com/s"})
    write_item(item)
    item.read()

    assert (item["mood"], item["energy"], item["link"], item["shop"]) == (
        "calm",
        "7",
        "https://example.com/l",
        "https://example.com/s",
    )


# Collisions


@pytest.mark.parametrize(
    "tag, owner",
    [
        ("TXXX:MusicBrainz Album Id", "mb_albumid"),
        ("TXXX:musicbrainz album id", "mb_albumid"),
        ("TXXX:REPLAYGAIN_TRACK_GAIN", "rg_track_gain"),
        ("TXXX:ASIN", "asin"),
        # Not a TXXX frame in beets, but the same Vorbis comment on FLAC and Ogg files.
        ("TXXX:BPM", "bpm"),
        ("WXXX:ARTIST", "artist"),
    ],
)
def test_description_that_beets_uses_aborts(plugin, tag, owner):
    with pytest.raises(ConflictError, match=rf"id3extract\.fields\.foo: tag .* beets field '{owner}'"):
        plugin({"fields": {"foo": tag}})


def test_share_tag_allows_description_that_beets_uses(plugin, lib, mp3_factory):
    plugin({"fields": {"asin_raw": {"tag": "TXXX:ASIN", "share_tag": True}}})
    path = mp3_factory(txxx("ASIN", "B000002UAL"))

    item = import_item(lib, path)

    assert item["asin_raw"] == "B000002UAL"
    assert item["asin"] == "B000002UAL"


@pytest.mark.parametrize(
    "fields, message",
    [
        ({"a": "TXXX:FOO", "b": "txxx:foo"}, r"id3extract\.fields\.b: tag TXXX:foo is already mapped to 'a'"),
        ({"a": "WXXX:FOO", "b": "WXXX:Foo"}, r"id3extract\.fields\.b: tag WXXX:Foo is already mapped to 'a'"),
        ({"a": "TXXX:FOO", "b": "WXXX:FOO"}, r"id3extract\.fields\.b: tag WXXX:FOO and the tag of 'a' .* non-MP3"),
        ({"a": "TMOO", "b": "TXXX:TMOO"}, r"id3extract\.fields\.b: tag TXXX:TMOO and the tag of 'a' .* non-MP3"),
    ],
)
def test_same_tag_for_two_fields_is_a_user_error(plugin, fields, message):
    with pytest.raises(UserError, match=message):
        plugin({"fields": fields})


def test_different_descriptions_do_not_collide(plugin):
    plugin({"fields": {"a": "TXXX:FOO", "b": "TXXX:BAR", "c": "WXXX:BAZ"}})
