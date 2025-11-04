"""Sanitize datasets by scrubbing PII and replacing with hashed placeholders."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Optional, Any

import typer

app = typer.Typer()

# PII patterns (simplified - production should use spaCy NER or similar)
EMAIL_PATTERN = re.compile(r'\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b')
PHONE_PATTERN = re.compile(r'\b(?:\+?1[-.]?)?\(?([0-9]{3})\)?[-.]?([0-9]{3})[-.]?([0-9]{4})\b')
SSN_PATTERN = re.compile(r'\b\d{3}-\d{2}-\d{4}\b')
CC_PATTERN = re.compile(r'\b(?:\d{4}[-\s]?){3}\d{4}\b')
URL_PATTERN = re.compile(r'https?://[^\s]+')

# Common name patterns (very basic - production needs better detection)
NAME_PREFIXES = ['Mr.', 'Mrs.', 'Ms.', 'Dr.', 'Prof.']


def stable_hash(value: str, prefix: str = "") -> str:
    """Generate a stable hash for PII replacement."""
    digest = hashlib.sha256(value.encode('utf-8')).hexdigest()[:8]
    return f"{prefix}{digest}" if prefix else digest


def sanitize_text(text: str, use_hashing: bool = True) -> tuple[str, list[str]]:
    """Scrub PII from text and return (sanitized_text, detected_pii_types).

    Args:
        text: Input text to sanitize
        use_hashing: If True, use stable hashes for replacements. If False, use generic placeholders.

    Returns:
        Tuple of (sanitized text, list of detected PII types)
    """
    detected = []
    sanitized = text

    # Email addresses
    for match in EMAIL_PATTERN.finditer(text):
        email = match.group()
        replacement = f"email_{stable_hash(email)}" if use_hashing else "[EMAIL_REDACTED]"
        sanitized = sanitized.replace(email, replacement)
        if "email" not in detected:
            detected.append("email")

    # Phone numbers
    for match in PHONE_PATTERN.finditer(text):
        phone = match.group()
        replacement = f"phone_{stable_hash(phone)}" if use_hashing else "[PHONE_REDACTED]"
        sanitized = sanitized.replace(phone, replacement)
        if "phone" not in detected:
            detected.append("phone")

    # SSN
    for match in SSN_PATTERN.finditer(text):
        ssn = match.group()
        replacement = f"ssn_{stable_hash(ssn)}" if use_hashing else "[SSN_REDACTED]"
        sanitized = sanitized.replace(ssn, replacement)
        if "ssn" not in detected:
            detected.append("ssn")

    # Credit cards
    for match in CC_PATTERN.finditer(text):
        cc = match.group()
        replacement = f"cc_{stable_hash(cc)}" if use_hashing else "[CC_REDACTED]"
        sanitized = sanitized.replace(cc, replacement)
        if "credit_card" not in detected:
            detected.append("credit_card")

    # URLs (optional - may want to keep some)
    # for match in URL_PATTERN.finditer(text):
    #     url = match.group()
    #     replacement = f"url_{stable_hash(url)}" if use_hashing else "[URL_REDACTED]"
    #     sanitized = sanitized.replace(url, replacement)
    #     if "url" not in detected:
    #         detected.append("url")

    return sanitized, detected


@app.command()
def sanitize_dataset_file(
    *,
    path: Path,
    out: Optional[Path] = None,
    in_place: bool = False,
    use_hashing: bool = True,
    dry_run: bool = False,
) -> dict[str, Any]:
    input_path = Path(path)
    if not input_path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    if in_place:
        output_path = input_path
    elif out:
        output_path = Path(out)
    else:
        output_path = input_path.with_stem(f"{input_path.stem}_sanitized")

    records = []
    with input_path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    sanitized_records = []
    pii_stats = {"email": 0, "phone": 0, "ssn": 0, "credit_card": 0}
    total_pii = 0

    for record in records:
        sanitized_record = record.copy()

        if "text" in record:
            sanitized_text, detected = sanitize_text(record["text"], use_hashing=use_hashing)
            sanitized_record["text"] = sanitized_text

            for pii_type in detected:
                if pii_type in pii_stats:
                    pii_stats[pii_type] += 1
                    total_pii += 1

            if detected and "tags" in sanitized_record:
                if "pii_sanitized" not in sanitized_record["tags"]:
                    sanitized_record["tags"].append("pii_sanitized")

        sanitized_records.append(sanitized_record)

    if not dry_run:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with output_path.open("w", encoding="utf-8") as f:
            for record in sanitized_records:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")

    return {
        "records": len(records),
        "pii": pii_stats,
        "total_pii": total_pii,
        "output_path": output_path,
        "dry_run": dry_run,
        "sample": sanitized_records[:3],
    }


@app.command()
def sanitize(
    path: str = typer.Option(..., help="Path to input dataset (JSONL)."),
    out: Optional[str] = typer.Option(None, help="Output path (default: <input>_sanitized.jsonl)."),
    in_place: bool = typer.Option(False, "--in-place", help="Overwrite input file."),
    use_hashing: bool = typer.Option(True, help="Use stable hashes for replacements (vs generic placeholders)."),
    dry_run: bool = typer.Option(False, "--dry-run", help="Show what would be sanitized without writing."),
) -> None:
    """Scrub PII from a dataset and replace with hashed placeholders.

    Detects and removes:
    - Email addresses
    - Phone numbers
    - Social Security Numbers
    - Credit card numbers

    Replacements use stable hashing so the same PII always maps to the same placeholder.

    Example:
        python scripts/sanitize_dataset.py \\
            --path datasets/raw_conversations.jsonl \\
            --out datasets/conversations_clean.jsonl
    """
    try:
        stats = sanitize_dataset_file(
            path=Path(path),
            out=Path(out) if out else None,
            in_place=in_place,
            use_hashing=use_hashing,
            dry_run=dry_run,
        )
    except FileNotFoundError as exc:
        raise typer.BadParameter(str(exc)) from exc

    typer.secho("✓ Sanitization complete", fg=typer.colors.GREEN)
    typer.echo(f"  Records processed: {stats['records']}")
    typer.echo(f"  Total PII instances: {stats['total_pii']}")
    for pii_type, count in stats["pii"].items():
        if count:
            typer.echo(f"    {pii_type}: {count}")

    if stats["dry_run"]:
        typer.echo("\n[DRY RUN] Would write to:", fg=typer.colors.YELLOW)
        typer.echo(f"  {stats['output_path']}")
        if stats["sample"]:
            typer.echo("\nSample sanitized records (first 3):")
            for record in stats["sample"]:
                typer.echo(json.dumps(record, indent=2))
    else:
        typer.echo(f"  Output: {stats['output_path']}")


if __name__ == "__main__":
    app()
