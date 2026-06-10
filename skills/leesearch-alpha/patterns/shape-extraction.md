---
name: shape-extraction
description: >-
  Practical how-to for extracting each data shape: structured from APIs/DBs, semi-structured
  from PDFs/tables, video via farm, OCR from image documents.
metadata:
  type: reference
---

# Shape extraction patterns

## When to use
Loop steps 2-3, when planning sources and collecting findings. This file tells you HOW to produce each artifact type.

## Structured (CSV/JSON/API)

| Source | How to extract |
|---|---|
| **DART** (dart.fss.or.kr) | API: `https://opendart.fss.or.kr/api/` — financial statements, major shareholder changes, disclosure search. Requires API key. Extract to JSON. |
| **KIPRIS** (kipris.or.kr) | Patent search API or web scrape. Extract patent counts, filing dates, IPC codes to structured format. |
| **NTIS** (ntis.go.kr) | National R&D project search. Extract project details, funding amounts, participating institutions. |
| **Exchange filings** | KRX KIND (kind.krx.co.kr) for Korean market disclosures. Extract to JSON with typed fields. |
| **Trade data** | UN Comtrade, KITA (kita.net), customs HS code data. Extract volume/value time series. |

**Key rule:** don't repackage news-sourced numbers into JSON and call it "structured." The structured shape requires data from an official source with typed fields.

## Semi-structured (PDF tables, dashboards)

1. **PDF extraction**: Use `deep-browser-research` or `farm_evidence_run` to capture the page, then `farm_extract_structured` for tables. Register the extraction as a finding.
2. **Dashboard screenshots**: `farm_sample_frames` on data dashboards (Social Blade, PlayBoard, FnGuide, Valueline). The labeled values in the screenshot = semi-structured.
3. **Analyst reports**: Often behind soft walls but summary pages are public. Extract the key metrics table.

**Key rule:** a semi-structured finding must have LABELED VALUES (column headers + data), not just prose that mentions numbers.

## Video/audio

1. **Search first**: YouTube search for "[topic] in Korean/English". Check results exist.
2. **Capture**: `farm_evidence_run` with the video URL → registers the page.
3. **Frame sampling**: `farm_sample_frames` → captures key frames as visual evidence.
4. **ASR (spoken content)**:
   - If captions available → `youtube-research` (fast, free)
   - If no captions / foreign language / need accuracy → `leesearch-video-heavy` (refcap whisper, local)
5. **Register**: Both frames and transcript as findings with shape = video.

**Key rule:** a YouTube URL in your findings ≠ video shape. You must actually capture frames or transcript content.

## OCR (image-based documents)

1. **Identify**: scanned PDFs (no selectable text), infographics, presentation slides, screenshots with embedded text.
2. **Capture**: `farm_evidence_run` → `farm_sample_frames` for the relevant pages/slides.
3. **Extract**: use OCR tooling (tesseract via refcap, or farm's text extraction on captured frames).
4. **Register**: the extracted text as a finding with shape = OCR.

**Key rule:** a regular PDF with selectable text is semi-structured, not OCR. OCR is specifically for image-to-text conversion.
