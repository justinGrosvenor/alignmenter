"""Placeholder script for dataset PII scrubbing."""

import typer

app = typer.Typer()


@app.command()
def sanitize(path: str, out: str | None = None) -> None:
    """Scrub PII from the dataset at PATH."""

    typer.echo(f"[scaffold] Would sanitize dataset from {path} -> {out or path}")


if __name__ == "__main__":
    app()
