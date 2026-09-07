"""A local provider process killed by the durable runner acceptance tests."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

from alignmenter.providers.base import ChatResponse
from alignmenter.runner import RunConfig, Runner


def main() -> None:
    root, pause = Path(sys.argv[1]), sys.argv[2]
    dataset = root / "dataset.jsonl"
    dataset.write_text(
        "".join(
            json.dumps({"session_id": name, "turn_index": index, "role": role, "text": text}) + "\n"
            for name in ("A", "B")
            for index, role, text in [(1, "user", name), (2, "assistant", "old")]
        )
    )

    def ready():
        print("READY:" + str(runner.run_dir), flush=True)
        os.read(0, 1)

    class Provider:
        name = "local-fixture"

        def __init__(self):
            self.calls = 0

        def chat(self, messages):
            self.calls += 1
            if pause == "before_first" and self.calls == 1:
                ready()
            with (root / "dispatch.jsonl").open("a") as handle:
                handle.write(json.dumps({"call": self.calls, "messages": messages}) + "\n")
                handle.flush()
                os.fsync(handle.fileno())
            if pause == "second_provider" and self.calls == 2:
                ready()
            return ChatResponse(text=f"answer-{self.calls}", context={"excerpts": []})

    def progress(_count):
        if pause == "after_commit":
            ready()

    runner = Runner(
        RunConfig(
            model="fixture:local",
            dataset_path=dataset,
            persona_path=root / "persona.yaml",
            report_out_dir=root / "reports",
        ),
        scorers=[],
        provider=Provider(),
        progress_callback=progress,
    )
    runner.execute()


if __name__ == "__main__":
    main()
