"""Known defects, tested against the desired behaviour.

Each test is a strict xfail naming the step that fixes it. Once the fix lands
the test passes, which strict mode reports as a failure until the marker is
removed.
"""

import pytest
from helpers import SPOTIFY_URL, import_item, read_frames, write_item
from mutagen.id3 import TXXX, WOAS

# URL round trip


@pytest.mark.xfail(strict=True, reason="fixed in step 3")
def test_spotify_url_survives_import_and_write(plugin, lib, mp3_factory):
    plugin({"mappings": {"WOAS": "track_id"}})
    path = mp3_factory(WOAS(url=SPOTIFY_URL))

    item = import_item(lib, path)
    write_item(item)

    assert read_frames(path)["WOAS"].url == SPOTIFY_URL


# TXXX frames


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_txxx_frame_is_read(plugin, lib, mp3_factory):
    plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(lib, path)

    assert item["foo"] == "bar"


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_unchanged_write_keeps_txxx_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(lib, path)
    write_item(item)

    assert read_frames(path)["TXXX:FOO"].text == ["bar"]


@pytest.mark.xfail(strict=True, reason="fixed in step 4")
def test_changed_write_updates_txxx_frame(plugin, lib, mp3_factory):
    plugin({"mappings": {"TXXX:FOO": "foo"}})
    path = mp3_factory(TXXX(encoding=3, desc="FOO", text=["bar"]))

    item = import_item(lib, path)
    item["foo"] = "baz"
    write_item(item)

    assert read_frames(path)["TXXX:FOO"].text == ["baz"]
