"""Tests for `dataset sample` — the change-aware selection primitive."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from alignmenter.cli import app
from alignmenter.utils.io import read_jsonl

runner = CliRunner()


def _session(sid, tags):
    """A two-turn session (user+assistant) sharing tags."""
    return [
        {
            "session_id": sid,
            "turn_index": 1,
            "role": "user",
            "text": "q",
            "tags": tags,
            "persona_id": "p",
        },
        {
            "session_id": sid,
            "turn_index": 2,
            "role": "assistant",
            "text": "a",
            "tags": tags,
            "persona_id": "p",
        },
    ]


def _write(tmp_path, sessions):
    src = tmp_path / "ds.jsonl"
    src.write_text("\n".join(json.dumps(r) for s in sessions for r in s) + "\n")
    return src


def _run(args):
    return runner.invoke(app, ["dataset", "sample", *args])


def test_samples_n_whole_sessions(tmp_path):
    src = _write(tmp_path, [_session(f"s{i}", ["group:nutrition"]) for i in range(10)])
    out = tmp_path / "out.jsonl"
    res = _run([str(src), "--out", str(out), "--n", "3"])
    assert res.exit_code == 0, res.output
    recs = read_jsonl(out)
    sessions = {r["session_id"] for r in recs}
    assert len(sessions) == 3
    # sessions kept whole -> 2 records each
    assert len(recs) == 6


def test_sample_is_seed_deterministic(tmp_path):
    src = _write(tmp_path, [_session(f"s{i}", ["group:x"]) for i in range(20)])
    o1, o2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _run([str(src), "--out", str(o1), "--n", "5", "--seed", "9"])
    _run([str(src), "--out", str(o2), "--n", "5", "--seed", "9"])
    assert read_jsonl(o1) == read_jsonl(o2)


def test_different_seed_can_differ(tmp_path):
    src = _write(tmp_path, [_session(f"s{i}", ["group:x"]) for i in range(20)])
    o1, o2 = tmp_path / "a.jsonl", tmp_path / "b.jsonl"
    _run([str(src), "--out", str(o1), "--n", "5", "--seed", "1"])
    _run([str(src), "--out", str(o2), "--n", "5", "--seed", "2"])
    s1 = {r["session_id"] for r in read_jsonl(o1)}
    s2 = {r["session_id"] for r in read_jsonl(o2)}
    assert s1 != s2  # extremely unlikely to coincide across 20 choose 5


def test_filter_tag_scopes_to_related_sessions(tmp_path):
    sessions = [_session(f"n{i}", ["tool:nutrition"]) for i in range(4)] + [
        _session(f"c{i}", ["tool:calendar"]) for i in range(4)
    ]
    src = _write(tmp_path, sessions)
    out = tmp_path / "out.jsonl"
    res = _run([str(src), "--out", str(out), "--n", "10", "--filter-tag", "tool:nutrition"])
    assert res.exit_code == 0, res.output
    kept = {r["session_id"] for r in read_jsonl(out)}
    assert kept == {"n0", "n1", "n2", "n3"}
    assert "sampled 4/4 eligible" in res.output


def test_filter_tag_or_semantics(tmp_path):
    sessions = (
        [_session("n0", ["tool:nutrition"])]
        + [_session("c0", ["tool:calendar"])]
        + [_session("s0", ["tool:sleep"])]
    )
    src = _write(tmp_path, sessions)
    out = tmp_path / "out.jsonl"
    _run(
        [
            str(src),
            "--out",
            str(out),
            "--n",
            "10",
            "--filter-tag",
            "tool:nutrition",
            "--filter-tag",
            "tool:calendar",
        ]
    )
    kept = {r["session_id"] for r in read_jsonl(out)}
    assert kept == {"n0", "c0"}


def test_filter_no_match_errors(tmp_path):
    src = _write(tmp_path, [_session("s0", ["tool:nutrition"])])
    res = _run(
        [str(src), "--out", str(tmp_path / "o.jsonl"), "--n", "1", "--filter-tag", "tool:nope"]
    )
    assert res.exit_code == 1
    assert "no units match" in res.output


def test_n_larger_than_eligible_returns_all(tmp_path):
    src = _write(tmp_path, [_session(f"s{i}", ["group:x"]) for i in range(3)])
    out = tmp_path / "out.jsonl"
    res = _run([str(src), "--out", str(out), "--n", "99"])
    assert res.exit_code == 0
    assert len({r["session_id"] for r in read_jsonl(out)}) == 3


def test_output_ordered_for_stable_digest(tmp_path):
    src = _write(tmp_path, [_session(f"s{i}", ["group:x"]) for i in range(8)])
    out = tmp_path / "out.jsonl"
    _run([str(src), "--out", str(out), "--n", "8", "--seed", "3"])
    recs = read_jsonl(out)
    sids = [r["session_id"] for r in recs]
    assert sids == sorted(sids)  # picked units emitted in sorted order


def test_bad_by_rejected(tmp_path):
    src = _write(tmp_path, [_session("s0", ["group:x"])])
    res = _run([str(src), "--out", str(tmp_path / "o.jsonl"), "--n", "1", "--by", "bogus"])
    assert res.exit_code != 0


def test_sample_by_group_keeps_group_whole(tmp_path):
    # a1+a2 share group g1; b1 is g2. Sampling 1 group unit keeps exactly one
    # group tag (and both sessions if g1 is drawn).
    sessions = [
        _session("a1", ["group:g1"]),
        _session("a2", ["group:g1"]),
        _session("b1", ["group:g2"]),
    ]
    src = _write(tmp_path, sessions)
    out = tmp_path / "out.jsonl"
    res = _run([str(src), "--out", str(out), "--n", "1", "--by", "group", "--seed", "1"])
    assert res.exit_code == 0, res.output
    groups = {t for r in read_jsonl(out) for t in r["tags"] if t.startswith("group:")}
    assert len(groups) == 1


def test_sample_by_persona_treats_persona_as_unit(tmp_path):
    # Both sessions share persona_id "p" -> one persona unit; n=1 keeps both.
    sessions = [_session("s0", ["group:x"]), _session("s1", ["group:x"])]
    src = _write(tmp_path, sessions)
    out = tmp_path / "out.jsonl"
    res = _run([str(src), "--out", str(out), "--n", "1", "--by", "persona"])
    assert res.exit_code == 0, res.output
    assert len({r["session_id"] for r in read_jsonl(out)}) == 2
