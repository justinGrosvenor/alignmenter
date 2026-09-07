"""Kill barriers around real production reservation/response/verdict commits."""

import os
import sys
from pathlib import Path

import yaml
from durable_evaluation_judge import make_judge, ready

from alignmenter.execution.evaluation import evaluate_saved
from alignmenter.schemas.evaluation import EvaluationSpec, JudgeBudget
from alignmenter.storage.evaluations import EvaluationStore

pause = os.environ["ALIGNMENTER_TEST_JUDGE_PAUSE"]
original_finish = EvaluationStore.finish_call


def finish_call(self, *args, **kwargs):
    saved = original_finish(self, *args, **kwargs)
    if pause == "after_raw":
        ready()
    return saved


def progress(result):
    if pause == "after_result":
        ready()


EvaluationStore.finish_call = finish_call
evaluate_saved(Path(sys.argv[1]), EvaluationSpec.model_validate(yaml.safe_load(Path(sys.argv[2]).read_text())),
               make_judge(), budget=JudgeBudget(max_calls=2), progress=progress)
