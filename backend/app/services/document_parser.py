from __future__ import annotations

import io
import os
import zipfile
from dataclasses import dataclass, field
from xml.etree import ElementTree

import fitz
import pdfplumber

from ..config import Settings

SUPPORTED_IMAGE_TYPES = {".png", ".jpg", ".jpeg", ".webp"}


@dataclass
class ParsedDocument:
    file_name: str
    file_type: str
    raw_text: str = ""
    preview_text: str = ""
    is_scanned_document: bool = False
    rendered_images: list[bytes] = field(default_factory=list)


def parse_document(
    file_name: str,
    file_bytes: bytes,
    settings: Settings,
) -> ParsedDocument:
    extension = os.path.splitext(file_name)[1].lower()

    if extension == ".pdf":
        text = _extract_text_from_pdf(file_bytes)
        is_scanned = len(text.strip()) < 80
        images = _render_pdf_to_png(file_bytes) if is_scanned else []
        return ParsedDocument(
            file_name=file_name,
            file_type=extension,
            raw_text=text,
            preview_text=_trim_preview(text, settings.max_preview_chars),
            is_scanned_document=is_scanned,
            rendered_images=images,
        )

    if extension == ".docx":
        text = _extract_text_from_docx(file_bytes)
        return ParsedDocument(
            file_name=file_name,
            file_type=extension,
            raw_text=text,
            preview_text=_trim_preview(text, settings.max_preview_chars),
        )

    if extension == ".txt":
        text = file_bytes.decode("utf-8", errors="ignore")
        return ParsedDocument(
            file_name=file_name,
            file_type=extension,
            raw_text=text,
            preview_text=_trim_preview(text, settings.max_preview_chars),
        )

    if extension in SUPPORTED_IMAGE_TYPES:
        return ParsedDocument(
            file_name=file_name,
            file_type=extension,
            is_scanned_document=True,
            rendered_images=[file_bytes],
        )

    raise ValueError(
        "Unsupported file type. Please upload a PDF, DOCX, TXT, PNG, JPG, JPEG, or WEBP file."
    )


def _extract_text_from_pdf(file_bytes: bytes) -> str:
    pages: list[str] = []
    with pdfplumber.open(io.BytesIO(file_bytes)) as pdf:
        for page in pdf.pages:
            text = page.extract_text() or ""
            if not text.strip():
                # Fallback extractor for pages where pdfminer-based parsing yields no text.
                text = page.extract_text_simple() or ""
            pages.append(text.strip())
    return "\n\n".join(filter(None, pages)).strip()


def _extract_text_from_docx(file_bytes: bytes) -> str:
    with zipfile.ZipFile(io.BytesIO(file_bytes)) as archive:
        document_xml = archive.read("word/document.xml")

    root = ElementTree.fromstring(document_xml)
    namespace = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}

    paragraphs: list[str] = []
    for paragraph in root.findall(".//w:p", namespace):
        texts = [
            node.text.strip()
            for node in paragraph.findall(".//w:t", namespace)
            if node.text and node.text.strip()
        ]
        if texts:
            paragraphs.append("".join(texts))
    return "\n".join(paragraphs).strip()


def _render_pdf_to_png(file_bytes: bytes, zoom: float = 2.0) -> list[bytes]:
    images: list[bytes] = []
    document = fitz.open(stream=file_bytes, filetype="pdf")
    try:
        for page in document:
            pixmap = page.get_pixmap(matrix=fitz.Matrix(zoom, zoom))
            images.append(pixmap.tobytes("png"))
    finally:
        document.close()
    return images


def _trim_preview(text: str, max_length: int) -> str:
    stripped = text.strip()
    if len(stripped) <= max_length:
        return stripped
    return f"{stripped[:max_length].rstrip()}..."
