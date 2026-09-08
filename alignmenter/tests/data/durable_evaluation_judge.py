"""Local judge fixture with an independent, fsynced acceptance log."""

import json
import os
from pathlib import Path

from alignmenter.providers.durable_judge import CallableJudge
from alignmenter.schemas.evaluation import JudgeContract, JudgeReply
from alignmenter.schemas.execution import content_digest


def ready():
    print("READY", flush=True)
    os.read(0, 1)


def make_judge():
    root = Path(os.environ["ALIGNMENTER_TEST_JUDGE_ROOT"])
    pause = os.environ.get("ALIGNMENTER_TEST_JUDGE_PAUSE")
    outcome = os.environ.get("ALIGNMENTER_TEST_JUDGE_OUTCOME", "met")
    calls = 0

    def judge(request):
        nonlocal calls
        calls += 1
        if calls == 1 and pause == "before_dispatch":
            ready()
        with (root / "accepted.jsonl").open("a") as handle:
            handle.write(json.dumps({"request": request.model_dump(mode="json")}) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        if calls == 1 and pause == "after_accept":
            ready()
        payload = json.loads(request.prompt)
        if payload["criterion"].get("evaluator") == "faithfulness":
            source_id, quote = next((k, v) for k, v in payload["supporting_sources"].items() if k.startswith("passage:"))
            return JudgeReply(finish_reason="stop", text=json.dumps({
                "claims": [{"text": payload["answer"]["text"], "status": "supported",
                            "evidence": [{"source_id": source_id, "quote": quote}]}],
                "correctness": 10, "answers_question": True, "abstained": False,
                "abstention_appropriate": None, "dangerous": False, "danger_reason": None,
                "reasoning": "Local transport fixture, not a qualified product judgment.", "no_claims_reason": None,
            }))
        return JudgeReply(finish_reason="stop", text=json.dumps({
            "outcome": outcome, "rationale": "Local fixture result; not a qualified product judgment.",
            "evidence": [{"source_id": "answer", "quote": payload["answer"]["text"]}],
        }))

    return CallableJudge(judge, JudgeContract(model="fixture:judge", configuration_digest=content_digest({
        "fixture": "durable-evaluation-v2", "outcome": outcome,
    })))
