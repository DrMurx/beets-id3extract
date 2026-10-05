"""Known defects, tested against the desired behaviour.

Each test is a strict xfail naming the step that fixes it. Once the fix lands
the test passes, which strict mode reports as a failure until the marker is
removed.
"""

import pytest
from beets.ui import UserError
from helpers import SPOTIFY_ID, SPOTIFY_URL, import_item, read_frames, write_item
from mutagen.id3 import TKEY, TXXX, WOAS

# Text frames


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_text_frame_is_read(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TKEY": "mykey"}})
    path = mp3_factory(TKEY(encoding=3, text=["Am"]))

    item = import_item(instance, lib, path)

    assert item["mykey"] == "Am"


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_unchanged_write_keeps_text_frame(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TKEY": "mykey"}})
    path = mp3_factory(TKEY(encoding=3, text=["Am"]))

    item = import_item(instance, lib, path)
    write_item(item)

    assert read_frames(path)["TKEY"].text == ["Am"]


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_changed_write_produces_text_frame(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TKEY": "mykey"}})
    path = mp3_factory(TKEY(encoding=3, text=["Am"]))

    item = import_item(instance, lib, path)
    item["mykey"] = "Bm"
    write_item(item)

    frames = read_frames(path)
    assert frames["TKEY"].text == ["Bm"]
    assert "WOAS" not in frames


# Field registration


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_no_shadow_field_named_after_tag(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(instance, lib, path)

    assert "woas" not in item.keys()


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_lowercase_tag_name_behaves_like_uppercase(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"woas": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(instance, lib, path)

    assert item["track_id"] == SPOTIFY_ID


@pytest.mark.xfail(strict=True, reason="fixed in step 2")
def test_collision_with_mediafile_property_is_a_user_error(plugin):
    with pytest.raises(UserError):
        plugin({"mappings": {"TITLE": "x"}})


# URL round trip


@pytest.mark.xfail(strict=True, reason="fixed in step 3")
def test_spotify_url_survives_import_and_write(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(instance, lib, path)
    write_item(item)

    assert read_frames(path)["WOAS"].url == SPOTIFY_URL


# TXXX frames


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_txxx_frame_is_read(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(instance, lib, path)

    assert item["foo"] == "bar"


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_unchanged_write_keeps_txxx_frame(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(instance, lib, path)
    write_item(item)

    assert read_frames(path)["TXXX:FOO"].text == ["bar"]


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_changed_write_updates_txxx_frame(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(instance, lib, path)
    item["foo"] = "baz"
    write_item(item)

    assert read_frames(path)["TXXX:FOO"].text == ["baz"]
