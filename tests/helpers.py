"""Helpers shared by the test modules.

The tests go through these instead of touching the plugin's import and write
mechanics directly, so a change to those mechanics is made here once.
"""

import mutagen.id3
from beets.library import Item

SPOTIFY_ID = "2BOUrjXoRIo2YHVAyZyXVX"
SPOTIFY_URL = f"https://open.spotify.com/track/{SPOTIFY_ID}"


def import_item(plugin, lib, path):
    """Add the file at `path` to the library the way a singleton import does."""
    item = Item.from_path(bytes(path))
    lib.add(item)
    plugin.item_imported(lib, item)
    return item


def import_album(plugin, lib, paths):
    """Add the files at `paths` to the library the way an album import does."""
    items = [Item.from_path(bytes(path)) for path in paths]
    album = lib.add_album(items)
    plugin.album_imported(lib, album)
    return list(album.items())


def write_item(item):
    """Write the item's fields to its file, as `beet write` does."""
    item.write()


def read_frames(path):
    """Return the ID3 frames currently stored in the file at `path`."""
    return mutagen.id3.ID3(path)
