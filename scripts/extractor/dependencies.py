import importlib.util
import os
import shutil
import subprocess
import sys
from extractor.config import PYTHON_DEPENDENCIES, HTML_EXTENSIONS


# Ordered groups for the --check preflight report. Each entry describes one
# format and what it needs. `modules` are optional Python packages (any one is
# enough unless noted); `system` are external commands resolved via PATH.
DEPENDENCY_GROUPS = [
    {
        "label": "PDF (text-heavy)",
        "modules": ["PyPDF2", "pdfminer"],
        "any_of_modules": True,
        "any_tool_suffices": True,
        "system": [("pdftotext", "poppler-utils", "sudo apt install poppler-utils")],
        "note": "any one of pdftotext / PyPDF2 / pdfminer is enough",
    },
    {
        "label": "PDF (technical: tables, code, formulas)",
        "modules": ["docling"],
        "any_of_modules": True,
        "system": [],
        "note": "needed only for --mode technical; otherwise falls back to the text chain",
    },
    {
        "label": "EPUB",
        "modules": ["ebooklib", "bs4"],
        "any_of_modules": False,
        "system": [],
        "note": "falls back to a stdlib zipfile parser if missing",
    },
    {
        "label": "DOCX",
        "modules": ["docx"],
        "any_of_modules": True,
        "system": [],
        "note": "falls back to a stdlib ZIP/XML parser if missing",
    },
    {
        "label": "HTML",
        "modules": ["bs4"],
        "any_of_modules": True,
        "system": [],
        "note": "falls back to the stdlib html.parser if missing",
    },
    {
        "label": "RTF",
        "modules": ["striprtf"],
        "any_of_modules": True,
        "system": [],
        "note": "falls back to a basic regex cleanup if missing",
    },
    {
        "label": "MOBI / AZW / AZW3",
        "modules": [],
        "any_of_modules": True,
        "required": True,
        "system": [
            ("ebook-convert", "Calibre", "install Calibre: https://calibre-ebook.com/download"),
        ],
        "note": "no fallback — Calibre is required for these formats",
    },
]


def python_module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def missing_python_packages(module_names: list[str]) -> list[str]:
    missing = []
    for module_name in module_names:
        if not python_module_available(module_name):
            missing.append(PYTHON_DEPENDENCIES[module_name])
    return missing


def install_python_packages(packages: list[str]) -> bool:
    if not packages:
        return True

    print(f"Installing missing Python package(s): {', '.join(packages)}")
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", *packages],
            text=True,
            timeout=600,
        )
    except Exception as exc:
        print(f"Package installation failed: {exc}", file=sys.stderr)
        return False

    importlib.invalidate_caches()
    return result.returncode == 0


def normalize_install_mode(argv: list[str]) -> str:
    mode = os.environ.get("BOOK_SKILL_INSTALL_MISSING", "ask").lower()
    if "--no-install-missing" in argv:
        return "no"
    if "--install-missing" in argv:
        idx = argv.index("--install-missing")
        if idx + 1 < len(argv) and not argv[idx + 1].startswith("--"):
            mode = argv[idx + 1].lower()
        else:
            mode = "yes"
    if mode in {"1", "true", "y", "yes", "install"}:
        return "yes"
    if mode in {"0", "false", "n", "no", "fallback", "skip"}:
        return "no"
    return "ask"


def offer_dependency_install(
    *,
    feature: str,
    module_names: list[str],
    fallback: str | None,
    install_mode: str,
) -> None:
    packages = missing_python_packages(module_names)
    if not packages:
        return

    message = f"{feature} uses {', '.join(packages)} if installed"
    if fallback:
        message += f", otherwise {fallback}"
    message += "."
    print(message)

    should_install = False
    if install_mode == "yes":
        should_install = True
    elif install_mode == "ask" and sys.stdin.isatty():
        answer = input("Missing package(s) detected. Do you want to install? y=install, n=fallback: ").strip().lower()
        should_install = answer in {"y", "yes", "install"}
    else:
        if fallback:
            print("Non-interactive mode or install disabled; using fallback.")
        else:
            print("Non-interactive mode or install disabled; installation skipped.")

    if not should_install:
        if fallback:
            print(f"Using fallback: {fallback}.")
        return

    if install_python_packages(packages):
        still_missing = missing_python_packages(module_names)
        if not still_missing:
            print("Package installation complete.")
            return
        print(f"Package installation incomplete; still missing: {', '.join(still_missing)}", file=sys.stderr)
    else:
        print("Package installation failed.", file=sys.stderr)

    if fallback:
        print(f"Using fallback: {fallback}.")


def prepare_dependencies(ext: str, extraction_mode: str, install_mode: str) -> None:
    if ext == ".pdf" and extraction_mode == "technical":
        offer_dependency_install(
            feature="Technical PDF extraction",
            module_names=["docling"],
            fallback="the PDF text fallback chain",
            install_mode=install_mode,
        )

    if ext == ".pdf" and not shutil.which("pdftotext"):
        offer_dependency_install(
            feature="PDF text extraction",
            module_names=["PyPDF2", "pdfminer"],
            fallback="any installed Python PDF parser; extraction fails if none are available",
            install_mode=install_mode,
        )

    if ext == ".epub":
        offer_dependency_install(
            feature="EPUB extraction",
            module_names=["ebooklib", "bs4"],
            fallback="a stdlib ZIP/HTML parser",
            install_mode=install_mode,
        )

    if ext in HTML_EXTENSIONS:
        offer_dependency_install(
            feature="HTML extraction",
            module_names=["bs4"],
            fallback="a stdlib HTML parser",
            install_mode=install_mode,
        )

    if ext == ".docx":
        offer_dependency_install(
            feature="DOCX extraction",
            module_names=["docx"],
            fallback="a stdlib ZIP/XML parser",
            install_mode=install_mode,
        )

    if ext == ".rtf":
        offer_dependency_install(
            feature="RTF extraction",
            module_names=["striprtf"],
            fallback="a basic regex cleanup fallback",
            install_mode=install_mode,
        )


def run_dependency_check() -> int:
    """Scan every optional dependency across all formats and print a status
    report plus the exact command to install whatever is missing.

    Returns a process exit code: 0 always (a missing optional dep is not an
    error — most formats degrade to a fallback). Intended for `extract.py --check`.
    """
    print("book-to-skill — dependency check\n")

    missing_pip_packages: list[str] = []
    missing_system: list[tuple[str, str]] = []  # (name, install hint)

    for group in DEPENDENCY_GROUPS:
        print(f"  {group['label']}")

        present_modules = [m for m in group["modules"] if python_module_available(m)]
        absent_modules = [m for m in group["modules"] if not python_module_available(m)]
        system_present = [c for c, _, _ in group["system"] if shutil.which(c)]
        system_absent = [c for c, _, _ in group["system"] if not shutil.which(c)]

        for module_name in group["modules"]:
            pip_name = PYTHON_DEPENDENCIES.get(module_name, module_name)
            ok = module_name in present_modules
            print(f"      {'✓' if ok else '✗'} python: {pip_name}")
            if not ok:
                missing_pip_packages.append(pip_name)

        for cmd, pretty, hint in group["system"]:
            ok = cmd in system_present
            print(f"      {'✓' if ok else '✗'} system: {cmd} ({pretty})")
            if not ok:
                missing_system.append((pretty, hint))

        # Satisfaction semantics:
        #  - any_tool_suffices: any single extractor (module OR system) is enough
        #  - any_of_modules: at least one module present
        #  - otherwise: every listed module present
        #  - system tools that aren't alternatives are always required
        if group.get("any_tool_suffices"):
            satisfied = bool(present_modules) or bool(system_present)
        else:
            if group["modules"]:
                satisfied = bool(present_modules) if group["any_of_modules"] else not absent_modules
            else:
                satisfied = True
            if system_absent:
                satisfied = False

        if satisfied:
            status = "ready"
        elif group.get("required"):
            status = "MISSING — required, no fallback"
        else:
            status = "fallback available (install for best quality)"
        print(f"      → {status} — {group['note']}\n")

    # Deduplicate while preserving order
    missing_pip_packages = list(dict.fromkeys(missing_pip_packages))
    missing_system = list(dict.fromkeys(missing_system))

    if not missing_pip_packages and not missing_system:
        print("All optional dependencies are installed. You're ready for every format.")
        return 0

    print("To enable the best extractor for every format, install the missing pieces:\n")
    if missing_pip_packages:
        print(f"  {sys.executable} -m pip install {' '.join(missing_pip_packages)}")
    for pretty, hint in missing_system:
        print(f"  # {pretty}: {hint}")
    print(
        "\nNote: missing Python packages are optional — most formats fall back to a "
        "stdlib parser. Calibre is the only hard requirement, and only for MOBI/AZW files."
    )
    return 0
