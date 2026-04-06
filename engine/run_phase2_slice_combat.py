#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.combat import (
    EN_DRAGONLORD1,
    apply_damage,
    apply_heal,
    check_spell_fail,
    enemy_attack_damage,
    enemy_hp_init,
    enemy_hurt_damage,
    enemy_hurtmore_damage,
    excellent_move_check,
    excellent_move_damage,
    heal_spell_hp,
    healmore_spell_hp,
    hurt_spell_damage,
    hurtmore_spell_damage,
    player_attack_damage,
)


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_combat_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()
    labels = [
        "PlyrCalcHitDmg",
        "EnCalcHitDmg",
        "NormalAttack",
        "PlyrWeakAttack",
        "EnWeakAttack",
        "DoHeal",
        "DoHealmore",
        "ModEnHitPoints",
        "CheckEnRun",
        "ChkSpellFail",
        "EnCastHurt",
        "EnCastHurtmore",
        "LE61F",
    ]
    return {
        "completed": True,
        "slice": "phase2-combat",
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

    read_gate = _collect_combat_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_combat_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    vectors = {
        "player_attack_max_atk": player_attack_damage(255, 0, ScriptedRNG([255])),
        "player_attack_weak_negative": player_attack_damage(0, 255, ScriptedRNG([2])),
        "player_attack_weak_lt2": player_attack_damage(1, 2, ScriptedRNG([3])),
        "enemy_attack_zero_zero": enemy_attack_damage(0, 0, ScriptedRNG([255])),
        "enemy_attack_equal_threshold": enemy_attack_damage(100, 98, ScriptedRNG([200])),
        "enemy_hp_init_low": enemy_hp_init(1, ScriptedRNG([255])),
        "excellent_move_non_dl": excellent_move_check(0, ScriptedRNG([0])),
        "excellent_move_dl_blocked": excellent_move_check(EN_DRAGONLORD1, ScriptedRNG([0])),
        "excellent_move_damage": excellent_move_damage(140, ScriptedRNG([255])),
        "heal_min": heal_spell_hp(ScriptedRNG([0])),
        "heal_max": heal_spell_hp(ScriptedRNG([7])),
        "healmore_min": healmore_spell_hp(ScriptedRNG([0])),
        "healmore_max": healmore_spell_hp(ScriptedRNG([15])),
        "hurt_min": hurt_spell_damage(ScriptedRNG([0])),
        "hurt_max": hurt_spell_damage(ScriptedRNG([7])),
        "hurtmore_min": hurtmore_spell_damage(ScriptedRNG([0])),
        "hurtmore_max": hurtmore_spell_damage(ScriptedRNG([7])),
        "enemy_hurt_armor": enemy_hurt_damage(ScriptedRNG([7]), armor_reduction=True),
        "enemy_hurt_armor_base5": enemy_hurt_damage(
            ScriptedRNG([2]), armor_reduction=True
        ),
        "enemy_hurtmore_armor": enemy_hurtmore_damage(
            ScriptedRNG([15]), armor_reduction=True
        ),
        "enemy_hurtmore_armor_base32": enemy_hurtmore_damage(
            ScriptedRNG([2]), armor_reduction=True
        ),
        "spell_fail_true": check_spell_fail(0xF0, ScriptedRNG([0x0E])),
        "spell_fail_false": check_spell_fail(0xF0, ScriptedRNG([0x0F])),
        "force_field_clamp": apply_damage(5, 15),
        "swamp_clamp": apply_damage(1, 2),
        "step_heal_cap": apply_heal(254, 1, 254),
    }
    (fixtures_dir / "combat_golden_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank03_labels": [
                        "PlyrCalcHitDmg",
                        "EnCalcHitDmg",
                        "NormalAttack",
                        "PlyrWeakAttack",
                        "EnWeakAttack",
                        "DoHeal",
                        "DoHealmore",
                        "ModEnHitPoints",
                        "ChkSpellFail",
                        "EnCastHurt",
                        "EnCastHurtmore",
                        "LE61F",
                    ]
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    heal_samples = [heal_spell_hp(ScriptedRNG([value])) for value in range(256)]
    healmore_samples = [healmore_spell_hp(ScriptedRNG([value])) for value in range(256)]

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_combat_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "heal_range_10_17": min(heal_samples) == 10 and max(heal_samples) == 17,
        "healmore_range_85_100": min(healmore_samples) == 85 and max(healmore_samples) == 100,
        "force_field_clamps_to_zero": vectors["force_field_clamp"] == 0,
        "swamp_clamps_to_zero": vectors["swamp_clamp"] == 0,
        "enemy_attack_equal_threshold_22": vectors["enemy_attack_equal_threshold"] == 22,
        "enemy_hurt_base5_reduced_to_3": vectors["enemy_hurt_armor_base5"] == 3,
        "enemy_hurtmore_base32_reduced_to_21": vectors["enemy_hurtmore_armor_base32"] == 21,
    }

    artifact = {
        "slice": "phase2-combat",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_combat_read_gate.json",
            "formula_report": "artifacts/phase2_combat_formulas.json",
            "vectors_fixture": "tests/fixtures/combat_golden_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase2_combat_formulas.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
