"""Supply-chain controls for the database bootstrap image."""

from pathlib import Path


def test_bootstrap_image_installs_only_hash_pinned_binary_dependencies():
    root = Path(__file__).parents[1]
    dockerfile = (root / "services/database_bootstrap/Dockerfile").read_text()
    lockfile = (root / "services/database_bootstrap/requirements.lock").read_text()

    assert "COPY services/database_bootstrap/requirements.lock" in dockerfile
    assert "--require-hashes" in dockerfile
    assert "--only-binary=:all:" in dockerfile
    assert "--no-cache-dir" in dockerfile
    assert "--hash=sha256:" in lockfile
