import pytest


@pytest.fixture(autouse=True)
def isolated_cwd(tmp_path, monkeypatch):
    """Keep the developer's real .env from leaking into resolution tests."""

    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("COLUMNS", "100")
    return tmp_path
