"""Known defects, tested against the desired behaviour.

Each test is a strict xfail naming the step that fixes it. Once the fix lands
the test passes, which strict mode reports as a failure until the marker is
removed.
"""

import pytest
from helpers import import_item, read_frames, write_item
from mutagen.id3 import TXXX

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
