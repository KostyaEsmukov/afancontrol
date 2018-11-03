import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def temp_path():
    with tempfile.TemporaryDirectory() as tmpdirname:
        yield Path(tmpdirname).resolve()
