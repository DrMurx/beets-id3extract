"""Shared fixtures for the id3extract tests."""

import beets
import beets.plugins
import mediafile
import mutagen.id3
import pytest
from beets.library import Item, Library
from beets.util import cached_classproperty

from beetsplug.id3extract import ID3ExtractPlugin

# One MPEG-1 Layer III frame (128 kbit/s, 44.1 kHz) with a silent payload.
MP3_FRAME = b"\xff\xfb\x90\x00" + b"\x00" * 413


def make_mp3(path, frames=()):
    """Write a synthetic MP3 to `path` and tag it with the given mutagen frames."""
    path.write_bytes(MP3_FRAME * 20)
    tags = mutagen.id3.ID3()
    for frame in frames:
        tags.add(frame)
    tags.save(path)
    return path


@pytest.fixture
def mp3_factory(tmp_path):
    """Return a function `(*frames, name="test.mp3")` creating a tagged MP3 in `tmp_path`."""

    def factory(*frames, name="test.mp3"):
        return make_mp3(tmp_path / name, frames)

    return factory


@pytest.fixture
def plugin():
    """Return a function that instantiates the plugin from an `id3extract` config dict.

    Everything the plugin registers is global to the process (MediaFile
    properties, `Item._media_fields`, event listeners), so all of it is undone
    on teardown.
    """
    media_attrs = set(vars(mediafile.MediaFile))
    media_fields = set(Item._media_fields)
    raw_listeners = {k: list(v) for k, v in beets.plugins.BeetsPlugin._raw_listeners.items()}
    listeners = {k: list(v) for k, v in beets.plugins.BeetsPlugin.listeners.items()}

    def factory(config=None):
        beets.config.clear()
        beets.config.read(user=False)
        beets.config["id3extract"] = config or {}
        instance = ID3ExtractPlugin()
        beets.plugins._instances[:] = [instance]
        cached_classproperty.cache.clear()
        return instance

    yield factory

    for name in set(vars(mediafile.MediaFile)) - media_attrs:
        delattr(mediafile.MediaFile, name)
    Item._media_fields.intersection_update(media_fields)
    for registry, snapshot in (
        (beets.plugins.BeetsPlugin._raw_listeners, raw_listeners),
        (beets.plugins.BeetsPlugin.listeners, listeners),
    ):
        registry.clear()
        registry.update(snapshot)
    beets.plugins._instances.clear()
    cached_classproperty.cache.clear()
    beets.config.clear()
    beets.config.read(user=False)


@pytest.fixture
def lib(tmp_path, monkeypatch):
    """An in-memory library. Its `.bak` files land in `tmp_path`, not in the repo."""
    monkeypatch.chdir(tmp_path)
    library = Library(":memory:")
    yield library
    library._close()
