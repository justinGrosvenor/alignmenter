"""Tests for the dataset importers (HealthBench adapter + shared sampling)."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.importers import available, get_importer, import_corpus
from alignmenter.importers.healthbench import healthbench_to_records
from alignmenter.schemas.dataset import validate_records
from alignmenter.utils.io import read_jsonl

runner = CliRunner()


def _hb_row(pid, prompt, rubrics=None, tags=None):
    return {
        "prompt": prompt,
        "rubrics": rubrics or [],
        "example_tags": tags or [],
        "prompt_id": pid,
    }


def _single(pid, text, theme="emergency_referrals"):
    return _hb_row(
        pid,
        [{"role": "user", "content": text}],
        rubrics=[
            {"criterion": "Advises emergency care", "points": 10, "tags": ["cluster:emergency"]}
        ],
        tags=[f"theme:{theme}"],
    )


# --- mapping ---------------------------------------------------------------


def test_single_turn_maps_to_one_user_record():
    recs = healthbench_to_records(_single("p1", "I have crushing chest pain."))
    assert len(recs) == 1
    r = recs[0]
    assert r["session_id"] == "healthbench:p1"
    assert r["turn_index"] == 1
    assert r["role"] == "user"
    assert r["text"] == "I have crushing chest pain."
    assert r["persona_id"] == "reference"
    assert "source:healthbench" in r["tags"]
    assert "group:healthbench" in r["tags"]
    assert "theme:emergency_referrals" in r["tags"]


def test_rubrics_and_provenance_ride_final_user_turn():
    row = _hb_row(
        "p2",
        [
            {"role": "user", "content": "My kid has a fever."},
            {"role": "assistant", "content": "How high, and for how long?"},
            {"role": "user", "content": "39C for two days."},
        ],
        rubrics=[{"criterion": "Asks about duration", "points": 5}],
        tags=["theme:context_seeking"],
    )
    recs = healthbench_to_records(row)
    assert [r["turn_index"] for r in recs] == [1, 2, 3]
    assert [r["role"] for r in recs] == ["user", "assistant", "user"]
    # metadata only on the last (answerable) turn
    assert "metadata" not in recs[0]
    assert "metadata" not in recs[1]
    md = recs[2]["metadata"]
    assert md["benchmark"] == "healthbench"
    assert md["prompt_id"] == "p2"
    assert md["rubrics"] == [{"criterion": "Asks about duration", "points": 5}]
    assert md["example_tags"] == ["theme:context_seeking"]


def test_bare_example_tag_gets_theme_prefix():
    row = _hb_row("p3", [{"role": "user", "content": "hi"}], tags=["global_health"])
    recs = healthbench_to_records(row)
    assert "theme:global_health" in recs[0]["tags"]


def test_stable_id_when_prompt_id_missing():
    prompt = [{"role": "user", "content": "same text"}]
    a = healthbench_to_records({"prompt": prompt})
    b = healthbench_to_records({"prompt": prompt})
    assert a[0]["session_id"] == b[0]["session_id"]
    assert a[0]["session_id"].startswith("healthbench:")


# --- skips (malformed rows) ------------------------------------------------


def test_skips_empty_or_bad_prompt():
    assert healthbench_to_records({"prompt": []}) == []
    assert healthbench_to_records({"prompt": "nope"}) == []
    assert healthbench_to_records({}) == []


def test_skips_when_final_turn_is_assistant():
    row = _hb_row(
        "p4",
        [
            {"role": "user", "content": "hi"},
            {"role": "assistant", "content": "bye"},
        ],
    )
    assert healthbench_to_records(row) == []


def test_skips_blank_or_bad_message():
    assert healthbench_to_records({"prompt": [{"role": "user", "content": "   "}]}) == []
    assert healthbench_to_records({"prompt": [{"role": "system", "content": "x"}]}) == []
    assert healthbench_to_records({"prompt": ["notadict"]}) == []


# --- import_corpus (sampling + report) -------------------------------------


def _corpus(n, themes=("a", "b", "c")):
    return [_single(f"p{i}", f"question {i}", theme=themes[i % len(themes)]) for i in range(n)]


def test_import_corpus_maps_all_and_reports():
    rows = _corpus(6)
    mapper, prefix = get_importer("healthbench")
    records, report = import_corpus(rows, mapper, stratify_prefix=prefix)
    assert report["input_rows"] == 6
    assert report["skipped"] == 0
    assert report["sessions_out"] == 6
    assert report["records_out"] == 6
    # output is a valid lenient dataset
    assert validate_records(records) == []


def test_import_corpus_counts_skips():
    rows = _corpus(3) + [{"prompt": []}, {"not": "a row"}]
    mapper, prefix = get_importer("healthbench")
    _, report = import_corpus(rows, mapper, stratify_prefix=prefix)
    assert report["input_rows"] == 5
    assert report["skipped"] == 2
    assert report["sessions_out"] == 3


def test_stratified_sample_is_deterministic_and_covers_strata():
    rows = _corpus(30)  # 10 each of theme a/b/c
    mapper, prefix = get_importer("healthbench")
    r1, rep1 = import_corpus(rows, mapper, sample=6, seed=7, stratify_prefix=prefix)
    r2, _ = import_corpus(rows, mapper, sample=6, seed=7, stratify_prefix=prefix)
    ids1 = [rec["session_id"] for rec in r1]
    assert ids1 == [rec["session_id"] for rec in r2]  # seed-deterministic
    assert rep1["sessions_out"] == 6
    # even round-robin over 3 strata -> 2 apiece
    assert set(rep1["strata"].values()) == {2}


def test_sample_larger_than_corpus_returns_all():
    rows = _corpus(4)
    mapper, prefix = get_importer("healthbench")
    records, report = import_corpus(rows, mapper, sample=99, stratify_prefix=prefix)
    assert report["sessions_out"] == 4
    assert len(records) == 4


def test_output_order_is_stable_regardless_of_input_order():
    rows = _corpus(5)
    mapper, prefix = get_importer("healthbench")
    a, _ = import_corpus(rows, mapper, stratify_prefix=prefix)
    b, _ = import_corpus(list(reversed(rows)), mapper, stratify_prefix=prefix)
    assert [r["session_id"] for r in a] == [r["session_id"] for r in b]


# --- CLI -------------------------------------------------------------------


def test_cli_import_writes_dataset(tmp_path):
    src = tmp_path / "hb.jsonl"
    src.write_text("\n".join(json.dumps(r) for r in _corpus(9)) + "\n")
    out = tmp_path / "out.jsonl"
    result = runner.invoke(
        app,
        [
            "dataset",
            "import",
            "healthbench",
            str(src),
            "--out",
            str(out),
            "--sample",
            "3",
            "--manifest",
        ],
    )
    assert result.exit_code == 0, result.output
    assert "imported 3 records / 3 sessions" in result.output
    assert out.exists()
    assert len(read_jsonl(out)) == 3
    manifest = out.with_suffix(out.suffix + ".manifest.json")
    assert manifest.exists()
    payload = json.loads(manifest.read_text())
    assert payload["record_count"] == 3
    assert payload["provenance"][0]["kind"] == "import"


def test_cli_import_unknown_source_errors(tmp_path):
    src = tmp_path / "x.jsonl"
    src.write_text(json.dumps(_single("p1", "hi")) + "\n")
    result = runner.invoke(
        app, ["dataset", "import", "nope", str(src), "--out", str(tmp_path / "o.jsonl")]
    )
    assert result.exit_code != 0
    assert "unknown source" in result.output


def test_available_lists_healthbench():
    assert "healthbench" in available()


# --- collisions (content-addressed id) -------------------------------------


def test_identical_rows_without_id_are_deduped():
    # Two byte-identical rows with no prompt_id would collide on session_id and
    # emit a duplicate turn_index. They must collapse to one valid session.
    prompt = [{"role": "user", "content": "identical question"}]
    row = {"prompt": prompt, "rubrics": [], "example_tags": ["theme:a"]}
    mapper, prefix = get_importer("healthbench")
    records, report = import_corpus([dict(row), dict(row)], mapper, stratify_prefix=prefix)
    assert report["sessions_out"] == 1
    assert report["deduped"] == 1
    assert validate_records(records) == []


def test_same_prompt_different_rubrics_is_disambiguated():
    # Same prompt (same hash) but different rubrics = distinct cases; ids must
    # be made unique rather than dropped, and the output must stay valid.
    prompt = [{"role": "user", "content": "same prompt text"}]
    a = {
        "prompt": prompt,
        "rubrics": [{"criterion": "A", "points": 1}],
        "example_tags": ["theme:x"],
    }
    b = {
        "prompt": prompt,
        "rubrics": [{"criterion": "B", "points": 2}],
        "example_tags": ["theme:x"],
    }
    mapper, prefix = get_importer("healthbench")
    records, report = import_corpus([a, b], mapper, stratify_prefix=prefix)
    assert report["sessions_out"] == 2
    assert report["deduped"] == 0
    sids = {r["session_id"] for r in records}
    assert len(sids) == 2
    assert any(s.endswith("#2") for s in sids)
    assert validate_records(records) == []


def test_sampling_selection_is_input_order_invariant():
    # Same seed + same rows in any order -> same selection (stratified and plain).
    rows = _corpus(30)
    mapper, prefix = get_importer("healthbench")
    a, _ = import_corpus(rows, mapper, sample=6, seed=5, stratify_prefix=prefix)
    b, _ = import_corpus(list(reversed(rows)), mapper, sample=6, seed=5, stratify_prefix=prefix)
    assert [r["session_id"] for r in a] == [r["session_id"] for r in b]
    c, _ = import_corpus(rows, mapper, sample=6, seed=5, stratify_prefix=None)
    d, _ = import_corpus(list(reversed(rows)), mapper, sample=6, seed=5, stratify_prefix=None)
    assert [r["session_id"] for r in c] == [r["session_id"] for r in d]


def test_no_stratify_path_samples_valid_subset():
    rows = _corpus(9)
    mapper, _ = get_importer("healthbench")
    records, report = import_corpus(rows, mapper, sample=3, seed=1, stratify_prefix=None)
    assert report["sessions_out"] == 3
    assert validate_records(records) == []
