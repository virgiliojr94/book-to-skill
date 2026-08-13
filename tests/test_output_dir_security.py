import os
import stat

import pytest

from book_to_skill.exceptions import ExtractionError
from book_to_skill.utils import prepare_output_dir

# Permission bits are a POSIX concept. On Windows os.chmod only toggles the
# read-only flag and st_mode always reports 0o666/0o777, so asserting 0o700
# fails there even though prepare_output_dir() behaves correctly — it guards
# the symlink and non-directory cases on every platform and only tightens the
# mode where the mode means something.
posix_permissions = pytest.mark.skipif(
    not hasattr(os, "getuid"), reason="POSIX-only permission bits"
)


@posix_permissions
def test_prepare_output_dir_creates_dir_with_restrictive_permissions(tmp_path):
    target = tmp_path / "work"

    prepare_output_dir(target)

    assert target.is_dir()
    assert stat.S_IMODE(target.stat().st_mode) == 0o700


def test_prepare_output_dir_rejects_symlink(tmp_path):
    real_dir = tmp_path / "real"
    real_dir.mkdir()
    link = tmp_path / "work"
    link.symlink_to(real_dir)

    with pytest.raises(ExtractionError, match="symbolic link"):
        prepare_output_dir(link)


def test_prepare_output_dir_rejects_non_directory(tmp_path):
    target = tmp_path / "work"
    target.write_text("not a directory")

    with pytest.raises(ExtractionError, match="not a directory"):
        prepare_output_dir(target)


@posix_permissions
def test_prepare_output_dir_tightens_permissions_on_existing_own_dir(tmp_path):
    target = tmp_path / "work"
    target.mkdir()
    os.chmod(target, 0o777)  # simulate a pre-existing, overly-permissive dir

    prepare_output_dir(target)

    assert stat.S_IMODE(target.stat().st_mode) == 0o700


@posix_permissions
def test_prepare_output_dir_rejects_directory_owned_by_another_user(tmp_path, monkeypatch):
    target = tmp_path / "work"
    target.mkdir()

    real_getuid = os.getuid
    monkeypatch.setattr(os, "getuid", lambda: real_getuid() + 1)

    with pytest.raises(ExtractionError, match="owned by a different user"):
        prepare_output_dir(target)
