from io import BytesIO

import pytest

from app.services.document_parser import UnsupportedFileTypeError, extract_text


def test_pdf_extraction(tmp_path):
    fitz = pytest.importorskip("fitz")
    path = tmp_path / "resume.pdf"
    doc = fitz.open()
    doc.new_page().insert_text((50, 50), "Jane Doe\nPython Engineer")
    doc.save(path)
    doc.close()
    assert "Jane Doe" in extract_text(path)


def test_docx_extraction(tmp_path):
    docx = pytest.importorskip("docx")
    path = tmp_path / "resume.docx"
    document = docx.Document()
    document.add_paragraph("Jane Doe")
    document.add_paragraph("Python Engineer")
    document.save(path)
    assert "Python Engineer" in extract_text(path)


def test_unsupported_file_type():
    with pytest.raises(UnsupportedFileTypeError):
        extract_text(BytesIO(b"text"))
