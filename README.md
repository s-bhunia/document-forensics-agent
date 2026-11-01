# Doxket Forensics

Finds signs of editing in screenshots, scans, photos, PDFs and Word documents. Upload a file and get a risk
score, a summary and a list of findings, each boxed on the page.

## Quick start

```bash
cp .env.example .env          # optional: set LLM_* for AI summaries
docker compose up -d --build
```

- App: http://localhost:8080
- API docs (OpenAPI): http://localhost:8000/docs

## Architecture

```
browser ──► web (nginx + React) ──/api──► api (FastAPI) ──► PostgreSQL (analyses, results as JSONB)
                                              │
                                              └─ enqueue ─► Redis ─► worker × N (RQ) ──► forensics pipeline
                                                                         │
                                         shared volume /data  ◄──────────┘  (uploads, page images, heatmaps)
```

| Service | Tech |
|---|---|
| web | React 18, TypeScript, Vite, Tailwind, TanStack Query, served by nginx |
| api | FastAPI, SQLAlchemy 2, Pydantic 2 |
| worker | RQ worker running the forensics pipeline |
| db | PostgreSQL 16 |
| queue | Redis 7 |

## How the analysis works

| Stage | What it does | Libraries |
|---|---|---|
| Ingest | Detects the file type from its bytes. Images are EXIF-rotated and flattened; PDF pages are rendered and their text layer is used when present; DOCX text, formatting and embedded images are read. | Pillow, PyMuPDF, python-docx |
| OCR | Word-level text with boxes and line grouping (Tesseract 5 LSTM, dense then sparse layout). | Tesseract, pytesseract |
| Word measurements | Per word: stroke width and stroke contrast (distance transform on the skeleton), cap/x-height, ink colour and darkness relative to the local background (CIELAB), edge sharpness normalised by contrast, background grain, baseline. | OpenCV, scikit-image, NumPy |
| Line consistency | Each word against the other words on its line. Catches words retyped into an existing sentence. | |
| Peer consistency | Words grouped by size and ink colour; robust z-scores flag the odd one out. | |
| Digit widths | Values in the same format (e.g. `dd-mm-yyyy`) at the same size must have identical widths, because printed digits are tabular. | |
| Alignment | Words that sit off the baseline formed by their neighbours. | |
| Error level | JPEG re-compression residual normalised by local detail; heatmap layer plus outlier regions. | OpenCV |
| Grain map | Local noise level on smooth areas; regions that lost or gained grain. | OpenCV, SciPy |
| Copy-move | SIFT self-matching outside text, clustered by displacement; plus pixel-identical regions across pages (cloned stamps and signatures). | OpenCV |
| PDF checks | Incremental revisions, editing tools in producer/creator, font changes inside a line, the same font embedded twice, filled boxes over scanned images, visible text typed over a scan. | PyMuPDF |
| DOCX checks | Font/size changes inside a paragraph, values typed in a later editing session (rsid), tracked changes, author vs last editor. | python-docx |
| ID checks | PAN holder type, Aadhaar Verhoeff checksum, GSTIN checksum, impossible calendar dates. | |
| AI review (optional) | Any OpenAI-compatible chat API writes the summary and adds semantic findings (totals, date order, cross-field mismatches). | httpx |
| Scoring | Severity-weighted, diminishing per category, into `likely_authentic`, `suspicious` or `highly_risky`. | |

Findings carry normalised boxes, the measured values and the peer medians so a reviewer can see why something
was flagged. Template quirks (whole paragraphs in another font, uneven photocopy quality) are deliberately
weighted low; changes *within* a line or a field are weighted high.

## AI review

Set these in `.env`, then `docker compose up -d`:

```
LLM_BASE_URL=https://api.openai.com/v1     # or any OpenAI-compatible endpoint
LLM_API_KEY=...
LLM_MODEL=...
LLM_JSON_MODE=true                         # set false if the provider rejects response_format
```

Without a key the pipeline runs fully and writes a rule-based summary.

## Tests

```bash
docker compose run --rm --no-deps api pytest            # backend: detectors, pipeline, API
docker compose run --rm --no-deps api pytest --cov=app  # with coverage
cd frontend && npm ci && npm test -- --run              # frontend
```

Backend tests render synthetic documents with Liberation Serif/Sans (metric clones of Times/Arial) and
check both directions: edited documents are flagged in the right place, clean ones are not.

## API

See [docs/api.md](docs/api.md). Main calls: `POST /api/analyses` (multipart `file`), `GET /api/analyses/{id}`,
`GET /api/analyses`, `DELETE /api/analyses/{id}`, `GET /api/analyses/{id}/files/{path}`.

## Configuration

| Variable | Default | |
|---|---|---|
| `MAX_UPLOAD_MB` | 25 | Upload limit |
| `OCR_LANG` | eng | Tesseract languages, e.g. `eng+hin` |
| `WORKER_REPLICAS` | 2 | Parallel analyses |
| `POSTGRES_*` | doxket | Database credentials |

## Accuracy on real samples

Four real documents with known answers, run through the full pipeline:

| Sample | Truth | Result |
|---|---|---|
| PAN card, DOB retyped in regular weight | Edited | Only finding: the DOB, high (stroke contrast 0.39 vs 0.20, 24% larger) |
| Same PAN card, original | Genuine | Likely authentic (risk 0.06) |
| Driving licence, DOB retyped | Edited | Top finding: DOB is 3.2% wider than 4 matching dates (96 vs 93 px), plus two layout false alarms |
| University NOC scan, "Research Intern in" retyped in Arial | Edited | Missed; the scan app's filtering makes the inserted sans words measure like the serif text |

Four samples show the method works, not how accurate it is. Build a labelled set of your own documents and
tune the thresholds in `app/forensics/consistency.py` against it.

## Limits

- Text checks depend on OCR. Busy security backgrounds and tiny screenshots lose words; five OCR passes are merged to reduce this.
- Heavily filtered or recompressed scans flatten typeface differences. A trained serif/sans classifier per word would be the next upgrade.
- Dense ID-card layouts mix fonts on purpose, so line checks there produce more false alarms than on letters and invoices.
- Pixel checks need several comparable words. A field with no peers in the same style can only be judged by the line it sits in.
- Findings are evidence for a reviewer, not proof.
