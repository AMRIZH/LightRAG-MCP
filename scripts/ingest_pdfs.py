from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple
from urllib.parse import urlparse

import requests
from pypdf import PdfReader

REQUIRED_FIELDS = ("author", "title", "year")
OPTIONAL_FIELDS = (
    "journal",
    "venue",
    "publisher",
    "doi",
    "url",
    "volume",
    "issue",
    "pages",
)
LOCAL_HOSTS = {"localhost", "127.0.0.1", "::1"}
DEFAULT_MAX_PDF_SIZE_BYTES = 50 * 1024 * 1024
DEFAULT_MAX_PAGES = 500


def extract_pdf_text(pdf_path: Path, max_pages: int) -> str:
    reader = PdfReader(str(pdf_path))
    if max_pages > 0 and len(reader.pages) > max_pages:
        raise ValueError(
            f"PDF has {len(reader.pages)} pages, exceeding max-pages={max_pages}: {pdf_path.name}"
        )

    chunks: List[str] = []
    for index, page in enumerate(reader.pages, start=1):
        page_text = page.extract_text() or ""
        if page_text.strip():
            chunks.append(f"\\n[PAGE {index}]\\n{page_text}")
    return "\\n".join(chunks).strip()


def load_metadata(meta_path: Path, pdf_path: Path, allow_missing_metadata: bool) -> Dict[str, Any]:
    if not meta_path.exists():
        if not allow_missing_metadata:
            raise FileNotFoundError(f"Missing metadata sidecar: {meta_path}")
        return {"filename": pdf_path.name}

    with meta_path.open("r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, dict):
        raise ValueError(f"Metadata must be a JSON object: {meta_path}")

    data = {str(k): v for k, v in data.items()}
    data.setdefault("filename", pdf_path.name)
    return data


def validate_metadata(meta: Dict[str, Any], pdf_path: Path) -> List[str]:
    errors: List[str] = []
    for field in REQUIRED_FIELDS:
        if not str(meta.get(field, "")).strip():
            errors.append(f"{pdf_path.name}: missing required metadata field '{field}'")
    return errors


def build_apa_reference(meta: Dict[str, Any]) -> str:
    author = str(meta.get("author", "Unknown Author")).strip()
    year = str(meta.get("year", "n.d.")).strip()
    title = str(meta.get("title", "Untitled")).strip()

    source = (
        str(meta.get("journal", "")).strip()
        or str(meta.get("venue", "")).strip()
        or str(meta.get("publisher", "")).strip()
    )

    doi = str(meta.get("doi", "")).strip()
    url = str(meta.get("url", "")).strip()

    parts = [f"{author} ({year}).", f"{title}."]
    if source:
        parts.append(source + ".")
    if doi:
        parts.append(f"https://doi.org/{doi}" if not doi.startswith("http") else doi)
    elif url:
        parts.append(url)

    return " ".join(part for part in parts if part).strip()


def build_enriched_text(meta: Dict[str, Any], pdf_text: str) -> str:
    apa_ref = build_apa_reference(meta)

    metadata_lines = [
        "[REFERENCE_METADATA]",
        f"filename: {meta.get('filename', '')}",
        f"apa_reference: {apa_ref}",
        f"author: {meta.get('author', '')}",
        f"title: {meta.get('title', '')}",
        f"year: {meta.get('year', '')}",
    ]

    for key in OPTIONAL_FIELDS:
        value = meta.get(key, "")
        if str(value).strip():
            metadata_lines.append(f"{key}: {value}")

    metadata_lines.extend([
        "[/REFERENCE_METADATA]",
        "",
        "[DOCUMENT_CONTENT]",
        pdf_text,
        "[/DOCUMENT_CONTENT]",
        "",
    ])

    return "\\n".join(metadata_lines)


def upload_file(
    server: str,
    prepared_path: Path,
    timeout: int = 120,
    api_key: str | None = None,
    allow_remote: bool = False,
) -> Tuple[bool, str]:
    endpoint = server.rstrip("/") + "/documents/upload"

    parsed = urlparse(endpoint)
    if parsed.scheme not in ("http", "https"):
        return False, f"Unsupported server URL scheme: {parsed.scheme}"

    hostname = (parsed.hostname or "").lower()
    is_local = hostname in LOCAL_HOSTS
    if not is_local and not allow_remote:
        return False, "Remote upload blocked. Use --allow-remote to enable non-localhost targets."

    if not is_local and parsed.scheme != "https":
        return False, "Remote upload must use HTTPS."

    headers: Dict[str, str] = {}
    if api_key:
        headers["X-API-Key"] = api_key

    with prepared_path.open("rb") as f:
        response = requests.post(
            endpoint,
            files={"file": (prepared_path.name, f, "text/plain")},
            headers=headers,
            timeout=timeout,
        )
    if response.ok:
        return True, response.text
    return False, f"HTTP {response.status_code}: {response.text}"


def discover_pdfs(pdf_dir: Path, recursive: bool) -> List[Path]:
    pattern = "**/*.pdf" if recursive else "*.pdf"
    return sorted(pdf_dir.glob(pattern))


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare metadata-enriched text from PDFs for LightRAG ingestion."
    )
    parser.add_argument("--pdf-dir", default="data/inputs", help="Directory with PDF files")
    parser.add_argument(
        "--meta-dir",
        default="data/metadata",
        help="Directory with per-file metadata JSON sidecars",
    )
    parser.add_argument(
        "--prepared-dir",
        default="data/inputs_prepared",
        help="Output directory for enriched text files",
    )
    parser.add_argument(
        "--report",
        default="logs/ingest_report.json",
        help="Output report path",
    )
    parser.add_argument("--recursive", action="store_true", help="Scan PDFs recursively")
    parser.add_argument(
        "--skip-existing",
        action="store_true",
        help="Skip output files that already exist",
    )
    parser.add_argument(
        "--allow-missing-metadata",
        action="store_true",
        help="Allow missing sidecar files or required fields (not recommended)",
    )
    parser.add_argument(
        "--upload",
        action="store_true",
        help="Upload prepared files to /documents/upload",
    )
    parser.add_argument(
        "--server",
        default="http://127.0.0.1:9621",
        help="LightRAG server base URL",
    )
    parser.add_argument(
        "--api-key",
        default=os.environ.get("LIGHTRAG_API_KEY", ""),
        help="Optional LightRAG API key sent as X-API-Key",
    )
    parser.add_argument(
        "--allow-remote",
        action="store_true",
        help="Allow non-localhost upload targets",
    )
    parser.add_argument(
        "--max-pdf-size-bytes",
        type=int,
        default=DEFAULT_MAX_PDF_SIZE_BYTES,
        help="Maximum allowed PDF size in bytes (0 disables check)",
    )
    parser.add_argument(
        "--max-pages",
        type=int,
        default=DEFAULT_MAX_PAGES,
        help="Maximum pages per PDF (0 disables check)",
    )

    args = parser.parse_args()

    pdf_dir = Path(args.pdf_dir)
    meta_dir = Path(args.meta_dir)
    prepared_dir = Path(args.prepared_dir)
    report_path = Path(args.report)

    if not pdf_dir.exists():
        print(f"PDF directory not found: {pdf_dir}")
        return 1

    prepared_dir.mkdir(parents=True, exist_ok=True)
    report_path.parent.mkdir(parents=True, exist_ok=True)

    pdf_files = discover_pdfs(pdf_dir, recursive=args.recursive)
    if not pdf_files:
        print("No PDF files found.")
        return 0

    report: Dict[str, Any] = {
        "prepared": 0,
        "uploaded": 0,
        "failed": 0,
        "items": [],
    }

    for pdf_path in pdf_files:
        rel = pdf_path.relative_to(pdf_dir)
        out_path = (prepared_dir / rel).with_suffix(".txt")
        meta_path = (meta_dir / rel).with_suffix(".json")

        out_path.parent.mkdir(parents=True, exist_ok=True)

        if args.skip_existing and out_path.exists():
            report["items"].append(
                {"file": str(pdf_path), "status": "skipped_existing", "output": str(out_path)}
            )
            continue

        try:
            pdf_size = pdf_path.stat().st_size
            if args.max_pdf_size_bytes > 0 and pdf_size > args.max_pdf_size_bytes:
                raise ValueError(
                    f"PDF is {pdf_size} bytes, exceeding max-pdf-size-bytes={args.max_pdf_size_bytes}"
                )

            metadata = load_metadata(
                meta_path,
                pdf_path,
                allow_missing_metadata=args.allow_missing_metadata,
            )
            metadata_errors = validate_metadata(metadata, pdf_path)
            if metadata_errors and not args.allow_missing_metadata:
                raise ValueError("; ".join(metadata_errors))

            pdf_text = extract_pdf_text(pdf_path, max_pages=args.max_pages)
            if not pdf_text.strip():
                raise ValueError("Extracted text is empty")

            enriched_text = build_enriched_text(metadata, pdf_text)
            out_path.write_text(enriched_text, encoding="utf-8")

            item = {
                "file": str(pdf_path),
                "metadata": str(meta_path),
                "output": str(out_path),
                "status": "prepared",
                "metadata_errors": metadata_errors,
            }
            report["prepared"] += 1

            if args.upload:
                ok, message = upload_file(
                    args.server,
                    out_path,
                    api_key=(args.api_key or None),
                    allow_remote=args.allow_remote,
                )
                item["upload"] = "ok" if ok else "failed"
                item["upload_result"] = message
                if ok:
                    report["uploaded"] += 1
                else:
                    report["failed"] += 1

            report["items"].append(item)

        except Exception as exc:
            report["failed"] += 1
            report["items"].append(
                {
                    "file": str(pdf_path),
                    "metadata": str(meta_path),
                    "status": "failed",
                    "error": str(exc),
                }
            )

    report_path.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(
        f"Prepared: {report['prepared']} | Uploaded: {report['uploaded']} | Failed: {report['failed']}"
    )
    print(f"Report: {report_path}")

    return 1 if report["failed"] else 0


if __name__ == "__main__":
    sys.exit(main())
