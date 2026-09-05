import pymupdf

# spec2.md section 12: fixed-size chunking, 800-1200 tokens with 100-200
# overlap. Chinese text runs roughly 1 token/char under most tokenizers, so
# character counts are used directly as a token-count proxy rather than
# pulling in a separate tokenizer dependency.
CHUNK_SIZE = 1000
CHUNK_OVERLAP = 150


def extract_pages(file_bytes: bytes) -> list[tuple[int, str]]:
    """Extract per-page text. Pages with no extractable text (e.g. pure
    scanned images) are skipped rather than failing the whole document."""
    doc = pymupdf.open(stream=file_bytes, filetype="pdf")
    try:
        pages = []
        for page_num, page in enumerate(doc, start=1):
            text = page.get_text()
            if text.strip():
                pages.append((page_num, text))
        return pages
    finally:
        doc.close()


def chunk_pages(pages: list[tuple[int, str]]) -> list[dict]:
    """Fixed-size chunking with overlap, kept within page boundaries so
    each chunk's `page` metadata stays exact for source citation."""
    chunks = []
    chunk_index = 0
    for page_num, text in pages:
        start = 0
        length = len(text)
        while start < length:
            end = min(start + CHUNK_SIZE, length)
            content = text[start:end].strip()
            if content:
                chunks.append({"page": page_num, "chunk_index": chunk_index, "content": content})
                chunk_index += 1
            if end == length:
                break
            start = end - CHUNK_OVERLAP
    return chunks
