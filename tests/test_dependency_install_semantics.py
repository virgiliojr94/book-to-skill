"""Runtime dependency prompts should match the extractor fallback semantics."""

from book_to_skill import dependencies


def _fail_install(packages):
    raise AssertionError(f"unexpected dependency installation: {packages}")


def test_pdf_preflight_accepts_one_available_python_parser(monkeypatch):
    monkeypatch.setattr(dependencies.shutil, "which", lambda _command: None)
    monkeypatch.setattr(
        dependencies,
        "python_module_available",
        lambda module: module == "pypdf",
    )
    monkeypatch.setattr(dependencies, "install_python_packages", _fail_install)

    dependencies.prepare_dependencies(".pdf", "text", "yes")


def test_html_preflight_accepts_available_trafilatura(monkeypatch):
    monkeypatch.setattr(
        dependencies,
        "python_module_available",
        lambda module: module == "trafilatura",
    )
    monkeypatch.setattr(dependencies, "install_python_packages", _fail_install)

    dependencies.prepare_dependencies(".html", "text", "yes")


def test_any_of_group_installs_only_the_preferred_parser(monkeypatch):
    installed = []
    monkeypatch.setattr(dependencies, "python_module_available", lambda _module: False)
    monkeypatch.setattr(
        dependencies,
        "install_python_packages",
        lambda packages: installed.append(packages) or False,
    )

    dependencies.offer_dependency_install(
        feature="HTML extraction",
        module_names=["trafilatura", "bs4"],
        fallback="the stdlib HTML parser",
        install_mode="yes",
        any_of_modules=True,
    )

    assert installed == [["trafilatura"]]


def test_all_required_group_still_installs_every_missing_package(monkeypatch):
    installed = []
    monkeypatch.setattr(dependencies, "python_module_available", lambda _module: False)
    monkeypatch.setattr(
        dependencies,
        "install_python_packages",
        lambda packages: installed.append(packages) or False,
    )

    dependencies.offer_dependency_install(
        feature="EPUB extraction",
        module_names=["ebooklib", "bs4"],
        fallback="a stdlib ZIP/HTML parser",
        install_mode="yes",
    )

    assert installed == [["ebooklib", "beautifulsoup4"]]
