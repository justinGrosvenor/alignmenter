"""Tests for HTML report rendering of the authenticity scoring basis."""

from __future__ import annotations

from alignmenter.reporting.html import _render_calibration_section


def test_calibration_section_shows_blended_basis() -> None:
    html = _render_calibration_section(
        {
            "authenticity": {
                "basis": "blended",
                "judge_weight": 0.6,
                "judge_mean": 0.9,
                "deterministic_mean": 0.5,
                "judge_sessions": 3,
            }
        }
    )
    assert "Authenticity Basis" in html
    assert "Judge-blended" in html
    assert "60% judge (0.900)" in html
    assert "40% deterministic (0.500)" in html
    assert "3 sessions judged" in html


def test_calibration_section_shows_deterministic_basis() -> None:
    html = _render_calibration_section({"authenticity": {"basis": "deterministic"}})
    assert "Authenticity Basis" in html
    assert "Deterministic" in html
    assert "No judge configured" in html
