"""Helpers shared by the test modules.

The tests go through these instead of touching beets' import and write
mechanics directly, so a change to those mechanics is made here once.
"""

import mutagen.id3
from beets.library import Item

SPOTIFY_ID = "2BOUrjXoRIo2YHVAyZyXVX"
SPOTIFY_URL = f"https://open.spotify.com/track/{SPOTIFY_ID}"


def import_item(lib, path):
    """Add the file at `path` to the library, reading its tags as an import does."""
    item = Item.from_path(bytes(path))
    lib.add(item)
    return item


def write_item(item):
    """Write the item's fields to its file, as `beet write` does."""
    item.write()


def read_frames(path):
    """Return the ID3 frames currently stored in the file at `path`."""
    return mutagen.id3.ID3(path)
