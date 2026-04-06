#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.movement import (
    AR_ERDK_ARMR,
    AR_MAGIC_ARMR,
    BLK_FFIELD,
    BLK_GRASS,
    BLK_HILL,
    BLK_SAND,
    BLK_SWAMP,
    apply_step_regen,
    choose_enemy_from_row,
    choose_overworld_enemy,
    encounter_triggered,
    overworld_zone_id,
    repel_succeeds,
    resolve_step_hp,
    zone_zero_allows_fight,
)


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_movement_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()
    labels = [
        "MovementUpdates",
        "LCDC8",
        "LCE02",
        "LCE06",
        "LCE1F",
        "LCDFD",
        "ChkRandomFight",
        "LCE82",
        "LCEBD",
        "ChkFightRepel",
        "RepelTbl",
        "OvrWrldEnGrid",
        "EnemyGroupsTbl",
        "CaveEnIndexTbl",
    ]
    return {
        "completed": True,
        "slice": "phase2-movement",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in labels},
            }
        },
    }


class ScriptedRNG:
    def __init__(self, sequence: list[int]) -> None:
        self._sequence = [value & 0xFF for value in sequence]
        self.rng_lb = 0
        self.rng_ub = 0
        self._idx = 0

    def tick(self) -> int:
        if self._idx >= len(self._sequence):
            raise IndexError("scripted RNG exhausted")
        self.rng_ub = self._sequence[self._idx]
        self.rng_lb = self.rng_ub
        self._idx += 1
        return self.rng_lb


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    zones = json.loads((root / "extractor" / "data_out" / "zones.json").read_text())
    zone_grid = zones["overworld_zone_grid"]
    enemy_groups = zones["enemy_groups_table"]
    repel_table = zones["repel_table"]

    read_gate = _collect_movement_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_movement_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    vectors = {
        "regen_erdrick": list(apply_step_regen(10, 20, AR_ERDK_ARMR, 9)),
        "regen_magic_no_heal": list(apply_step_regen(10, 20, AR_MAGIC_ARMR, 2)),
        "regen_magic_heal_on_counter_mod4_zero": list(
            apply_step_regen(10, 20, AR_MAGIC_ARMR, 3)
        ),
        "swamp_plain": list(resolve_step_hp(10, 20, BLK_SWAMP, 0, 0)),
        "swamp_erdrick": list(resolve_step_hp(10, 20, BLK_SWAMP, AR_ERDK_ARMR, 0)),
        "force_field_plain": list(resolve_step_hp(10, 20, BLK_FFIELD, 0, 0)),
        "encounter_normal_true": encounter_triggered(BLK_GRASS, 0x10),
        "encounter_normal_false": encounter_triggered(BLK_GRASS, 0x11),
        "encounter_sand_true": encounter_triggered(BLK_SAND, 0x08),
        "zone_0_0": overworld_zone_id(0, 0, zone_grid),
        "zone_119_119": overworld_zone_id(119, 119, zone_grid),
        "zone0_non_hill_allows": zone_zero_allows_fight(BLK_GRASS, 0x0E),
        "zone0_non_hill_blocks": zone_zero_allows_fight(BLK_GRASS, 0x0F),
        "zone0_hill_allows": zone_zero_allows_fight(BLK_HILL, 0x04),
        "zone0_hill_blocks": zone_zero_allows_fight(BLK_HILL, 0x05),
        "choose_enemy_reroll": choose_enemy_from_row(enemy_groups[3], ScriptedRNG([7, 6, 4])),
        "choose_overworld_enemy_zone3": choose_overworld_enemy(
            0, 0, BLK_GRASS, zone_grid, enemy_groups, ScriptedRNG([4])
        ),
        "choose_overworld_enemy_zone0_none": choose_overworld_enemy(
            30, 30, BLK_GRASS, zone_grid, enemy_groups, ScriptedRNG([1])
        ),
        "repel_true_negative_diff": repel_succeeds(0, 20, repel_table),
        "repel_true_threshold": repel_succeeds(0, 8, repel_table),
        "repel_false": repel_succeeds(0, 0, repel_table),
    }

    (fixtures_dir / "movement_golden_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank03_labels": [
                        "MovementUpdates",
                        "LCDC8",
                        "LCE1F",
                        "LCDFD",
                        "ChkRandomFight",
                        "LCE82",
                        "LCEBD",
                        "ChkFightRepel",
                    ]
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_movement_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "zone_grid_is_8x8": len(zone_grid) == 8 and all(len(row) == 8 for row in zone_grid),
        "enemy_groups_has_20_rows": len(enemy_groups) == 20,
        "repel_table_has_40_values": len(repel_table) == 40,
        "zone_0_0_matches_expected": vectors["zone_0_0"] == 3,
        "zone_119_119_matches_expected": vectors["zone_119_119"] == 9,
        "swamp_plain_damages_2": vectors["swamp_plain"] == [8, 0],
        "force_field_plain_clamps_to_zero": vectors["force_field_plain"] == [0, 0],
        "zone0_abort_path_returns_none": vectors["choose_overworld_enemy_zone0_none"] is None,
        "repel_false_case_locked": vectors["repel_false"] is False,
    }

    artifact = {
        "slice": "phase2-movement",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_movement_read_gate.json",
            "report": "artifacts/phase2_movement_logic.json",
            "vectors_fixture": "tests/fixtures/movement_golden_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase2_movement_logic.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
