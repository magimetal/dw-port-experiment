#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.state import GameState
from ui.status_panel import (
    decode_equipment_abbreviations,
    low_resource_flags,
    render_status_lines,
)


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    normal_state = _clone_state(
        GameState.fresh_game("ERDRICK"),
        hp=15,
        max_hp=20,
        mp=6,
        max_mp=8,
        level=7,
        experience=450,
        gold=321,
        equipment_byte=((3 << 5) | (2 << 2) | 1),
    )
    critical_state = _clone_state(normal_state, hp=4, mp=1)

    normal_lines = render_status_lines(normal_state, width=20)
    critical_lines = render_status_lines(critical_state, width=20)
    normal_equipment = decode_equipment_abbreviations(normal_state.equipment_byte)
    critical_flags = low_resource_flags(critical_state)

    vectors = {
        "equipment": {
            "equipment_byte": normal_state.equipment_byte,
            "decoded": list(normal_equipment),
            "line": normal_lines[6],
        },
        "thresholds": {
            "critical_flags": list(critical_flags),
            "critical_hp_line": critical_lines[2],
            "critical_mp_line": critical_lines[3],
        },
        "required_labels": {
            "name": normal_lines[0],
            "level": normal_lines[1],
            "hp": normal_lines[2],
            "mp": normal_lines[3],
            "exp": normal_lines[4],
            "gold": normal_lines[5],
            "equipment": normal_lines[6],
        },
        "shape": {
            "line_count": len(normal_lines),
            "line_widths": [len(line) for line in normal_lines],
            "deterministic_repeat_match": normal_lines == render_status_lines(normal_state, width=20),
        },
    }

    (fixtures_dir / "ui_status_panel_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "required_fields_present": all(
            marker in vectors["required_labels"][key]
            for key, marker in {
                "name": "NAME ",
                "level": "LV",
                "hp": "HP",
                "mp": "MP",
                "exp": "EXP",
                "gold": "GOLD",
                "equipment": "EQ ",
            }.items()
        ),
        "equipment_row_decodes_expected": normal_equipment == ("COPR", "LETH", "SML")
        and "EQ COPR/LETH/SML" in normal_lines[6],
        "low_threshold_markers_present": critical_flags == (True, True)
        and "HP!" in critical_lines[2]
        and "MP*" in critical_lines[3],
        "fixed_width_and_deterministic": len(normal_lines) == 9
        and all(len(line) == 20 for line in normal_lines)
        and vectors["shape"]["deterministic_repeat_match"] is True,
    }

    artifact = {
        "slice": "phase3-status-panel",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_status_panel.json",
            "vectors_fixture": "tests/fixtures/ui_status_panel_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded status-panel completion only: required fields, equipment row, and deterministic low HP/MP threshold markers.",
    }
    (artifacts_dir / "phase3_status_panel.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
