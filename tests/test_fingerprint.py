"""Per-source content fingerprint recorded by the extractor (round-2 ask)."""
import hashlib
import json
from pathlib import Path

from book_to_skill.utils import _sha256_file, extract_single_file, reuse_is_safe


def _write(tmp_path: Path, name: str, content: str) -> Path:
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_metadata_records_sha256_per_source(tmp_path):
    src = _write(tmp_path, "doc.txt", "chapter one\n" + "body text.\n" * 500)
    res = extract_single_file(src, "auto", "ask")
    expected = hashlib.sha256(src.read_bytes()).hexdigest()
    assert res["sha256"] == expected


def test_same_size_different_content_gives_different_fingerprint(tmp_path):
    # The maintainer's exact scenario: same filename, same byte size,
    # changed content. Round-1 gate (name+size) passes both; fingerprint must not.
    a = _write(tmp_path, "doc_a.txt", "Allow sharing.\n" + "x" * 1000)
    b = _write(tmp_path, "doc_b.txt", "Avoid sharing.\n" + "x" * 1000)
    assert len(a.read_bytes()) == len(b.read_bytes())   # sanity: same size
    ra = extract_single_file(a, "auto", "ask")
    rb = extract_single_file(b, "auto", "ask")
    assert ra["sha256"] != rb["sha256"]


def test_metadata_sources_list_carries_sha256(tmp_path, monkeypatch):
    # The guard reads metadata.json, so the per-source fingerprint must survive
    # consolidation. Follows test_metadata_encoding.py's pattern: run main()
    # end-to-end with OUTPUT_META pointed at a tmp path, then parse the JSON.
    from book_to_skill.utils import main

    src = _write(tmp_path, "doc.txt", "content\n" * 100)
    expected = hashlib.sha256(src.read_bytes()).hexdigest()

    out_dir = tmp_path / "output"
    out_meta = out_dir / "metadata.json"
    monkeypatch.setenv("BOOK_SKILL_WORKDIR", str(out_dir))
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_DIR", out_dir)
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_TEXT", out_dir / "full_text.txt")
    monkeypatch.setattr("book_to_skill.utils.OUTPUT_META", out_meta)
    monkeypatch.setattr("book_to_skill.utils.prepare_dependencies", lambda *a: None)
    monkeypatch.setattr(
        "sys.argv", ["extract.py", str(src), "--install-missing", "no"]
    )

    main()
    meta = json.loads(out_meta.read_text(encoding="utf-8"))
    assert meta["sources"][0]["sha256"] == expected


def test_hook_path_result_carries_sha256(tmp_path, monkeypatch):
    # Text-mode PDFs take the pdf-inspector fast path, which returns its own
    # per-source dict. That dict must carry the fingerprint too (review F3).
    from types import SimpleNamespace

    import book_to_skill.pdf_inspector_integration as pii

    src = _write(tmp_path, "doc.pdf", "%PDF-1.4 fake minimal payload\n" * 50)
    expected = hashlib.sha256(src.read_bytes()).hexdigest()

    fake_utils = SimpleNamespace(
        extract_single_file=lambda *a: {"extraction_method": "legacy"},
        sanitize_extracted_text=lambda text: (text, 0),
        detect_structure=lambda t: {
            "chapters_detected": 0,
            "chapters_method": "none",
            "has_toc": False,
        },
        count_pages=lambda p: 1,
        estimate_tokens=lambda t: len(t) // 4,
    )
    inspection = {
        "confidence": 0.99,
        "page_count": 1,
        "pdf_type": "text_based",
        "native_markdown_trusted": True,
        "pages_needing_ocr": [],
        "has_encoding_issues": False,
    }

    pii._reset_state_for_tests()
    # monkeypatch, NOT bare assignment — a bare `pii.inspect_pdf = ...` leaks
    # across the whole suite (later pdf-inspector tests then see the stub).
    monkeypatch.setattr(
        pii, "inspect_pdf", lambda _path: ("# Native Markdown\nBody", inspection)
    )
    pii.install_pdf_inspector_hook(fake_utils)
    res = fake_utils.extract_single_file(src, "text", "ask")
    assert res["sha256"] == expected


# ---------------------------------------------------------------------------
# Phase 2 — the executable reuse decision (round-2 ask d)
# ---------------------------------------------------------------------------


def _make_metadata(tmp_path, src: Path, mode="text"):
    res = extract_single_file(src, mode, "ask")
    workdir = tmp_path / "work"
    workdir.mkdir(exist_ok=True)   # the happy path needs an EXISTING workdir
    return {
        "workdir": str(workdir),
        # extract_single_file's return dict has extraction_METHOD, not
        # extraction_MODE — the mode key only exists at metadata.json top level.
        # Take it from the mode parameter.
        "extraction_mode": mode,
        "sources": [
            {k: res[k] for k in ("filename", "file_size_mb", "sha256")}
        ],
    }, res


def test_scenario_reuse_same_content(tmp_path):
    src = _write(tmp_path, "doc.txt", "chapter one\n" + "body.\n" * 500)
    meta, res = _make_metadata(tmp_path, src)
    ok, reason = reuse_is_safe([(src, res["sha256"])], meta, current_mode="text")
    assert ok, reason


def test_scenario_changed_content_same_size_falls_back(tmp_path):
    # THE maintainer scenario: "Allow sharing." -> "Avoid sharing."
    src_a = _write(tmp_path, "doc.txt", "Allow sharing.\n" + "x" * 1000)
    meta, _ = _make_metadata(tmp_path, src_a)
    src_b = _write(tmp_path, "doc.txt", "Avoid sharing.\n" + "x" * 1000)
    assert src_a.stat().st_size == src_b.stat().st_size   # sanity: same size
    ok, reason = reuse_is_safe([(src_b, hashlib.sha256(src_b.read_bytes()).hexdigest())],
                               meta, current_mode="text")
    assert not ok
    assert "content changed" in reason


def test_scenario_missing_workdir_falls_back(tmp_path):
    src = _write(tmp_path, "doc.txt", "text\n" * 100)
    meta, res = _make_metadata(tmp_path, src)
    import shutil
    shutil.rmtree(meta["workdir"])   # ONLY this test points at an absent workdir
    ok, reason = reuse_is_safe([(src, res["sha256"])], meta, current_mode="text")
    assert not ok
    assert "workdir" in reason


def test_scenario_mode_mismatch_falls_back(tmp_path):
    # The function OWNS the mode check via current_mode — the docstring's
    # "caller compares" phrasing would leave the check nowhere. Valid modes are
    # "technical"/"text" — the parse_arguments enum.
    src = _write(tmp_path, "doc.txt", "text\n" * 100)
    meta, res = _make_metadata(tmp_path, src, mode="text")
    ok, reason = reuse_is_safe([(src, res["sha256"])], meta, current_mode="technical")
    assert not ok


def test_scenario_legacy_metadata_without_sha256_falls_back(tmp_path):
    # Older workdirs have no fingerprint: cannot establish freshness -> fresh extraction.
    src = _write(tmp_path, "doc.txt", "text\n" * 100)
    meta, res = _make_metadata(tmp_path, src)
    for s in meta["sources"]:
        del s["sha256"]
    ok, reason = reuse_is_safe([(src, res["sha256"])], meta, current_mode="text")
    assert not ok


def test_scenario_sources_changed_falls_back(tmp_path):
    # The contract's remaining clause: recorded sources must match the current
    # inputs one-to-one on filename. A renamed input cannot reuse the workdir,
    # and neither can a different number of inputs.
    src = _write(tmp_path, "doc.txt", "text\n" * 100)
    meta, res = _make_metadata(tmp_path, src)

    renamed = _write(tmp_path, "other.txt", "text\n" * 100)
    ok, reason = reuse_is_safe([(renamed, res["sha256"])], meta, current_mode="text")
    assert not ok
    assert "sources changed" in reason

    ok, reason = reuse_is_safe(
        [(src, res["sha256"]), (renamed, res["sha256"])], meta, current_mode="text"
    )
    assert not ok
    assert "sources changed" in reason


def test_sha256_file_streams_across_chunks(tmp_path):
    # _sha256_file reads in 1 MiB chunks; every other fixture here is ~1 KB, so a
    # truncating bug in the loop would go unnoticed. Real inputs are tens of MB,
    # and a truncated fingerprint is the silent-stale-accept failure class this
    # PR closes — so compare a multi-chunk file against hashlib directly.
    src = _write(tmp_path, "big.txt", "line of text\n" * 200_000)   # ~2.6 MB, >2 chunks
    assert src.stat().st_size > 2 << 20
    assert _sha256_file(str(src)) == hashlib.sha256(src.read_bytes()).hexdigest()
