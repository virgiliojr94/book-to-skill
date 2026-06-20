from __future__ import annotations

import glob
import json
import os
import sys
import re
import concurrent.futures
from pathlib import Path

from book_to_skill.exceptions import ExtractionError
from book_to_skill.config import (
    SUPPORTED_EXTENSIONS,
    supported_formats_message,
)
from book_to_skill.dependencies import (
    normalize_install_mode,
    run_dependency_check,
)
from book_to_skill.chapter_detector import detect_structure
import book_to_skill.utils as utils
from book_to_skill.glossary_extractor import (
    extract_glossary_data,
    generate_cheatsheet_markdown,
)


def parse_arguments(argv: list[str]) -> tuple[list[str], str, str]:
    """Parse argv into (input_paths, extraction_mode, install_mode)."""
    input_paths = []
    extraction_mode = "text"
    
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg == "--mode":
            if i + 1 < len(args):
                extraction_mode = args[i+1].lower()
                i += 2
            else:
                i += 1
        elif arg == "--install-missing":
            if i + 1 < len(args) and not args[i+1].startswith("--"):
                i += 2
            else:
                i += 1
        elif arg == "--no-install-missing":
            i += 1
        elif arg == "--no-cache":
            utils.USE_CACHE = False
            i += 1
        elif arg in ("--workers", "--jobs"):
            if i + 1 < len(args) and not args[i+1].startswith("--"):
                i += 2
            else:
                i += 1
        elif arg.startswith("-"):
            i += 1
        else:
            input_paths.append(arg)
            i += 1
            
    install_mode = normalize_install_mode(argv)
    if extraction_mode not in ("technical", "text"):
        extraction_mode = "text"
        
    return input_paths, extraction_mode, install_mode


def parse_workers(argv: list[str]) -> int:
    """Parse argv to find the number of workers requested (default is 1).
    Supports --workers <N> and --jobs <N>.
    If the value is 'auto', it returns os.cpu_count() or 4 (as a sensible fallback).
    If it is 0 or less, or not a number, it defaults to 1.
    """
    args = argv[1:]
    i = 0
    while i < len(args):
        arg = args[i]
        if arg in ("--workers", "--jobs"):
            if i + 1 < len(args):
                val = args[i+1].lower()
                if val == "auto":
                    return os.cpu_count() or 4
                try:
                    num = int(val)
                    return max(1, num)
                except ValueError:
                    return 1
            return 1
        i += 1
    return 1


def resolve_input_files(paths: list[str]) -> list[Path]:
    """Resolve paths including files, directories, and glob patterns to Path objects.

    User-given order is preserved for explicit file arguments.  Expanded
    results (directories, globs) are sorted deterministically so repeated
    runs produce the same output.
    """
    resolved = []
    for path_str in paths:
        # Check if it has glob wildcards
        if any(char in path_str for char in ("*", "?", "[")):
            glob_matches = glob.glob(path_str, recursive=True)
            # Sort expanded glob results deterministically
            expanded = []
            for match in glob_matches:
                p = Path(match)
                if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    expanded.append(p.resolve())
            expanded.sort(key=lambda x: str(x).lower())
            resolved.extend(expanded)
        else:
            p = Path(path_str)
            if p.is_dir():
                # Sort expanded directory results deterministically
                dir_files = []
                for root, _, files in os.walk(p):
                    for file in files:
                        file_path = Path(root) / file
                        if file_path.suffix.lower() in SUPPORTED_EXTENSIONS:
                            dir_files.append(file_path.resolve())
                dir_files.sort(key=lambda x: str(x).lower())
                resolved.extend(dir_files)
            else:
                # Keep even if it doesn't exist so the error check can report it
                resolved.append(p.resolve())

    # Deduplicate while preserving insertion order (user order for explicit files)
    seen = set()
    unique_paths = []
    for path in resolved:
        resolved_path = path.resolve() if path.exists() else path
        if resolved_path not in seen:
            seen.add(resolved_path)
            unique_paths.append(resolved_path)

    return unique_paths


def print_banner() -> None:
    """Print the attribution banner. Done here (not only in SKILL.md) so it
    shows on every run regardless of how the agent invokes extraction."""
    banner = Path(__file__).resolve().parent.parent / "scripts" / "banner.txt"
    try:
        sys.stderr.write(banner.read_text(encoding="utf-8") + "\n")
    except Exception:
        pass  # best-effort: never block extraction on the banner


def main():
    # Force UTF-8 stdout/stderr to avoid UnicodeEncodeError on Windows console
    for _stream in (sys.stdout, sys.stderr):
        try:
            _stream.reconfigure(encoding="utf-8")
        except (AttributeError, ValueError):
            # Ignore if the stream does not support reconfigure (e.g. mock streams during testing)
            pass

    print_banner()

    if "--check" in sys.argv[1:]:
        sys.exit(run_dependency_check())

    if "--clear-cache" in sys.argv[1:]:
        if utils.CACHE_DIR.exists():
            for f in utils.CACHE_DIR.glob("*.json"):
                try:
                    f.unlink()
                except Exception:
                    pass
        print("Cache cleared successfully.")
        sys.exit(0)

    if len(sys.argv) < 2:
        print("Usage: extract.py <path-to-document-folder-or-glob>... [--mode technical|text] [--install-missing ask|yes|no] [--no-cache] [--clear-cache] [--workers N]", file=sys.stderr)
        print("       extract.py --check    # report which extractors are installed", file=sys.stderr)
        print(f"Supported formats: {supported_formats_message()}", file=sys.stderr)
        sys.exit(1)
        
    raw_input_paths, extraction_mode, install_mode = parse_arguments(sys.argv)
    
    if not raw_input_paths:
        print("ERROR: No input document, folder, or glob pattern specified.", file=sys.stderr)
        sys.exit(1)
        
    input_files = resolve_input_files(raw_input_paths)
    
    if not input_files:
        print(f"ERROR: No supported files found matching: {', '.join(raw_input_paths)}", file=sys.stderr)
        sys.exit(1)
        
    utils.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    
    workers = parse_workers(sys.argv)
    
    extracted_sources = []
    combined_texts = []
    errors = []
    
    if workers > 1 and len(input_files) > 1:
        def worker_fn(file_path):
            try:
                res = utils.extract_single_file(file_path, extraction_mode, install_mode)
                return (file_path, res, None)
            except Exception as exc:
                return (file_path, None, exc)
                
        with concurrent.futures.ThreadPoolExecutor(max_workers=workers) as executor:
            futures = [executor.submit(worker_fn, fp) for fp in input_files]
            results = [fut.result() for fut in futures]
            
        for file_path, res, exc in results:
            if exc is not None:
                print(f"WARNING: Skipping {file_path.name}: {exc}", file=sys.stderr)
                errors.append((file_path, str(exc)))
            else:
                extracted_sources.append(res)
                # Format the text with a clear boundary
                separator = f"\n\n{'=' * 80}\nSOURCE: {res['filename']} (Path: {res['source_file']})\n{'=' * 80}\n\n"
                combined_texts.append(separator + res["text"])
    else:
        for file_path in input_files:
            try:
                res = utils.extract_single_file(file_path, extraction_mode, install_mode)
            except ExtractionError as exc:
                print(f"WARNING: Skipping {file_path.name}: {exc}", file=sys.stderr)
                errors.append((file_path, str(exc)))
                continue
            extracted_sources.append(res)
            
            # Format the text with a clear boundary
            separator = f"\n\n{'=' * 80}\nSOURCE: {res['filename']} (Path: {res['source_file']})\n{'=' * 80}\n\n"
            combined_texts.append(separator + res["text"])
    
    if not extracted_sources:
        print(f"\nERROR: All {len(errors)} source(s) failed extraction:", file=sys.stderr)
        for path, err in errors:
            print(f"  - {path.name}: {err}", file=sys.stderr)
        sys.exit(1)
        
    # Combine texts
    consolidated_text = "".join(combined_texts).strip()
    
    # Write combined text
    utils.OUTPUT_TEXT.write_text(consolidated_text, encoding="utf-8")
    
    # Consolidate metadata
    total_file_size_mb = sum(src["file_size_mb"] for src in extracted_sources)
    total_pages = sum(src["pages"] for src in extracted_sources)
    total_chars = len(consolidated_text)
    total_words = len(consolidated_text.split())
    total_tokens = utils.estimate_tokens(consolidated_text)
    
    # Detect structure on consolidated text
    consolidated_structure = detect_structure(consolidated_text)
    
    metadata = {
        "source_file": "Consolidated from multiple sources" if len(extracted_sources) > 1 else extracted_sources[0]["source_file"],
        "filename": "multi-source" if len(extracted_sources) > 1 else extracted_sources[0]["filename"],
        "format": "mixed" if len(extracted_sources) > 1 else extracted_sources[0]["format"],
        "extraction_method": "multi-method" if len(extracted_sources) > 1 else extracted_sources[0]["extraction_method"],
        "extraction_mode": extraction_mode,
        "file_size_mb": round(total_file_size_mb, 2),
        "pages": total_pages,
        "chars": total_chars,
        "words": total_words,
        "estimated_tokens": total_tokens,
        "estimated_tokens_human": f"~{total_tokens // 1000}K",
        "output_text": str(utils.OUTPUT_TEXT),
        "total_sources": len(extracted_sources),
        "sources": [
            {
                "source_file": src["source_file"],
                "filename": src["filename"],
                "format": src["format"],
                "extraction_method": src["extraction_method"],
                "file_size_mb": src["file_size_mb"],
                "pages": src["pages"],
                "pages_label": src["pages_label"],
                "chars": src["chars"],
                "words": src["words"],
                "estimated_tokens": src["estimated_tokens"],
                "chapters_detected": src["chapters_detected"],
                "has_toc": src["has_toc"]
            }
            for src in extracted_sources
        ],
        **consolidated_structure,
    }
    
    utils.OUTPUT_META.write_text(json.dumps(metadata, indent=2, ensure_ascii=False))
    
    chunk_mode = "--chunk" in sys.argv
    extract_glossary_mode = "--extract-glossary" in sys.argv

    # Global Glossary / Cheatsheet Extraction
    if extract_glossary_mode:
        glossary_data = extract_glossary_data(consolidated_text)
        cheatsheet_md = generate_cheatsheet_markdown(consolidated_text, glossary_data, metadata["filename"])
        
        glossary_path = utils.OUTPUT_DIR / "glossary.json"
        cheatsheet_path = utils.OUTPUT_DIR / "cheatsheet.md"
        glossary_path.write_text(json.dumps(glossary_data, indent=2, ensure_ascii=False), encoding="utf-8")
        cheatsheet_path.write_text(cheatsheet_md, encoding="utf-8")

    # AST-Aware Chunking
    chunks_count = 0
    if chunk_mode:
        chunks_dir = utils.OUTPUT_DIR / "chunks"
        chunks_dir.mkdir(parents=True, exist_ok=True)
        
        manifest_chunks = []
        
        def slugify(title_text: str) -> str:
            text_lower = title_text.lower()
            text_clean = re.sub(r"[^a-z0-9\s_-]", "", text_lower)
            text_underscored = re.sub(r"[\s_-]+", "_", text_clean)
            return text_underscored.strip("_")
            
        for idx, node in enumerate(consolidated_structure["ast"]):
            title = node["title"]
            start_char = node["start_char"]
            end_char = node["end_char"]
            
            chunk_text = consolidated_text[start_char:end_char]
            slug = slugify(title) or f"section_{idx+1}"
            folder_name = f"chunk_{idx+1:03d}_{slug}"
            chunk_folder = chunks_dir / folder_name
            chunk_folder.mkdir(parents=True, exist_ok=True)
            
            # Write sliced text
            text_file = chunk_folder / "text.txt"
            text_file.write_text(chunk_text, encoding="utf-8")
            
            chunk_tokens = utils.estimate_tokens(chunk_text)
            chunk_words = len(chunk_text.split())
            
            chunk_info = {
                "index": idx + 1,
                "title": title,
                "folder": folder_name,
                "start_char": start_char,
                "end_char": end_char,
                "words": chunk_words,
                "estimated_tokens": chunk_tokens,
            }
            
            # Generate chunk-specific glossary & cheatsheet if requested
            if extract_glossary_mode:
                chunk_glossary = extract_glossary_data(chunk_text)
                chunk_cheatsheet = generate_cheatsheet_markdown(chunk_text, chunk_glossary, title)
                
                (chunk_folder / "glossary.json").write_text(json.dumps(chunk_glossary, indent=2, ensure_ascii=False), encoding="utf-8")
                (chunk_folder / "cheatsheet.md").write_text(chunk_cheatsheet, encoding="utf-8")
                
            manifest_chunks.append(chunk_info)
            
        chunks_count = len(manifest_chunks)
        # Write chunks manifest.json
        manifest_data = {
            "book_filename": metadata["filename"],
            "total_chunks": chunks_count,
            "chunks": manifest_chunks
        }
        (chunks_dir / "manifest.json").write_text(json.dumps(manifest_data, indent=2, ensure_ascii=False), encoding="utf-8")
    
    page_line = f"   Total Pages: {total_pages}"
    print("\nExtraction complete:")
    print(f"   Sources : {len(extracted_sources)} processed")
    print(f"   Size    : {total_file_size_mb:.2f} MB")
    print(page_line)
    print(f"   Words   : {total_words:,}")
    print(f"   Tokens  : ~{total_tokens // 1000}K")
    print(f"   Chapters: {consolidated_structure['chapters_detected']} detected overall")
    print(f"   ToC     : {'yes' if consolidated_structure['has_toc'] else 'not detected'}")
    if not consolidated_structure["has_toc"]:
        print(
            "   WARN    : No table of contents detected — chapter mapping in Step 3 "
            "will rely on heading scan only, which may miss or duplicate sections."
        )
    print(f"\n   Text -> {utils.OUTPUT_TEXT}")
    print(f"   Meta -> {utils.OUTPUT_META}")
    if extract_glossary_mode and not chunk_mode:
        print(f"   Glossary -> {utils.OUTPUT_DIR / 'glossary.json'}")
        print(f"   Cheatsheet -> {utils.OUTPUT_DIR / 'cheatsheet.md'}")
    if chunk_mode:
        print(f"   Chunks   -> {utils.OUTPUT_DIR / 'chunks'} ({chunks_count} sections sliced)")
    if errors:
        print(f"\n   WARNING: {len(errors)} source(s) skipped due to errors:")
        for path, err in errors:
            print(f"     - {path.name}: {err}")


if __name__ == "__main__":
    main()
