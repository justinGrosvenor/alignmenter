"""Placeholder script for bootstrapping datasets."""

import typer

app = typer.Typer()


@app.command()
def bootstrap(source: str, out: str, turns: int = 10) -> None:
    """Generate a balanced evaluation dataset from SOURCE."""

    typer.echo(
        f"[scaffold] Would bootstrap dataset from {source} with {turns} turns -> {out}"
    )


if __name__ == "__main__":
    app()
