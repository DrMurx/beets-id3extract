"""Characterization tests: what the plugin does today."""

from beets.library import Item
from helpers import SPOTIFY_ID, SPOTIFY_URL, import_album, import_item
from mutagen.id3 import TIT2, WOAS

# Config


def test_mappings_are_loaded(plugin):
    instance = plugin({"mappings": {"WOAS": "track_id", "WOAF": "file_url"}})

    assert instance.mappings == [("WOAS", "track_id"), ("WOAF", "file_url")]


def test_missing_mappings_key_yields_no_mappings(plugin):
    assert plugin({}).mappings == []


# Import


def test_spotify_url_is_reduced_to_track_id(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(instance, lib, path)

    assert item["track_id"] == SPOTIFY_ID


def test_spotify_url_query_string_is_stripped(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=f"{SPOTIFY_URL}?si=abc123"))

    item = import_item(instance, lib, path)

    assert item["track_id"] == SPOTIFY_ID


def test_non_spotify_url_is_kept_whole(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url="https://example.com/track/42"))

    item = import_item(instance, lib, path)

    assert item["track_id"] == "https://example.com/track/42"


def test_absent_tag_leaves_field_unset(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(TIT2(encoding=3, text=["Title"]))

    item = import_item(instance, lib, path)

    assert "track_id" not in item.keys()


def test_imported_value_is_stored_in_library(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(instance, lib, path)

    assert lib.get_item(item.id)["track_id"] == SPOTIFY_ID


def test_album_import_processes_every_item(plugin, lib, mp3_factory):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    paths = [
        mp3_factory(WOAS(url=f"https://open.spotify.com/track/{track_id}"), name=f"{track_id}.mp3")
        for track_id in ("first", "second")
    ]

    items = import_album(instance, lib, paths)

    assert sorted(item["track_id"] for item in items) == ["first", "second"]


# Write


def test_on_write_adds_field_under_lowercase_tag_name(plugin):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    item = Item(track_id=SPOTIFY_ID)
    tags = {}

    instance.on_write(item, item.path, tags)

    assert tags == {"woas": SPOTIFY_ID}


def test_on_write_skips_empty_field(plugin):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    item = Item(track_id="")
    tags = {}

    instance.on_write(item, item.path, tags)

    assert tags == {}


def test_on_write_skips_missing_field(plugin):
    instance = plugin({"mappings": {"WOAS": "track_id"}})
    item = Item()
    tags = {}

    instance.on_write(item, item.path, tags)

    assert tags == {}
