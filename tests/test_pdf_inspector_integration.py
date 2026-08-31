import json
import sys
from types import SimpleNamespace

import book_to_skill.pdf_inspector_integration as integration


def _fake_result(**overrides):
    values = {
        "pdf_type": "text_based",
        "confidence": 0.99,
        "markdown": "# Chapter 1\n\nUseful text",
        "page_count": 12,
        "pages_needing_ocr": [],
        "ocr_reasons_by_page": [],
        "pages_with_tables": [3],
        "pages_with_columns": [4],
        "has_encoding_issues": False,
        "is_complex_layout": True,
    }
    values.update(overrides)
    return SimpleNamespace(**values)


def test_inspect_pdf_accepts_only_high_confidence_native_markdown(monkeypatch):
    fake_module = SimpleNamespace(process_pdf=lambda _path: _fake_result())
    monkeypatch.setitem(sys.modules, "pdf_inspector", fake_module)

    markdown, metadata = integration.inspect_pdf("book.pdf")

    assert markdown.startswith("# Chapter 1")
    assert metadata["pdf_type"] == "text_based"
    assert metadata["native_markdown_trusted"] is True
    assert metadata["pages_with_tables"] == [3]
    assert metadata["pages_with_columns"] == [4]


def test_inspect_pdf_rejects_native_markdown_when_ocr_is_recommended(monkeypatch):
    reason = SimpleNamespace(page=7, reasons=["suspected_garbled_text"])
    fake_module = SimpleNamespace(
        process_pdf=lambda _path: _fake_result(
            pages_needing_ocr=[7],
            ocr_reasons_by_page=[reason],
        )
    )
    monkeypatch.setitem(sys.modules, "pdf_inspector", fake_module)

    markdown, metadata = integration.inspect_pdf("book.pdf")

    assert markdown is None
    assert metadata["native_markdown_trusted"] is False
    assert metadata["pages_needing_ocr"] == [7]
    assert metadata["ocr_reasons_by_page"] == [
        {"page": 7, "reasons": ["suspected_garbled_text"]}
    ]


def test_hook_uses_inspector_for_clean_text_pdf(tmp_path, monkeypatch):
    integration._reset_state_for_tests()
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7\nfixture")

    original_calls = []

    def original(*args):
        original_calls.append(args)
        return {"extraction_method": "legacy"}

    fake_utils = SimpleNamespace(
        extract_single_file=original,
        sanitize_extracted_text=lambda text: (text, 0),
        detect_structure=lambda _text: {
            "chapters_detected": 1,
            "chapters_method": "numeric",
            "chapter_headings_sample": ["Chapter 1"],
            "has_toc": False,
        },
        count_pages=lambda _path: 12,
        estimate_tokens=lambda _text: 42,
    )
    inspection = {
        "confidence": 0.99,
        "page_count": 12,
        "pdf_type": "text_based",
        "native_markdown_trusted": True,
        "pages_needing_ocr": [],
        "has_encoding_issues": False,
    }
    monkeypatch.setattr(
        integration,
        "inspect_pdf",
        lambda _path: ("Chapter 1\nBody", inspection),
    )

    integration.install_pdf_inspector_hook(fake_utils)
    result = fake_utils.extract_single_file(pdf, "text", "no")

    assert result["extraction_method"] == "pdf-inspector"
    assert result["pages"] == 12
    assert original_calls == []
    assert integration._INSPECTIONS[str(pdf.resolve())] == inspection


def test_hook_keeps_technical_mode_on_existing_pipeline(tmp_path, monkeypatch):
    integration._reset_state_for_tests()
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.7\nfixture")

    def original(*_args):
        return {"extraction_method": "docling"}

    fake_utils = SimpleNamespace(extract_single_file=original)
    inspection = {
        "confidence": 0.99,
        "page_count": 12,
        "pdf_type": "text_based",
        "native_markdown_trusted": True,
        "pages_needing_ocr": [],
        "has_encoding_issues": False,
    }
    monkeypatch.setattr(
        integration,
        "inspect_pdf",
        lambda _path: ("# Native Markdown", inspection),
    )

    integration.install_pdf_inspector_hook(fake_utils)
    result = fake_utils.extract_single_file(pdf, "technical", "no")

    assert result["extraction_method"] == "docling"


def test_metadata_is_enriched_with_machine_readable_pdf_signals(tmp_path):
    integration._reset_state_for_tests()
    source = tmp_path / "book.pdf"
    source.write_bytes(b"%PDF-1.7\nfixture")
    metadata_path = tmp_path / "metadata.json"
    metadata_path.write_text(
        json.dumps(
            {
                "total_sources": 1,
                "sources": [
                    {
                        "source_file": str(source.resolve()),
                        "filename": "book.pdf",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    inspection = {
        "engine": "pdf-inspector",
        "pdf_type": "mixed",
        "confidence": 0.87,
        "native_markdown_trusted": False,
        "pages_needing_ocr": [5],
        "ocr_reasons_by_page": [{"page": 5, "reasons": ["no_text"]}],
    }
    integration._INSPECTIONS[str(source.resolve())] = inspection

    integration.enrich_pdf_inspector_metadata(metadata_path)
    payload = json.loads(metadata_path.read_text(encoding="utf-8"))

    assert payload["sources"][0]["pdf_inspector"] == inspection
    assert payload["pdf_inspector"] == inspection
