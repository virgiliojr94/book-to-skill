import sys
from book_to_skill.utils import main as utils_main

def main():
    # Force UTF-8 stdout/stderr to avoid UnicodeEncodeError on Windows console
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            # Ignore if the stream does not support reconfigure (e.g. mock streams during testing)
            pass
    utils_main()

# Expose main for packaging console scripts entry points
if __name__ == "__main__":
    main()
