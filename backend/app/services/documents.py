import io
import zipfile

from docx import Document
from pypdf import PdfReader


def extract(data: bytes, mime_type: str, max_chars: int):
  pages = []
  total = 0
  if mime_type == "application/pdf":
    if not data.startswith(b"%PDF-"):
      raise ValueError("invalid_pdf")
    reader = PdfReader(io.BytesIO(data), strict=True)
    if reader.is_encrypted:
      raise ValueError("encrypted_pdf_not_supported")
    if len(reader.pages) > 500:
      raise ValueError("too_many_pages")
    for number, page in enumerate(reader.pages, 1):
      text = (page.extract_text() or "").replace("\x00", "").strip()
      total += len(text)
      if total > max_chars:
        raise ValueError("document_too_large")
      if text:
        pages.append((number, text))
  elif mime_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
      if sum(item.file_size for item in archive.infolist()) > 50 * 1024 * 1024:
        raise ValueError("docx_expansion_limit")
    document = Document(io.BytesIO(data))
    texts = [p.text for p in document.paragraphs]
    texts.extend("\t".join(cell.text for cell in row.cells)
                 for table in document.tables for row in table.rows)
    pages = [(None, "\n".join(texts).replace("\x00", "").strip())]
  elif mime_type == "text/plain":
    pages = [(None, data.decode("utf-8-sig").replace("\x00", "").strip())]
  else:
    raise ValueError("unsupported_document")
  if not any(text for _, text in pages):
    raise ValueError("no_extractable_text_ocr_required")
  if sum(len(text) for _, text in pages) > max_chars:
    raise ValueError("document_too_large")
  return pages


def split(pages, size, overlap, max_chunks):
  chunks = []
  for page_no, text in pages:
    start = 0
    while start < len(text):
      end = min(start + size, len(text))
      chunks.append({"chunk_index": len(chunks), "content": text[start:end],
                     "page_no": page_no, "char_start": start, "char_end": end})
      if len(chunks) > max_chunks:
        raise ValueError("too_many_chunks")
      if end == len(text):
        break
      start = end - overlap
  return chunks


def _extract_child(connection, data, mime_type, max_chars):
  # Independent process can be terminated on timeout; no stuck parser poisons a shared pool.
  try:
    import resource
    import sys
    if sys.platform == "linux":
      resource.setrlimit(resource.RLIMIT_AS, (768 * 1024 * 1024, 768 * 1024 * 1024))
    connection.send((True, extract(data, mime_type, max_chars)))
  except Exception as error:
    code = str(error) if isinstance(error, ValueError) and str(error).isidentifier() else "document_parse_failed"
    connection.send((False, code))
  finally:
    connection.close()


async def parse_isolated(data, mime_type, max_chars):
  import asyncio
  import multiprocessing
  context = multiprocessing.get_context("spawn")
  receiver, sender = context.Pipe(duplex=False)
  process = context.Process(target=_extract_child, args=(sender, data, mime_type, max_chars), daemon=True)
  process.start()
  sender.close()
  try:
    while not receiver.poll():
      if not process.is_alive():
        raise ValueError("document_parser_exited")
      await asyncio.sleep(0.05)
    ok, result = receiver.recv()
    if not ok:
      raise ValueError(result)
    return result
  finally:
    receiver.close()
    if process.is_alive():
      process.terminate()
    await asyncio.to_thread(process.join, 2)
    if process.is_alive():
      process.kill()
      await asyncio.to_thread(process.join, 1)
