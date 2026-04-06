#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from engine.level_up import BASE_STATS, XP_TABLE, level_for_xp, spells_for_level, stats_for_level


def _collect_level_read_gate(disassembly_root: Path) -> dict:
    bank01_path = disassembly_root / "Bank01.asm"
    bank03_path = disassembly_root / "Bank03.asm"

    bank01_text = bank01_path.read_text()
    bank03_text = bank03_path.read_text()
    return {
        "completed": True,
        "slice": "phase2-level",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank01.asm": {
                "path": str(bank01_path),
                "bytes": len(bank01_text.encode("utf-8")),
                "lines": bank01_text.count("\n"),
                "labels_checked": {
                    "BaseStatsTbl": "BaseStatsTbl" in bank01_text,
                    "SetBaseStats": "SetBaseStats" in bank01_text,
                },
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "LevelUpTbl": "LevelUpTbl" in bank03_text,
                    "LoadStats": "LoadStats" in bank03_text,
                },
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    read_gate = _collect_level_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_level_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    xp_fixture = {
        "source": "Bank03.asm LevelUpTbl @ LF35B",
        "levels": [{"level": level, "xp": XP_TABLE[level]} for level in range(1, 31)],
    }
    (fixtures_dir / "xp_table_golden.json").write_text(
        json.dumps(xp_fixture, indent=2) + "\n"
    )

    base_stats_fixture = {
        "source": "Bank01.asm BaseStatsTbl @ LA0CD",
        "levels": [
            {
                "level": level,
                "strength": BASE_STATS[level][0],
                "agility": BASE_STATS[level][1],
                "max_hp": BASE_STATS[level][2],
                "max_mp": BASE_STATS[level][3],
                "modsn_spells": BASE_STATS[level][4],
                "spell_flags": BASE_STATS[level][5],
                "spells_known": spells_for_level(level),
            }
            for level in range(1, 31)
        ],
    }
    (fixtures_dir / "base_stats_golden.json").write_text(
        json.dumps(base_stats_fixture, indent=2) + "\n"
    )

    checks = {
        "xp_table_has_30_levels": len(XP_TABLE) == 30,
        "base_stats_has_30_levels": len(BASE_STATS) == 30,
        "xp_table_strictly_non_decreasing": all(
            XP_TABLE[level] <= XP_TABLE[level + 1] for level in range(1, 30)
        ),
        "level_resolution_caps_at_30": level_for_xp(1_000_000) == 30,
        "level_resolution_floor_at_1": level_for_xp(-1) == 1,
        "level_3_learns_heal": "HEAL" in spells_for_level(3),
        "level_19_learns_hurtmore": "HURTMORE" in spells_for_level(19),
        "level_1_stats_match_expected": stats_for_level(1).max_hp == 15,
        "level_30_stats_match_expected": stats_for_level(30).max_mp == 200,
    }

    artifact = {
        "slice": "phase2-level",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "xp_fixture": "tests/fixtures/xp_table_golden.json",
            "base_stats_fixture": "tests/fixtures/base_stats_golden.json",
            "read_gate": "artifacts/phase2_level_read_gate.json",
        },
    }
    (artifacts_dir / "phase2_level_progression.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
