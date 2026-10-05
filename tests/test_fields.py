"""The `fields` option (`<beets field>: <tag>`)."""

import pytest
from beets import dbcore
from beets.library import Item
from beets.ui import UserError
from helpers import import_item, read_frames, write_item
from mutagen.id3 import ID3, TDLY, TKEY, TMOO, WOAF, WOAS

# Text frames


def test_text_frame_round_trip(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    item = import_item(lib, path)
    assert item["mood"] == "calm"

    write_item(item)
    assert read_frames(path)["TMOO"].text == ["calm"]

    item["mood"] = "tense"
    write_item(item)
    assert read_frames(path).getall("TMOO") == [TMOO(encoding=3, text=["tense"])]


def test_long_form_is_equivalent_to_short_form(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": {"tag": "TMOO"}}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    assert import_item(lib, path)["mood"] == "calm"


def test_tag_name_is_case_insensitive(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "tmoo"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    assert import_item(lib, path)["mood"] == "calm"


# URL frames


@pytest.mark.parametrize("frame", [WOAS, WOAF])
def test_url_frame_round_trip(plugin, lib, mp3_factory, frame):
    tag = frame.__name__
    plugin({"fields": {"link": tag}})
    path = mp3_factory(frame(url="https://example.com/a"))

    item = import_item(lib, path)
    assert item["link"] == "https://example.com/a"

    write_item(item)
    assert read_frames(path)[tag].url == "https://example.com/a"

    item["link"] = "https://example.com/b"
    write_item(item)
    assert read_frames(path).getall(tag) == [frame(url="https://example.com/b")]


def test_spotify_url_is_not_reduced(plugin, lib, mp3_factory):
    plugin({"fields": {"link": "WOAS"}})
    path = mp3_factory(WOAS(url="https://open.spotify.com/track/abc"))

    assert import_item(lib, path)["link"] == "https://open.spotify.com/track/abc"


# Native sync


def test_read_picks_up_tag_edited_outside_beets(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))
    item = import_item(lib, path)

    tags = ID3(path)
    tags.setall("TMOO", [TMOO(encoding=3, text=["tense"])])
    tags.save()
    item.read()

    assert item["mood"] == "tense"


def test_write_creates_missing_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO"}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["mood"] = "calm"
    write_item(item)

    assert read_frames(path)["TMOO"].text == ["calm"]


def test_write_without_value_adds_no_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO", "energy": {"tag": "TDLY", "type": "int"}}})
    path = mp3_factory()

    item = import_item(lib, path)
    write_item(item)

    frames = read_frames(path)
    assert "TMOO" not in frames
    assert "TDLY" not in frames


def test_clearing_field_deletes_frame(plugin, lib, mp3_factory):
    plugin({"fields": {"mood": "TMOO"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    item = import_item(lib, path)
    item["mood"] = None
    write_item(item)

    assert "TMOO" not in read_frames(path)


def test_value_survives_library_round_trip(plugin, lib, mp3_factory):
    plugin({"fields": {"energy": {"tag": "TDLY", "type": "int"}}})
    path = mp3_factory(TDLY(encoding=3, text=["7"]))

    item = import_item(lib, path)
    item.store()

    assert lib.get_item(item.id)["energy"] == 7


# Types


@pytest.mark.parametrize(
    "type_name, text, value, changed, changed_text",
    [
        ("str", "7", "7", "8", "8"),
        ("int", "7", 7, 8, "8"),
        ("float", "0.125", 0.125, 0.3333, "0.3333"),
        ("bool", "1", True, False, "0"),
    ],
)
def test_typed_field_round_trip(plugin, lib, mp3_factory, type_name, text, value, changed, changed_text):
    plugin({"fields": {"energy": {"tag": "TDLY", "type": type_name}}})
    path = mp3_factory(TDLY(encoding=3, text=[text]))

    item = import_item(lib, path)
    assert item["energy"] == value
    assert type(item["energy"]) is type(value)

    item["energy"] = changed
    write_item(item)
    assert read_frames(path)["TDLY"].text == [changed_text]

    item.read()
    assert item["energy"] == changed


def test_typed_field_is_queried_numerically(plugin, lib, mp3_factory):
    plugin({"fields": {"energy": {"tag": "TDLY", "type": "int"}}})
    for energy in ("3", "7", "10"):
        path = mp3_factory(TDLY(encoding=3, text=[energy]), name=f"{energy}.mp3")
        import_item(lib, path).store()

    assert sorted(item["energy"] for item in lib.items("energy:5..")) == [7, 10]


def test_typed_field_declares_item_type(plugin):
    instance = plugin({"fields": {"mood": "TMOO", "energy": {"tag": "TDLY", "type": "int"}}})

    assert set(instance.item_types) == {"energy"}
    assert isinstance(Item._types["energy"], dbcore.types.NullInteger)


# Tags that beets uses itself


def test_tag_shared_with_beets_field_logs_a_warning(plugin, caplog):
    plugin({"fields": {"mykey": "TKEY"}})

    assert "id3extract.fields.mykey" in caplog.text
    assert "'initial_key'" in caplog.text


def test_tag_shared_with_beets_field_is_read(plugin, lib, mp3_factory):
    plugin({"fields": {"mykey": "TKEY"}})
    path = mp3_factory(TKEY(encoding=3, text=["Am"]))

    item = import_item(lib, path)

    assert item["mykey"] == "Am"
    assert item["initial_key"] == "Am"


def test_other_tag_logs_no_warning(plugin, caplog):
    plugin({"fields": {"mood": "TMOO"}})

    assert caplog.text == ""


# Validation


@pytest.mark.parametrize(
    "config, message",
    [
        ({"fields": ["TMOO"]}, r"id3extract\.fields"),
        ({"fields": "TMOO"}, r"id3extract\.fields"),
        ({"mappings": ["TMOO"]}, r"id3extract\.mappings"),
        ({"fields": {"mood": 5}}, r"id3extract\.fields\.mood: expected a tag"),
        ({"fields": {"mood": {"type": "int"}}}, r"id3extract\.fields\.mood: a tag is required"),
        ({"fields": {"mood": {"tag": "TMOO", "typ": "int"}}}, r"id3extract\.fields\.mood: unknown option 'typ'"),
        ({"fields": {"mood": {"tag": "TMOO", "spotify_id": True}}}, r"id3extract\.fields\.mood: unknown option"),
        ({"fields": {"mood": {"tag": "TMOO", "type": "date"}}}, r"id3extract\.fields\.mood: unknown type 'date'"),
        ({"fields": {"mood": "XXXX"}}, r"id3extract\.fields\.mood: unknown ID3 frame 'XXXX'"),
        ({"fields": {"mood": "TXXX:MOOD"}}, r"id3extract\.fields\.mood: TXXX .* not supported yet"),
        ({"fields": {"mood": "TXXX"}}, r"id3extract\.fields\.mood: TXXX .* not supported yet"),
        ({"fields": {"link": "WXXX:LINK"}}, r"id3extract\.fields\.link: WXXX .* not supported yet"),
        ({"fields": {"note": "COMM"}}, r"id3extract\.fields\.note: COMM frames are not supported yet"),
        ({"fields": {"people": "TIPL"}}, r"id3extract\.fields\.people: TIPL frames are not supported yet"),
        ({"fields": {"title": "TMOO"}}, r"id3extract\.fields\.title: 'title' is already a beets field"),
        ({"fields": {"bitrate": "TMOO"}}, r"id3extract\.fields\.bitrate: 'bitrate' is already a beets field"),
        ({"fields": {"path": "TMOO"}}, r"id3extract\.fields\.path: 'path' is already a beets field"),
        ({"fields": {"mood": "TMOO", "mood2": "tmoo"}}, r"id3extract\.fields\.mood2: tag TMOO is already mapped to 'mood'"),
        ({"mappings": {"TXXX:FOO": "foo"}}, r"id3extract\.mappings\.TXXX:FOO: TXXX"),
    ],
)
def test_invalid_config_is_a_user_error(plugin, config, message):
    with pytest.raises(UserError, match=message):
        plugin(config)


def test_invalid_config_registers_nothing(plugin):
    with pytest.raises(UserError):
        plugin({"fields": {"mood": "TMOO", "other": "XXXX"}})

    assert "mood" not in Item._media_fields
