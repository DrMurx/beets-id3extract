import mediafile
import mutagen.id3
from beets.library import Item


def test_plugin_instantiates_with_empty_config(plugin):
    assert plugin().item_types == {}


def test_fixtures_work_together(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(mutagen.id3.WOAS(url="https://example.com/a"))

    item = Item.from_path(bytes(path))
    lib.add(item)

    assert item["track_id"] == "https://example.com/a"


def test_plugin_registrations_are_undone():
    assert "track_id" not in vars(mediafile.MediaFile)
    assert "track_id" not in Item._media_fields
