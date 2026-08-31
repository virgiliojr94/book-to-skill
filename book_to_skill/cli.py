import sys
from book_to_skill.utils import main as utils_main
from book_to_skill.pdf_inspector_integration import (
    enrich_pdf_inspector_metadata,
    install_pdf_inspector_hook,
)


def main():
    # Force UTF-8 stdout/stderr to avoid UnicodeEncodeError on Windows console
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            # Ignore if the stream does not support reconfigure (e.g. mock streams during testing)
            pass

    # pdf-inspector is an optional accelerator/trust layer. When unavailable,
    # this hook is a no-op and the legacy extraction chain behaves unchanged.
    install_pdf_inspector_hook()
    utils_main()
    enrich_pdf_inspector_metadata()


# Expose main for packaging console scripts entry points
if __name__ == "__main__":
    main()
