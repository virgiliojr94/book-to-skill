"""A module installed as a tool (pipx) is not importable, and saying only
"missing" sends the user to reinstall something they already have.

The hint must never claim the module is available: the parsers import Docling,
so an executable on PATH does not make the import work. It only tells us where
an environment that can import it lives.
"""

import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

from book_to_skill import dependencies


class TestNoExecutable:
    def test_returns_none_when_nothing_on_path(self, monkeypatch):
        monkeypatch.setattr(dependencies.shutil, "which", lambda _: None)

        assert dependencies.isolated_install_hint("docling") is None


class TestExecutableFound:
    def test_names_the_executable(self, monkeypatch):
        monkeypatch.setattr(
            dependencies.shutil, "which", lambda _: "/home/u/.local/bin/docling"
        )

        hint = dependencies.isolated_install_hint("docling")

        assert hint is not None
        assert "/home/u/.local/bin/docling" in hint
        assert "isolated environment" in hint

    def test_points_at_the_venv_python_when_it_exists(self, monkeypatch, tmp_path):
        venv_bin = tmp_path / "venvs" / "docling" / "bin"
        venv_bin.mkdir(parents=True)
        (venv_bin / "python").write_text("")
        (venv_bin / "docling").write_text("")
        monkeypatch.setattr(
            dependencies.shutil, "which", lambda _: str(venv_bin / "docling")
        )

        hint = dependencies.isolated_install_hint("docling")

        assert str(venv_bin / "python") in hint
        assert "scripts/extract.py" in hint

    def test_omits_the_interpreter_line_when_there_is_no_sibling_python(
        self, monkeypatch, tmp_path
    ):
        lone = tmp_path / "docling"
        lone.write_text("")
        monkeypatch.setattr(dependencies.shutil, "which", lambda _: str(lone))

        hint = dependencies.isolated_install_hint("docling")

        assert hint is not None
        assert "scripts/extract.py" not in hint

    def test_still_treats_the_module_as_missing(self, monkeypatch, capsys):
        """The parsers import it; a binary on PATH does not make that work.

        The report must keep the ✗ and keep offering to install — the hint adds
        a diagnosis, it does not reclassify the dependency as satisfied.
        """
        monkeypatch.setattr(dependencies.shutil, "which", lambda cmd: (
            "/home/u/.local/bin/docling" if cmd == "docling" else None
        ))
        monkeypatch.setattr(dependencies, "python_module_available", lambda _: False)

        dependencies.run_dependency_check()

        out = capsys.readouterr().out
        assert "✗ python: docling" in out
        assert "isolated environment" in out
