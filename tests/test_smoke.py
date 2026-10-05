import mediafile
import mutagen.id3
from beets.library import Item


def test_plugin_instantiates_with_empty_config(plugin):
    assert plugin().mappings == []


def test_fixtures_work_together(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(mutagen.id3.WOAS(url="https://example.com/a"))

    item = Item.from_path(bytes(path))
    lib.add(item)

    assert item["woas"] == "https://example.com/a"


def test_plugin_registrations_are_undone():
    assert "woas" not in vars(mediafile.MediaFile)
    assert "woas" not in Item._media_fields
