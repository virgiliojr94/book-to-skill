"""Regenerate the tiny, synthetic PDF used by page-provenance tests.

Requires reportlab only when regenerating the checked-in fixture; tests do not.
"""

from pathlib import Path

from reportlab.pdfgen import canvas


def main() -> None:
    target = Path(__file__).with_name("pdf_page_provenance.pdf")
    document = canvas.Canvas(str(target), pagesize=(300, 200), invariant=1)

    document.setFont("Helvetica", 12)
    document.drawString(30, 160, "Page one evidence: ALPHA")
    document.showPage()

    document.setFont("Helvetica", 12)
    document.drawString(30, 160, "Page two evidence: BETA")
    document.drawString(30, 120, "Synthetic Table 1")
    document.line(60, 104, 150, 104)
    document.line(60, 72, 150, 72)
    document.line(107, 72, 107, 104)
    values = document.beginText(70, 84)
    values.setFont("Courier", 12)
    values.textOut("0.207")
    # A two-point visual gap and a cell rule, but no text-space character.
    # pypdf currently emits 0.2070.110; this is a layout warning, not a
    # license to guess where the table's cell separator belongs.
    values.moveCursor(38, 0)
    values.textOut("0.110")
    document.drawText(values)
    document.save()


if __name__ == "__main__":
    main()
