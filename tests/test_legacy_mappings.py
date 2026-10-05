"""The deprecated `mappings` option (`<tag>: <beets field>`)."""

import pytest
from beets.library import Item
from beets.ui import UserError
from beetsplug.id3extract import ConflictError
from helpers import SPOTIFY_ID, SPOTIFY_URL, import_item, read_frames, write_item
from mutagen.id3 import TIT2, TMOO, WOAF, WOAS

# Config


def test_mappings_are_registered_as_media_fields(plugin):
    plugin({"mappings": {"WOAS": "track_id", "WOAF": "file_url"}})

    assert {"track_id", "file_url"} <= Item._media_fields


def test_mappings_log_a_deprecation_warning(plugin, caplog):
    plugin({"mappings": {"WOAS": "track_id"}})

    assert "'mappings' option is deprecated" in caplog.text


def test_fields_do_not_log_a_deprecation_warning(plugin, caplog):
    plugin({"fields": {"track_id": "WOAS"}})

    assert "deprecated" not in caplog.text


def test_mappings_and_fields_are_combined(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}, "fields": {"file_url": "WOAF"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL), WOAF(url="https://example.com/file"))

    item = import_item(lib, path)

    assert item["track_id"] == SPOTIFY_ID
    assert item["file_url"] == "https://example.com/file"


def test_field_in_both_mappings_and_fields_is_a_user_error(plugin):
    with pytest.raises(UserError, match=r"id3extract\.mappings\.WOAS"):
        plugin({"mappings": {"WOAS": "track_id"}, "fields": {"track_id": "WOAF"}})


def test_unknown_tag_is_a_user_error(plugin):
    with pytest.raises(UserError, match=r"id3extract\.mappings\.TITLE"):
        plugin({"mappings": {"TITLE": "x"}})


@pytest.mark.parametrize("mappings", [{"TMOO": "title"}, {"TKEY": "mykey"}])
def test_collision_with_beets_aborts(plugin, mappings):
    with pytest.raises(ConflictError, match=r"id3extract\.mappings\."):
        plugin({"mappings": mappings})


# Read


def test_spotify_url_is_reduced_to_track_id(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)

    assert item["track_id"] == SPOTIFY_ID


def test_spotify_url_query_string_is_stripped(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=f"{SPOTIFY_URL}?si=abc123"))

    item = import_item(lib, path)

    assert item["track_id"] == SPOTIFY_ID


def test_non_spotify_url_is_kept_whole(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url="https://example.com/track/42"))

    item = import_item(lib, path)

    assert item["track_id"] == "https://example.com/track/42"


def test_spotify_url_in_other_frame_is_kept_whole(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAF": "file_url"}})
    path = mp3_factory(WOAF(url=SPOTIFY_URL))

    item = import_item(lib, path)

    assert item["file_url"] == SPOTIFY_URL


def test_lowercase_tag_name_behaves_like_uppercase(plugin, lib, mp3_factory):
    plugin({"mappings": {"woas": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)

    assert item["track_id"] == SPOTIFY_ID


def test_no_shadow_field_named_after_tag(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)

    assert "woas" not in item.keys()


def test_text_frame_is_read(plugin, lib, mp3_factory):
    plugin({"mappings": {"TMOO": "mood"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    item = import_item(lib, path)

    assert item["mood"] == "calm"


def test_absent_tag_leaves_field_empty(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(TIT2(encoding=3, text=["Title"]))

    item = import_item(lib, path)

    assert item["track_id"] is None


def test_imported_value_is_stored_in_library(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)
    item.store()

    assert lib.get_item(item.id)["track_id"] == SPOTIFY_ID


# Write


def test_write_stores_field_in_mapped_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory()

    item = import_item(lib, path)
    item["track_id"] = SPOTIFY_ID
    write_item(item)

    assert read_frames(path)["WOAS"].url == SPOTIFY_URL


def test_spotify_url_survives_import_and_write(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)
    write_item(item)

    assert read_frames(path)["WOAS"].url == SPOTIFY_URL


def test_non_spotify_url_survives_import_and_write(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url="https://example.com/track/42"))

    item = import_item(lib, path)
    write_item(item)

    assert read_frames(path)["WOAS"].url == "https://example.com/track/42"


def test_write_without_value_adds_no_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory()

    item = import_item(lib, path)
    write_item(item)

    assert "WOAS" not in read_frames(path)


def test_unchanged_write_keeps_text_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"TMOO": "mood"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    item = import_item(lib, path)
    write_item(item)

    assert read_frames(path)["TMOO"].text == ["calm"]


def test_changed_write_produces_text_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"TMOO": "mood"}})
    path = mp3_factory(TMOO(encoding=3, text=["calm"]))

    item = import_item(lib, path)
    item["mood"] = "tense"
    write_item(item)

    frames = read_frames(path)
    assert frames["TMOO"].text == ["tense"]
    assert "WOAS" not in frames
