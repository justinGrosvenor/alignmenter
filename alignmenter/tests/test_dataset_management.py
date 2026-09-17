"""Dataset-management: canonical validation, manifest, and the dataset CLI commands."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.schemas.dataset import build_manifest, validate_records
from alignmenter.utils.io import read_jsonl, write_jsonl

runner = CliRunner()


def _records():
    return [
        {"session_id": "a", "turn_index": 0, "role": "user", "text": "hi", "tags": ["family:g"], "persona_id": "aver"},
        {"session_id": "a", "turn_index": 1, "role": "assistant", "text": "hello", "tags": ["family:g"], "persona_id": "aver"},
        {"session_id": "b", "turn_index": 0, "role": "user", "text": "q", "tags": ["group:x"], "persona_id": "aver"},
        {"session_id": "b", "turn_index": 1, "role": "assistant", "text": "a", "tags": ["group:x"], "persona_id": "aver"},
    ]


def _write(tmp_path, records, name="data.jsonl") -> Path:
    p = tmp_path / name
    write_jsonl(p, records)
    return p


# ---- schema / manifest ----

def test_validate_accepts_good_records():
    assert validate_records(_records()) == []


def test_validate_flags_missing_session_bad_role_and_dup_turn():
    bad = [
        {"role": "user", "text": "x"},                                  # missing session_id
        {"session_id": "s", "role": "bot", "text": "x"},               # bad role
        {"session_id": "s", "turn_index": 3, "role": "user", "text": "x"},
        {"session_id": "s", "turn_index": 3, "role": "assistant", "text": "x"},  # dup turn_index
    ]
    errors = validate_records(bad)
    assert any("session_id" in e for e in errors)
    assert any("role must be one of" in e for e in errors)
    assert any("duplicate turn_index" in e for e in errors)


def test_validate_strict_requires_persona_and_assistant_turn():
    records = [{"session_id": "s", "turn_index": 0, "role": "user", "text": "x", "tags": []}]  # no persona, no assistant
    errors = validate_records(records, strict=True)
    assert any("persona_id is required" in e for e in errors)
    assert any("has no assistant turn" in e for e in errors)


def test_manifest_digest_is_order_independent_and_counts_are_right():
    m1 = build_manifest(_records(), id="d", revision="v1")
    m2 = build_manifest(list(reversed(_records())), id="d", revision="v1")
    assert m1.content_digest == m2.content_digest       # canonical, order-independent
    assert m1.record_count == 4 and m1.session_count == 2
    assert m1.personas == {"aver": 4}
    assert m1.tags["family:g"] == 2 and m1.tags["group:x"] == 2


# ---- CLI ----

def test_cli_stats_json(tmp_path):
    p = _write(tmp_path, _records())
    res = runner.invoke(app, ["dataset", "stats", str(p), "--json"])
    assert res.exit_code == 0, res.output
    report = json.loads(res.output)
    assert report["records"] == 4 and report["sessions"] == 2 and report["roles"]["assistant"] == 2


def test_cli_validate_exit_codes(tmp_path):
    good = _write(tmp_path, _records(), "good.jsonl")
    assert runner.invoke(app, ["dataset", "validate", str(good)]).exit_code == 0
    bad = _write(tmp_path, [{"role": "user", "text": "x"}], "bad.jsonl")
    assert runner.invoke(app, ["dataset", "validate", str(bad)]).exit_code == 1


def test_cli_dedupe(tmp_path):
    p = _write(tmp_path, _records() + _records()[:1])  # one duplicate
    out = tmp_path / "dd.jsonl"
    res = runner.invoke(app, ["dataset", "dedupe", str(p), "--out", str(out)])
    assert res.exit_code == 0 and "removed 1 duplicate" in res.output
    assert len(read_jsonl(out)) == 4


def test_cli_merge_namespaces_sessions(tmp_path):
    a = _write(tmp_path, _records()[:2], "a.jsonl")
    b = _write(tmp_path, _records()[2:], "b.jsonl")
    out = tmp_path / "m.jsonl"
    res = runner.invoke(app, ["dataset", "merge", str(a), str(b), "--out", str(out), "--namespace-sessions"])
    assert res.exit_code == 0
    sessions = {r["session_id"] for r in read_jsonl(out)}
    assert sessions == {"a:a", "b:b"}


def test_cli_split_keeps_groups_together(tmp_path):
    # two group:* groups; a holdout must contain whole groups, never split one across sides
    records = []
    for g in ("g1", "g2"):
        for i in range(3):
            records.append({"session_id": f"{g}-{i}", "role": "assistant", "text": "x", "tags": [f"group:{g}"]})
    p = _write(tmp_path, records)
    out = tmp_path / "split"
    res = runner.invoke(app, ["dataset", "split", str(p), "--out", str(out), "--by", "group", "--holdout", "0.5"])
    assert res.exit_code == 0, res.output
    train = {t for r in read_jsonl(out / "train.jsonl") for t in r["tags"]}
    hold = {t for r in read_jsonl(out / "holdout.jsonl") for t in r["tags"]}
    assert train and hold and train.isdisjoint(hold)   # no group straddles the boundary


def test_cli_split_tolerates_non_dict_rows(tmp_path):
    p = tmp_path / "mixed.jsonl"
    write_jsonl(p, _records() + [[1, 2, 3]])  # a non-dict row must not crash split
    out = tmp_path / "s"
    res = runner.invoke(app, ["dataset", "split", str(p), "--out", str(out), "--by", "session", "--holdout", "0.5"])
    assert res.exit_code == 0, res.output


def test_cli_manifest_verify_bad_json_errors_friendly(tmp_path):
    p = _write(tmp_path, _records())
    bad = tmp_path / "bad-manifest.json"
    bad.write_text("not json at all")
    res = runner.invoke(app, ["dataset", "manifest", str(p), "--verify", str(bad)])
    assert res.exit_code != 0
    assert "Could not read manifest" in res.output


def test_cli_manifest_build_and_verify(tmp_path):
    p = _write(tmp_path, _records())
    man = tmp_path / "manifest.json"
    assert runner.invoke(app, ["dataset", "manifest", str(p), "--out", str(man)]).exit_code == 0
    assert json.loads(man.read_text())["record_count"] == 4
    assert runner.invoke(app, ["dataset", "manifest", str(p), "--verify", str(man)]).exit_code == 0
    # mutate the data → verify must fail
    write_jsonl(p, _records() + [{"session_id": "z", "role": "user", "text": "new"}])
    assert runner.invoke(app, ["dataset", "manifest", str(p), "--verify", str(man)]).exit_code == 2
