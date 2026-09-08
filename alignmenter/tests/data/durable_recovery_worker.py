"""Fresh runner process used to exercise lease and recovery boundaries."""

import json
import os
from pathlib import Path

from durable_recovery_target import make_target, ready

from alignmenter.runner import RunConfig, Runner

root = Path(os.environ["ALIGNMENTER_TEST_TARGET_ROOT"])
dataset = root / "dataset.jsonl"
dataset.write_text("".join(
    json.dumps({"session_id": name, "role": role, "text": text}) + "\n"
    for name in ("A", "B")
    for role, text in [("user", f"question-{name}"), ("assistant", "old")]
))
target = make_target()


def progress(_count):
    if os.environ.get("ALIGNMENTER_TEST_PAUSE") == "after_commit":
        ready(root)


Runner(RunConfig(model=target.model, dataset_path=dataset, persona_path=root / "persona.yaml",
                 report_out_dir=root / "reports"), scorers=[], provider=target.provider,
       progress_callback=progress).capture()
