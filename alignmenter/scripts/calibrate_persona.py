"""Placeholder for persona calibration notebook entry point."""

import typer

app = typer.Typer()


@app.command()
def calibrate(persona_path: str, dataset: str) -> None:
    """Fit persona-specific trait weights."""

    typer.echo(
        f"[scaffold] Would calibrate persona weights for {persona_path} using {dataset}"
    )


if __name__ == "__main__":
    app()
