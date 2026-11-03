import io

from pypdf import PdfReader

from app.pdf import sample_report


def test_sample_report_renders_pages_with_numbers():
    data = sample_report.render()
    reader = PdfReader(io.BytesIO(data))
    assert len(reader.pages) >= 1
    text = reader.pages[0].extract_text()
    assert "Page 1 of" in text and "Sample Inspection Report" in text


def test_no_base14_font_is_referenced():
    assert b"Helvetica" not in sample_report.render()
