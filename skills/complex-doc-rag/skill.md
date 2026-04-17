---
name: complex-doc-rag
description: RAG design patterns for complex documents — PDFs (scanned, native, multi-column, tables, embedded images, text-in-images), Excel (multi-sheet, merged cells, embedded charts), CSV (dialect, encoding, wide tables), and standalone images — covering extraction, chunking, metadata, and cost-tiered processing.
---

# Complex Document RAG

RAG pipelines for documents that mix text, tables, images, and layout structure.

## When to Activate

- Building a RAG pipeline that ingests PDFs, Excel, CSV, or image files
- Debugging silent data loss from document extraction (empty chunks, missing tables, dropped figures)
- Designing chunking for documents with tables, figures, or hierarchical headings
- Choosing between OCR libraries or managed document intelligence services
- Optimizing cost when processing large batches of mixed-format documents
- Handling edge cases: scanned PDFs, merged cells, embedded charts, photographed tables
- Deciding how to index multimodal content (charts, diagrams, infographics)

## Extraction Tool Decision Matrix

| Document Type | First-Choice Tool | Fallback / Managed |
|---|---|---|
| PDF — native text | `pdfplumber` or `PyMuPDF` | — |
| PDF — tables | `pdfplumber.extract_tables()` or `camelot-py` | Azure Document Intelligence `prebuilt-layout` |
| PDF — scanned pages | `pdf2image` + `pytesseract` | AWS Textract, Azure Document Intelligence Read, Google Document AI |
| PDF — layout-aware (multi-column) | `unstructured.io` or `Surya` | AWS Textract AnalyzeDocument |
| PDF — embedded images | `PyMuPDF` `page.get_images()` → vision model | — |
| Excel — structure-aware | `openpyxl` | — |
| Excel — formulas as values | `openpyxl(data_only=True)` or `xlrd` | — |
| CSV — dialect/encoding | `csv.Sniffer` + `chardet` | — |
| Image — printed text | `pytesseract` (≥150 DPI) or `PaddleOCR` | Google Vision API, Azure AI Vision Read |
| Image — handwriting | — | Azure AI Vision Read, Google Vision API |
| Image — tables | `TableTransformer` (HuggingFace) | AWS Textract AnalyzeDocument `TABLES` |
| Image — visual/diagrams | — | GPT-4o vision, Claude Sonnet vision, Gemini 1.5 Pro |
| Math formulas | `pix2tex` | Mathpix |
| Multilingual | `PaddleOCR` or `EasyOCR` | Google Vision, Azure AI Vision |

## Tiered Processing Strategy

Never call a vision model on content that can be extracted structurally. Escalate only when lower tiers fail.

```
Tier 1 — free, instant
  ├─ Native PDF: pdfplumber/PyMuPDF text extraction
  ├─ Excel: openpyxl data_only read
  └─ CSV: pandas read with dialect + encoding detection

Tier 2 — cheap, moderate latency
  ├─ Scanned pages: pdf2image + pytesseract / PaddleOCR
  └─ Table structure in images: TableTransformer

Tier 3 — expensive, use sparingly
  └─ Vision model call: only when Tier 1+2 produce
     < confidence_threshold OR content is purely visual
```

```python
def extraction_tier(page_text: str, ocr_confidence: float) -> str:
    if len(page_text.strip()) > 100:          # Tier 1 succeeded
        return "native_text"
    if ocr_confidence >= 0.70:                # Tier 2 acceptable
        return "ocr"
    return "vision_model"                     # Tier 3 required
```

Cache by content hash — never re-call a vision model for a page you've already processed.

```python
import hashlib, json
from pathlib import Path

def vision_with_cache(image_bytes: bytes, prompt: str, cache_dir: Path) -> str:
    key = hashlib.sha256(image_bytes + prompt.encode()).hexdigest()
    cache_file = cache_dir / f"{key}.json"
    if cache_file.exists():
        return json.loads(cache_file.read_text())["description"]
    description = call_vision_model(image_bytes, prompt)
    cache_file.write_text(json.dumps({"description": description}))
    return description
```

## PDF Processing

### Detect Native vs Scanned vs Mixed

```python
import fitz  # PyMuPDF

def classify_pages(pdf_path: str) -> list[dict]:
    doc = fitz.open(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        text = page.get_text().strip()
        images = page.get_images(full=True)
        pages.append({
            "page": i + 1,
            "type": "native" if len(text) > 100 else ("scanned" if images else "blank"),
            "char_count": len(text),
            "image_count": len(images),
        })
    return pages
```

### Native Text Extraction

```python
import pdfplumber

def extract_native_text(pdf_path: str) -> list[dict]:
    chunks = []
    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # Strip headers/footers: exclude top 5% and bottom 7% of page
            h = page.height
            crop = page.crop((0, h * 0.05, page.width, h * 0.93))
            text = crop.extract_text(layout=True) or ""
            if text.strip():
                chunks.append({"page": page.page_number, "text": text, "type": "text"})
    return chunks
```

### Scanned Page OCR

```python
from pdf2image import convert_from_path
import pytesseract
from PIL import Image

def ocr_page(page_image: Image.Image, lang: str = "eng") -> dict:
    data = pytesseract.image_to_data(
        page_image, lang=lang, output_type=pytesseract.Output.DICT
    )
    # Filter low-confidence words
    words = [
        w for w, conf in zip(data["text"], data["conf"])
        if int(conf) > 40 and w.strip()
    ]
    text = " ".join(words)
    avg_conf = sum(c for c in data["conf"] if int(c) > 0) / max(
        sum(1 for c in data["conf"] if int(c) > 0), 1
    )
    return {"text": text, "ocr_confidence": avg_conf / 100}

def ocr_pdf(pdf_path: str, dpi: int = 300) -> list[dict]:
    images = convert_from_path(pdf_path, dpi=dpi)
    return [{"page": i + 1, **ocr_page(img)} for i, img in enumerate(images)]
```

### Multi-Column Layout

```python
# BAD: top-to-bottom reading interleaves columns
text = page.extract_text()

# GOOD: cluster by x-coordinate, sort each column independently
def extract_columns(page) -> str:
    words = page.extract_words()
    if not words:
        return ""
    # Detect column boundaries by gap in x-coordinates
    x_positions = sorted({int(w["x0"] // 50) * 50 for w in words})
    mid_x = (x_positions[0] + x_positions[-1]) / 2 if len(x_positions) > 1 else float("inf")

    left = sorted([w for w in words if w["x0"] < mid_x], key=lambda w: (w["top"], w["x0"]))
    right = sorted([w for w in words if w["x0"] >= mid_x], key=lambda w: (w["top"], w["x0"]))

    def words_to_text(ws):
        return " ".join(w["text"] for w in ws)

    return words_to_text(left) + "\n\n" + words_to_text(right)
```

### Table Extraction from PDFs

```python
def extract_tables_from_page(page) -> list[dict]:
    tables = page.extract_tables()
    result = []
    for table in tables:
        if not table or not table[0]:
            continue
        headers = [str(h or "").strip() for h in table[0]]
        rows = []
        for row in table[1:]:
            if any(cell for cell in row if cell):  # skip all-empty rows
                rows.append({headers[i]: str(cell or "").strip()
                              for i, cell in enumerate(row)})
        # Serialize as Markdown — preserves structure in embedding
        md = "| " + " | ".join(headers) + " |\n"
        md += "| " + " | ".join("---" for _ in headers) + " |\n"
        for row in rows:
            md += "| " + " | ".join(row.get(h, "") for h in headers) + " |\n"
        result.append({"type": "table", "markdown": md, "row_count": len(rows)})
    return result
```

#### Cross-Page Tables

```python
# BAD: Each page's table fragment is an independent chunk
# GOOD: Carry headers forward onto continuation pages

def merge_cross_page_tables(page_tables: list[list[dict]]) -> list[dict]:
    merged = []
    pending_header = None
    for page_idx, tables in enumerate(page_tables):
        for table in tables:
            headers = table["headers"]
            # If this table's column count matches the last seen header,
            # and it has no header row of its own, it's a continuation
            if (pending_header and
                    len(headers) == len(pending_header) and
                    headers == pending_header):
                # Prepend headers to continuation chunk
                table["continuation"] = True
                table["headers_prepended"] = pending_header
            else:
                pending_header = headers
            merged.append(table)
    return merged
```

### Embedded Images in PDFs

```python
import fitz
import base64
import anthropic

client = anthropic.Anthropic()

def extract_and_describe_images(pdf_path: str, cache_dir) -> list[dict]:
    doc = fitz.open(pdf_path)
    figures = []
    for page_num, page in enumerate(doc, 1):
        for img_index, img in enumerate(page.get_images(full=True)):
            xref = img[0]
            base_image = doc.extract_image(xref)
            image_bytes = base_image["image"]

            description = vision_with_cache(
                image_bytes,
                "Describe this image. If it is a chart or graph, extract: "
                "chart type, title, axis labels, approximate values, and key trends. "
                "If it contains text, extract all visible text verbatim.",
                cache_dir,
            )
            # Find adjacent caption text (heuristic: text within 50pt below image bbox)
            figures.append({
                "page": page_num,
                "type": "figure",
                "description": description,
                "image_index": img_index,
            })
    return figures
```

### Heading Hierarchy Detection

```python
def detect_headings(page) -> list[dict]:
    """Extract text with font size metadata for hierarchy inference."""
    blocks = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:  # skip image blocks
            continue
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                blocks.append({
                    "text": span["text"].strip(),
                    "size": round(span["size"]),
                    "bold": "bold" in span.get("font", "").lower(),
                    "bbox": span["bbox"],
                })
    # Infer heading level from font size rank
    sizes = sorted({b["size"] for b in blocks}, reverse=True)
    size_to_level = {s: i + 1 for i, s in enumerate(sizes[:4])}
    return [
        {**b, "heading_level": size_to_level.get(b["size"])}
        for b in blocks
        if b["bold"] or b["size"] in size_to_level
    ]
```

## Excel Processing

### Multi-Sheet with Visibility Check

```python
import openpyxl

def load_workbook_sheets(path: str, include_hidden: bool = False) -> dict:
    wb = openpyxl.load_workbook(path, data_only=True)
    sheets = {}
    for name in wb.sheetnames:
        ws = wb[name]
        if not include_hidden and ws.sheet_state != "visible":
            continue  # never silently include hidden data in public-facing RAG
        sheets[name] = ws
    return sheets
```

### Merged Cell Normalization

```python
def normalize_merged_cells(ws) -> list[list]:
    """Fill merged cell siblings with the top-left value before DataFrame conversion."""
    for merge_range in ws.merged_cells.ranges:
        top_left = ws.cell(merge_range.min_row, merge_range.min_col).value
        for row in ws.iter_rows(
            min_row=merge_range.min_row, max_row=merge_range.max_row,
            min_col=merge_range.min_col, max_col=merge_range.max_col,
        ):
            for cell in row:
                cell.value = top_left  # fill siblings

    return [[cell.value for cell in row] for row in ws.iter_rows()]
```

### Formula vs Value Handling

```python
# BAD: reads formula strings, not computed values
wb = openpyxl.load_workbook(path)   # data_only defaults to False

# GOOD: reads cached computed values
wb = openpyxl.load_workbook(path, data_only=True)
# If a cell returns None under data_only=True, the file was never calculated
# → warn and flag for manual review; do NOT embed None as "missing"

def safe_cell_value(cell) -> str:
    val = cell.value
    if val is None:
        return ""
    # Normalize Excel date serials
    if cell.is_date and isinstance(val, (int, float)):
        from openpyxl.utils.datetime import from_excel
        return from_excel(val).isoformat()
    return str(val).strip()
```

### Wide Table — Vertical Chunking

```python
import pandas as pd

def chunk_wide_table(df: pd.DataFrame, source: str, sheet: str,
                     max_cols: int = 20) -> list[dict]:
    chunks = []
    if len(df.columns) <= max_cols:
        # Narrow enough — represent each row as a JSON-keyed string
        for i, row in df.iterrows():
            non_null = {k: v for k, v in row.items() if pd.notna(v) and str(v).strip()}
            if not non_null:
                continue
            text = "; ".join(f"{k}: {v}" for k, v in non_null.items())
            chunks.append({
                "text": text, "source": source, "sheet": sheet, "row": i + 2,
                "type": "table_row",
            })
    else:
        # Very wide: column-group chunking
        col_groups = [list(df.columns[i:i + max_cols])
                      for i in range(0, len(df.columns), max_cols)]
        for group in col_groups:
            sub_df = df[group].dropna(how="all")
            for i, row in sub_df.iterrows():
                non_null = {k: v for k, v in row.items() if pd.notna(v)}
                if not non_null:
                    continue
                text = "; ".join(f"{k}: {v}" for k, v in non_null.items())
                chunks.append({
                    "text": text, "source": source, "sheet": sheet,
                    "row": i + 2, "col_group": group[0], "type": "table_row",
                })
    return chunks
```

### Embedded Charts

```python
def extract_chart_metadata(ws) -> list[dict]:
    descriptions = []
    for chart in getattr(ws, "_charts", []):
        title = getattr(chart.title, "tx", None) or "Untitled Chart"
        series_names = [str(getattr(s, "title", "") or "") for s in chart.series]
        descriptions.append({
            "type": "chart",
            "title": str(title),
            "chart_type": type(chart).__name__,
            "series": series_names,
            # Embed chart title + series as text; for visual content
            # extract EMF/PNG from xlsx zip and send to vision model
            "text": f"Chart: {title}. Type: {type(chart).__name__}. "
                    f"Series: {', '.join(filter(None, series_names))}",
        })
    return descriptions
```

## CSV Processing

### Dialect and Encoding Detection

```python
import csv, chardet
from io import StringIO

def load_csv_robust(path: str) -> tuple[pd.DataFrame, dict]:
    raw = open(path, "rb").read()
    detected = chardet.detect(raw)
    encoding = detected["encoding"] or "utf-8"

    text = raw.decode(encoding, errors="replace")
    dialect = csv.Sniffer().sniff(text[:4096], delimiters=",;\t|")

    df = pd.read_csv(
        StringIO(text),
        sep=dialect.delimiter,
        encoding="utf-8",          # already decoded
        encoding_errors="replace",
        on_bad_lines="warn",
        engine="python",           # handles embedded newlines in quoted fields
    )
    # Strip BOM from column names
    df.columns = [c.lstrip("\ufeff").strip() for c in df.columns]
    # Strip whitespace from string columns
    str_cols = df.select_dtypes(include="object").columns
    df[str_cols] = df[str_cols].apply(lambda c: c.str.strip())

    return df, {"encoding": encoding, "delimiter": dialect.delimiter}
```

### Header Detection Heuristic

```python
def has_header_row(df: pd.DataFrame) -> bool:
    """Returns False if the first row looks like data, not headers."""
    try:
        pd.to_numeric(pd.Series(df.columns))
        return False  # numeric column names → no header
    except (ValueError, TypeError):
        pass
    # If all column names are single digits or short numbers, probably no header
    numeric_names = sum(1 for c in df.columns if str(c).replace(".", "").isdigit())
    return numeric_names < len(df.columns) / 2
```

### Aggregate / Footer Row Detection

```python
AGGREGATE_KEYWORDS = {"total", "sum", "average", "grand total", "subtotal", "count"}

def strip_footer_rows(df: pd.DataFrame) -> pd.DataFrame:
    first_col = df.iloc[:, 0].astype(str).str.lower().str.strip()
    is_footer = first_col.isin(AGGREGATE_KEYWORDS)
    return df[~is_footer]
```

## Image Processing

### Pre-Processing Before OCR

```python
import cv2
import numpy as np
from PIL import Image

def preprocess_for_ocr(img: Image.Image) -> Image.Image:
    cv_img = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
    gray = cv2.cvtColor(cv_img, cv2.COLOR_BGR2GRAY)
    # Deskew
    coords = np.column_stack(np.where(gray < 200))
    angle = cv2.minAreaRect(coords)[-1]
    if angle < -45:
        angle = 90 + angle
    (h, w) = gray.shape
    M = cv2.getRotationMatrix2D((w // 2, h // 2), angle, 1.0)
    rotated = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                              borderMode=cv2.BORDER_REPLICATE)
    # Contrast enhancement
    clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
    enhanced = clahe.apply(rotated)
    return Image.fromarray(enhanced)

def check_resolution(img: Image.Image, min_dpi: int = 150) -> bool:
    dpi = img.info.get("dpi", (72, 72))
    return min(dpi) >= min_dpi
```

### Image Routing Logic

```python
def process_image(image_bytes: bytes, cache_dir) -> dict:
    img = Image.open(io.BytesIO(image_bytes))

    # Low-resolution: warn, attempt upscale or flag
    if not check_resolution(img):
        return {"text": "", "method": "skipped", "reason": "low_resolution",
                "ocr_confidence": 0.0}

    img = preprocess_for_ocr(img)

    # Try OCR first
    data = pytesseract.image_to_data(img, output_type=pytesseract.Output.DICT)
    confidences = [int(c) for c in data["conf"] if int(c) > 0]
    avg_conf = sum(confidences) / len(confidences) if confidences else 0
    text = " ".join(w for w, c in zip(data["text"], data["conf"])
                    if int(c) > 40 and w.strip())

    if avg_conf >= 70 and len(text.strip()) > 20:
        return {"text": text, "method": "ocr", "ocr_confidence": avg_conf / 100}

    # Fallback: vision model
    description = vision_with_cache(
        image_bytes,
        "Extract all visible text from this image verbatim. "
        "If the image is a chart, diagram, or infographic, describe it in detail: "
        "include all labels, values, trends, and the relationships shown.",
        cache_dir,
    )
    return {"text": description, "method": "vision_model", "ocr_confidence": None}
```

### Photographed / Tilted Tables

```python
from transformers import AutoModelForObjectDetection, AutoImageProcessor
import torch

def detect_table_structure(img: Image.Image) -> list[dict]:
    """Use Microsoft Table Transformer to detect rows and columns."""
    processor = AutoImageProcessor.from_pretrained(
        "microsoft/table-structure-recognition-v1.1-all"
    )
    model = AutoModelForObjectDetection.from_pretrained(
        "microsoft/table-structure-recognition-v1.1-all"
    )
    inputs = processor(images=img, return_tensors="pt")
    with torch.no_grad():
        outputs = model(**inputs)
    target_sizes = torch.tensor([img.size[::-1]])
    results = processor.post_process_object_detection(
        outputs, threshold=0.7, target_sizes=target_sizes
    )[0]
    return [
        {"label": model.config.id2label[label.item()], "bbox": box.tolist()}
        for label, box in zip(results["labels"], results["boxes"])
    ]
```

## Chunking for Complex Documents

### Chunk Schema

Every chunk regardless of source type:

```python
from dataclasses import dataclass, field
from datetime import datetime

@dataclass
class DocumentChunk:
    id: str                          # sha256(source + page + chunk_index)
    text: str                        # text for embedding
    source_file: str                 # original file path / URI
    document_type: str               # pdf | xlsx | csv | image
    page_or_sheet: str               # "page_3" | "sheet_January" | "rows_2-50"
    element_type: str                # text | table | figure | heading | footnote
    chunk_index: int
    extraction_method: str           # native_text | ocr | vision_model
    ocr_confidence: float | None     # None for native text
    heading_path: str                # "Chapter 3 > Section 3.2"
    last_modified: datetime | None
    extra: dict = field(default_factory=dict)  # source-specific extras
```

### Table-Aware Chunking (Never Split Mid-Row)

```python
from langchain.text_splitter import RecursiveCharacterTextSplitter

def chunk_document(chunks: list[DocumentChunk],
                   max_tokens: int = 512) -> list[DocumentChunk]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=max_tokens * 4,   # ~4 chars/token
        chunk_overlap=64,
        separators=["\n\n", "\n", ". ", " "],
    )
    result = []
    for chunk in chunks:
        if chunk.element_type == "table":
            # Tables are atomic — never split; keep as-is
            # If table exceeds limit, split only at row boundaries (| separator)
            if len(chunk.text) <= max_tokens * 4:
                result.append(chunk)
            else:
                result.extend(_split_table_by_rows(chunk, max_tokens))
        elif chunk.element_type == "figure":
            result.append(chunk)           # figures + captions stay atomic
        else:
            # Prose: normal recursive split
            for i, sub_text in enumerate(splitter.split_text(chunk.text)):
                result.append(DocumentChunk(
                    **{**chunk.__dict__, "text": sub_text, "chunk_index": i}
                ))
    return result

def _split_table_by_rows(chunk: DocumentChunk, max_tokens: int) -> list[DocumentChunk]:
    lines = chunk.text.split("\n")
    header = lines[:2]    # Markdown table header + separator row
    body = lines[2:]
    max_chars = max_tokens * 4
    sub_chunks, current, idx = [], header[:], 0
    for line in body:
        if sum(len(l) for l in current) + len(line) > max_chars:
            text = "\n".join(current)
            sub_chunks.append(DocumentChunk(
                **{**chunk.__dict__, "text": text, "chunk_index": idx,
                   "extra": {**chunk.extra, "headers_prepended": True}}
            ))
            current = header + [line]   # prepend headers to every split
            idx += 1
        else:
            current.append(line)
    if current:
        sub_chunks.append(DocumentChunk(
            **{**chunk.__dict__, "text": "\n".join(current), "chunk_index": idx,
               "extra": {**chunk.extra, "headers_prepended": True}}
        ))
    return sub_chunks
```

### Figure + Caption Co-location

```python
def attach_captions(figures: list[dict], page_text_blocks: list[dict]) -> list[dict]:
    """
    Match figures to their captions by spatial proximity.
    Caption heuristic: text starting with Figure/Fig./Chart/Table/Diagram
    within 50pt below the image bounding box.
    """
    import re
    CAPTION_RE = re.compile(
        r"^(Figure|Fig\.|Chart|Diagram|Table|Image)\s*\d+", re.IGNORECASE
    )
    for figure in figures:
        fig_bottom = figure.get("bbox", {}).get("y1", 0)
        candidates = [
            b for b in page_text_blocks
            if CAPTION_RE.match(b["text"])
            and b.get("top", 0) >= fig_bottom
            and b.get("top", 0) <= fig_bottom + 50
        ]
        if candidates:
            figure["caption"] = candidates[0]["text"]
            # Merge caption into chunk text so they're never separated
            figure["text"] = figure["description"] + "\n\nCaption: " + figure["caption"]
    return figures
```

### Heading-Aware Chunk Prefix

```python
def prefix_with_hierarchy(chunk: DocumentChunk, hierarchy: dict) -> DocumentChunk:
    """
    Prepend heading path so the chunk is self-contained for retrieval.
    e.g. "[Chapter 3 > Section 3.2] Revenue increased by 12%..."
    """
    if chunk.heading_path:
        chunk.text = f"[{chunk.heading_path}]\n{chunk.text}"
    return chunk
```

### Long Text Cell Splitting (Excel/CSV)

```python
MAX_CELL_CHARS = 500

def handle_long_cells(df: pd.DataFrame, source: str, sheet: str) -> list[dict]:
    chunks = []
    for i, row in df.iterrows():
        for col in df.columns:
            val = str(row[col]) if pd.notna(row[col]) else ""
            if len(val) <= MAX_CELL_CHARS:
                continue
            # Split long cell; prepend column name to every sub-chunk
            splitter = RecursiveCharacterTextSplitter(chunk_size=MAX_CELL_CHARS, chunk_overlap=50)
            for j, sub in enumerate(splitter.split_text(val)):
                chunks.append({
                    "text": f"{col}: {sub}",
                    "source": source, "sheet": sheet, "row": i + 2,
                    "col": col, "sub_chunk": j, "type": "long_cell",
                })
    return chunks
```

## Edge Case Reference

| Edge Case | Symptom | Fix |
|---|---|---|
| Scanned PDF — no text layer | Empty chunks | Detect via `len(page_text) < 100`; route to OCR |
| Mixed PDF (some scanned, some native) | Missing pages | Per-page detection; hybrid extraction |
| Multi-column PDF | Interleaved sentences | Cluster words by x-coord; sort each column |
| Cross-page table | Orphan data rows without headers | Carry header row forward; detect by column-count match |
| Table split mid-row | Broken records in chunks | Use table-aware chunker; only split at row boundaries |
| Embedded PDF image (figure) | Lost visual content | Extract with `page.get_images()`; describe via vision model |
| Text in PDF image (callout, watermark) | Silent loss | OCR all extracted images, not just fully scanned pages |
| Headers / footers in text | Boilerplate pollutes chunks | Exclude top 5% and bottom 7% by y-coordinate |
| Footnote spliced into body | Broken paragraph coherence | Detect by y-position + font size; attach as metadata |
| ToC chunked as content | Retrieval surfaces navigation, not answers | Detect ToC pages; skip for content, use for hierarchy map |
| Password-protected PDF | Crash or empty index | Catch `FileNotDecryptedError`; queue as `status: blocked` |
| DRM / copy-restricted PDF | Empty extraction despite visible content | Check `doc.permissions`; flag `text_extractable: false` |
| Multi-column RTL text (Arabic, Hebrew) | Wrong character order | Use PyMuPDF (better bidi); apply `python-bidi` post-extraction |
| Excel hidden sheets | Sensitive data indexed | Check `ws.sheet_state`; default to skip hidden |
| Excel merged cells | NaN column names / values | Normalize merges with openpyxl before DataFrame conversion |
| Excel `data_only=True` returns None | Formula never computed | Warn + flag; do not index `None` as content |
| Excel date serial number | `44927.0` instead of `2023-01-01` | Check `cell.is_date`; apply `from_excel()` |
| Excel embedded chart | Key insight invisible | Extract chart title + series as text; optionally send chart image to vision model |
| CSV ambiguous delimiter | One giant column | `csv.Sniffer()` auto-detect; try `,;\t\|` candidates |
| CSV no header row | First data row used as column names | Heuristic: numeric column names → `header=None` |
| CSV aggregate footer row (`Total`, `Sum`) | Corrupts numeric stats | Detect and strip aggregate keywords from first column |
| CSV encoding (`cp1252`, `latin-1`) | Mojibake in chunks | `chardet.detect()` before read; normalize to UTF-8 |
| Image below 150 DPI | Garbage OCR output | Check DPI; flag `low_resolution: true`; attempt Real-ESRGAN upscale |
| Handwritten text | Poor OCR output | Use Azure AI Vision Read or Google Vision API; never pytesseract |
| Diagram without OCR-able text | Zero-content chunk | Route all images to vision model description |
| Photographed table | Lost row/column structure | Apply TableTransformer cell detection; OCR each cell individually |
| Figure caption in different chunk | Retrieval splits context | Attach caption within 50pt below figure bbox to same chunk |
| Oversized text cell (Excel/CSV) | Chunk exceeds context window | Split long cells; prepend column name to each sub-chunk |
| Corrupt / truncated file | Batch job crash | Wrap all `open()` calls in try/except; dead-letter queue |
| Cross-reference (`see Figure 3`) | Retrieved chunk has no figure description | Dereference during extraction: append target figure description inline |
| Version / re-indexing | Stale or duplicate chunks | Per-page SHA-256 hash; delete-then-reindex only changed pages |
| Vision API cost at scale | Budget blowout | Tier 1→2→3 escalation; content-hash cache; use Batch API (50% discount) |

## Checklist

Before shipping a complex document RAG pipeline:

- [ ] Per-page/per-sheet content detection in place (native vs scanned vs blank)
- [ ] Tiered processing: native text → OCR → vision model, never vision-first
- [ ] Vision API results cached by content hash; no duplicate calls on re-index
- [ ] PDF tables extracted via `pdfplumber.extract_tables()` or `camelot-py`, not raw text
- [ ] Cross-page table headers carried forward to every continuation chunk
- [ ] Figures extracted from PDFs and described via vision model; captions co-located
- [ ] Headers/footers stripped (top 5% / bottom 7% y-position exclusion)
- [ ] Excel hidden sheets excluded by default; policy documented
- [ ] Excel merged cells normalized before DataFrame conversion
- [ ] Excel dates converted from serial numbers to ISO 8601 strings
- [ ] CSV dialect auto-detected; BOM stripped; encoding normalized to UTF-8
- [ ] CSV aggregate/footer rows stripped before chunking
- [ ] Every chunk carries mandatory metadata: `source_file`, `page_or_sheet`, `element_type`, `extraction_method`, `ocr_confidence`
- [ ] Table chunks never split mid-row; header row prepended to every split fragment
- [ ] Long text cells (>500 chars) split with column name prefix on each sub-chunk
- [ ] Corrupt files caught and routed to dead-letter queue; batch never crashes
- [ ] Per-page SHA-256 hash stored for incremental re-indexing
- [ ] Low-confidence OCR output (`< 0.7`) flagged in metadata and reviewed before production use

> See also: `ai-engineer`, `azure`, `observability`
