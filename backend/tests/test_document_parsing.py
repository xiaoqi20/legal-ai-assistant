import io

import pytest
from docx import Document
from pypdf import PdfWriter
from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

from app.services.documents import extract, parse_isolated, split


async def test_pdf_docx_and_unicode_text_extraction():
  writer = PdfWriter()
  page = writer.add_blank_page(width=300, height=200)
  font = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
    NameObject("/Subtype"): NameObject("/Type1"), NameObject("/BaseFont"): NameObject("/Helvetica")})
  page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})})
  stream = DecodedStreamObject()
  stream.set_data(b"BT /F1 12 Tf 10 100 Td (Synthetic contract CNY 1000000) Tj ET")
  page[NameObject("/Contents")] = stream
  pdf = io.BytesIO()
  writer.write(pdf)
  assert extract(pdf.getvalue(), "application/pdf", 10000)[0][0] == 1
  assert "1000000" in extract(pdf.getvalue(), "application/pdf", 10000)[0][1]
  document = Document()
  document.add_paragraph("合成合同价款100万元。")
  table = document.add_table(rows=1, cols=1)
  table.cell(0, 0).text = "已支付80万元。"
  docx = io.BytesIO()
  document.save(docx)
  pages = await parse_isolated(docx.getvalue(), "application/vnd.openxmlformats-officedocument.wordprocessingml.document", 10000)
  assert "已支付80万元" in pages[0][1]
  chunks = split([(3, "中文🙂合成材料" * 100)], 200, 30, 50)
  assert all(chunk["page_no"] == 3 for chunk in chunks)
  assert chunks[0]["content"][-30:] == chunks[1]["content"][:30]
  assert chunks[-1]["char_end"] == 700


def test_scanned_and_encrypted_pdf_report_specific_errors():
  writer = PdfWriter()
  writer.add_blank_page(width=100, height=100)
  data = io.BytesIO()
  writer.write(data)
  with pytest.raises(ValueError, match="ocr_required"):
    extract(data.getvalue(), "application/pdf", 10000)
  writer.encrypt("test-password")
  data = io.BytesIO()
  writer.write(data)
  with pytest.raises(ValueError, match="encrypted_pdf"):
    extract(data.getvalue(), "application/pdf", 10000)
