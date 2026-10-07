import json
import sys
from types import ModuleType, SimpleNamespace

import pytest

from book_to_skill import utils
from book_to_skill.parsers.pdf import extract_with_docling


def test_docling_runtime_error_reaches_the_fallback(monkeypatch):
    class FailingConverter:
        def __init__(self, **_kwargs):
            pass

        def convert(self, _path):
            raise OSError("model cache unavailable")

    modules = {
        "docling": ModuleType("docling"),
        "docling.datamodel": ModuleType("docling.datamodel"),
        "docling.document_converter": ModuleType("docling.document_converter"),
        "docling.datamodel.pipeline_options": ModuleType(
            "docling.datamodel.pipeline_options"
        ),
        "docling.datamodel.base_models": ModuleType("docling.datamodel.base_models"),
    }
    modules["docling.document_converter"].DocumentConverter = FailingConverter
    modules["docling.document_converter"].PdfFormatOption = lambda **_kwargs: None
    modules["docling.datamodel.pipeline_options"].PdfPipelineOptions = SimpleNamespace
    modules["docling.datamodel.base_models"].InputFormat = SimpleNamespace(PDF="pdf")
    for name, module in modules.items():
        monkeypatch.setitem(sys.modules, name, module)

    with pytest.raises(OSError, match="model cache unavailable"):
        extract_with_docling("book.pdf")


@pytest.mark.parametrize(
    ("docling_result", "expected_reason"),
    [(None, "docling_unavailable"), ("", "docling_empty")],
)
def test_technical_pdf_records_fallback_reason(
    tmp_path, monkeypatch, docling_result, expected_reason
):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture")
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *_: None)
    monkeypatch.setattr(utils, "looks_image_only", lambda *_: False)
    monkeypatch.setattr(utils, "extract_with_docling", lambda *_: docling_result)
    monkeypatch.setattr(
        utils, "extract_with_pdftotext", lambda *_: "# Technical book\n\nText only."
    )
    monkeypatch.setattr(utils, "count_pages", lambda *_: 1)

    result = utils.extract_single_file(pdf, "technical", "no")

    assert result["extraction_method"] == "pdftotext"
    assert result["fallback_reason"] == expected_reason


def test_docling_runtime_failure_is_recorded_in_metadata(tmp_path, monkeypatch, capsys):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture")
    output_dir = tmp_path / "output"
    monkeypatch.setattr(utils, "OUTPUT_DIR", output_dir)
    monkeypatch.setattr(utils, "OUTPUT_TEXT", output_dir / "full_text.txt")
    monkeypatch.setattr(utils, "OUTPUT_META", output_dir / "metadata.json")
    monkeypatch.setattr(
        sys,
        "argv",
        ["extract.py", str(pdf), "--mode", "technical", "--no-install-missing"],
    )
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *_: None)
    monkeypatch.setattr(utils, "looks_image_only", lambda *_: False)
    monkeypatch.setattr(utils, "count_pages", lambda *_: 1)
    monkeypatch.setattr(
        utils, "extract_with_pdftotext", lambda *_: "# Technical book\n\nText only."
    )

    def fail_docling(_path):
        raise OSError("model cache unavailable")

    monkeypatch.setattr(utils, "extract_with_docling", fail_docling)

    utils.main()

    metadata = json.loads((output_dir / "metadata.json").read_text(encoding="utf-8"))
    assert metadata["extraction_mode"] == "technical"
    assert metadata["extraction_method"] == "pdftotext"
    assert metadata["sources"][0]["fallback_reason"] == "docling_failed"
    assert "Docling failed" in capsys.readouterr().err


def test_successful_docling_has_no_fallback_reason(tmp_path, monkeypatch):
    pdf = tmp_path / "book.pdf"
    pdf.write_bytes(b"%PDF-1.4\nfixture")
    monkeypatch.setattr(utils, "prepare_dependencies", lambda *_: None)
    monkeypatch.setattr(utils, "looks_image_only", lambda *_: False)
    monkeypatch.setattr(
        utils, "extract_with_docling", lambda *_: "# Technical book\n\n| A | B |"
    )
    monkeypatch.setattr(utils, "count_pages", lambda *_: 1)

    result = utils.extract_single_file(pdf, "technical", "no")

    assert result["extraction_method"] == "docling"
    assert result["fallback_reason"] is None
