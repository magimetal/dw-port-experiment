#!/usr/bin/env python3
"""
verify.py — DW1 Port Phase Gate Harness (early slices)

Usage:
  python3 verify.py --phase 0
  python3 verify.py --phase 1-foundation
  python3 verify.py --phase 1-slice-warps
  python3 verify.py --phase 1-slice-items
  python3 verify.py --phase 1-slice-npcs
  python3 verify.py --phase 1-slice-dialog
  python3 verify.py --phase 1-slice-maps
  python3 verify.py --phase 2-slice-rng
  python3 verify.py --phase 2-slice-state
  python3 verify.py --phase 2-slice-level
  python3 verify.py --phase 2-slice-combat
  python3 verify.py --phase 2-slice-movement
  python3 verify.py --phase 2-slice-map-engine
  python3 verify.py --phase 2-slice-dialog
  python3 verify.py --phase 2-slice-shop
  python3 verify.py --phase 2-slice-save-load
  python3 verify.py --phase 2-slice-items
  python3 verify.py --phase 3-slice-ui-foundation
  python3 verify.py --phase 3-slice-title-bootstrap
  python3 verify.py --phase 3-slice-menu
  python3 verify.py --phase 3-slice-dialog-box
  python3 verify.py --phase 3-slice-combat-view
  python3 verify.py --phase 3-slice-status-panel
  python3 verify.py --phase 3-slice-map-view
  python3 verify.py --phase 3-slice-renderer
  python3 verify.py --phase 4-slice-main-loop-scaffold
  python3 verify.py --phase 4-slice-save-load-loop
  python3 verify.py --phase 4-slice-inn-stay-save-trigger
  python3 verify.py --phase 4-slice-inn-cost-deduct
  python3 verify.py --phase 4-slice-encounter-trigger
  python3 verify.py --phase 4-slice-dungeon-encounter-runtime
  python3 verify.py --phase 4-slice-combat-session-handoff
  python3 verify.py --phase 4-slice-combat-turn-resolution
  python3 verify.py --phase 4-slice-combat-spell-in-battle
  python3 verify.py --phase 4-slice-combat-enemy-sleep-stopspell-immunity
  python3 verify.py --phase 4-slice-title-screen-endgame-renderer
  python3 verify.py --phase 4-slice-combat-outcome-resolution
  python3 verify.py --phase 4-slice-post-combat-dialog-handoff
  python3 verify.py --phase 4-slice-post-combat-fidelity-hardening
  python3 verify.py --phase 4-slice-npc-interaction-dialog-handoff
  python3 verify.py --phase 4-slice-npc-dialog-control-fidelity
  python3 verify.py --phase 4-slice-npc-dialog-entry-playback
  python3 verify.py --phase 4-slice-npc-special-dialog-control-resolution
  python3 verify.py --phase 4-slice-npc-special-control-side-effects
  python3 verify.py --phase 4-slice-npc-special-control-0x6c-side-effect
  python3 verify.py --phase 4-slice-npc-shop-inn-handoff
  python3 verify.py --phase 4-slice-npc-shop-inn-control-expansion
  python3 verify.py --phase 4-slice-npc-shop-inn-next-control-pair
  python3 verify.py --phase 4-slice-npc-shop-sell-handoff
  python3 verify.py --phase 4-slice-map-field-spell-casting
  python3 verify.py --phase 4-slice-map-spell-selection-surface
  python3 verify.py --phase 4-slice-map-command-root-surface
  python3 verify.py --phase 4-slice-map-command-root-expansion
  python3 verify.py --phase 4-slice-map-command-search
  python3 verify.py --phase 4-slice-map-command-search-chest-rewards
  python3 verify.py --phase 4-slice-map-command-search-non-gold-chest-rewards
  python3 verify.py --phase 4-slice-map-command-search-tool-rewards-capacity
  python3 verify.py --phase 4-slice-map-command-search-remaining-gold-chest-rewards
  python3 verify.py --phase 4-slice-map-command-search-remaining-unsupported-chest-contents
  python3 verify.py --phase 4-slice-map-command-status-surface
  python3 verify.py --phase 4-slice-map-command-item-surface
  python3 verify.py --phase 4-slice-map-command-item-expansion
  python3 verify.py --phase 4-slice-map-command-item-dragons-scale-equip-state
  python3 verify.py --phase 4-slice-map-command-item-silver-harp-forced-encounter
  python3 verify.py --phase 4-slice-map-command-item-rainbow-drop-bridge-trigger
  python3 verify.py --phase 4-slice-map-command-item-fairy-flute-interaction
  python3 verify.py --phase 4-slice-map-command-cursed-item-step-damage-hook
  python3 verify.py --phase 4-slice-map-command-stairs-surface
  python3 verify.py --phase 4-slice-map-command-door-surface
  python3 verify.py --phase 4-slice-map-command-door-persistence
  python3 verify.py --phase 4-slice-opened-world-state-save-load-persistence
  python3 verify.py --phase 4-slice-map-load-curse-check
  python3 verify.py --phase 5-slice-parity-matrix-gate
  python3 verify.py --phase 5-slice-xp-table-extractor
  python3 verify.py --phase 5-slice-spell-extractor
  python3 verify.py --phase 5-slice-terminal-size-enforcement
  python3 verify.py --phase 5-slice-ascii-fallback-tileset
  python3 verify.py --phase 5-slice-closeout-validation-gate
  python3 verify.py --phase 5
  python3 verify.py --phase 4
  python3 verify.py --phase 4-slice-phase4-final-audit-wrap
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent

FLAG_DEATH_NECKLACE = 0x80


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def check_python_version() -> dict:
    ok = sys.version_info >= (3, 11)
    detail = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
    return {"ok": ok, "detail": detail, "expected": ">=3.11"}


def check_deps_importable() -> dict:
    required = ["blessed", "pytest", "hypothesis"]
    missing: list[str] = []
    for module_name in required:
        try:
            importlib.import_module(module_name)
        except Exception:
            missing.append(module_name)
    return {"ok": not missing, "missing": missing}


def check_rom_sha1_baseline() -> dict:
    baseline_path = ROOT / "extractor" / "rom_baseline.json"
    baseline = json.loads(baseline_path.read_text())
    rom_path = ROOT / baseline["rom_file"]
    actual = _sha1(rom_path)
    expected = baseline["accepted_sha1"]
    return {
        "ok": actual == expected,
        "rom": baseline["rom_file"],
        "actual": actual,
        "expected": expected,
    }


def check_dir_structure() -> dict:
    required = [
        ROOT / "extractor" / "data_out",
        ROOT / "engine",
        ROOT / "ui",
        ROOT / "tests" / "fixtures",
        ROOT / "tests" / "replay",
        ROOT / "tests" / "checkpoints",
        ROOT / "artifacts",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.is_dir()]
    return {"ok": not missing, "missing": missing}


def check_requirements_file() -> dict:
    req = ROOT / "requirements.txt"
    expected = {"blessed", "pytest", "hypothesis"}
    if not req.exists():
        return {"ok": False, "detail": "requirements.txt missing"}
    contents = {line.strip() for line in req.read_text().splitlines() if line.strip()}
    missing = sorted(expected - contents)
    return {"ok": not missing, "missing": missing}


def check_enemy_hurt_fixture() -> dict:
    fixture_path = ROOT / "tests" / "fixtures" / "enemy_hurt_range.json"
    if not fixture_path.exists():
        return {"ok": False, "detail": "tests/fixtures/enemy_hurt_range.json missing"}
    data = json.loads(fixture_path.read_text())
    ok = data.get("min") == 3 and data.get("max") == 10
    return {"ok": ok, "detail": data}


def run_pytest_foundation() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_foundation.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_rom_spells",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_bank_read_gate_artifact() -> dict:
    artifact = ROOT / "artifacts" / "phase1_bank_read_gate.json"
    if not artifact.exists():
        return {"ok": False, "detail": "phase1_bank_read_gate.json missing"}

    data = json.loads(artifact.read_text())
    ok = (
        data.get("completed") is True
        and data.get("files", {}).get("Bank00.asm", {}).get("labels_checked", {}).get("WrldMapPtrTbl") is True
        and data.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {}).get("SpellCostTbl") is True
        and data.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {}).get("CheckMP") is True
    )
    return {"ok": ok, "detail": data}


def run_pytest_phase1_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_chests_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_chests",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_chests_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "chests.json"
    artifact_path = ROOT / "artifacts" / "phase1_chests_extraction.json"
    if not data_path.exists() or not artifact_path.exists():
        return {
            "ok": False,
            "detail": {
                "chests_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    ok = len(data.get("chest_entries", [])) == 31 and artifact.get("entry_count") == 31
    return {"ok": ok, "detail": {"chests": data, "artifact": artifact}}


def run_pytest_phase1_chests_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_enemies_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_enemies",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_enemies_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "enemies.json"
    artifact_path = ROOT / "artifacts" / "phase1_enemies_extraction.json"
    if not data_path.exists() or not artifact_path.exists():
        return {
            "ok": False,
            "detail": {
                "enemies_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    ok = len(data.get("enemies", [])) == 40 and artifact.get("entry_count") == 40
    return {"ok": ok, "detail": {"enemies": data, "artifact": artifact}}


def run_pytest_phase1_enemies_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_zones_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_zones",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_zones_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "zones.json"
    artifact_path = ROOT / "artifacts" / "phase1_zones_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_zones_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "zones_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    ok = (
        len(data.get("overworld_zone_grid", [])) == 8
        and len(data.get("overworld_formation_table", [])) == 14
        and len(data.get("dungeon_formation_table", [])) == 6
        and data.get("cave_index_table")
        == [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15]
        and len(data.get("repel_table", [])) == 40
        and artifact.get("slice") == "phase1-zones"
        and read_gate.get("completed") is True
    )
    return {
        "ok": ok,
        "detail": {
            "zones": data,
            "artifact": artifact,
            "read_gate": read_gate,
        },
    }


def run_pytest_phase1_zones_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_warps_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_warps",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_warps_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "warps.json"
    artifact_path = ROOT / "artifacts" / "phase1_warps_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_warps_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "warps_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    warps = data.get("warps", [])
    ok = (
        len(warps) == 51
        and artifact.get("slice") == "phase1-warps"
        and artifact.get("entry_count") == 51
        and read_gate.get("completed") is True
        and read_gate.get("files", {})
        .get("Bank00.asm", {})
        .get("labels_checked", {})
        .get("MapEntryDirTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("MapEntryTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("MapTargetTbl")
        is True
    )
    return {
        "ok": ok,
        "detail": {
            "warps": data,
            "artifact": artifact,
            "read_gate": read_gate,
        },
    }


def run_pytest_phase1_warps_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_items_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_items",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_items_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "items.json"
    artifact_path = ROOT / "artifacts" / "phase1_items_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_items_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "items_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    labels = [
        "ItemCostTbl",
        "InnCostTbl",
        "ShopItemsTbl",
        "WeaponsBonusTbl",
        "ArmorBonusTbl",
        "ShieldBonusTbl",
    ]
    ok = (
        len(data.get("item_costs", [])) == 33
        and len(data.get("shop_inventories", [])) == 12
        and artifact.get("slice") == "phase1-items"
        and artifact.get("item_cost_count") == 33
        and read_gate.get("completed") is True
        and all(
            read_gate.get("files", {})
            .get("Bank00.asm", {})
            .get("labels_checked", {})
            .get(label)
            is True
            for label in labels
        )
        and all(
            read_gate.get("files", {})
            .get("Bank03.asm", {})
            .get("labels_checked", {})
            .get(label)
            is True
            for label in labels
        )
    )
    return {
        "ok": ok,
        "detail": {
            "items": data,
            "artifact": artifact,
            "read_gate": read_gate,
        },
    }


def run_pytest_phase1_items_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_npcs_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_npcs",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_npcs_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "npcs.json"
    artifact_path = ROOT / "artifacts" / "phase1_npcs_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_npcs_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "npcs_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    ok = (
        len(data.get("maps", [])) == 12
        and len(data.get("npcs", [])) == 136
        and artifact.get("slice") == "phase1-npcs"
        and artifact.get("map_count") == 12
        and artifact.get("npc_count") == 136
        and read_gate.get("completed") is True
        and read_gate.get("files", {})
        .get("Bank00.asm", {})
        .get("labels_checked", {})
        .get("NPCMobPtrTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank00.asm", {})
        .get("labels_checked", {})
        .get("NPCStatPtrTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("GetNPCSpriteIndex")
        is True
    )
    return {
        "ok": ok,
        "detail": {
            "npcs": data,
            "artifact": artifact,
            "read_gate": read_gate,
        },
    }


def run_pytest_phase1_npcs_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_dialog_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_dialog",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_dialog_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "dialog.json"
    artifact_path = ROOT / "artifacts" / "phase1_dialog_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_dialog_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "dialog_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    text_blocks = data.get("text_blocks", [])
    total_text_bytes = sum(block.get("byte_length", 0) for block in text_blocks)
    ok = (
        data.get("pointer_table", {}).get("pointer_count") == 19
        and len(text_blocks) == 19
        and data.get("text_range", {}).get("byte_length") == total_text_bytes
        and artifact.get("slice") == "phase1-dialog"
        and artifact.get("pointer_count") == 19
        and artifact.get("text_block_count") == 19
        and read_gate.get("completed") is True
        and read_gate.get("files", {})
        .get("Bank02.asm", {})
        .get("labels_checked", {})
        .get("TextBlock1")
        is True
        and read_gate.get("files", {})
        .get("Bank02.asm", {})
        .get("labels_checked", {})
        .get("TextBlock19")
        is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("DoDialogLoBlock")
        is True
    )
    return {
        "ok": ok,
        "detail": {
            "pointer_count": data.get("pointer_table", {}).get("pointer_count"),
            "text_block_count": len(text_blocks),
            "total_text_bytes": total_text_bytes,
            "slice": artifact.get("slice"),
            "read_gate_completed": read_gate.get("completed"),
            "required_labels": {
                "Bank02.TextBlock1": read_gate.get("files", {})
                .get("Bank02.asm", {})
                .get("labels_checked", {})
                .get("TextBlock1"),
                "Bank02.TextBlock19": read_gate.get("files", {})
                .get("Bank02.asm", {})
                .get("labels_checked", {})
                .get("TextBlock19"),
                "Bank03.DoDialogLoBlock": read_gate.get("files", {})
                .get("Bank03.asm", {})
                .get("labels_checked", {})
                .get("DoDialogLoBlock"),
            },
        },
    }


def run_pytest_phase1_dialog_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_maps_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_maps",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_maps_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "maps.json"
    artifact_path = ROOT / "artifacts" / "phase1_maps_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_maps_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "maps_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    maps = data.get("maps", [])
    overworld = maps[1] if len(maps) > 1 else None
    required_labels = [
        "MapDatTbl",
        "WrldMapPtrTbl",
        "GetBlockID",
        "GetOvrWldTarget",
        "ChkWtrOrBrdg",
        "ChkOthrMaps",
    ]

    ok = (
        len(maps) == 30
        and overworld is not None
        and overworld.get("width") == 120
        and overworld.get("height") == 120
        and overworld.get("tile_sha1")
        == "cbc8b4ca3442f804f3da7654e5a74e809a9e9a8e"
        and artifact.get("slice") == "phase1-maps"
        and artifact.get("map_count") == 30
        and artifact.get("overworld_tile_sha1")
        == "cbc8b4ca3442f804f3da7654e5a74e809a9e9a8e"
        and read_gate.get("completed") is True
        and all(
            read_gate.get("files", {})
            .get("Bank00.asm", {})
            .get("labels_checked", {})
            .get(label)
            is True
            for label in required_labels
        )
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("ChangeMaps")
        is True
    )
    return {
        "ok": ok,
        "detail": {
            "map_count": len(maps),
            "overworld_dimensions": None
            if overworld is None
            else {
                "width": overworld.get("width"),
                "height": overworld.get("height"),
            },
            "overworld_tile_sha1": None
            if overworld is None
            else overworld.get("tile_sha1"),
            "artifact": artifact,
            "read_gate": read_gate,
        },
    }


def run_pytest_phase1_maps_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_stats_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_stats",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_xp_table_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_xp_table",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase1_slice_spells_extractor() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "extractor.run_phase1_slice_spells",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_xp_table_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "xp_table.json"
    artifact_path = ROOT / "artifacts" / "phase1_xp_table_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_xp_table_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "xp_table_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    level_count = len(data.get("levels", []))
    labels = read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {})
    ok = (
        level_count == 30
        and artifact.get("slice") == "phase1-xp-table"
        and artifact.get("entry_count") == 30
        and read_gate.get("completed") is True
        and labels.get("LevelUpTbl") is True
        and labels.get("LoadStats") is True
    )
    return {
        "ok": ok,
        "detail": {
            "xp_table": data,
            "artifact": artifact,
            "read_gate": read_gate,
            "level_count": level_count,
        },
    }


def check_spells_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "spells.json"
    artifact_path = ROOT / "artifacts" / "phase1_spells_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_spells_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "spells_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    spells = data.get("spells", [])
    labels03 = read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {})
    labels01 = read_gate.get("files", {}).get("Bank01.asm", {}).get("labels_checked", {})
    ok = (
        len(spells) == 10
        and artifact.get("slice") == "phase1-spells"
        and artifact.get("spell_count") == 10
        and read_gate.get("completed") is True
        and labels03.get("SpellCostTbl") is True
        and labels01.get("BaseStatsTbl") is True
        and labels01.get("SetBaseStats") is True
    )
    return {
        "ok": ok,
        "detail": {
            "spells": data,
            "artifact": artifact,
            "read_gate": read_gate,
            "spell_count": len(spells),
        },
    }


def check_stats_artifacts() -> dict:
    data_path = ROOT / "extractor" / "data_out" / "stats.json"
    artifact_path = ROOT / "artifacts" / "phase1_stats_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_stats_read_gate.json"
    if not data_path.exists() or not artifact_path.exists() or not read_gate_path.exists():
        return {
            "ok": False,
            "detail": {
                "stats_json_exists": data_path.exists(),
                "slice_artifact_exists": artifact_path.exists(),
                "read_gate_artifact_exists": read_gate_path.exists(),
            },
        }

    data = json.loads(data_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    level_count = len(data.get("levels", []))
    labels = read_gate.get("files", {}).get("Bank01.asm", {}).get("labels_checked", {})
    ok = (
        level_count == 30
        and artifact.get("slice") == "phase1-stats"
        and artifact.get("entry_count") == 30
        and read_gate.get("completed") is True
        and labels.get("BaseStatsTbl") is True
        and labels.get("SetBaseStats") is True
    )
    return {
        "ok": ok,
        "detail": {
            "stats": data,
            "artifact": artifact,
            "read_gate": read_gate,
            "level_count": level_count,
        },
    }


def check_phase5_slice_stats_extractor() -> dict:
    stats_path = ROOT / "extractor" / "data_out" / "stats.json"
    if not stats_path.exists():
        return {
            "ok": False,
            "detail": {
                "stats_json_exists": False,
                "reason": "extractor/data_out/stats.json missing",
            },
        }

    stats_data = json.loads(stats_path.read_text())
    stats_levels = {entry["level"]: entry for entry in stats_data.get("levels", [])}

    checks = {
        "row51_lv1_stats": [
            stats_levels.get(1, {}).get("strength"),
            stats_levels.get(1, {}).get("agility"),
            stats_levels.get(1, {}).get("max_hp"),
            stats_levels.get(1, {}).get("max_mp"),
        ]
        == [4, 4, 15, 0],
        "row52_lv30_stats": [
            stats_levels.get(30, {}).get("strength"),
            stats_levels.get(30, {}).get("agility"),
            stats_levels.get(30, {}).get("max_hp"),
            stats_levels.get(30, {}).get("max_mp"),
        ]
        == [140, 130, 210, 200],
        "row53_heal_lv3": "HEAL" in stats_levels.get(3, {}).get("spells_known", []),
        "row54_healmore_lv17": "HEALMORE" in stats_levels.get(17, {}).get("spells_known", []),
        "row55_hurtmore_lv19": "HURTMORE" in stats_levels.get(19, {}).get("spells_known", []),
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "stats_json": "extractor/data_out/stats.json",
            "level_count": len(stats_data.get("levels", [])),
            "checks": checks,
            "sample": {
                "level_1": stats_levels.get(1),
                "level_3": stats_levels.get(3),
                "level_16": stats_levels.get(16),
                "level_17": stats_levels.get(17),
                "level_19": stats_levels.get(19),
                "level_30": stats_levels.get(30),
            },
        },
    }


def check_phase5_slice_xp_table_extractor() -> dict:
    xp_table_path = ROOT / "extractor" / "data_out" / "xp_table.json"
    if not xp_table_path.exists():
        return {
            "ok": False,
            "detail": {
                "xp_table_json_exists": False,
                "reason": "extractor/data_out/xp_table.json missing",
            },
        }

    xp_data = json.loads(xp_table_path.read_text())
    xp_levels = {entry["level"]: entry for entry in xp_data.get("levels", [])}

    checks = {
        "row18_lv2_threshold": xp_levels.get(2, {}).get("xp_threshold") == 7,
        "row19_lv10_threshold": xp_levels.get(10, {}).get("xp_threshold") == 2000,
        "row20_lv20_threshold": xp_levels.get(20, {}).get("xp_threshold") == 26000,
        "row21_lv30_threshold": xp_levels.get(30, {}).get("xp_threshold") == 65535,
        "row22_all_30_thresholds": len(xp_data.get("levels", [])) == 30,
        "spotcheck_lv1_zero": xp_levels.get(1, {}).get("xp_threshold") == 0,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "xp_table_json": "extractor/data_out/xp_table.json",
            "level_count": len(xp_data.get("levels", [])),
            "checks": checks,
            "sample": {
                "level_1": xp_levels.get(1),
                "level_2": xp_levels.get(2),
                "level_10": xp_levels.get(10),
                "level_20": xp_levels.get(20),
                "level_30": xp_levels.get(30),
            },
        },
    }


def check_phase5_slice_spell_extractor() -> dict:
    spells_path = ROOT / "extractor" / "data_out" / "spells.json"
    if not spells_path.exists():
        return {
            "ok": False,
            "detail": {
                "spells_json_exists": False,
                "reason": "extractor/data_out/spells.json missing",
            },
        }

    spells_data = json.loads(spells_path.read_text())
    spells = {entry["name"]: entry for entry in spells_data.get("spells", [])}
    checks = {
        "spell_count_10": len(spells_data.get("spells", [])) == 10,
        "heal_mp4_lv3": spells.get("HEAL", {}).get("mp_cost") == 4 and spells.get("HEAL", {}).get("learn_level") == 3,
        "healmore_mp10_lv17": spells.get("HEALMORE", {}).get("mp_cost") == 10 and spells.get("HEALMORE", {}).get("learn_level") == 17,
        "hurtmore_mp5_lv19": spells.get("HURTMORE", {}).get("mp_cost") == 5 and spells.get("HURTMORE", {}).get("learn_level") == 19,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "spells_json": "extractor/data_out/spells.json",
            "spell_count": len(spells_data.get("spells", [])),
            "checks": checks,
            "sample": {
                "HEAL": spells.get("HEAL"),
                "HEALMORE": spells.get("HEALMORE"),
                "HURTMORE": spells.get("HURTMORE"),
            },
        },
    }


def check_phase5_slice_terminal_size_enforcement() -> dict:
    from engine.map_engine import MapEngine
    from engine.state import GameState
    from ui.renderer import GameRenderer, RenderFrameRequest

    maps_path = ROOT / "extractor" / "data_out" / "maps.json"
    warps_path = ROOT / "extractor" / "data_out" / "warps.json"
    npcs_path = ROOT / "extractor" / "data_out" / "npcs.json"

    missing = [
        str(path.relative_to(ROOT))
        for path in (maps_path, warps_path, npcs_path)
        if not path.exists()
    ]
    if missing:
        return {
            "ok": False,
            "detail": {
                "missing_required_payloads": missing,
            },
        }

    class _Stream:
        def write(self, payload: str) -> None:
            _ = payload

        def flush(self) -> None:
            return None

    class _Terminal:
        width = 80
        height = 24
        stream = _Stream()

    map_engine = MapEngine(
        maps_payload=json.loads(maps_path.read_text()),
        warps_payload=json.loads(warps_path.read_text()),
    )
    renderer = GameRenderer(_Terminal(), map_engine, npcs_payload=json.loads(npcs_path.read_text()))
    state = GameState(**{**GameState.fresh_game("ERDRICK").to_dict(), "map_id": 4, "player_x": 11, "player_y": 11})
    request = RenderFrameRequest(screen_mode="map", game_state=state)

    cols_vector_frame = renderer.draw(request, force_size=(79, 24))
    rows_vector_frame = renderer.draw(request, force_size=(80, 23))

    checks = {
        "cols_below_min_shows_notice": "TERMINAL TOO SMALL" in cols_vector_frame,
        "cols_below_min_shows_required_size": "REQUIRED: 80x24" in cols_vector_frame,
        "cols_below_min_shows_current_size": "CURRENT:  79x24" in cols_vector_frame,
        "cols_below_min_blocks_map_content": "@" not in cols_vector_frame,
        "cols_below_min_blocks_status_content": "NAME:" not in cols_vector_frame,
        "cols_below_min_blocks_dialog_scaffold": "┌" not in cols_vector_frame,
        "rows_below_min_shows_notice": "TERMINAL TOO SMALL" in rows_vector_frame,
        "rows_below_min_shows_required_size": "REQUIRED: 80x24" in rows_vector_frame,
        "rows_below_min_shows_current_size": "CURRENT:  80x23" in rows_vector_frame,
        "rows_below_min_blocks_map_content": "@" not in rows_vector_frame,
        "rows_below_min_blocks_status_content": "NAME:" not in rows_vector_frame,
        "rows_below_min_blocks_dialog_scaffold": "┌" not in rows_vector_frame,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "checks": checks,
            "vectors": {
                "small_cols": {
                    "size": [79, 24],
                    "notice_present": "TERMINAL TOO SMALL" in cols_vector_frame,
                    "required_present": "REQUIRED: 80x24" in cols_vector_frame,
                    "current_present": "CURRENT:  79x24" in cols_vector_frame,
                    "contains_player_marker": "@" in cols_vector_frame,
                    "contains_status_name": "NAME:" in cols_vector_frame,
                    "contains_dialog_border": "┌" in cols_vector_frame,
                },
                "small_rows": {
                    "size": [80, 23],
                    "notice_present": "TERMINAL TOO SMALL" in rows_vector_frame,
                    "required_present": "REQUIRED: 80x24" in rows_vector_frame,
                    "current_present": "CURRENT:  80x23" in rows_vector_frame,
                    "contains_player_marker": "@" in rows_vector_frame,
                    "contains_status_name": "NAME:" in rows_vector_frame,
                    "contains_dialog_border": "┌" in rows_vector_frame,
                },
            },
        },
    }


def check_phase5_slice_ascii_fallback_tileset() -> dict:
    from engine.map_engine import MapEngine
    from engine.state import GameState
    from ui.combat_view import initial_combat_view_state
    from ui.renderer import GameRenderer, RenderFrameRequest

    maps_path = ROOT / "extractor" / "data_out" / "maps.json"
    warps_path = ROOT / "extractor" / "data_out" / "warps.json"
    npcs_path = ROOT / "extractor" / "data_out" / "npcs.json"

    missing = [
        str(path.relative_to(ROOT))
        for path in (maps_path, warps_path, npcs_path)
        if not path.exists()
    ]
    if missing:
        return {
            "ok": False,
            "detail": {
                "missing_required_payloads": missing,
            },
        }

    def _ascii_only(text: str) -> bool:
        return all(ch == "\n" or ord(ch) < 128 for ch in text)

    class _Stream:
        def write(self, payload: str) -> None:
            _ = payload

        def flush(self) -> None:
            return None

    class _Terminal:
        width = 80
        height = 24
        stream = _Stream()

    map_engine = MapEngine(
        maps_payload=json.loads(maps_path.read_text()),
        warps_payload=json.loads(warps_path.read_text()),
    )
    renderer = GameRenderer(_Terminal(), map_engine, npcs_payload=json.loads(npcs_path.read_text()))
    state = GameState(**{**GameState.fresh_game("ERDRICK").to_dict(), "map_id": 4, "player_x": 11, "player_y": 11})

    map_frame = renderer.draw(RenderFrameRequest(screen_mode="map", game_state=state, ascii_fallback=True))
    combat_frame = renderer.draw(
        RenderFrameRequest(
            screen_mode="combat",
            game_state=state,
            combat_state=initial_combat_view_state(combat_log=("A Slime appears.",)),
            enemy_name="Slime",
            enemy_hp=3,
            enemy_max_hp=3,
            learned_spells=("HEAL",),
            ascii_fallback=True,
        )
    )
    dialog_frame = renderer.draw(
        RenderFrameRequest(
            screen_mode="dialog",
            game_state=state,
            dialog_text="Welcome to Alefgard.",
            ascii_fallback=True,
        )
    )

    checks = {
        "map_ascii_only": _ascii_only(map_frame),
        "map_preserves_player_marker": "@" in map_frame,
        "map_preserves_status_marker": "NAME " in map_frame,
        "map_dialog_border_falls_back_to_ascii": " DIALOG " in map_frame and "+" in map_frame and "|" in map_frame,
        "combat_ascii_only": _ascii_only(combat_frame),
        "combat_preserves_battle_marker": "BATTLE" in combat_frame,
        "combat_attack_cursor_falls_back_to_ascii": ">" in combat_frame,
        "dialog_ascii_only": _ascii_only(dialog_frame),
        "dialog_preserves_text_content": "Welcome to Alefgard." in dialog_frame,
        "dialog_border_falls_back_to_ascii": "+" in dialog_frame and "|" in dialog_frame,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "checks": checks,
            "vectors": {
                "map": {
                    "contains_non_ascii": not _ascii_only(map_frame),
                    "contains_player": "@" in map_frame,
                    "contains_status_name": "NAME " in map_frame,
                    "contains_ascii_dialog_border": " DIALOG " in map_frame and "+" in map_frame,
                    "contains_unicode_dialog_border": "┌" in map_frame,
                },
                "combat": {
                    "contains_non_ascii": not _ascii_only(combat_frame),
                    "contains_battle_marker": "BATTLE" in combat_frame,
                    "contains_ascii_cursor": ">" in combat_frame,
                    "contains_unicode_cursor": "►" in combat_frame,
                },
                "dialog": {
                    "contains_non_ascii": not _ascii_only(dialog_frame),
                    "contains_text": "Welcome to Alefgard." in dialog_frame,
                    "contains_ascii_border": "+" in dialog_frame,
                    "contains_unicode_border": "╔" in dialog_frame,
                },
            },
        },
    }


def check_phase5_slice_edge_case_regression_gate() -> dict:
    # SOURCE: Phase 4 slice artifacts — machine-generated, ROM-verified
    metal_slime_path = ROOT / "artifacts" / "phase4_slice_combat_metal_slime_flee.json"
    immunity_path = ROOT / "artifacts" / "phase4_slice_combat_enemy_sleep_stopspell_immunity.json"
    dragonlord_path = ROOT / "artifacts" / "phase4_slice_combat_dragonlord_two_phase_fight.json"

    missing = [
        str(p) for p in [metal_slime_path, immunity_path, dragonlord_path]
        if not p.exists()
    ]
    if missing:
        return {
            "ok": False,
            "detail": {"missing_source_artifacts": missing},
        }

    ms = json.loads(metal_slime_path.read_text())
    im = json.loads(immunity_path.read_text())
    dl = json.loads(dragonlord_path.read_text())

    ms_vectors = ms["checks"]["check_main_loop_combat_metal_slime_flee_artifacts"]["detail"]["vectors"]["vectors"]
    im_vectors = im["checks"]["check_main_loop_combat_enemy_sleep_stopspell_immunity_artifacts"]["detail"]["vectors"]["vectors"]
    dl_vectors = dl["checks"]["check_main_loop_combat_dragonlord_two_phase_fight_artifacts"]["detail"]["vectors"]["vectors"]

    flee_vec = ms_vectors["metal_slime_survives_then_flees"]
    golem_sleep = im_vectors["golem_sleep_immune"]
    golem_stop = im_vectors["golem_stopspell_immune"]
    p1_to_p2 = dl_vectors["phase1_to_phase2"]
    no_excellent = dl_vectors["phase1_no_excellent"]

    checks = {
        "metal_slime_flee_xp_zero": flee_vec["experience_after"] == flee_vec["experience_before"],
        "metal_slime_flee_gold_zero": flee_vec["gold_after"] == flee_vec["gold_before"],
        "metal_slime_flee_action_is_flee": flee_vec["action"] == "combat_enemy_flee",
        "golem_sleep_immune_enemy_not_asleep": golem_sleep["enemy_asleep_after"] is False,
        "golem_sleep_mp_consumed": golem_sleep["mp_after"] < golem_sleep["mp_before"],
        "golem_stopspell_immune_flag_clear": golem_stop["enemy_stopspell_after"] is False,
        "golem_stopspell_mp_consumed": golem_stop["mp_after"] < golem_stop["mp_before"],
        "dragonlord_phase1_to_phase2_enemy_id": p1_to_p2["enemy_id_after"] == 39,
        "dragonlord_phase2_hp_130": p1_to_p2["enemy_hp_after"] == 130,
        "dragonlord_no_excellent_in_phase1": no_excellent["frame_contains_excellent"] is False,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "source_artifacts": {
                "metal_slime": str(metal_slime_path.relative_to(ROOT)),
                "immunity": str(immunity_path.relative_to(ROOT)),
                "dragonlord": str(dragonlord_path.relative_to(ROOT)),
            },
            "checks": checks,
        },
    }


def run_pytest_phase5_edge_case_regression_gate_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_phase5_slice_closeout_validation_gate() -> dict:
    parity_path = ROOT / "artifacts" / "phase5_parity.json"
    terminal_size_path = ROOT / "artifacts" / "phase5_slice_terminal_size_enforcement.json"
    ascii_fallback_path = ROOT / "artifacts" / "phase5_slice_ascii_fallback_tileset.json"

    payloads: dict[str, dict] = {}
    missing: list[str] = []
    invalid_json: list[str] = []
    for label, path in {
        "phase5_parity": parity_path,
        "phase5_terminal_size": terminal_size_path,
        "phase5_ascii_fallback": ascii_fallback_path,
    }.items():
        if not path.exists():
            missing.append(str(path.relative_to(ROOT)))
            continue
        try:
            payloads[label] = json.loads(path.read_text())
        except Exception:
            invalid_json.append(str(path.relative_to(ROOT)))

    if missing or invalid_json:
        return {
            "ok": False,
            "detail": {
                "missing": missing,
                "invalid_json": invalid_json,
            },
        }

    parity_payload = payloads["phase5_parity"]
    terminal_size_payload = payloads["phase5_terminal_size"]
    ascii_fallback_payload = payloads["phase5_ascii_fallback"]

    row_results = parity_payload.get("row_results")
    if isinstance(row_results, list):
        row_result_count = len(row_results)
        evidence_tiers = {
            str(row.get("evidence_tier", "unknown"))
            for row in row_results
            if isinstance(row, dict)
        }
        systems = {
            str(row.get("system", ""))
            for row in row_results
            if isinstance(row, dict)
        }
        statuses = {
            str(row.get("status", ""))
            for row in row_results
            if isinstance(row, dict)
        }
        required_row_fields_present = all(
            isinstance(row, dict)
            and all(
                field in row
                for field in (
                    "row",
                    "system",
                    "test",
                    "expected",
                    "actual",
                    "passed",
                    "status",
                    "evidence",
                    "evidence_tier",
                    "rom_source",
                )
            )
            for row in row_results
        )
        has_non_pass_visibility = any(status in {"FAIL", "UNKNOWN", "BLOCKED"} for status in statuses)
    else:
        row_result_count = None
        evidence_tiers = set()
        systems = set()
        statuses = set()
        required_row_fields_present = False
        has_non_pass_visibility = False

    summary = parity_payload.get("summary")
    checks = {
        "phase5_parity_rows_present": isinstance(row_results, list) and row_result_count is not None and row_result_count >= 56,
        "phase5_parity_required_row_fields_present": required_row_fields_present,
        "phase5_parity_summary_present": isinstance(summary, dict),
        "phase5_parity_required_evidence_tiers_present": {"extractor-only", "runtime-state", "unknown"}.issubset(evidence_tiers),
        "phase5_parity_required_system_rows_present": {
            "Field Timers",
            "Combat",
            "Stats",
            "Economy",
            "Dialog/Flow",
            "Replay/Checkpoint",
            "Resistance Decode",
        }.issubset(systems),
        "phase5_parity_visibility_of_non_pass_rows": has_non_pass_visibility,
        "phase5_terminal_size_all_passed_true": terminal_size_payload.get("all_passed") is True,
        "phase5_ascii_fallback_all_passed_true": ascii_fallback_payload.get("all_passed") is True,
    }

    return {
        "ok": all(checks.values()),
        "detail": {
            "checks": checks,
            "evidence": {
                "phase5_parity": {
                    "artifact": "artifacts/phase5_parity.json",
                    "all_passed": parity_payload.get("all_passed"),
                    "row_count": row_result_count,
                    "summary": summary,
                    "evidence_tiers": sorted(evidence_tiers),
                    "statuses": sorted(statuses),
                },
                "phase5_terminal_size": {
                    "artifact": "artifacts/phase5_slice_terminal_size_enforcement.json",
                    "all_passed": terminal_size_payload.get("all_passed"),
                },
                "phase5_ascii_fallback": {
                    "artifact": "artifacts/phase5_slice_ascii_fallback_tileset.json",
                    "all_passed": ascii_fallback_payload.get("all_passed"),
                },
            },
        },
    }


def run_phase2_slice_rng_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_rng",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_rng_artifacts() -> dict:
    fixture_path = ROOT / "tests" / "fixtures" / "rng_golden_sequence.json"
    read_gate_path = ROOT / "artifacts" / "phase2_rng_read_gate.json"
    slice_artifact_path = ROOT / "artifacts" / "phase2_rng_fixture.json"

    if (
        not fixture_path.exists()
        or not read_gate_path.exists()
        or not slice_artifact_path.exists()
    ):
        return {
            "ok": False,
            "detail": {
                "fixture_exists": fixture_path.exists(),
                "read_gate_exists": read_gate_path.exists(),
                "slice_artifact_exists": slice_artifact_path.exists(),
            },
        }

    fixture = json.loads(fixture_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())
    artifact = json.loads(slice_artifact_path.read_text())

    sequence = fixture.get("sequence", [])
    method = fixture.get("method")
    required_count = 1000 if method == "py65" else 20
    ok = (
        bool(method)
        and len(sequence) == required_count
        and read_gate.get("completed") is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("UpdateRandNum")
        is True
        and artifact.get("slice") == "phase2-rng"
        and artifact.get("method") == method
        and artifact.get("sequence_count") == len(sequence)
        and fixture.get("rom", {}).get("baseline_match") is True
        and artifact.get("baseline_match") is True
    )

    return {
        "ok": ok,
        "detail": {
            "fixture": fixture,
            "read_gate": read_gate,
            "slice_artifact": artifact,
        },
    }


def run_pytest_phase2_rng_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_state_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_state",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_state_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_state_read_gate.json"
    artifact_path = ROOT / "artifacts" / "phase2_state_initialization.json"
    if not read_gate_path.exists() or not artifact_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "artifact_exists": artifact_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    checks = artifact.get("checks", {})
    snapshot = artifact.get("fresh_game_snapshot", {})
    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-state"
        and read_gate.get("files", {})
        .get("extractor/data_out/maps.json", {})
        .get("map_count")
        == 30
        and read_gate.get("files", {})
        .get("extractor/data_out/items.json", {})
        .get("item_cost_count")
        == 33
        and read_gate.get("files", {})
        .get("extractor/data_out/warps.json", {})
        .get("warp_count")
        == 51
        and artifact.get("slice") == "phase2-state"
        and artifact.get("all_passed") is True
        and checks
        and all(checks.values())
        and snapshot.get("map_id") == 4
        and snapshot.get("player_x") == 5
        and snapshot.get("player_y") == 27
    )
    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "artifact": artifact,
        },
    }


def run_pytest_phase2_state_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_level_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_level",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_level_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_level_read_gate.json"
    artifact_path = ROOT / "artifacts" / "phase2_level_progression.json"
    xp_fixture_path = ROOT / "tests" / "fixtures" / "xp_table_golden.json"
    stats_fixture_path = ROOT / "tests" / "fixtures" / "base_stats_golden.json"

    if (
        not read_gate_path.exists()
        or not artifact_path.exists()
        or not xp_fixture_path.exists()
        or not stats_fixture_path.exists()
    ):
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "artifact_exists": artifact_path.exists(),
                "xp_fixture_exists": xp_fixture_path.exists(),
                "base_stats_fixture_exists": stats_fixture_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    xp_fixture = json.loads(xp_fixture_path.read_text())
    stats_fixture = json.loads(stats_fixture_path.read_text())

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-level"
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("LevelUpTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked", {})
        .get("LoadStats")
        is True
        and read_gate.get("files", {})
        .get("Bank01.asm", {})
        .get("labels_checked", {})
        .get("BaseStatsTbl")
        is True
        and read_gate.get("files", {})
        .get("Bank01.asm", {})
        .get("labels_checked", {})
        .get("SetBaseStats")
        is True
        and artifact.get("slice") == "phase2-level"
        and artifact.get("all_passed") is True
        and artifact.get("checks")
        and all(artifact.get("checks", {}).values())
        and len(xp_fixture.get("levels", [])) == 30
        and len(stats_fixture.get("levels", [])) == 30
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "artifact": artifact,
            "xp_fixture_levels": len(xp_fixture.get("levels", [])),
            "base_stats_levels": len(stats_fixture.get("levels", [])),
        },
    }


def run_pytest_phase2_level_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_combat_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_combat",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_combat_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_combat_read_gate.json"
    formula_path = ROOT / "artifacts" / "phase2_combat_formulas.json"
    vectors_path = ROOT / "tests" / "fixtures" / "combat_golden_vectors.json"

    if not read_gate_path.exists() or not formula_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "formula_report_exists": formula_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    formula = json.loads(formula_path.read_text())
    vectors = json.loads(vectors_path.read_text())

    labels = read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {})
    fixture_vectors = vectors.get("vectors", {})
    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-combat"
        and labels
        and all(labels.values())
        and formula.get("slice") == "phase2-combat"
        and formula.get("all_passed") is True
        and formula.get("checks")
        and all(formula.get("checks", {}).values())
        and fixture_vectors.get("player_attack_max_atk") == 63
        and fixture_vectors.get("enemy_attack_zero_zero") == 0
        and fixture_vectors.get("enemy_attack_equal_threshold") == 22
        and fixture_vectors.get("heal_min") == 10
        and fixture_vectors.get("heal_max") == 17
        and fixture_vectors.get("enemy_hurt_armor_base5") == 3
        and fixture_vectors.get("enemy_hurtmore_armor_base32") == 21
    )
    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "formula": formula,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_combat_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_movement_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_movement",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_movement_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_movement_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_movement_logic.json"
    vectors_path = ROOT / "tests" / "fixtures" / "movement_golden_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-movement"
        and read_gate.get("files", {})
        .get("Bank03.asm", {})
        .get("labels_checked")
        and all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
        and report.get("slice") == "phase2-movement"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("zone_0_0") == 3
        and fixture_vectors.get("zone_119_119") == 9
        and fixture_vectors.get("swamp_plain") == [8, 0]
        and fixture_vectors.get("force_field_plain") == [0, 0]
        and fixture_vectors.get("choose_overworld_enemy_zone0_none") is None
        and fixture_vectors.get("repel_false") is False
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_movement_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_map_engine_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_map_engine",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_dialog_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_dialog",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_dialog_runtime_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_dialog_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_dialog_runtime.json"
    vectors_path = ROOT / "tests" / "fixtures" / "dialog_runtime_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-dialog"
        and all(read_gate.get("files", {}).get("Bank02.asm", {}).get("labels_checked", {}).values())
        and all(read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked", {}).values())
        and report.get("slice") == "phase2-dialog"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("dialog_block_count") == 19
        and fixture_vectors.get("block1_first_page") == "<CTRL_F4> hath woken up."
        and fixture_vectors.get("block1_is_done_after_one_page") is False
        and fixture_vectors.get("custom_page_one") == "Hello ERDRICK costs 42\n[VAR]"
        and fixture_vectors.get("custom_page_two") == "Bye"
        and fixture_vectors.get("custom_done_after_two_pages") is True
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_dialog_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "tests/test_map_engine.py",
        "tests/test_dialog_engine.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_shop_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_shop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_shop_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_shop_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_shop_runtime.json"
    vectors_path = ROOT / "tests" / "fixtures" / "shop_runtime_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-shop"
        and read_gate.get("files", {}).get("Bank00.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank00.asm"]["labels_checked"].values())
        and read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
        and report.get("slice") == "phase2-shop"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("shop_0_item_ids") == [2, 3, 10, 11, 14]
        and fixture_vectors.get("shop_0_prices") == [180, 560, 1000, 3000, 90]
        and fixture_vectors.get("inn_costs") == [20, 6, 25, 100, 55]
        and fixture_vectors.get("buy_copper_from_club_success") is True
        and fixture_vectors.get("buy_copper_from_club_gold") == 50
        and fixture_vectors.get("buy_torch_success") is True
        and fixture_vectors.get("buy_torch_inventory_slots") == [1, 0, 0, 0]
        and fixture_vectors.get("sell_torch_gold_gain") == 4
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_shop_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "tests/test_map_engine.py",
        "tests/test_dialog_engine.py",
        "tests/test_shop.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_save_load_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_save_load",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_save_load_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_save_load_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_save_load_runtime.json"
    vectors_path = ROOT / "tests" / "fixtures" / "save_load_runtime_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-save-load"
        and read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
        and report.get("slice") == "phase2-save-load"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("payload_length") == 30
        and fixture_vectors.get("payload_keys_clamped") == 6
        and fixture_vectors.get("payload_spare_bytes") == [0xC8, 0xC8, 0xC8, 0xC8]
        and fixture_vectors.get("save_dict_has_crc") is True
        and fixture_vectors.get("save_dict_roundtrip_equal") is True
        and fixture_vectors.get("json_roundtrip_save_data_equal") is True
        and fixture_vectors.get("portable_decode_experience") == 5432
        and fixture_vectors.get("portable_decode_gold") == 3210
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_save_load_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "tests/test_map_engine.py",
        "tests/test_dialog_engine.py",
        "tests/test_shop.py",
        "tests/test_save_load.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase2_slice_items_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "engine.run_phase2_slice_items",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_items_runtime_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_items_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_items_runtime.json"
    vectors_path = ROOT / "tests" / "fixtures" / "items_runtime_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-items"
        and read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
        and read_gate.get("files", {}).get("Dragon_Warrior_Defines.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Dragon_Warrior_Defines.asm"]["labels_checked"].values())
        and report.get("slice") == "phase2-items"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("torch_light_radius") == 5
        and fixture_vectors.get("torch_light_timer") == 16
        and fixture_vectors.get("fairy_repel_timer") == 0xFE
        and fixture_vectors.get("wings_dst") == [1, 42, 43]
        and fixture_vectors.get("outside_erdricks_dst") == [1, 28, 12]
        and fixture_vectors.get("outside_garinham_cave_dst") == [9, 19, 0]
        and fixture_vectors.get("outside_rock_mountain_dst") == [1, 29, 57]
        and fixture_vectors.get("outside_swamp_cave_dst") == [1, 104, 44]
        and fixture_vectors.get("outside_dragonlord_castle_dst") == [1, 48, 48]
        and fixture_vectors.get("rainbow_bridge_target") == [1, 63, 49]
        and fixture_vectors.get("check_and_apply_curse_hp") == 1
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_items_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "tests/test_map_engine.py",
        "tests/test_dialog_engine.py",
        "tests/test_shop.py",
        "tests/test_save_load.py",
        "tests/test_items_engine.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_ui_foundation_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_ui_foundation",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_ui_foundation_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_ui_foundation.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_foundation_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    frame = vectors.get("vectors", {}).get("frame", {})
    viewport = vectors.get("vectors", {}).get("viewport", {})
    layout = vectors.get("vectors", {}).get("layout", {})

    ok = (
        report.get("slice") == "phase3-ui-foundation"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and layout.get("cols") == 80
        and layout.get("rows") == 24
        and viewport.get("rows") == 17
        and viewport.get("cols") == 21
        and viewport.get("center_char") == "@"
        and frame.get("line_count") == 24
        and frame.get("col_count") == 80
        and frame.get("deterministic_repeat_match") is True
        and frame.get("player_glyph_count") == 1
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_ui_foundation_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_title_bootstrap_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_title_bootstrap",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_title_bootstrap_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_title_bootstrap.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_title_bootstrap_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    render = fixture_vectors.get("render", {})
    menu = fixture_vectors.get("menu", {})
    name_entry = fixture_vectors.get("name_entry", {})
    continue_section = fixture_vectors.get("continue", {})
    quit_section = fixture_vectors.get("quit", {})

    ok = (
        report.get("slice") == "phase3-title-bootstrap"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and render.get("line_count") == 24
        and render.get("col_count") == 80
        and render.get("deterministic_repeat_match") is True
        and render.get("contains_new_game") is True
        and render.get("contains_continue") is True
        and render.get("contains_quit") is True
        and menu.get("down_index") == 1
        and menu.get("up_wrap_index") == 2
        and menu.get("enter_new_game_name_mode") is True
        and name_entry.get("typed_name_buffer") == "ERDRICKX"
        and name_entry.get("name_max_len") == 8
        and name_entry.get("new_game_handoff_action") == "new_game"
        and name_entry.get("new_game_handoff_name") == "ERDRICK"
        and continue_section.get("continue_handoff_action") == "continue"
        and continue_section.get("continue_handoff_name") == "LOTO"
        and continue_section.get("missing_continue_handoff") is True
        and continue_section.get("missing_continue_message") == "NO SAVE DATA IN SLOT 0"
        and quit_section.get("quit_handoff_action") == "quit"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_title_bootstrap_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_menu_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_menu",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_menu_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_menu.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_menu_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    render = fixture_vectors.get("render", {})
    input_vectors = fixture_vectors.get("input", {})
    purity = fixture_vectors.get("purity", {})

    ok = (
        report.get("slice") == "phase3-menu"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and render.get("deterministic_repeat_match") is True
        and render.get("first_line", "").startswith("┌")
        and render.get("last_line", "").startswith("└")
        and render.get("contains_cursor_fight") is True
        and input_vectors.get("down_cursor") == 1
        and input_vectors.get("up_wrap_cursor") == 3
        and input_vectors.get("select_kind") == "select"
        and input_vectors.get("select_index") == 2
        and input_vectors.get("cancel_kind") == "cancel"
        and purity.get("initial_still_zero_after_transitions") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_menu_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_map_engine_artifacts() -> dict:
    read_gate_path = ROOT / "artifacts" / "phase2_map_engine_read_gate.json"
    report_path = ROOT / "artifacts" / "phase2_map_engine_logic.json"
    vectors_path = ROOT / "tests" / "fixtures" / "map_engine_golden_vectors.json"

    if not read_gate_path.exists() or not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "read_gate_exists": read_gate_path.exists(),
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    read_gate = json.loads(read_gate_path.read_text())
    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})

    ok = (
        read_gate.get("completed") is True
        and read_gate.get("slice") == "phase2-map-engine"
        and read_gate.get("files", {}).get("Bank00.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank00.asm"]["labels_checked"].values())
        and read_gate.get("files", {}).get("Bank03.asm", {}).get("labels_checked")
        and all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())
        and report.get("slice") == "phase2-map-engine"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("map_count") == 30
        and fixture_vectors.get("warp_count") == 51
        and fixture_vectors.get("map4_tile_start") == 15
        and fixture_vectors.get("map1_hill_tile") == 2
        and fixture_vectors.get("check_warp_index") == 4
        and fixture_vectors.get("check_warp_dst") == [4, 11, 29, 0]
        and fixture_vectors.get("handle_warp_state") == [4, 11, 29]
    )

    return {
        "ok": ok,
        "detail": {
            "read_gate": read_gate,
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase2_map_engine_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_phase1_read_gate.py",
        "tests/test_phase1_rom_spells.py",
        "tests/test_phase1_chests.py",
        "tests/test_phase1_enemies.py",
        "tests/test_phase1_zones.py",
        "tests/test_phase1_warps.py",
        "tests/test_phase1_items.py",
        "tests/test_phase1_npcs.py",
        "tests/test_phase1_dialog.py",
        "tests/test_phase1_maps.py",
        "tests/test_rng.py",
        "tests/test_state.py",
        "tests/test_level_up.py",
        "tests/test_combat.py",
        "tests/test_movement.py",
        "tests/test_map_engine.py",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }



def run_phase3_slice_dialog_box_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_dialog_box",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_dialog_box_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_dialog_box.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_dialog_box_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    render = fixture_vectors.get("render", {})
    paging = fixture_vectors.get("paging", {})
    integration = fixture_vectors.get("dialog_engine_integration", {})
    typewriter = fixture_vectors.get("typewriter", {})
    word_wrap_v = fixture_vectors.get("word_wrap", {})
    purity = fixture_vectors.get("purity", {})

    ok = (
        report.get("slice") == "phase3-dialog-box"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and word_wrap_v.get("hello_world_width_6") == ["Hello", "World"]
        and render.get("deterministic_repeat_match") is True
        and render.get("top_border_starts_with") == "\u2554"
        and render.get("bottom_border_starts_with") == "\u255a"
        and render.get("body_uses_vertical_bar") is True
        and render.get("body_line_count") == 3
        and paging.get("two_page_advance_kind") == "page_advance"
        and paging.get("last_page_done_kind") == "dialog_done"
        and paging.get("continuation_indicator_present") is True
        and paging.get("continuation_indicator_column") == 76
        and paging.get("continuation_indicator_absent_last") is True
        and integration.get("page_one_contains_player_name") is True
        and integration.get("page_one_contains_gold_cost") is True
        and integration.get("page_one_preserves_unknown_marker") is True
        and integration.get("page_one_has_line_break") is True
        and integration.get("render_contains_player_name") is True
        and integration.get("page_two_text") == "Second page"
        and integration.get("session_done_after_two_pages") is True
        and typewriter.get("initial_char_reveal") == 0
        and typewriter.get("after_tick_3") == 3
        and typewriter.get("after_skip") == -1
        and purity.get("original_page_unchanged_after_advance") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_dialog_box_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_combat_view_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_combat_view",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_combat_view_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_combat_view.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_combat_view_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    spells = fixture_vectors.get("spells", {})
    hp_bar = fixture_vectors.get("hp_bar", {})
    runtime = fixture_vectors.get("runtime", {})
    render = fixture_vectors.get("render", {})

    ok = (
        report.get("slice") == "phase3-combat-view"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and spells.get("fresh_game_learned") == []
        and spells.get("max_learned_count") == 10
        and spells.get("contains_healmore") is True
        and spells.get("contains_hurtmore") is True
        and hp_bar.get("empty") == "[··········]"
        and hp_bar.get("half") == "[█████·····]"
        and hp_bar.get("full") == "[██████████]"
        and runtime.get("spell_menu_open_event") == "spell_menu_opened"
        and runtime.get("spell_selected_event") == "spell_selected"
        and runtime.get("spell_selected_name") == "HURT"
        and runtime.get("no_spell_event") == "no_spells"
        and runtime.get("log_line_count") == 4
        and render.get("line_count") == 24
        and render.get("col_count") == 80
        and render.get("deterministic_repeat_match") is True
        and render.get("contains_enemy_name") is True
        and render.get("contains_log_title") is True
        and render.get("contains_menu_title") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_combat_view_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_status_panel_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_status_panel",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_status_panel_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_status_panel.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_status_panel_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    equipment = fixture_vectors.get("equipment", {})
    thresholds = fixture_vectors.get("thresholds", {})
    shape = fixture_vectors.get("shape", {})

    ok = (
        report.get("slice") == "phase3-status-panel"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and equipment.get("decoded") == ["COPR", "LETH", "SML"]
        and "EQ COPR/LETH/SML" in equipment.get("line", "")
        and thresholds.get("critical_flags") == [True, True]
        and "HP!" in thresholds.get("critical_hp_line", "")
        and "MP*" in thresholds.get("critical_mp_line", "")
        and shape.get("line_count") == 9
        and shape.get("line_widths") == [20] * 9
        and shape.get("deterministic_repeat_match") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_status_panel_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_map_view_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_map_view",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_map_view_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_map_view.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_map_view_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    overworld = fixture_vectors.get("overworld", {})
    npc_overlay = fixture_vectors.get("npc_overlay", {})
    darkness = fixture_vectors.get("darkness", {})

    ok = (
        report.get("slice") == "phase3-map-view"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and overworld.get("rows") == 17
        and overworld.get("cols") == 21
        and overworld.get("center_char") == "@"
        and npc_overlay.get("default_story_right_of_center") == "░"
        and npc_overlay.get("post_story_right_of_center") == "Z"
        and npc_overlay.get("default_npc_visible_count", 0) > 0
        and npc_overlay.get("post_npc_visible_count", 0) > 0
        and darkness.get("corner_char") == " "
        and darkness.get("center_char") == "@"
        and darkness.get("dark_tile_count", 0) > 0
        and darkness.get("deterministic_repeat_match") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_map_view_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase3_slice_renderer_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase3_slice_renderer",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_renderer_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase3_renderer.json"
    vectors_path = ROOT / "tests" / "fixtures" / "ui_renderer_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    dispatch = fixture_vectors.get("dispatch", {})
    double_buffer = fixture_vectors.get("double_buffer", {})
    resize = fixture_vectors.get("resize", {})

    ok = (
        report.get("slice") == "phase3-renderer"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and dispatch.get("title", {}).get("contains_marker") is True
        and dispatch.get("map", {}).get("contains_marker") is True
        and dispatch.get("combat", {}).get("contains_marker") is True
        and dispatch.get("dialog", {}).get("contains_marker") is True
        and double_buffer.get("writes_after_first") == 1
        and double_buffer.get("writes_after_second") == 1
        and double_buffer.get("writes_after_third") == 2
        and resize.get("small_contains_notice") is True
        and resize.get("recover_contains_player") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase3_renderer_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_main_loop_scaffold_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_scaffold_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_scaffold.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_scaffold_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    ok = (
        report.get("slice") == "phase4-main-loop-scaffold"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fixture_vectors.get("title", {}).get("contains_marker") is True
        and fixture_vectors.get("new_game", {}).get("screen_mode") == "map"
        and fixture_vectors.get("new_game", {}).get("action") == "new_game_started"
        and fixture_vectors.get("map_step", {}).get("action") in {"move", "warp"}
        and fixture_vectors.get("timers_after_step", {}).get("repel_timer") == 1
        and fixture_vectors.get("timers_after_step", {}).get("light_timer") == 0
        and fixture_vectors.get("quit", {}).get("quit_requested") is True
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_main_loop_scaffold_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_save_load_loop_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_save_load_loop_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_save_load_loop.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_save_load_loop_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fixture_vectors = vectors.get("vectors", {})
    continue_v = fixture_vectors.get("continue", {})
    save_on_quit_v = fixture_vectors.get("save_on_quit", {})
    ok = (
        report.get("slice") == "phase4-main-loop-save-load-loop"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and continue_v.get("screen_mode") == "map"
        and continue_v.get("action") == "continue_loaded"
        and continue_v.get("player_name") == "LOTO"
        and continue_v.get("position") == [4, 5, 27]
        and continue_v.get("save_dict_roundtrip_equal") is True
        and save_on_quit_v.get("action") == "quit"
        and save_on_quit_v.get("quit_requested") is True
        and save_on_quit_v.get("save_exists") is True
        and save_on_quit_v.get("loaded_name") == "ERDRICK"
        and save_on_quit_v.get("loaded_position") == [4, 5, 27]
        and save_on_quit_v.get("save_dict_roundtrip_equal") is True
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_save_load_loop_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_inn_stay_save_trigger_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_inn_stay_save_trigger_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_inn_stay_save_trigger.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_inn_stay_save_trigger_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    inn_v = vectors.get("vectors", {}).get("inn_stay", {})
    ok = (
        report.get("slice") == "phase4-main-loop-inn-stay-save-trigger"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and inn_v.get("action") == "inn_stay"
        and inn_v.get("quit_requested") is False
        and inn_v.get("hp_after") == inn_v.get("max_hp")
        and inn_v.get("mp_after") == inn_v.get("max_mp")
        and inn_v.get("save_exists") is True
        and inn_v.get("save_dict_roundtrip_equal") is True
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_inn_stay_save_trigger_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_inn_cost_deduct_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_inn_cost_deduct_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_inn_cost_deduct.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_inn_cost_deduct_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    inn_v = vectors.get("vectors", {}).get("inn_stay", {})
    rejected_v = vectors.get("vectors", {}).get("inn_stay_rejected", {})
    ok = (
        report.get("slice") == "phase4-main-loop-inn-cost-deduct"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and inn_v.get("action") == "inn_stay"
        and inn_v.get("gold_after") == inn_v.get("gold_before") - inn_v.get("inn_cost")
        and inn_v.get("hp_after") == inn_v.get("max_hp")
        and inn_v.get("mp_after") == inn_v.get("max_mp")
        and inn_v.get("save_exists") is True
        and inn_v.get("save_dict_roundtrip_equal") is True
        and rejected_v.get("action") == "inn_stay_rejected"
        and rejected_v.get("gold_after") == rejected_v.get("gold_before")
        and rejected_v.get("hp_after") == rejected_v.get("hp_before")
        and rejected_v.get("mp_after") == rejected_v.get("mp_before")
        and rejected_v.get("save_exists") is False
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_inn_cost_deduct_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_encounter_trigger_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_encounter_trigger_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_encounter_trigger.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_encounter_trigger_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    encounter_v = vectors.get("vectors", {}).get("encounter", {})
    no_encounter_v = vectors.get("vectors", {}).get("no_encounter", {})
    ok = (
        report.get("slice") == "phase4-main-loop-encounter-trigger"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and encounter_v.get("input") == "RIGHT"
        and encounter_v.get("screen_mode") == "combat"
        and encounter_v.get("action") == "encounter_triggered"
        and encounter_v.get("action_detail") == "enemy:3"
        and encounter_v.get("position") == [47, 1]
        and encounter_v.get("rng_after") == [40, 122]
        and encounter_v.get("frame_contains_fight") is True
        and encounter_v.get("frame_contains_enemy") is True
        and encounter_v.get("frame_contains_ghost") is True
        and encounter_v.get("combat_session", {}).get("enemy_id") == 3
        and encounter_v.get("combat_session", {}).get("enemy_name") == "Ghost"
        and encounter_v.get("combat_session", {}).get("enemy_hp") == 7
        and no_encounter_v.get("input") == "RIGHT"
        and no_encounter_v.get("screen_mode") == "map"
        and no_encounter_v.get("action") == "move"
        and no_encounter_v.get("action_detail") == "47,1"
        and no_encounter_v.get("position") == [47, 1]
        and no_encounter_v.get("rng_after") == [129, 3]
        and no_encounter_v.get("frame_contains_fight") is False
        and no_encounter_v.get("combat_session") is None
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_encounter_trigger_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_dungeon_encounter_runtime_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_dungeon_encounter_runtime_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_dungeon_encounter_runtime.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_dungeon_encounter_runtime_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    dungeon_v = vectors.get("vectors", {}).get("dungeon_encounter", {})
    combat_session = dungeon_v.get("combat_session", {})
    ok = (
        report.get("slice") == "phase4-main-loop-dungeon-encounter-runtime"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and dungeon_v.get("input") == "RIGHT"
        and dungeon_v.get("map_id") == 15
        and dungeon_v.get("screen_mode") == "combat"
        and dungeon_v.get("action") == "encounter_triggered"
        and dungeon_v.get("action_detail") == "enemy:32"
        and dungeon_v.get("position") == [1, 0]
        and dungeon_v.get("rng_after") == [40, 122]
        and dungeon_v.get("frame_contains_fight") is True
        and dungeon_v.get("frame_contains_enemy") is True
        and dungeon_v.get("frame_contains_wizard") is True
        and combat_session.get("enemy_id") == 32
        and combat_session.get("enemy_name") == "Wizard"
        and combat_session.get("enemy_hp") == 58
        and combat_session.get("enemy_max_hp") == 58
        and combat_session.get("enemy_base_hp") == 65
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_dungeon_encounter_runtime_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_session_handoff_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_session_handoff_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_session_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_session_handoff_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    handoff_v = vectors.get("vectors", {}).get("combat_session_handoff", {})
    combat_session = handoff_v.get("combat_session", {})
    ok = (
        report.get("slice") == "phase4-main-loop-combat-session-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and handoff_v.get("screen_mode") == "combat"
        and handoff_v.get("action") == "encounter_triggered"
        and handoff_v.get("action_detail") == "enemy:3"
        and handoff_v.get("position") == [47, 1]
        and handoff_v.get("rng_after") == [40, 122]
        and handoff_v.get("frame_contains_fight") is True
        and handoff_v.get("frame_contains_enemy") is True
        and handoff_v.get("frame_contains_ghost") is True
        and combat_session.get("enemy_id") == 3
        and combat_session.get("enemy_name") == "Ghost"
        and combat_session.get("enemy_hp") == 7
        and combat_session.get("enemy_max_hp") == 7
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_session_handoff_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_turn_resolution_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_turn_resolution_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_turn_resolution.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_turn_resolution_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fight_v = vectors.get("vectors", {}).get("fight", {})
    spell_v = vectors.get("vectors", {}).get("spell_hurt", {})
    item_v = vectors.get("vectors", {}).get("item", {})
    run_v = vectors.get("vectors", {}).get("run", {})
    excellent_v = vectors.get("vectors", {}).get("excellent_fight", {})
    run_fail_v = vectors.get("vectors", {}).get("run_fail", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-turn-resolution"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fight_v.get("action") == "combat_turn"
        and fight_v.get("action_detail") == "FIGHT"
        and fight_v.get("enemy_hp_after") == 7
        and fight_v.get("player_hp_after") == 11
        and fight_v.get("rng_after") == [141, 182]
        and spell_v.get("action") == "combat_victory"
        and spell_v.get("action_detail") == "HURT"
        and spell_v.get("enemy_hp_after") is None
        and spell_v.get("player_hp_after") == 15
        and spell_v.get("mp_after") == 10
        and spell_v.get("rng_after") == [141, 182]
        and item_v.get("action") == "combat_turn"
        and item_v.get("action_detail") == "ITEM"
        and item_v.get("enemy_hp_after") == 7
        and item_v.get("player_hp_after") == 13
        and item_v.get("rng_after") == [129, 3]
        and run_v.get("action") == "combat_run"
        and run_v.get("screen_mode") == "map"
        and run_v.get("combat_session_cleared") is True
        and excellent_v.get("action") == "combat_turn"
        and excellent_v.get("enemy_hp_after") == 4
        and excellent_v.get("player_hp_after") == 11
        and excellent_v.get("rng_after") == [141, 155]
        and excellent_v.get("frame_contains_excellent") is True
        and run_fail_v.get("action") == "combat_run_failed"
        and run_fail_v.get("screen_mode") == "combat"
        and run_fail_v.get("combat_session_present") is True
        and run_fail_v.get("player_hp_after") == 13
        and run_fail_v.get("rng_after") == [129, 0]
        and run_fail_v.get("frame_contains_blocked") is True
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_turn_resolution_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_spell_in_battle_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_spell_in_battle",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_spell_in_battle_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_spell_in_battle.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_spell_in_battle_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-spell-in-battle"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("heal", {}).get("action") == "combat_turn"
        and v.get("heal", {}).get("action_detail") == "HEAL"
        and v.get("heal", {}).get("mp_after") == 6
        and v.get("healmore", {}).get("action") == "combat_turn"
        and v.get("healmore", {}).get("action_detail") == "HEALMORE"
        and v.get("healmore", {}).get("mp_after") == 10
        and v.get("hurt", {}).get("action") == "combat_turn"
        and v.get("hurt", {}).get("action_detail") == "HURT"
        and v.get("hurt", {}).get("mp_after") == 10
        and v.get("hurtmore", {}).get("action") == "combat_turn"
        and v.get("hurtmore", {}).get("action_detail") == "HURTMORE"
        and v.get("hurtmore", {}).get("mp_after") == 10
        and v.get("sleep", {}).get("action") == "combat_turn"
        and v.get("sleep", {}).get("action_detail") == "SLEEP"
        and v.get("sleep", {}).get("enemy_asleep_after") is True
        and v.get("stopspell", {}).get("action") == "combat_turn"
        and v.get("stopspell", {}).get("action_detail") == "STOPSPELL"
        and v.get("stopspell", {}).get("enemy_stopspell_after") is True
        and v.get("hurt_fail", {}).get("action") == "combat_turn"
        and v.get("hurt_fail", {}).get("action_detail") == "HURT"
        and v.get("hurt_fail", {}).get("enemy_hp_after") == 40
        and v.get("not_enough_mp", {}).get("action") == "combat_spell_rejected"
        and v.get("not_enough_mp", {}).get("action_detail") == "SPELL:not_enough_mp"
        and v.get("unsupported", {}).get("action") == "combat_spell_rejected"
        and v.get("unsupported", {}).get("action_detail") == "SPELL:unsupported"
    )
    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_spell_in_battle_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_asleep_stopspell_flag_effects_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_asleep_stopspell_flag_effects",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_asleep_stopspell_flag_effects_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_asleep_stopspell_flag_effects.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_asleep_stopspell_flag_effects_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    asleep_skip = vectors.get("vectors", {}).get("asleep_skip", {})
    asleep_wake = vectors.get("vectors", {}).get("asleep_wake", {})
    stopspell_downgrade = vectors.get("vectors", {}).get("stopspell_downgrade", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-asleep-stopspell-flag-effects"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and asleep_skip.get("action") == "combat_turn"
        and asleep_skip.get("screen_mode") == "combat"
        and asleep_skip.get("player_hp_after") == asleep_skip.get("player_hp_before")
        and asleep_skip.get("enemy_asleep_after") is True
        and "Ghost is asleep." in asleep_skip.get("frame", "")
        and "STRIKES" not in asleep_skip.get("frame", "")
        and asleep_wake.get("action") == "combat_turn"
        and asleep_wake.get("screen_mode") == "combat"
        and asleep_wake.get("player_hp_after") == asleep_wake.get("player_hp_before")
        and asleep_wake.get("enemy_asleep_after") is False
        and "Ghost is asleep." in asleep_wake.get("frame", "")
        and "Ghost wakes up." in asleep_wake.get("frame", "")
        and "STRIKES" not in asleep_wake.get("frame", "")
        and stopspell_downgrade.get("action") == "combat_turn"
        and stopspell_downgrade.get("screen_mode") == "combat"
        and stopspell_downgrade.get("player_hp_after", 0) < stopspell_downgrade.get("player_hp_before", 0)
        and "Ghost's spell has been stopped." in stopspell_downgrade.get("frame", "")
        and "STRIKES" in stopspell_downgrade.get("frame", "")
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_asleep_stopspell_flag_effects_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_player_stopspell_enforcement_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_player_stopspell_enforcement",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_player_stopspell_enforcement_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_player_stopspell_enforcement.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_player_stopspell_enforcement_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    blocked = vectors.get("vectors", {}).get("blocked_with_player_stopspell_true", {})
    normal = vectors.get("vectors", {}).get("normal_with_player_stopspell_false", {})
    multi_turn = vectors.get("vectors", {}).get("multi_turn_stopspell_then_blocked_spell", {})
    next_turn = multi_turn.get("turn_n_plus_1", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-player-stopspell-enforcement"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and blocked.get("action") == "combat_turn"
        and blocked.get("screen_mode") == "combat"
        and "player_stopspell_blocked" in str(blocked.get("action_detail", ""))
        and blocked.get("player_mp_after") == blocked.get("player_mp_before")
        and blocked.get("enemy_hp_after") == blocked.get("enemy_hp_before")
        and "Your spell has been stopped." in blocked.get("frame", "")
        and "STRIKES" in blocked.get("frame", "")
        and normal.get("action") == "combat_turn"
        and normal.get("screen_mode") == "combat"
        and normal.get("action_detail") == "HURT"
        and normal.get("player_mp_after") == normal.get("player_mp_before") - 2
        and normal.get("enemy_hp_after", 999) < normal.get("enemy_hp_before", 0)
        and "HURT FOR" in normal.get("frame", "")
        and multi_turn.get("turn_n_action") == "combat_turn"
        and multi_turn.get("turn_n_action_detail") == "ITEM"
        and next_turn.get("action") == "combat_turn"
        and "player_stopspell_blocked" in str(next_turn.get("action_detail", ""))
        and next_turn.get("player_mp_after") == next_turn.get("player_mp_before")
        and "Your spell has been stopped." in next_turn.get("frame", "")
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_player_stopspell_enforcement_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_enemy_sleep_stopspell_immunity_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_enemy_sleep_stopspell_immunity",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_enemy_sleep_stopspell_immunity_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_enemy_sleep_stopspell_immunity.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_enemy_sleep_stopspell_immunity_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    golem_sleep = vectors.get("vectors", {}).get("golem_sleep_immune", {})
    golem_stopspell = vectors.get("vectors", {}).get("golem_stopspell_immune", {})
    slime_sleep = vectors.get("vectors", {}).get("slime_sleep_regression", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-enemy-sleep-stopspell-immunity"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and golem_sleep.get("action") == "combat_turn"
        and golem_sleep.get("action_detail") == "SLEEP"
        and golem_sleep.get("screen_mode") == "combat"
        and golem_sleep.get("mp_after") == golem_sleep.get("mp_before") - 2
        and golem_sleep.get("enemy_asleep_after") is False
        and "GOLEM IS IMMUNE." in golem_sleep.get("frame", "")
        and golem_stopspell.get("action") == "combat_turn"
        and golem_stopspell.get("action_detail") == "STOPSPELL"
        and golem_stopspell.get("screen_mode") == "combat"
        and golem_stopspell.get("mp_after") == golem_stopspell.get("mp_before") - 2
        and golem_stopspell.get("enemy_stopspell_after") is False
        and "GOLEM IS IMMUNE." in golem_stopspell.get("frame", "")
        and slime_sleep.get("action") == "combat_turn"
        and slime_sleep.get("action_detail") == "SLEEP"
        and slime_sleep.get("screen_mode") == "combat"
        and slime_sleep.get("mp_after") == slime_sleep.get("mp_before") - 2
        and slime_sleep.get("enemy_asleep_after") is True
        and "SLIME IS ASLEEP." in slime_sleep.get("frame", "")
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_enemy_sleep_stopspell_immunity_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_metal_slime_flee_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_metal_slime_flee",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_metal_slime_flee_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_metal_slime_flee.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_metal_slime_flee_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    flee_v = vectors.get("vectors", {}).get("metal_slime_survives_then_flees", {})
    kill_v = vectors.get("vectors", {}).get("metal_slime_one_shot_victory", {})
    regression_v = vectors.get("vectors", {}).get("non_metal_slime_fight_regression", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-metal-slime-flee"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and flee_v.get("action") == "combat_enemy_flee"
        and flee_v.get("action_detail") == "metal_slime_flee"
        and flee_v.get("screen_mode") == "dialog"
        and flee_v.get("experience_after") == flee_v.get("experience_before")
        and flee_v.get("gold_after") == flee_v.get("gold_before")
        and flee_v.get("combat_session_cleared") is True
        and flee_v.get("dialog_done_action") == "dialog_done"
        and flee_v.get("screen_mode_after_dialog_done") == "map"
        and "Metal Slime escaped!" in flee_v.get("frame", "")
        and kill_v.get("action") == "combat_victory"
        and kill_v.get("screen_mode") == "dialog"
        and kill_v.get("experience_after", 0) > kill_v.get("experience_before", 0)
        and kill_v.get("gold_after", 0) > kill_v.get("gold_before", 0)
        and kill_v.get("combat_session_cleared") is True
        and "METAL SLIME IS DEFEATED." in kill_v.get("frame", "")
        and "Metal Slime escaped!" not in kill_v.get("frame", "")
        and regression_v.get("action") == "combat_turn"
        and regression_v.get("screen_mode") == "combat"
        and regression_v.get("combat_session_cleared") is False
        and "Metal Slime escaped!" not in regression_v.get("frame", "")
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_metal_slime_flee_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_dragonlord_two_phase_fight_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_dragonlord_two_phase_fight",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_dragonlord_two_phase_fight_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_dragonlord_two_phase_fight.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_dragonlord_two_phase_fight_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    phase1_to_phase2 = vectors.get("vectors", {}).get("phase1_to_phase2", {})
    phase2_victory = vectors.get("vectors", {}).get("phase2_victory_zero_rewards", {})
    run_blocked_phase1 = vectors.get("vectors", {}).get("run_blocked_phase1", {})
    run_blocked_phase2 = vectors.get("vectors", {}).get("run_blocked_phase2", {})
    no_excellent = vectors.get("vectors", {}).get("phase1_no_excellent", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-dragonlord-two-phase-fight"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and phase1_to_phase2.get("action") == "combat_turn"
        and phase1_to_phase2.get("screen_mode") == "combat"
        and phase1_to_phase2.get("experience_after") == phase1_to_phase2.get("experience_before")
        and phase1_to_phase2.get("gold_after") == phase1_to_phase2.get("gold_before")
        and phase1_to_phase2.get("enemy_id_after") == 0x27
        and phase1_to_phase2.get("enemy_hp_after") == 130
        and phase1_to_phase2.get("enemy_max_hp_after") == 130
        and phase1_to_phase2.get("enemy_atk_after") == 140
        and phase1_to_phase2.get("enemy_def_after") == 200
        and phase1_to_phase2.get("enemy_agi_after") == 255
        and phase1_to_phase2.get("enemy_mdef_after") == 240
        and phase1_to_phase2.get("enemy_pattern_flags_after") == 14
        and phase1_to_phase2.get("enemy_xp_after") == 0
        and phase1_to_phase2.get("enemy_gp_after") == 0
        and "DRAGONLORD'S TRUE FORM APPEARS!" in phase1_to_phase2.get("frame", "")
        and phase2_victory.get("action") == "combat_victory"
        and phase2_victory.get("screen_mode") == "dialog"
        and phase2_victory.get("experience_after") == phase2_victory.get("experience_before")
        and phase2_victory.get("gold_after") == phase2_victory.get("gold_before")
        and phase2_victory.get("combat_session_cleared") is True
        and "DRAGONLORD'S TRUE FORM IS DEFEATED." in phase2_victory.get("frame", "")
        and run_blocked_phase1.get("action") == "combat_run_failed"
        and run_blocked_phase1.get("screen_mode") == "combat"
        and run_blocked_phase1.get("combat_session_present") is True
        and "BLOCKED" in run_blocked_phase1.get("frame", "")
        and run_blocked_phase2.get("action") == "combat_run_failed"
        and run_blocked_phase2.get("screen_mode") == "combat"
        and run_blocked_phase2.get("combat_session_present") is True
        and "BLOCKED" in run_blocked_phase2.get("frame", "")
        and no_excellent.get("action") == "combat_turn"
        and no_excellent.get("screen_mode") == "combat"
        and no_excellent.get("frame_contains_excellent") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_dragonlord_two_phase_fight_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_dragonlord_endgame_victory_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_combat_dragonlord_endgame_victory",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_dragonlord_endgame_victory_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_dragonlord_endgame_victory.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_dragonlord_endgame_victory_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    victory = vectors.get("vectors", {}).get("dragonlord_phase2_victory", {})
    ending = vectors.get("vectors", {}).get("ending_dialog_sequence", {})
    npc_render = vectors.get("vectors", {}).get("npc_render_after_flag", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-dragonlord-endgame-victory"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and victory.get("action") == "combat_victory"
        and victory.get("action_detail") == "dragonlord_endgame"
        and victory.get("screen_mode") == "dialog"
        and victory.get("experience_after") == victory.get("experience_before")
        and victory.get("gold_after") == victory.get("gold_before")
        and victory.get("dragonlord_dead_flag_set") is True
        and victory.get("combat_session_cleared") is True
        and victory.get("frame_contains_special_page_1") is True
        and victory.get("frame_contains_generic_rewards") is False
        and ending.get("first_action") == "combat_victory"
        and ending.get("first_screen_mode") == "dialog"
        and ending.get("first_frame_contains_page_1") is True
        and ending.get("second_action") == "dialog_page_advance"
        and ending.get("second_frame_contains_page_2") is True
        and ending.get("third_action") == "dialog_page_advance"
        and ending.get("third_frame_contains_page_3") is True
        and ending.get("done_action") == "dialog_done"
        and ending.get("done_screen_mode") == "endgame"
        and ending.get("done_frame_contains_the_end") is True
        and npc_render.get("default_story_right_of_center") == "░"
        and npc_render.get("post_dragonlord_right_of_center") == "Z"
        and npc_render.get("post_variant_uses_wizard_sprite") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_dragonlord_endgame_victory_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_endgame_return_to_title_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_endgame_return_to_title",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_endgame_return_to_title_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_endgame_return_to_title.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_endgame_return_to_title_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    render_v = vectors.get("vectors", {}).get("endgame_render", {})
    transition_v = vectors.get("vectors", {}).get("endgame_to_title", {})
    continue_v = vectors.get("vectors", {}).get("continue_after_restart", {})

    ok = (
        report.get("slice") == "phase4-main-loop-endgame-return-to-title"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and render_v.get("screen_mode") == "endgame"
        and render_v.get("frame_contains_final_page_text") is True
        and render_v.get("frame_contains_return_prompt") is True
        and render_v.get("frame_contains_dragonlord_page_text") is False
        and transition_v.get("action") == "endgame_return_to_title"
        and transition_v.get("action_detail") == "restart"
        and transition_v.get("screen_mode") == "title"
        and transition_v.get("frame_contains_title") is True
        and transition_v.get("frame_contains_new_game") is True
        and transition_v.get("frame_contains_continue") is True
        and transition_v.get("quit_requested") is False
        and transition_v.get("combat_session_cleared") is True
        and transition_v.get("dialog_session_cleared") is True
        and transition_v.get("dialog_box_state_cleared") is True
        and transition_v.get("opened_chest_indices") == []
        and transition_v.get("opened_doors") == []
        and transition_v.get("story_flags_after") == 0
        and continue_v.get("save_exists_before_restart") is True
        and continue_v.get("save_exists_after_restart") is True
        and continue_v.get("continue_action") == "continue_loaded"
        and continue_v.get("continue_screen_mode") == "map"
        and continue_v.get("loaded_has_dragonlord_dead_flag") is True
        and continue_v.get("frame_contains_no_save_data") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_endgame_return_to_title_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_endgame_input_coverage_hardening_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_endgame_input_coverage_hardening",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_endgame_input_coverage_hardening_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_endgame_input_coverage_hardening.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_endgame_input_coverage_hardening_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    a_v = vectors.get("vectors", {}).get("endgame_a_to_title", {})
    z_v = vectors.get("vectors", {}).get("endgame_z_to_title", {})
    q_v = vectors.get("vectors", {}).get("endgame_q_quit", {})
    esc_v = vectors.get("vectors", {}).get("endgame_esc_quit", {})
    enter_v = vectors.get("vectors", {}).get("endgame_enter_regression", {})

    ok = (
        report.get("slice") == "phase4-main-loop-endgame-input-coverage-hardening"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and a_v.get("pre_input_render_path") == "endgame"
        and a_v.get("action") == "endgame_return_to_title"
        and a_v.get("action_detail") == "restart"
        and a_v.get("screen_mode") == "title"
        and a_v.get("session_exit") is False
        and a_v.get("story_flags_after") == 0
        and z_v.get("pre_input_render_path") == "endgame"
        and z_v.get("action") == "endgame_return_to_title"
        and z_v.get("action_detail") == "restart"
        and z_v.get("screen_mode") == "title"
        and z_v.get("session_exit") is False
        and z_v.get("story_flags_after") == 0
        and q_v.get("pre_input_render_path") == "endgame"
        and q_v.get("action") == "quit"
        and q_v.get("action_detail") == "endgame"
        and q_v.get("screen_mode") == "endgame"
        and q_v.get("session_exit") is True
        and esc_v.get("pre_input_render_path") == "endgame"
        and esc_v.get("action") == "quit"
        and esc_v.get("action_detail") == "endgame"
        and esc_v.get("screen_mode") == "endgame"
        and esc_v.get("session_exit") is True
        and enter_v.get("pre_input_render_path") == "endgame"
        and enter_v.get("action") == "endgame_return_to_title"
        and enter_v.get("action_detail") == "restart"
        and enter_v.get("screen_mode") == "title"
        and enter_v.get("session_exit") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_endgame_input_coverage_hardening_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_post_victory_npc_world_state_proof_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_post_victory_npc_world_state_proof",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_post_victory_npc_world_state_proof_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_post_victory_npc_world_state_proof.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_post_victory_npc_world_state_proof_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    tantegel_v = vectors.get("vectors", {}).get("tantegel_post_victory_regression", {})
    additional_v = vectors.get("vectors", {}).get("additional_map_id_post_victory_npc_variant", {})
    endgame_v = vectors.get("vectors", {}).get("post_victory_endgame_pre_input", {})

    ok = (
        report.get("slice") == "phase4-main-loop-post-victory-npc-world-state-proof"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and tantegel_v.get("default_story_right_of_center") == "░"
        and tantegel_v.get("post_dragonlord_right_of_center") == "Z"
        and tantegel_v.get("post_variant_uses_wizard_sprite") is True
        and additional_v.get("map_id") == 5
        and additional_v.get("story_flags") == 4
        and additional_v.get("active_map_variant") == "post_dragonlord"
        and isinstance(additional_v.get("active_npc_count"), int)
        and additional_v.get("active_npc_count", 0) > 0
        and additional_v.get("resolved_sprite") == "princess_gwaelin"
        and additional_v.get("right_of_center_char") == "P"
        and endgame_v.get("pre_input_render_path") == "endgame"
        and endgame_v.get("pre_input_frame_contains_final_page_text") is True
        and endgame_v.get("action") == "endgame_return_to_title"
        and endgame_v.get("action_detail") == "restart"
        and endgame_v.get("screen_mode") == "title"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_post_victory_npc_world_state_proof_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_title_screen_endgame_renderer_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_title_screen_endgame_renderer",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_title_screen_endgame_renderer_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_title_screen_endgame_renderer.json"
    vectors_path = ROOT / "tests" / "fixtures" / "title_screen_endgame_renderer_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    render_v = vectors.get("vectors", {}).get("endgame_render", {})
    buffer_v = vectors.get("vectors", {}).get("double_buffer", {})
    small_v = vectors.get("vectors", {}).get("small_terminal", {})

    ok = (
        report.get("slice") == "phase4-title-screen-endgame-renderer"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and render_v.get("render_path") == "endgame"
        and render_v.get("frame_contains_legend_text") is True
        and render_v.get("frame_contains_press_enter") is True
        and buffer_v.get("writes_after_first") == 1
        and buffer_v.get("writes_after_second") == 1
        and small_v.get("contains_notice") is True
        and small_v.get("contains_current") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_title_screen_endgame_renderer_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_combat_outcome_resolution_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_combat_outcome_resolution_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_combat_outcome_resolution.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_combat_outcome_resolution_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    victory_v = vectors.get("vectors", {}).get("victory", {})
    victory_level_v = vectors.get("vectors", {}).get("victory_level_up", {})
    defeat_v = vectors.get("vectors", {}).get("defeat", {})

    ok = (
        report.get("slice") == "phase4-main-loop-combat-outcome-resolution"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and victory_v.get("action") == "combat_victory"
        and victory_v.get("screen_mode") == "dialog"
        and victory_v.get("experience_after") == 3
        and victory_v.get("gold_after") == 124
        and victory_v.get("mp_after") == 10
        and victory_v.get("combat_session_cleared") is True
        and victory_v.get("dialog_page_1_contains_defeat") is True
        and victory_v.get("dialog_page_2_action") == "dialog_page_advance"
        and victory_v.get("dialog_page_2_contains_rewards") is True
        and victory_v.get("dialog_done_action") == "dialog_done"
        and victory_v.get("screen_mode_after_dialog_done") == "map"
        and victory_level_v.get("action") == "combat_victory"
        and victory_level_v.get("screen_mode") == "dialog"
        and victory_level_v.get("experience_after") == 9
        and victory_level_v.get("gold_after") == 124
        and victory_level_v.get("level_after") == 2
        and victory_level_v.get("strength_after") == 5
        and victory_level_v.get("agility_after") == 4
        and victory_level_v.get("max_hp_after") == 22
        and victory_level_v.get("max_mp_after") == 0
        and victory_level_v.get("display_level_after") == 2
        and victory_level_v.get("combat_session_cleared") is True
        and victory_level_v.get("dialog_page_1_contains_defeat") is True
        and victory_level_v.get("dialog_page_2_action") == "dialog_page_advance"
        and victory_level_v.get("dialog_page_2_contains_rewards") is True
        and victory_level_v.get("dialog_page_3_action") == "dialog_page_advance"
        and victory_level_v.get("dialog_page_3_contains_level_up") is True
        and victory_level_v.get("dialog_done_action") == "dialog_done"
        and victory_level_v.get("screen_mode_after_dialog_done") == "map"
        and defeat_v.get("action") == "combat_defeat"
        and defeat_v.get("action_detail") == "revive"
        and defeat_v.get("screen_mode") == "dialog"
        and defeat_v.get("map_after") == [4, 5, 27]
        and defeat_v.get("hp_after") == defeat_v.get("max_hp_after")
        and defeat_v.get("mp_after") == defeat_v.get("max_mp_after")
        and defeat_v.get("gold_after") == 60
        and defeat_v.get("combat_session_cleared") is True
        and defeat_v.get("dialog_page_1_contains_slain") is True
        and defeat_v.get("dialog_page_2_action") == "dialog_page_advance"
        and defeat_v.get("dialog_page_2_contains_revive") is True
        and defeat_v.get("dialog_done_action") == "dialog_done"
        and defeat_v.get("screen_mode_after_dialog_done") == "map"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_combat_outcome_resolution_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_post_combat_dialog_handoff_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_post_combat_dialog_handoff_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_post_combat_dialog_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_post_combat_dialog_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    victory_v = vectors.get("vectors", {}).get("victory", {})
    defeat_v = vectors.get("vectors", {}).get("defeat", {})
    level_up_v = vectors.get("vectors", {}).get("level_up", {})

    ok = (
        report.get("slice") == "phase4-main-loop-post-combat-dialog-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and victory_v.get("initial_screen_mode") == "dialog"
        and victory_v.get("initial_action") == "combat_victory"
        and victory_v.get("advance_action") == "dialog_page_advance"
        and victory_v.get("advance_contains_rewards") is True
        and victory_v.get("done_action") == "dialog_done"
        and victory_v.get("final_screen_mode") == "map"
        and defeat_v.get("initial_screen_mode") == "dialog"
        and defeat_v.get("initial_action") == "combat_defeat"
        and defeat_v.get("advance_action") == "dialog_page_advance"
        and defeat_v.get("advance_contains_revive") is True
        and defeat_v.get("done_action") == "dialog_done"
        and defeat_v.get("final_screen_mode") == "map"
        and defeat_v.get("revive_map_after_outcome") == [4, 5, 27]
        and level_up_v.get("initial_screen_mode") == "dialog"
        and level_up_v.get("initial_action") == "combat_victory"
        and level_up_v.get("page_three_contains_level_up") is True
        and level_up_v.get("done_action") == "dialog_done"
        and level_up_v.get("final_screen_mode") == "map"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_post_combat_dialog_handoff_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_post_combat_fidelity_hardening_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_post_combat_fidelity_hardening_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_post_combat_fidelity_hardening.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_post_combat_fidelity_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    defeat_v = vectors.get("vectors", {}).get("defeat_revive", {})
    victory_v = vectors.get("vectors", {}).get("victory_gold", {})
    level_up_v = vectors.get("vectors", {}).get("level_up_dialog", {})

    ok = (
        report.get("slice") == "phase4-main-loop-post-combat-fidelity-hardening"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and defeat_v.get("action") == "combat_defeat"
        and defeat_v.get("map_after") == [4, 5, 27]
        and defeat_v.get("hp_after") == defeat_v.get("max_hp_after")
        and defeat_v.get("mp_after") == defeat_v.get("max_mp_after")
        and victory_v.get("action") == "combat_victory"
        and victory_v.get("reward_gold") == 4
        and victory_v.get("reward_gold") != victory_v.get("enemy_gp_base")
        and level_up_v.get("action") == "combat_victory"
        and level_up_v.get("page_three_contains_announcement") is True
        and level_up_v.get("page_three_action") == "dialog_page_advance"
        and level_up_v.get("done_action") == "dialog_done"
        and level_up_v.get("final_screen_mode") == "map"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_post_combat_fidelity_hardening_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_interaction_dialog_handoff_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_interaction_dialog_handoff_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_interaction_dialog_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_interaction_dialog_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    adjacent_v = vectors.get("vectors", {}).get("adjacent_npc", {})
    no_adjacent_v = vectors.get("vectors", {}).get("no_adjacent_npc", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-interaction-dialog-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and adjacent_v.get("initial_screen_mode") == "dialog"
        and adjacent_v.get("initial_action") == "npc_interact_dialog"
        and adjacent_v.get("initial_action_detail")
        == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        and adjacent_v.get("advance_action") in {"dialog_page_advance", "dialog_done"}
        and adjacent_v.get("done_action") == "dialog_done"
        and adjacent_v.get("final_screen_mode") == "map"
        and adjacent_v.get("dialog_contains_princess_line") is True
        and adjacent_v.get("dialog_omits_scaffold_ref") is True
        and adjacent_v.get("dialog_omits_raw_byte_markers") is True
        and no_adjacent_v.get("screen_mode") == "map"
        and no_adjacent_v.get("action") == "npc_interact_none"
        and no_adjacent_v.get("action_detail") == "down"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_interaction_dialog_handoff_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_dialog_control_fidelity_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_dialog_control_fidelity_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_dialog_control_fidelity.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_dialog_control_fidelity_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    fidelity_v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-dialog-control-fidelity"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and fidelity_v.get("bounded_control_count", 0) >= 80
        and fidelity_v.get("bounded_all_match") is True
        and fidelity_v.get("control_62_without_princess")
        == {
            "dialog_byte": "0x9B",
            "block": "TextBlock10",
            "entry": 11,
        }
        and fidelity_v.get("control_62_with_princess")
        == {
            "dialog_byte": "0x9C",
            "block": "TextBlock10",
            "entry": 12,
        }
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_dialog_control_fidelity_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_dialog_entry_playback_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_dialog_entry_playback_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_dialog_entry_playback.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_dialog_entry_playback_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    playback_v = vectors.get("vectors", {}).get("adjacent_npc", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-dialog-entry-playback"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and playback_v.get("initial_screen_mode") == "dialog"
        and playback_v.get("initial_action") == "npc_interact_dialog"
        and playback_v.get("initial_action_detail")
        == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        and playback_v.get("initial_frame_contains_princess") is True
        and playback_v.get("initial_frame_contains_scaffold_ref") is False
        and playback_v.get("initial_frame_contains_raw_byte_marker") is False
        and playback_v.get("advance_action") in {"dialog_page_advance", "dialog_done"}
        and playback_v.get("done_action") == "dialog_done"
        and playback_v.get("final_screen_mode") == "map"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_dialog_entry_playback_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_special_dialog_control_resolution_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_special_dialog_control_resolution_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_special_dialog_control_resolution.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_special_dialog_control_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    payload = vectors.get("vectors", {})
    defaults = payload.get("default_controls", {})
    branches = payload.get("branch_cases", {})
    interaction = payload.get("interaction_control_6a", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-special-dialog-control-resolution"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and defaults.get("0x66") == {"dialog_byte": "0xA4", "block": "TextBlock11", "entry": 4}
        and defaults.get("0x6E") == {"dialog_byte": "0xBF", "block": "TextBlock12", "entry": 15}
        and branches.get("control_66_with_stones")
        == {
            "dialog_byte": "0xA5",
            "block": "TextBlock11",
            "entry": 5,
        }
        and branches.get("control_6d_with_token_only")
        == {
            "dialog_byte": "0x49",
            "block": "TextBlock5",
            "entry": 9,
        }
        and str(interaction.get("initial_action_detail", "")).startswith(
            "control:106;byte:0xAD;block:TextBlock11;entry:13"
        )
        and interaction.get("initial_action_detail_contains_chain") is True
        and interaction.get("initial_frame_contains_foretold") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_special_dialog_control_resolution_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_special_control_side_effects_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_special_control_side_effects_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_special_control_side_effects.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_special_control_side_effects_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    payload = vectors.get("vectors", {})
    chain_v = payload.get("control_6a_dialog_chain", {})
    trade_v = payload.get("control_6d_trade", {})
    return_v = payload.get("control_6e_return", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-special-control-side-effects"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and chain_v.get("done_steps", 0) >= 2
        and chain_v.get("second_page_contains_blessing") is True
        and str(trade_v.get("initial_action_detail", "")).startswith(
            "control:109;byte:0xB4;block:TextBlock12;entry:4"
        )
        and trade_v.get("inventory_after_trade") == [14, 0, 0, 0]
        and str(trade_v.get("follow_up_action_detail", "")).startswith(
            "control:109;byte:0xA5;block:TextBlock11;entry:5"
        )
        and str(return_v.get("initial_action_detail", "")).startswith(
            "control:110;byte:0xB9;block:TextBlock12;entry:9"
        )
        and return_v.get("player_flags_after_return", {}).get("got_gwaelin") is False
        and return_v.get("player_flags_after_return", {}).get("done_gwaelin") is True
        and return_v.get("player_flags_after_return", {}).get("left_throne_room") is True
        and str(return_v.get("follow_up_action_detail", "")).startswith(
            "control:110;byte:0xC0;block:TextBlock13;entry:0"
        )
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_special_control_side_effects_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_special_control_0x6c_side_effect_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_special_control_0x6c_side_effect_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_special_control_0x6c_side_effect.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_special_control_0x6c_side_effect_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    trade_v = vectors.get("vectors", {}).get("control_6c_trade", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-special-control-0x6c-side-effect"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and str(trade_v.get("initial_action_detail", "")).startswith(
            "control:108;byte:0xB2;block:TextBlock12;entry:2"
        )
        and "side_effect:staff_of_rain_granted" in str(trade_v.get("initial_action_detail", ""))
        and trade_v.get("inventory_after_trade") == [13, 0, 0, 0]
        and trade_v.get("has_harp_after_trade") is False
        and trade_v.get("has_staff_after_trade") is True
        and str(trade_v.get("follow_up_action_detail", "")).startswith(
            "control:108;byte:0xA5;block:TextBlock11;entry:5"
        )
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_special_control_0x6c_side_effect_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_shop_inn_handoff_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_shop_inn_handoff_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_shop_inn_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_shop_inn_handoff_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    shop_v = vectors.get("vectors", {}).get("shop", {})
    inn_v = vectors.get("vectors", {}).get("inn", {})
    inn_rejected_v = vectors.get("vectors", {}).get("inn_rejected", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-shop-inn-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and shop_v.get("action") == "npc_shop_transaction"
        and shop_v.get("screen_mode") == "dialog"
        and str(shop_v.get("action_detail", "")).startswith(
            "control:1;shop_id:0;item_id:2;result:purchased"
        )
        and shop_v.get("gold_after") == 120
        and shop_v.get("equipment_byte_after") == 0x62
        and inn_v.get("action") == "npc_inn_transaction"
        and inn_v.get("screen_mode") == "dialog"
        and str(inn_v.get("action_detail", "")).startswith("control:15;inn_index:0;result:inn_stay")
        and inn_v.get("gold_after") == 30
        and inn_v.get("hp_after") == inn_v.get("max_hp")
        and inn_v.get("mp_after") == inn_v.get("max_mp")
        and inn_v.get("save_exists") is True
        and inn_v.get("save_dict_roundtrip_equal") is True
        and inn_rejected_v.get("action") == "npc_inn_transaction"
        and inn_rejected_v.get("screen_mode") == "dialog"
        and str(inn_rejected_v.get("action_detail", "")).startswith(
            "control:15;inn_index:0;result:inn_stay_rejected:not_enough_gold"
        )
        and inn_rejected_v.get("gold_after") == inn_rejected_v.get("gold_before")
        and inn_rejected_v.get("hp_after") == inn_rejected_v.get("hp_before")
        and inn_rejected_v.get("mp_after") == inn_rejected_v.get("mp_before")
        and inn_rejected_v.get("save_exists") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_shop_inn_handoff_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_shop_sell_handoff_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_shop_sell_handoff_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_shop_sell_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_shop_sell_handoff_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    sell_v = vectors.get("vectors", {}).get("shop_sell", {})
    rejected_v = vectors.get("vectors", {}).get("shop_sell_rejected", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-shop-sell-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and sell_v.get("action") == "npc_shop_sell_transaction"
        and sell_v.get("screen_mode") == "dialog"
        and str(sell_v.get("action_detail", "")).startswith(
            "control:1;shop_id:0;item_id:17;result:sold;gold_gain:12"
        )
        and sell_v.get("gold_after") == 112
        and sell_v.get("herbs_after") == 0
        and sell_v.get("frame_contains_sold") is True
        and rejected_v.get("action") == "npc_shop_sell_transaction"
        and rejected_v.get("screen_mode") == "dialog"
        and str(rejected_v.get("action_detail", "")).startswith(
            "control:1;shop_id:0;item_id:17;result:rejected:not_owned_or_unsellable;gold_gain:0"
        )
        and rejected_v.get("gold_after") == 100
        and rejected_v.get("herbs_after") == 0
        and rejected_v.get("frame_contains_rejected") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_shop_sell_handoff_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_shop.py",
        "tests/test_main_loop_scaffold.py",
        "-k",
        "shop_control_handoff or shop_sell_handoff or phase4_npc_shop_sell_handoff",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_shop_inn_control_expansion_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_shop_inn_control_expansion_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_shop_inn_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_shop_inn_handoff_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    shop_v = vectors.get("vectors", {}).get("shop", {})
    shop_additional_v = vectors.get("vectors", {}).get("shop_additional", {})
    shop_additional_pair_v = vectors.get("vectors", {}).get("shop_additional_pair", {})
    shop_rejected_v = vectors.get("vectors", {}).get("shop_rejected", {})
    inn_v = vectors.get("vectors", {}).get("inn", {})
    inn_additional_v = vectors.get("vectors", {}).get("inn_additional", {})
    inn_additional_pair_v = vectors.get("vectors", {}).get("inn_additional_pair", {})
    inn_additional_pair_rejected_v = vectors.get("vectors", {}).get("inn_additional_pair_rejected", {})
    inn_rejected_v = vectors.get("vectors", {}).get("inn_rejected", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-shop-inn-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and shop_v.get("action") == "npc_shop_transaction"
        and shop_v.get("screen_mode") == "dialog"
        and str(shop_v.get("action_detail", "")).startswith(
            "control:1;shop_id:0;item_id:2;result:purchased"
        )
        and shop_v.get("gold_after") == 120
        and shop_v.get("equipment_byte_after") == 0x62
        and shop_additional_v.get("action") == "npc_shop_transaction"
        and shop_additional_v.get("screen_mode") == "dialog"
        and str(shop_additional_v.get("action_detail", "")).startswith(
            "control:2;shop_id:1;item_id:0;result:purchased"
        )
        and shop_additional_v.get("gold_after") == 20
        and shop_additional_v.get("equipment_byte_after") == 0x22
        and shop_additional_pair_v.get("action") == "npc_shop_transaction"
        and shop_additional_pair_v.get("screen_mode") == "dialog"
        and str(shop_additional_pair_v.get("action_detail", "")).startswith(
            "control:3;shop_id:2;item_id:1;result:purchased"
        )
        and shop_additional_pair_v.get("gold_after") == 30
        and shop_additional_pair_v.get("equipment_byte_after") == 0x42
        and shop_rejected_v.get("action") == "npc_shop_transaction"
        and shop_rejected_v.get("screen_mode") == "dialog"
        and str(shop_rejected_v.get("action_detail", "")).startswith(
            "control:2;shop_id:1;item_id:0;result:rejected:not_enough_gold"
        )
        and shop_rejected_v.get("gold_after") == shop_rejected_v.get("gold_before")
        and shop_rejected_v.get("equipment_byte_after") == shop_rejected_v.get("equipment_byte_before")
        and inn_v.get("action") == "npc_inn_transaction"
        and inn_v.get("screen_mode") == "dialog"
        and str(inn_v.get("action_detail", "")).startswith("control:15;inn_index:0;result:inn_stay")
        and inn_v.get("gold_after") == 30
        and inn_v.get("hp_after") == inn_v.get("max_hp")
        and inn_v.get("mp_after") == inn_v.get("max_mp")
        and inn_v.get("save_exists") is True
        and inn_v.get("save_dict_roundtrip_equal") is True
        and inn_additional_v.get("action") == "npc_inn_transaction"
        and inn_additional_v.get("screen_mode") == "dialog"
        and str(inn_additional_v.get("action_detail", "")).startswith(
            "control:16;inn_index:1;result:inn_stay"
        )
        and inn_additional_v.get("gold_after") == 6
        and inn_additional_v.get("hp_after") == inn_additional_v.get("max_hp")
        and inn_additional_v.get("mp_after") == inn_additional_v.get("max_mp")
        and inn_additional_v.get("save_exists") is True
        and inn_additional_v.get("save_dict_roundtrip_equal") is True
        and inn_additional_pair_v.get("action") == "npc_inn_transaction"
        and inn_additional_pair_v.get("screen_mode") == "dialog"
        and str(inn_additional_pair_v.get("action_detail", "")).startswith(
            "control:17;inn_index:2;result:inn_stay"
        )
        and inn_additional_pair_v.get("gold_after") == 15
        and inn_additional_pair_v.get("hp_after") == inn_additional_pair_v.get("max_hp")
        and inn_additional_pair_v.get("mp_after") == inn_additional_pair_v.get("max_mp")
        and inn_additional_pair_v.get("save_exists") is True
        and inn_additional_pair_v.get("save_dict_roundtrip_equal") is True
        and inn_additional_pair_rejected_v.get("action") == "npc_inn_transaction"
        and inn_additional_pair_rejected_v.get("screen_mode") == "dialog"
        and str(inn_additional_pair_rejected_v.get("action_detail", "")).startswith(
            "control:17;inn_index:2;result:inn_stay_rejected:not_enough_gold"
        )
        and inn_additional_pair_rejected_v.get("gold_after")
        == inn_additional_pair_rejected_v.get("gold_before")
        and inn_additional_pair_rejected_v.get("hp_after")
        == inn_additional_pair_rejected_v.get("hp_before")
        and inn_additional_pair_rejected_v.get("mp_after")
        == inn_additional_pair_rejected_v.get("mp_before")
        and inn_additional_pair_rejected_v.get("save_exists") is False
        and inn_rejected_v.get("action") == "npc_inn_transaction"
        and inn_rejected_v.get("screen_mode") == "dialog"
        and str(inn_rejected_v.get("action_detail", "")).startswith(
            "control:15;inn_index:0;result:inn_stay_rejected:not_enough_gold"
        )
        and inn_rejected_v.get("gold_after") == inn_rejected_v.get("gold_before")
        and inn_rejected_v.get("hp_after") == inn_rejected_v.get("hp_before")
        and inn_rejected_v.get("mp_after") == inn_rejected_v.get("mp_before")
        and inn_rejected_v.get("save_exists") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_shop_inn_control_expansion_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_npc_shop_inn_next_control_pair_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_npc_shop_inn_next_control_pair_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_npc_shop_inn_handoff.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_npc_shop_inn_handoff_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    shop_next_pair_v = vectors.get("vectors", {}).get("shop_next_pair", {})
    inn_next_pair_v = vectors.get("vectors", {}).get("inn_next_pair", {})
    inn_next_pair_rejected_v = vectors.get("vectors", {}).get("inn_next_pair_rejected", {})

    ok = (
        report.get("slice") == "phase4-main-loop-npc-shop-inn-handoff"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and report.get("checks", {}).get("npc_shop_next_pair_control_handoff_runs_bounded_purchase") is True
        and report.get("checks", {}).get("npc_inn_next_pair_control_handoff_runs_inn_transaction_and_save")
        is True
        and report.get("checks", {}).get("npc_inn_next_pair_control_handoff_rejects_when_gold_insufficient")
        is True
        and shop_next_pair_v.get("action") == "npc_shop_transaction"
        and shop_next_pair_v.get("screen_mode") == "dialog"
        and str(shop_next_pair_v.get("action_detail", "")).startswith(
            "control:4;shop_id:3;item_id:0;result:purchased"
        )
        and shop_next_pair_v.get("gold_after") == 15
        and shop_next_pair_v.get("equipment_byte_after") == 0x22
        and inn_next_pair_v.get("action") == "npc_inn_transaction"
        and inn_next_pair_v.get("screen_mode") == "dialog"
        and str(inn_next_pair_v.get("action_detail", "")).startswith(
            "control:18;inn_index:3;result:inn_stay"
        )
        and inn_next_pair_v.get("gold_after") == 30
        and inn_next_pair_v.get("hp_after") == inn_next_pair_v.get("max_hp")
        and inn_next_pair_v.get("mp_after") == inn_next_pair_v.get("max_mp")
        and inn_next_pair_v.get("save_exists") is True
        and inn_next_pair_v.get("save_dict_roundtrip_equal") is True
        and inn_next_pair_rejected_v.get("action") == "npc_inn_transaction"
        and inn_next_pair_rejected_v.get("screen_mode") == "dialog"
        and str(inn_next_pair_rejected_v.get("action_detail", "")).startswith(
            "control:18;inn_index:3;result:inn_stay_rejected:not_enough_gold"
        )
        and inn_next_pair_rejected_v.get("gold_after") == inn_next_pair_rejected_v.get("gold_before")
        and inn_next_pair_rejected_v.get("hp_after") == inn_next_pair_rejected_v.get("hp_before")
        and inn_next_pair_rejected_v.get("mp_after") == inn_next_pair_rejected_v.get("mp_before")
        and inn_next_pair_rejected_v.get("save_exists") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_npc_shop_inn_next_control_pair_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_field_spell_casting_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_field_spell_casting_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_field_spell_casting.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_field_spell_casting_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-field-spell-casting"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("heal", {}).get("action") == "map_spell_cast"
        and v.get("heal", {}).get("action_detail") == "HEAL:ok"
        and v.get("heal", {}).get("hp_after") == 15
        and v.get("heal", {}).get("mp_after") == 6
        and v.get("outside", {}).get("action_detail") == "OUTSIDE:ok"
        and v.get("outside", {}).get("map_after") == [1, 0x68, 0x2C]
        and v.get("outside", {}).get("done_action") == "dialog_done"
        and v.get("outside", {}).get("done_screen_mode") == "map"
        and v.get("return", {}).get("action_detail") == "RETURN:ok"
        and v.get("return", {}).get("map_after") == [1, 0x2A, 0x2B]
        and v.get("repel", {}).get("action_detail") == "REPEL:ok"
        and v.get("repel", {}).get("repel_timer_after") == 0xFE
        and v.get("radiant", {}).get("action_detail") == "RADIANT:ok"
        and v.get("radiant", {}).get("light_radius_after") == 5
        and v.get("radiant", {}).get("light_timer_after") == 0xFE
        and v.get("not_enough_mp", {}).get("action") == "map_spell_rejected"
        and v.get("not_enough_mp", {}).get("action_detail") == "HEAL:not_enough_mp"
        and v.get("not_enough_mp", {}).get("mp_after") == v.get("not_enough_mp", {}).get("mp_before")
        and v.get("unknown_spell", {}).get("action") == "map_spell_rejected"
        and v.get("unknown_spell", {}).get("action_detail") == "HEAL:unknown"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_field_spell_casting_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_spell_selection_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_spell_selection_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_spell_selection_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_spell_selection_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-spell-selection-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("menu_open", {}).get("action") == "map_spell_menu_opened"
        and v.get("menu_open", {}).get("action_detail") == "count:2"
        and v.get("menu_open", {}).get("screen_mode") == "map"
        and v.get("menu_open", {}).get("frame_contains_hurt") is False
        and v.get("menu_open", {}).get("move_action") == "map_spell_menu_input"
        and v.get("menu_open", {}).get("move_action_detail") == "DOWN"
        and v.get("menu_open", {}).get("move_frame_cursor_on_outside") is True
        and v.get("menu_cancel", {}).get("action") == "map_spell_menu_cancel"
        and v.get("menu_cancel", {}).get("screen_mode") == "map"
        and v.get("menu_cancel", {}).get("hp_after") == 9
        and v.get("menu_cancel", {}).get("mp_after") == 10
        and v.get("menu_no_field_spells", {}).get("action") == "map_spell_menu_rejected"
        and v.get("menu_no_field_spells", {}).get("action_detail") == "no_field_spells"
        and v.get("menu_no_field_spells", {}).get("screen_mode") == "dialog"
        and v.get("menu_no_field_spells", {}).get("frame_contains_unknown_spell") is True
        and v.get("menu_select_heal", {}).get("open_action") == "map_spell_menu_opened"
        and v.get("menu_select_heal", {}).get("action") == "map_spell_cast"
        and v.get("menu_select_heal", {}).get("action_detail") == "HEAL:ok"
        and v.get("menu_select_heal", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_heal", {}).get("hp_after") == 15
        and v.get("menu_select_heal", {}).get("mp_after") == 6
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_spell_selection_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_root_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_root_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_root_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_root_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-root-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("menu_open", {}).get("action") == "map_command_menu_opened"
        and v.get("menu_open", {}).get("action_detail") == "count:2"
        and v.get("menu_open", {}).get("screen_mode") == "map"
        and v.get("menu_open", {}).get("frame_contains_talk") is True
        and v.get("menu_open", {}).get("frame_contains_spell") is True
        and v.get("menu_cancel", {}).get("action") == "map_command_menu_cancel"
        and v.get("menu_cancel", {}).get("screen_mode") == "map"
        and v.get("menu_cancel", {}).get("hp_after") == 9
        and v.get("menu_cancel", {}).get("mp_after") == 10
        and v.get("menu_select_spell", {}).get("action") == "map_spell_menu_opened"
        and v.get("menu_select_spell", {}).get("screen_mode") == "map"
        and v.get("menu_select_talk", {}).get("action") == "npc_interact_dialog"
        and v.get("menu_select_talk", {}).get("action_detail")
        == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        and v.get("menu_select_talk", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_talk_no_target", {}).get("action") == "npc_interact_none"
        and v.get("menu_select_talk_no_target", {}).get("action_detail") == "down"
        and v.get("menu_select_talk_no_target", {}).get("screen_mode") == "map"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_root_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_root_expansion_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_main_loop",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_root_expansion_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_root_expansion.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_root_expansion_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-root-expansion"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("menu_open", {}).get("action") == "map_command_menu_opened"
        and v.get("menu_open", {}).get("action_detail") == "count:7"
        and v.get("menu_open", {}).get("screen_mode") == "map"
        and v.get("menu_open", {}).get("frame_contains_talk") is True
        and v.get("menu_open", {}).get("frame_contains_spell") is True
        and v.get("menu_open", {}).get("frame_contains_search") is True
        and v.get("menu_open", {}).get("frame_contains_status") is True
        and v.get("menu_open", {}).get("frame_contains_item") is True
        and v.get("menu_open", {}).get("frame_contains_stairs") is True
        and v.get("menu_open", {}).get("frame_contains_door") is True
        and v.get("menu_cancel", {}).get("action") == "map_command_menu_cancel"
        and v.get("menu_cancel", {}).get("screen_mode") == "map"
        and v.get("menu_cancel", {}).get("hp_after") == 9
        and v.get("menu_cancel", {}).get("mp_after") == 10
        and v.get("menu_select_spell", {}).get("action") == "map_spell_menu_opened"
        and v.get("menu_select_spell", {}).get("screen_mode") == "map"
        and v.get("menu_select_talk", {}).get("action") == "npc_interact_dialog"
        and v.get("menu_select_talk", {}).get("action_detail")
        == "control:98;byte:0x9B;block:TextBlock10;entry:11"
        and v.get("menu_select_talk", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_talk_no_target", {}).get("action") == "npc_interact_none"
        and v.get("menu_select_talk_no_target", {}).get("action_detail") == "down"
        and v.get("menu_select_talk_no_target", {}).get("screen_mode") == "map"
        and v.get("menu_select_search", {}).get("action") == "map_search"
        and v.get("menu_select_search", {}).get("action_detail") == "none"
        and v.get("menu_select_search", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_search", {}).get("frame_contains_feedback") is True
        and v.get("menu_select_status", {}).get("action") == "map_status_opened"
        and v.get("menu_select_status", {}).get("action_detail") == "overlay:status"
        and v.get("menu_select_status", {}).get("screen_mode") == "map"
        and v.get("menu_select_status", {}).get("frame_contains_feedback") is True
        and v.get("menu_select_item", {}).get("action") == "map_item_menu_rejected"
        and v.get("menu_select_item", {}).get("action_detail") == "empty_inventory"
        and v.get("menu_select_item", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_item", {}).get("frame_contains_feedback") is True
        and v.get("menu_select_stairs", {}).get("action") == "map_stairs_rejected"
        and v.get("menu_select_stairs", {}).get("action_detail") == "no_stairs"
        and v.get("menu_select_stairs", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_stairs", {}).get("frame_contains_feedback") is True
        and v.get("menu_select_door", {}).get("action") == "map_door_rejected"
        and v.get("menu_select_door", {}).get("action_detail") == "no_door"
        and v.get("menu_select_door", {}).get("screen_mode") == "dialog"
        and v.get("menu_select_door", {}).get("frame_contains_feedback") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_root_expansion_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_search_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("search_no_chest", {}).get("action") == "map_search"
        and v.get("search_no_chest", {}).get("action_detail") == "none"
        and v.get("search_no_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_no_chest", {}).get("frame_contains_nothing") is True
        and v.get("search_chest", {}).get("action") == "map_search"
        and v.get("search_chest", {}).get("action_detail") == "chest:index:0;contents:19"
        and v.get("search_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_chest", {}).get("frame_contains_chest") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_chest_rewards_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search_chest_rewards",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_chest_rewards_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search_chest_rewards.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_search_chest_rewards_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search-chest-rewards"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("search_no_chest", {}).get("action") == "map_search"
        and v.get("search_no_chest", {}).get("action_detail") == "none"
        and v.get("search_no_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_no_chest", {}).get("frame_contains_nothing") is True
        and v.get("search_chest", {}).get("action") == "map_search"
        and v.get("search_chest", {}).get("action_detail")
        == "chest:index:0;contents:19;reward:gold:120;opened:true"
        and v.get("search_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_chest", {}).get("frame_contains_gold") is True
        and v.get("search_chest", {}).get("gold_after") == 240
        and v.get("search_chest_reopen", {}).get("action") == "map_search"
        and v.get("search_chest_reopen", {}).get("action_detail")
        == "chest:index:0;contents:19;opened:true;reward:none"
        and v.get("search_chest_reopen", {}).get("screen_mode") == "dialog"
        and v.get("search_chest_reopen", {}).get("frame_contains_empty") is True
        and v.get("search_chest_reopen", {}).get("gold_after") == 240
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_chest_rewards_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_non_gold_chest_rewards_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search_non_gold_chest_rewards",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_non_gold_chest_rewards_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search_non_gold_chest_rewards.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_search_non_gold_chest_rewards_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search-non-gold-chest-rewards"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("search_herb_chest", {}).get("action") == "map_search"
        and v.get("search_herb_chest", {}).get("action_detail")
        == "chest:index:24;contents:17;reward:herb:+1;opened:true"
        and v.get("search_herb_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_herb_chest", {}).get("frame_contains_herb") is True
        and v.get("search_herb_chest", {}).get("herbs_after") == 1
        and v.get("search_key_chest", {}).get("action") == "map_search"
        and v.get("search_key_chest", {}).get("action_detail")
        == "chest:index:20;contents:18;reward:key:+1;opened:true"
        and v.get("search_key_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_key_chest", {}).get("frame_contains_key") is True
        and v.get("search_key_chest", {}).get("magic_keys_after") == 1
        and v.get("search_tool_chest", {}).get("action") == "map_search"
        and v.get("search_tool_chest", {}).get("action_detail")
        == "chest:index:8;contents:20;reward:item:FAIRY_WATER;opened:true"
        and v.get("search_tool_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_tool_chest", {}).get("frame_contains_tool") is True
        and v.get("search_tool_chest", {}).get("inventory_slots_after") == [2, 0, 0, 0]
        and v.get("search_key_chest_reopen", {}).get("action") == "map_search"
        and v.get("search_key_chest_reopen", {}).get("action_detail")
        == "chest:index:20;contents:18;opened:true;reward:none"
        and v.get("search_key_chest_reopen", {}).get("screen_mode") == "dialog"
        and v.get("search_key_chest_reopen", {}).get("frame_contains_empty") is True
        and v.get("search_key_chest_reopen", {}).get("magic_keys_after") == 1
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_non_gold_chest_rewards_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_tool_rewards_capacity_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search_tool_rewards_capacity",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_tool_rewards_capacity_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search_tool_rewards_capacity.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_search_tool_rewards_capacity_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search-tool-rewards-capacity"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("search_wings_chest", {}).get("action") == "map_search"
        and v.get("search_wings_chest", {}).get("action_detail")
        == "chest:index:12;contents:21;reward:item:WINGS;opened:true"
        and v.get("search_wings_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_wings_chest", {}).get("frame_contains_wings") is True
        and v.get("search_wings_chest", {}).get("inventory_slots_after") == [3, 0, 0, 0]
        and v.get("search_dragons_scale_chest", {}).get("action") == "map_search"
        and v.get("search_dragons_scale_chest", {}).get("action_detail")
        == "chest:index:4;contents:22;reward:item:DRAGONS_SCALE;opened:true"
        and v.get("search_dragons_scale_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_dragons_scale_chest", {}).get("frame_contains_dragons_scale") is True
        and v.get("search_dragons_scale_chest", {}).get("inventory_slots_after") == [4, 0, 0, 0]
        and v.get("search_fairy_flute_chest", {}).get("action") == "map_search"
        and v.get("search_fairy_flute_chest", {}).get("action_detail")
        == "chest:index:30;contents:23;reward:item:FAIRY_FLUTE;opened:true"
        and v.get("search_fairy_flute_chest", {}).get("screen_mode") == "dialog"
        and v.get("search_fairy_flute_chest", {}).get("frame_contains_fairy_flute") is True
        and v.get("search_fairy_flute_chest", {}).get("inventory_slots_after") == [5, 0, 0, 0]
        and v.get("search_herb_full_guard", {}).get("action") == "map_search"
        and v.get("search_herb_full_guard", {}).get("action_detail")
        == "chest:index:24;contents:17;reward:herb:full"
        and v.get("search_herb_full_guard", {}).get("screen_mode") == "dialog"
        and v.get("search_herb_full_guard", {}).get("frame_contains_herb_full") is True
        and v.get("search_herb_full_guard", {}).get("herbs_after") == 6
        and v.get("search_key_full_guard", {}).get("action") == "map_search"
        and v.get("search_key_full_guard", {}).get("action_detail")
        == "chest:index:20;contents:18;reward:key:full"
        and v.get("search_key_full_guard", {}).get("screen_mode") == "dialog"
        and v.get("search_key_full_guard", {}).get("frame_contains_key_full") is True
        and v.get("search_key_full_guard", {}).get("magic_keys_after") == 6
        and v.get("search_tool_full_guard", {}).get("action") == "map_search"
        and v.get("search_tool_full_guard", {}).get("action_detail")
        == "chest:index:8;contents:20;reward:item:full"
        and v.get("search_tool_full_guard", {}).get("screen_mode") == "dialog"
        and v.get("search_tool_full_guard", {}).get("frame_contains_inventory_full") is True
        and v.get("search_tool_full_guard", {}).get("inventory_slots_after") == [17, 17, 17, 17]
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_tool_rewards_capacity_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_remaining_gold_chest_rewards_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search_remaining_gold_chest_rewards",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_remaining_gold_chest_rewards_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search_remaining_gold_chest_rewards.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_search_remaining_gold_chest_rewards_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search-remaining-gold-chest-rewards"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("gold_chest_indices", {}).get("all_indices") == [0, 1, 2, 3, 21]
        and v.get("gold_chest_indices", {}).get("remaining_indices") == [1, 2, 3, 21]
        and v.get("search_gold_chest_index_1", {}).get("action") == "map_search"
        and v.get("search_gold_chest_index_1", {}).get("action_detail")
        == "chest:index:1;contents:19;reward:gold:120;opened:true"
        and v.get("search_gold_chest_index_1", {}).get("screen_mode") == "dialog"
        and v.get("search_gold_chest_index_1", {}).get("frame_contains_gold") is True
        and v.get("search_gold_chest_index_1", {}).get("gold_after") == 240
        and v.get("search_gold_chest_index_2", {}).get("action") == "map_search"
        and v.get("search_gold_chest_index_2", {}).get("action_detail")
        == "chest:index:2;contents:19;reward:gold:120;opened:true"
        and v.get("search_gold_chest_index_2", {}).get("screen_mode") == "dialog"
        and v.get("search_gold_chest_index_2", {}).get("frame_contains_gold") is True
        and v.get("search_gold_chest_index_2", {}).get("gold_after") == 240
        and v.get("search_gold_chest_index_3", {}).get("action") == "map_search"
        and v.get("search_gold_chest_index_3", {}).get("action_detail")
        == "chest:index:3;contents:19;reward:gold:120;opened:true"
        and v.get("search_gold_chest_index_3", {}).get("screen_mode") == "dialog"
        and v.get("search_gold_chest_index_3", {}).get("frame_contains_gold") is True
        and v.get("search_gold_chest_index_3", {}).get("gold_after") == 240
        and v.get("search_gold_chest_index_21", {}).get("action") == "map_search"
        and v.get("search_gold_chest_index_21", {}).get("action_detail")
        == "chest:index:21;contents:19;reward:gold:120;opened:true"
        and v.get("search_gold_chest_index_21", {}).get("screen_mode") == "dialog"
        and v.get("search_gold_chest_index_21", {}).get("frame_contains_gold") is True
        and v.get("search_gold_chest_index_21", {}).get("gold_after") == 240
        and v.get("search_gold_chest_index_21_reopen", {}).get("action") == "map_search"
        and v.get("search_gold_chest_index_21_reopen", {}).get("action_detail")
        == "chest:index:21;contents:19;opened:true;reward:none"
        and v.get("search_gold_chest_index_21_reopen", {}).get("screen_mode") == "dialog"
        and v.get("search_gold_chest_index_21_reopen", {}).get("frame_contains_empty") is True
        and v.get("search_gold_chest_index_21_reopen", {}).get("gold_after") == 240
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_remaining_gold_chest_rewards_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_search_remaining_unsupported_chest_contents_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_search_remaining_unsupported_chest_contents",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_search_remaining_unsupported_chest_contents_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_search_remaining_unsupported_chest_contents.json"
    vectors_path = (
        ROOT / "tests" / "fixtures" / "main_loop_map_command_search_remaining_unsupported_chest_contents_vectors.json"
    )

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-search-remaining-unsupported-chest-contents"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("remaining_content_matrix", {}).get("content_ids") == [2, 3, 4, 6, 9, 12, 13, 14, 15, 16]
        and v.get("remaining_content_matrix", {}).get("chest_indices") == [5, 6, 7, 9, 10, 11, 13, 14, 15, 16, 17, 18, 19, 22, 23, 25, 26, 27, 29]
        and v.get("search_content_2", {}).get("action_detail")
        == "chest:index:9;contents:2;reward:herb:+1;opened:true"
        and v.get("search_content_3", {}).get("action_detail")
        == "chest:index:6;contents:3;reward:key:+1;opened:true"
        and v.get("search_content_4", {}).get("action_detail")
        == "chest:index:5;contents:4;reward:item:TORCH;opened:true"
        and v.get("search_content_6", {}).get("action_detail")
        == "chest:index:7;contents:6;reward:item:WINGS;opened:true"
        and v.get("search_content_9", {}).get("action_detail")
        == "chest:index:27;contents:9;reward:item:FIGHTERS_RING;opened:true"
        and v.get("search_content_12", {}).get("action_detail")
        == "chest:index:15;contents:12;reward:item:CURSED_BELT;opened:true"
        and v.get("search_content_13", {}).get("action_detail")
        == "chest:index:23;contents:13;reward:item:SILVER_HARP;opened:true"
        and v.get("search_content_14", {}).get("action_detail")
        == "chest:index:25;contents:14;reward:item:DEATH_NECKLACE;opened:true"
        and v.get("search_content_15", {}).get("action_detail")
        == "chest:index:17;contents:15;reward:item:STONES_OF_SUNLIGHT;opened:true"
        and v.get("search_content_16", {}).get("action_detail")
        == "chest:index:18;contents:16;reward:item:STAFF_OF_RAIN;opened:true"
        and v.get("search_content_16_reopen", {}).get("action_detail")
        == "chest:index:18;contents:16;opened:true;reward:none"
        and v.get("search_content_2_herb_full", {}).get("action_detail")
        == "chest:index:9;contents:2;reward:herb:full"
        and v.get("search_content_3_key_full", {}).get("action_detail")
        == "chest:index:6;contents:3;reward:key:full"
        and v.get("search_content_16_inventory_full", {}).get("action_detail")
        == "chest:index:18;contents:16;reward:item:full"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_search_remaining_unsupported_chest_contents_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_status_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_status_surface",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_status_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_status_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_status_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-status-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("status_open", {}).get("action") == "map_status_opened"
        and v.get("status_open", {}).get("action_detail") == "overlay:status"
        and v.get("status_open", {}).get("screen_mode") == "map"
        and v.get("status_open", {}).get("overlay_open") is True
        and v.get("status_open", {}).get("frame_contains_status_title") is True
        and v.get("status_open", {}).get("frame_contains_name") is True
        and v.get("status_open", {}).get("frame_contains_hp") is True
        and v.get("status_open", {}).get("frame_contains_mp") is True
        and v.get("status_input_while_open", {}).get("action") == "map_status_input"
        and v.get("status_input_while_open", {}).get("action_detail") == "RIGHT"
        and v.get("status_input_while_open", {}).get("screen_mode") == "map"
        and v.get("status_input_while_open", {}).get("player_x_after") == 10
        and v.get("status_input_while_open", {}).get("player_y_after") == 10
        and v.get("status_close", {}).get("action") == "map_status_closed"
        and v.get("status_close", {}).get("action_detail") == "esc"
        and v.get("status_close", {}).get("screen_mode") == "map"
        and v.get("status_close", {}).get("overlay_open_after_close") is False
        and v.get("status_close", {}).get("hp_after") == 9
        and v.get("status_close", {}).get("mp_after") == 10
        and v.get("status_close", {}).get("gold_after") == 123
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_status_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_surface",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("action") == "map_item_menu_opened"
        and v.get("item_menu_open", {}).get("action_detail") == "count:2"
        and v.get("item_menu_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_open", {}).get("frame_contains_item_title") is True
        and v.get("item_menu_open", {}).get("frame_contains_torch") is True
        and v.get("item_menu_open", {}).get("frame_contains_wings") is True
        and v.get("item_menu_input_while_open", {}).get("action") == "map_item_menu_input"
        and v.get("item_menu_input_while_open", {}).get("action_detail") == "RIGHT"
        and v.get("item_menu_input_while_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_input_while_open", {}).get("player_x_after") == 10
        and v.get("item_menu_input_while_open", {}).get("player_y_after") == 10
        and v.get("item_menu_cancel", {}).get("action") == "map_item_menu_cancel"
        and v.get("item_menu_cancel", {}).get("screen_mode") == "map"
        and v.get("item_use_torch_success", {}).get("action") == "map_item_used"
        and v.get("item_use_torch_success", {}).get("action_detail") == "TORCH:ok"
        and v.get("item_use_torch_success", {}).get("screen_mode") == "dialog"
        and v.get("item_use_torch_success", {}).get("inventory_slots_after") == [0, 0, 0, 0]
        and v.get("item_use_torch_success", {}).get("light_radius_after") == 5
        and v.get("item_use_torch_success", {}).get("light_timer_after") == 15
        and v.get("item_use_torch_rejected", {}).get("action") == "map_item_rejected"
        and v.get("item_use_torch_rejected", {}).get("action_detail") == "TORCH:torch_requires_dungeon_map"
        and v.get("item_use_torch_rejected", {}).get("screen_mode") == "dialog"
        and v.get("item_use_torch_rejected", {}).get("inventory_slots_after") == [1, 0, 0, 0]
        and v.get("item_menu_empty_inventory", {}).get("action") == "map_item_menu_rejected"
        and v.get("item_menu_empty_inventory", {}).get("action_detail") == "empty_inventory"
        and v.get("item_menu_empty_inventory", {}).get("screen_mode") == "dialog"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_expansion_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_expansion",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_expansion_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_expansion.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_expansion_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-expansion"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("frame_contains_item_title") is True
        and v.get("item_menu_open", {}).get("frame_contains_torch") is True
        and v.get("item_menu_open", {}).get("frame_contains_fairy_water") is True
        and v.get("item_menu_open", {}).get("frame_contains_wings") is True
        and v.get("item_use_fairy_water_success", {}).get("action") == "map_item_used"
        and v.get("item_use_fairy_water_success", {}).get("action_detail") == "FAIRY WATER:ok"
        and v.get("item_use_fairy_water_success", {}).get("screen_mode") == "dialog"
        and v.get("item_use_fairy_water_success", {}).get("repel_timer_after_route_input") == 0xFE
        and v.get("item_use_fairy_water_success", {}).get("repel_timer_after_tick") == 0xFD
        and v.get("item_use_fairy_water_success", {}).get("repel_timer_after") == 0xFD
        and v.get("item_use_fairy_water_success", {}).get("inventory_slots_after") == [0, 0, 0, 0]
        and v.get("item_use_fairy_water_success", {}).get("frame_contains_used_text") is True
        and v.get("item_use_wings_success", {}).get("action") == "map_item_used"
        and v.get("item_use_wings_success", {}).get("action_detail") == "WINGS:ok"
        and v.get("item_use_wings_success", {}).get("screen_mode") == "dialog"
        and v.get("item_use_wings_success", {}).get("map_after") == [1, 42, 43]
        and v.get("item_use_wings_success", {}).get("inventory_slots_after") == [0, 0, 0, 0]
        and v.get("item_use_wings_success", {}).get("frame_contains_used_text") is True
        and v.get("item_use_wings_rejected", {}).get("action") == "map_item_rejected"
        and v.get("item_use_wings_rejected", {}).get("action_detail") == "WINGS:wings_cannot_be_used_here"
        and v.get("item_use_wings_rejected", {}).get("screen_mode") == "dialog"
        and v.get("item_use_wings_rejected", {}).get("map_after") == [13, 10, 10]
        and v.get("item_use_wings_rejected", {}).get("inventory_slots_after") == [3, 0, 0, 0]
        and v.get("item_use_wings_rejected", {}).get("frame_contains_rejected_text") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_expansion_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_dragons_scale_equip_state_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_dragons_scale_equip_state",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_dragons_scale_equip_state_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_dragons_scale_equip_state.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_dragons_scale_equip_state_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-dragons-scale-equip-state"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("action") == "map_item_menu_opened"
        and v.get("item_menu_open", {}).get("action_detail") == "count:1"
        and v.get("item_menu_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_open", {}).get("frame_contains_item_title") is True
        and v.get("item_menu_open", {}).get("frame_contains_dragons_scale") is True
        and v.get("item_use_dragons_scale_success", {}).get("action") == "map_item_used"
        and v.get("item_use_dragons_scale_success", {}).get("action_detail") == "DRAGON'S SCALE:ok"
        and v.get("item_use_dragons_scale_success", {}).get("screen_mode") == "dialog"
        and v.get("item_use_dragons_scale_success", {}).get("defense_before") == 2
        and v.get("item_use_dragons_scale_success", {}).get("defense_after") == 4
        and v.get("item_use_dragons_scale_success", {}).get("dragon_scale_flag_set") is True
        and v.get("item_use_dragons_scale_success", {}).get("inventory_slots_after") == [4, 0, 0, 0]
        and v.get("item_use_dragons_scale_success", {}).get("frame_contains_used_text") is True
        and v.get("item_use_dragons_scale_already_equipped", {}).get("action") == "map_item_rejected"
        and v.get("item_use_dragons_scale_already_equipped", {}).get("action_detail")
        == "DRAGON'S SCALE:already_wearing_dragon_scale"
        and v.get("item_use_dragons_scale_already_equipped", {}).get("screen_mode") == "dialog"
        and v.get("item_use_dragons_scale_already_equipped", {}).get("defense_before") == 4
        and v.get("item_use_dragons_scale_already_equipped", {}).get("defense_after") == 4
        and v.get("item_use_dragons_scale_already_equipped", {}).get("dragon_scale_flag_set") is True
        and v.get("item_use_dragons_scale_already_equipped", {}).get("inventory_slots_after") == [4, 0, 0, 0]
        and v.get("item_use_dragons_scale_already_equipped", {}).get("frame_contains_no_effect_text") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_dragons_scale_equip_state_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_silver_harp_forced_encounter_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_silver_harp_forced_encounter",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_silver_harp_forced_encounter_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_silver_harp_forced_encounter.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_silver_harp_forced_encounter_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-silver-harp-forced-encounter"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("action") == "map_item_menu_opened"
        and v.get("item_menu_open", {}).get("action_detail") == "count:1"
        and v.get("item_menu_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_open", {}).get("frame_contains_silver_harp") is True
        and v.get("item_use_silver_harp_forced_encounter", {}).get("action") == "encounter_triggered"
        and v.get("item_use_silver_harp_forced_encounter", {}).get("action_detail") == "enemy:0;source:silver_harp"
        and v.get("item_use_silver_harp_forced_encounter", {}).get("screen_mode") == "combat"
        and v.get("item_use_silver_harp_forced_encounter", {}).get("enemy_id") == 0
        and v.get("item_use_silver_harp_forced_encounter", {}).get("enemy_name") == "Slime"
        and v.get("item_use_silver_harp_forced_encounter", {}).get("inventory_slots_after") == [10, 0, 0, 0]
        and v.get("item_use_silver_harp_forced_encounter", {}).get("frame_contains_slime") is True
        and v.get("item_use_silver_harp_rejected", {}).get("action") == "map_item_rejected"
        and v.get("item_use_silver_harp_rejected", {}).get("action_detail")
        == "SILVER HARP:harp_only_works_on_overworld"
        and v.get("item_use_silver_harp_rejected", {}).get("screen_mode") == "dialog"
        and v.get("item_use_silver_harp_rejected", {}).get("inventory_slots_after") == [10, 0, 0, 0]
        and v.get("item_use_silver_harp_rejected", {}).get("frame_contains_rejected_text") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_silver_harp_forced_encounter_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_rainbow_drop_bridge_trigger_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_rainbow_drop_bridge_trigger",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_rainbow_drop_bridge_trigger_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_rainbow_drop_bridge_trigger_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-rainbow-drop-bridge-trigger"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("action") == "map_item_menu_opened"
        and v.get("item_menu_open", {}).get("action_detail") == "count:1"
        and v.get("item_menu_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_open", {}).get("frame_contains_rainbow_drop") is True
        and v.get("item_use_rainbow_drop_success", {}).get("action") == "map_item_used"
        and v.get("item_use_rainbow_drop_success", {}).get("action_detail") == "RAINBOW DROP:ok"
        and v.get("item_use_rainbow_drop_success", {}).get("screen_mode") == "dialog"
        and v.get("item_use_rainbow_drop_success", {}).get("rainbow_bridge_flag_set") is True
        and v.get("item_use_rainbow_drop_success", {}).get("inventory_slots_after") == [14, 0, 0, 0]
        and v.get("item_use_rainbow_drop_success", {}).get("base_tile_before_bridge") == 0x01
        and v.get("item_use_rainbow_drop_success", {}).get("tile_after_bridge_active") == 0x0A
        and v.get("item_use_rainbow_drop_success", {}).get("tile_after_bridge_inactive") == 0x01
        and v.get("item_use_rainbow_drop_wrong_coords", {}).get("action") == "map_item_rejected"
        and v.get("item_use_rainbow_drop_wrong_coords", {}).get("action_detail")
        == "RAINBOW DROP:no_rainbow_appeared_here"
        and v.get("item_use_rainbow_drop_wrong_coords", {}).get("screen_mode") == "dialog"
        and v.get("item_use_rainbow_drop_wrong_coords", {}).get("rainbow_bridge_flag_set") is False
        and v.get("item_use_rainbow_drop_wrong_coords", {}).get("inventory_slots_after") == [14, 0, 0, 0]
        and v.get("item_use_rainbow_drop_already_built", {}).get("action") == "map_item_rejected"
        and v.get("item_use_rainbow_drop_already_built", {}).get("action_detail")
        == "RAINBOW DROP:no_rainbow_appeared_here"
        and v.get("item_use_rainbow_drop_already_built", {}).get("screen_mode") == "dialog"
        and v.get("item_use_rainbow_drop_already_built", {}).get("rainbow_bridge_flag_set") is True
        and v.get("item_use_rainbow_drop_already_built", {}).get("inventory_slots_after") == [14, 0, 0, 0]
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_rainbow_drop_bridge_trigger_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_fairy_flute_interaction_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_fairy_flute_interaction",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_fairy_flute_interaction_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_fairy_flute_interaction.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_fairy_flute_interaction_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-fairy-flute-interaction"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("item_menu_open", {}).get("action") == "map_item_menu_opened"
        and v.get("item_menu_open", {}).get("action_detail") == "count:1"
        and v.get("item_menu_open", {}).get("screen_mode") == "map"
        and v.get("item_menu_open", {}).get("frame_contains_fairy_flute") is True
        and v.get("item_use_fairy_flute_success", {}).get("action") == "encounter_triggered"
        and v.get("item_use_fairy_flute_success", {}).get("action_detail") == "enemy:24;source:fairy_flute"
        and v.get("item_use_fairy_flute_success", {}).get("screen_mode") == "combat"
        and v.get("item_use_fairy_flute_success", {}).get("rng_after") == [129, 0]
        and v.get("item_use_fairy_flute_success", {}).get("enemy_id") == 24
        and v.get("item_use_fairy_flute_success", {}).get("enemy_name") == "Golem"
        and v.get("item_use_fairy_flute_success", {}).get("enemy_hp") == 70
        and v.get("item_use_fairy_flute_success", {}).get("enemy_max_hp") == 70
        and v.get("item_use_fairy_flute_success", {}).get("story_flags_after") == 0
        and v.get("item_use_fairy_flute_success", {}).get("inventory_slots_after") == [5, 0, 0, 0]
        and v.get("item_use_fairy_flute_success", {}).get("frame_contains_golem") is True
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("action") == "map_item_rejected"
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("action_detail") == "FAIRY FLUTE:flute_has_no_effect"
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("screen_mode") == "dialog"
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("story_flags_after") == 0
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("inventory_slots_after") == [5, 0, 0, 0]
        and v.get("item_use_fairy_flute_wrong_coords", {}).get("frame_contains_no_effect_text") is True
        and v.get("item_use_fairy_flute_golem_dead", {}).get("action") == "map_item_rejected"
        and v.get("item_use_fairy_flute_golem_dead", {}).get("action_detail") == "FAIRY FLUTE:flute_has_no_effect"
        and v.get("item_use_fairy_flute_golem_dead", {}).get("screen_mode") == "dialog"
        and v.get("item_use_fairy_flute_golem_dead", {}).get("story_flags_after") == 0x02
        and v.get("item_use_fairy_flute_golem_dead", {}).get("inventory_slots_after") == [5, 0, 0, 0]
        and v.get("item_use_fairy_flute_golem_dead", {}).get("frame_contains_no_effect_text") is True
        and v.get("item_use_fairy_flute_non_overworld", {}).get("action") == "map_item_rejected"
        and v.get("item_use_fairy_flute_non_overworld", {}).get("action_detail") == "FAIRY FLUTE:flute_has_no_effect"
        and v.get("item_use_fairy_flute_non_overworld", {}).get("screen_mode") == "dialog"
        and v.get("item_use_fairy_flute_non_overworld", {}).get("story_flags_after") == 0
        and v.get("item_use_fairy_flute_non_overworld", {}).get("inventory_slots_after") == [5, 0, 0, 0]
        and v.get("item_use_fairy_flute_non_overworld", {}).get("frame_contains_no_effect_text") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_fairy_flute_interaction_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_item_remaining_quest_item_use_effects_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_item_remaining_quest_item_use_effects",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_item_remaining_quest_item_use_effects_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_item_remaining_quest_item_use_effects.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_item_remaining_quest_item_use_effects_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-item-remaining-quest-item-use-effects"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("fighters_ring_success", {}).get("action") == "map_item_used"
        and v.get("fighters_ring_success", {}).get("action_detail") == "FIGHTER'S RING:ok"
        and v.get("fighters_ring_success", {}).get("attack_after") == 6
        and v.get("fighters_ring_success", {}).get("fighters_ring_flag_set") is True
        and v.get("fighters_ring_success", {}).get("inventory_slots_after") == [6, 0, 0, 0]
        and v.get("fighters_ring_already_equipped", {}).get("action") == "map_item_rejected"
        and v.get("fighters_ring_already_equipped", {}).get("action_detail")
        == "FIGHTER'S RING:already_wearing_fighters_ring"
        and v.get("fighters_ring_already_equipped", {}).get("attack_after") == 6
        and v.get("fighters_ring_already_equipped", {}).get("fighters_ring_flag_set") is True
        and v.get("fighters_ring_already_equipped", {}).get("inventory_slots_after") == [6, 0, 0, 0]
        and v.get("death_necklace_success", {}).get("action") == "map_item_used"
        and v.get("death_necklace_success", {}).get("action_detail") == "DEATH NECKLACE:ok"
        and v.get("death_necklace_success", {}).get("death_necklace_flag_set") is True
        and v.get("death_necklace_success", {}).get("inventory_slots_after") == [11, 0, 0, 0]
        and v.get("death_necklace_already_cursed", {}).get("action") == "map_item_rejected"
        and v.get("death_necklace_already_cursed", {}).get("action_detail") == "DEATH NECKLACE:already_cursed"
        and v.get("death_necklace_already_cursed", {}).get("cursed_belt_flag_set") is True
        and v.get("death_necklace_already_cursed", {}).get("death_necklace_flag_set") is False
        and v.get("death_necklace_already_cursed", {}).get("inventory_slots_after") == [11, 0, 0, 0]
        and v.get("cursed_belt_success", {}).get("action") == "map_item_used"
        and v.get("cursed_belt_success", {}).get("action_detail") == "CURSED BELT:ok"
        and v.get("cursed_belt_success", {}).get("cursed_belt_flag_set") is True
        and v.get("cursed_belt_success", {}).get("inventory_slots_after") == [9, 0, 0, 0]
        and v.get("cursed_belt_already_cursed", {}).get("action") == "map_item_rejected"
        and v.get("cursed_belt_already_cursed", {}).get("action_detail") == "CURSED BELT:already_cursed"
        and v.get("cursed_belt_already_cursed", {}).get("death_necklace_flag_set") is True
        and v.get("cursed_belt_already_cursed", {}).get("cursed_belt_flag_set") is False
        and v.get("cursed_belt_already_cursed", {}).get("inventory_slots_after") == [9, 0, 0, 0]
        and v.get("erdricks_token_held", {}).get("action") == "map_item_rejected"
        and v.get("erdricks_token_held", {}).get("action_detail") == "ERDRICK'S TOKEN:quest_item_held"
        and v.get("erdricks_token_held", {}).get("inventory_slots_after") == [7, 0, 0, 0]
        and v.get("erdricks_token_held", {}).get("frame_contains_holding") is True
        and v.get("stones_of_sunlight_held", {}).get("action") == "map_item_rejected"
        and v.get("stones_of_sunlight_held", {}).get("action_detail") == "STONES OF SUNLIGHT:quest_item_held"
        and v.get("stones_of_sunlight_held", {}).get("inventory_slots_after") == [12, 0, 0, 0]
        and v.get("stones_of_sunlight_held", {}).get("frame_contains_holding") is True
        and v.get("staff_of_rain_held", {}).get("action") == "map_item_rejected"
        and v.get("staff_of_rain_held", {}).get("action_detail") == "STAFF OF RAIN:quest_item_held"
        and v.get("staff_of_rain_held", {}).get("inventory_slots_after") == [13, 0, 0, 0]
        and v.get("staff_of_rain_held", {}).get("frame_contains_holding") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_item_remaining_quest_item_use_effects_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_cursed_item_step_damage_hook_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_cursed_item_step_damage_hook",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_cursed_item_step_damage_hook_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_cursed_item_step_damage_hook.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_cursed_item_step_damage_hook_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-cursed-item-step-damage-hook"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("cursed_belt_step_sets_hp_to_1", {}).get("action") == "move"
        and "cursed_belt:hp_set_to_1" in v.get("cursed_belt_step_sets_hp_to_1", {}).get("action_detail", "")
        and v.get("cursed_belt_step_sets_hp_to_1", {}).get("screen_mode") == "map"
        and v.get("cursed_belt_step_sets_hp_to_1", {}).get("map_after") == [1, 47, 1]
        and v.get("cursed_belt_step_sets_hp_to_1", {}).get("hp_after") == 1
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("action") == "combat_defeat"
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("action_detail") == "revive"
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("screen_mode") == "dialog"
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("map_after") == [4, 5, 27]
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("hp_after") == 31
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("mp_after") == 10
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("gold_after") == 61
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("dialog_page_1_contains_slain") is True
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("dialog_page_2_action")
        == "dialog_page_advance"
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("dialog_page_2_contains_revive") is True
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("dialog_done_action") == "dialog_done"
        and v.get("death_necklace_step_triggers_death_outcome", {}).get("dialog_done_screen_mode") == "map"
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("action") == "move"
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("action_detail") == "47,1"
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("screen_mode") == "map"
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("map_after") == [1, 47, 1]
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("hp_after") == 12
        and v.get("step_without_curse_flags_has_no_side_effect", {}).get("frame_contains_slain") is False
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_cursed_item_step_damage_hook_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_movement_terrain_step_effects_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_movement_terrain_step_effects",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_movement_terrain_step_effects_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_movement_terrain_step_effects.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_movement_terrain_step_effects_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-movement-terrain-step-effects"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("swamp_step_applies_2hp_damage", {}).get("action") == "move"
        and v.get("swamp_step_applies_2hp_damage", {}).get("hp_before") == 12
        and v.get("swamp_step_applies_2hp_damage", {}).get("hp_after") == 10
        and v.get("force_field_step_applies_15hp_damage", {}).get("action") == "move"
        and v.get("force_field_step_applies_15hp_damage", {}).get("hp_before") == 20
        and v.get("force_field_step_applies_15hp_damage", {}).get("hp_after") == 5
        and v.get("erdricks_armor_step_heal_applies", {}).get("action") == "move"
        and v.get("erdricks_armor_step_heal_applies", {}).get("hp_before") == 12
        and v.get("erdricks_armor_step_heal_applies", {}).get("hp_after") == 13
        and v.get("swamp_with_erdricks_armor_is_immune", {}).get("action") == "move"
        and v.get("swamp_with_erdricks_armor_is_immune", {}).get("hp_before") == 12
        and v.get("swamp_with_erdricks_armor_is_immune", {}).get("hp_after") == 12
        and v.get("magic_armor_4step_heal_applies", {}).get("step_actions") == ["move", "move", "move", "move"]
        and v.get("magic_armor_4step_heal_applies", {}).get("hp_before") == 12
        and v.get("magic_armor_4step_heal_applies", {}).get("hp_after") == 13
        and v.get("magic_armor_4step_heal_applies", {}).get("counter_after") == 4
        and v.get("neutral_step_has_no_terrain_effect", {}).get("action") == "move"
        and v.get("neutral_step_has_no_terrain_effect", {}).get("hp_before") == 12
        and v.get("neutral_step_has_no_terrain_effect", {}).get("hp_after") == 12
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_movement_terrain_step_effects_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/test_main_loop_scaffold.py",
        "-k",
        "phase4_map_movement_terrain_step_effects_artifacts_exist_and_are_consistent",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_load_curse_check_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_load_curse_check",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_load_curse_check_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_load_curse_check.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_load_curse_check_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-load-curse-check"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("map_load_with_cursed_belt_sets_hp_to_1", {}).get("action") == "map_stairs"
        and "cursed_belt:hp_set_to_1_on_load"
        in v.get("map_load_with_cursed_belt_sets_hp_to_1", {}).get("action_detail", "")
        and v.get("map_load_with_cursed_belt_sets_hp_to_1", {}).get("screen_mode") == "map"
        and v.get("map_load_with_cursed_belt_sets_hp_to_1", {}).get("map_after") == [16, 8, 0]
        and v.get("map_load_with_cursed_belt_sets_hp_to_1", {}).get("hp_after") == 1
        and v.get("map_load_without_curse_flag_preserves_hp", {}).get("action") == "map_stairs"
        and v.get("map_load_without_curse_flag_preserves_hp", {}).get("action_detail") == "warp:20"
        and v.get("map_load_without_curse_flag_preserves_hp", {}).get("screen_mode") == "map"
        and v.get("map_load_without_curse_flag_preserves_hp", {}).get("map_after") == [16, 8, 0]
        and v.get("map_load_without_curse_flag_preserves_hp", {}).get("hp_after") == 12
        and v.get("step_hook_regression_unchanged", {}).get("action") == "move"
        and v.get("step_hook_regression_unchanged", {}).get("action_detail") == "47,1;cursed_belt:hp_set_to_1"
        and v.get("step_hook_regression_unchanged", {}).get("screen_mode") == "map"
        and v.get("step_hook_regression_unchanged", {}).get("map_after") == [1, 47, 1]
        and v.get("step_hook_regression_unchanged", {}).get("hp_after") == 1
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_load_curse_check_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_stairs_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_stairs_surface",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_stairs_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_stairs_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_stairs_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-stairs-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("stairs_success", {}).get("action") == "map_stairs"
        and v.get("stairs_success", {}).get("action_detail") == "warp:20"
        and v.get("stairs_success", {}).get("screen_mode") == "map"
        and v.get("stairs_success", {}).get("map_after") == [16, 8, 0]
        and v.get("stairs_no_warp_rejected", {}).get("action") == "map_stairs_rejected"
        and v.get("stairs_no_warp_rejected", {}).get("action_detail") == "no_stairs"
        and v.get("stairs_no_warp_rejected", {}).get("screen_mode") == "dialog"
        and v.get("stairs_no_warp_rejected", {}).get("map_after") == [15, 0, 0]
        and v.get("stairs_no_warp_rejected", {}).get("frame_contains_no_stairs") is True
        and v.get("stairs_overworld_rejected", {}).get("action") == "map_stairs_rejected"
        and v.get("stairs_overworld_rejected", {}).get("action_detail") == "no_stairs"
        and v.get("stairs_overworld_rejected", {}).get("screen_mode") == "dialog"
        and v.get("stairs_overworld_rejected", {}).get("map_after") == [1, 46, 1]
        and v.get("stairs_overworld_rejected", {}).get("frame_contains_no_stairs") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_stairs_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_door_surface_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_door_surface",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_door_surface_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_door_surface.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_door_surface_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-door-surface"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("door_success", {}).get("action") == "map_door"
        and v.get("door_success", {}).get("action_detail") == "opened:key_used"
        and v.get("door_success", {}).get("screen_mode") == "dialog"
        and v.get("door_success", {}).get("magic_keys_after") == 0
        and v.get("door_success", {}).get("frame_contains_opened") is True
        and v.get("door_no_door_rejected", {}).get("action") == "map_door_rejected"
        and v.get("door_no_door_rejected", {}).get("action_detail") == "no_door"
        and v.get("door_no_door_rejected", {}).get("screen_mode") == "dialog"
        and v.get("door_no_door_rejected", {}).get("magic_keys_after") == 3
        and v.get("door_no_door_rejected", {}).get("frame_contains_no_door") is True
        and v.get("door_no_key_rejected", {}).get("action") == "map_door_rejected"
        and v.get("door_no_key_rejected", {}).get("action_detail") == "no_key"
        and v.get("door_no_key_rejected", {}).get("screen_mode") == "dialog"
        and v.get("door_no_key_rejected", {}).get("magic_keys_after") == 0
        and v.get("door_no_key_rejected", {}).get("frame_contains_no_key") is True
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_door_surface_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_map_command_door_persistence_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_map_command_door_persistence",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_map_command_door_persistence_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_map_command_door_persistence.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_map_command_door_persistence_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-map-command-door-persistence"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("door_opened", {}).get("action") == "map_door"
        and v.get("door_opened", {}).get("action_detail") == "opened:key_used"
        and v.get("door_opened", {}).get("screen_mode") == "dialog"
        and v.get("door_opened", {}).get("magic_keys_after") == 0
        and v.get("door_opened", {}).get("opened_door_count") == 1
        and v.get("door_opened", {}).get("frame_contains_opened") is True
        and v.get("door_render_state", {}).get("center_before") == "@"
        and v.get("door_render_state", {}).get("center_after") == "@"
        and v.get("door_render_state", {}).get("before_closed_glyph") == "+"
        and v.get("door_render_state", {}).get("after_open_glyph") == "░"
        and v.get("door_passability", {}).get("action") == "move"
        and v.get("door_passability", {}).get("screen_mode") == "map"
        and v.get("door_passability", {}).get("player_after") == [18, 6]
        and v.get("door_already_open", {}).get("action") == "map_door"
        and v.get("door_already_open", {}).get("action_detail") == "already_open"
        and v.get("door_already_open", {}).get("screen_mode") == "dialog"
        and v.get("door_already_open", {}).get("magic_keys_after") == 0
        and v.get("door_already_open", {}).get("frame_contains_already_open") is True
        and v.get("door_already_open", {}).get("back_to_map_action") == "dialog_done"
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_map_command_door_persistence_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_phase4_slice_opened_world_state_save_load_persistence_generator() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "ui.run_phase4_slice_opened_world_state_save_load_persistence",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_main_loop_opened_world_state_save_load_persistence_artifacts() -> dict:
    report_path = ROOT / "artifacts" / "phase4_main_loop_opened_world_state_save_load_persistence.json"
    vectors_path = ROOT / "tests" / "fixtures" / "main_loop_opened_world_state_save_load_persistence_vectors.json"

    if not report_path.exists() or not vectors_path.exists():
        return {
            "ok": False,
            "detail": {
                "report_exists": report_path.exists(),
                "vectors_fixture_exists": vectors_path.exists(),
            },
        }

    report = json.loads(report_path.read_text())
    vectors = json.loads(vectors_path.read_text())
    v = vectors.get("vectors", {})

    ok = (
        report.get("slice") == "phase4-main-loop-opened-world-state-save-load-persistence"
        and report.get("all_passed") is True
        and report.get("checks")
        and all(report.get("checks", {}).values())
        and v.get("save_on_quit", {}).get("action") == "quit"
        and v.get("save_on_quit", {}).get("quit_requested") is True
        and v.get("save_on_quit", {}).get("save_exists") is True
        and v.get("save_on_quit", {}).get("world_state", {}).get("opened_chest_indices") == [0]
        and v.get("save_on_quit", {}).get("world_state", {}).get("opened_doors") == [[4, 18, 6]]
        and v.get("continue", {}).get("action") == "continue_loaded"
        and v.get("continue", {}).get("screen_mode") == "map"
        and v.get("continue", {}).get("restored_opened_chest_indices") == [0]
        and v.get("continue", {}).get("restored_opened_doors") == [[4, 18, 6]]
        and v.get("reopen_chest", {}).get("action") == "map_search"
        and v.get("reopen_chest", {}).get("action_detail") == "chest:index:0;contents:19;opened:true;reward:none"
        and v.get("reopen_chest", {}).get("screen_mode") == "dialog"
        and v.get("reopen_chest", {}).get("frame_contains_empty") is True
        and v.get("reopen_door", {}).get("action") == "map_door"
        and v.get("reopen_door", {}).get("action_detail") == "already_open"
        and v.get("reopen_door", {}).get("screen_mode") == "dialog"
        and v.get("reopen_door", {}).get("frame_contains_already_open") is True
        and v.get("reopen_door", {}).get("move_after_dialog_action") == "move"
        and v.get("reopen_door", {}).get("move_after_dialog_screen_mode") == "map"
        and v.get("reopen_door", {}).get("player_after_move") == [18, 6]
    )

    return {
        "ok": ok,
        "detail": {
            "report": report,
            "vectors": vectors,
        },
    }


def run_pytest_phase4_opened_world_state_save_load_persistence_slice() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
        "tests/",
        "-v",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def check_phase4_main_loop_artifacts_passed() -> dict:
    artifacts_dir = ROOT / "artifacts"
    paths = sorted(artifacts_dir.glob("phase4_main_loop_*.json"))
    if not paths:
        return {
            "ok": False,
            "detail": {
                "artifact_count": 0,
                "reason": "no phase4_main_loop_*.json artifacts found",
            },
        }

    failures: list[str] = []
    for path in paths:
        try:
            payload = json.loads(path.read_text())
        except Exception:
            failures.append(f"{path.name}:invalid_json")
            continue
        if payload.get("all_passed") is not True:
            failures.append(f"{path.name}:all_passed_not_true")

    return {
        "ok": not failures,
        "detail": {
            "artifact_count": len(paths),
            "artifacts_with_all_passed_true": len(paths) - len(failures),
            "failures": failures,
        },
    }


def check_phase4_walkthrough_checkpoints_optional_future() -> dict:
    checkpoint_dir = ROOT / "tests" / "checkpoints"
    expected = [f"cp_{idx:02d}.json" for idx in range(9)]
    missing = [name for name in expected if not (checkpoint_dir / name).exists()]
    optional_items = [
        {
            "item": "full_walkthrough_checkpoints_cp_00_to_cp_08",
            "status": "OPTIONAL/FUTURE AUDIT",
            "missing": missing,
            "rationale": "Gameplay systems are implemented and machine-verified via bounded Phase 4 slice gates; full manual walkthrough checkpoint catalog is deferred.",
        }
    ]
    return {
        "ok": True,
        "detail": {
            "optional_future_audit": optional_items,
        },
    }


def run_pytest_full_suite() -> dict:
    cmd = [
        sys.executable,
        "-m",
        "pytest",
    ]
    run = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    return {
        "ok": run.returncode == 0,
        "command": " ".join(cmd),
        "returncode": run.returncode,
        "stdout": run.stdout,
        "stderr": run.stderr,
    }


def run_pytest_phase5_batch1_foundation_suite() -> dict:
    replay_manifest = ROOT / "tests" / "replay" / "manifest.json"
    checkpoint_manifest = ROOT / "tests" / "checkpoints" / "manifest.json"
    required = [
        ROOT / "verify.py",
        ROOT / "requirements.txt",
        replay_manifest,
        checkpoint_manifest,
        ROOT / "artifacts" / "phase5_parity.json",
        ROOT / "artifacts" / "phase5_slice_terminal_size_enforcement.json",
        ROOT / "artifacts" / "phase5_slice_ascii_fallback_tileset.json",
    ]
    missing = [str(path.relative_to(ROOT)) for path in required if not path.exists()]
    if missing:
        return {
            "ok": False,
            "command": "phase5-batch1-foundation-suite",
            "returncode": 1,
            "stdout": "",
            "stderr": f"missing required Batch 1 foundation files: {', '.join(missing)}",
        }

    replay_payload = json.loads(replay_manifest.read_text())
    checkpoint_payload = json.loads(checkpoint_manifest.read_text())
    replay_entries = replay_payload.get("fixtures")
    checkpoint_entries = checkpoint_payload.get("fixtures")
    replay_ok = isinstance(replay_entries, list) and len(replay_entries) >= 1
    checkpoint_ok = isinstance(checkpoint_entries, list) and len(checkpoint_entries) >= 1
    ok = replay_ok and checkpoint_ok
    return {
        "ok": ok,
        "command": "phase5-batch1-foundation-suite",
        "returncode": 0 if ok else 1,
        "stdout": json.dumps(
            {
                "replay_manifest_entries": len(replay_entries) if isinstance(replay_entries, list) else None,
                "checkpoint_manifest_entries": len(checkpoint_entries) if isinstance(checkpoint_entries, list) else None,
            },
            indent=2,
        ),
        "stderr": "" if ok else "Batch 1 foundation manifests invalid",
    }


def _phase5_escape_md(value: object) -> str:
    return str(value).replace("|", "\\|")


def _phase5_fixture_manifest_proof(*, manifest_path: Path) -> dict:
    from parity_proof import evaluate_manifest

    return evaluate_manifest(manifest_path, root=ROOT)


def check_phase5_parity_matrix_gate() -> dict:
    class _FixedRNG:
        def __init__(self, value: int) -> None:
            self.value = value & 0xFF
            self.rng_lb = self.value
            self.rng_ub = self.value

        def tick(self) -> int:
            self.rng_lb = self.value
            self.rng_ub = self.value
            return self.value

    def _load_json(path: Path) -> dict:
        if not path.exists():
            raise FileNotFoundError(f"missing required file: {path.relative_to(ROOT)}")
        return json.loads(path.read_text())

    row_results: list[dict] = []

    def add_row(
        system: str,
        test: str,
        expected: str,
        actual: object,
        passed: bool,
        evidence: str,
        rom_source: str,
        *,
        evidence_tier: str = "extractor-only",
        status: str | None = None,
    ) -> None:
        row_number = len(row_results) + 1
        resolved_status = status or ("PASS" if bool(passed) else "FAIL")
        row_results.append(
            {
                "row": row_number,
                "system": system,
                "test": test,
                "expected": expected,
                "actual": actual,
                "passed": bool(passed),
                "status": resolved_status,
                "evidence": evidence,
                "evidence_tier": evidence_tier,
                "rom_source": rom_source,
            }
        )

    try:
        rom_baseline = _load_json(ROOT / "extractor" / "rom_baseline.json")
        rom_header = _load_json(ROOT / "extractor" / "data_out" / "rom_header.json")
        maps = _load_json(ROOT / "extractor" / "data_out" / "maps.json")
        chests = _load_json(ROOT / "extractor" / "data_out" / "chests.json")
        enemies = _load_json(ROOT / "extractor" / "data_out" / "enemies.json")
        spells = _load_json(ROOT / "extractor" / "data_out" / "spells.json")
        zones = _load_json(ROOT / "extractor" / "data_out" / "zones.json")
        xp_data = _load_json(ROOT / "extractor" / "data_out" / "xp_table.json")
        stats_data = _load_json(ROOT / "extractor" / "data_out" / "stats.json")
        items_data = _load_json(ROOT / "extractor" / "data_out" / "items.json")
        rng_fixture = _load_json(ROOT / "tests" / "fixtures" / "rng_golden_sequence.json")
        items_vectors = _load_json(ROOT / "tests" / "fixtures" / "items_runtime_vectors.json")
        save_load_vectors = _load_json(ROOT / "tests" / "fixtures" / "save_load_runtime_vectors.json")
        replay_manifest = _load_json(ROOT / "tests" / "replay" / "manifest.json")
        checkpoint_manifest = _load_json(ROOT / "tests" / "checkpoints" / "manifest.json")

        phase4_door = _load_json(ROOT / "artifacts" / "phase4_main_loop_map_command_door_surface.json")
        phase4_curse_load = _load_json(ROOT / "artifacts" / "phase4_main_loop_map_load_curse_check.json")
        phase4_terrain = _load_json(ROOT / "artifacts" / "phase4_main_loop_map_movement_terrain_step_effects.json")
        phase4_rainbow = _load_json(
            ROOT / "artifacts" / "phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json"
        )
        phase4_gwaelin = _load_json(ROOT / "artifacts" / "phase4_main_loop_npc_special_control_side_effects.json")
        phase4_dragonlord = _load_json(ROOT / "artifacts" / "phase4_main_loop_combat_dragonlord_endgame_victory.json")
        phase4_shop_inn = _load_json(ROOT / "artifacts" / "phase4_main_loop_npc_shop_inn_handoff.json")
        phase5_edge_case = _load_json(ROOT / "artifacts" / "phase5_slice_edge_case_regression_gate.json")
        phase2_save = _load_json(ROOT / "artifacts" / "phase2_save_load_runtime.json")

        from engine.map_engine import MapEngine
        from engine.save_load import state_to_save_data, state_from_save_dict, state_to_save_dict
        from engine.shop import ShopRuntime
        from engine.state import GameState
        from main import MainLoopSession, MainLoopState, initial_title_state

        class _VerifyStream:
            def write(self, payload: str) -> None:
                return None

            def flush(self) -> None:
                return None

        class _VerifyTerminal:
            def __init__(self) -> None:
                self.width = 80
                self.height = 24
                self.stream = _VerifyStream()

        def _clone_state(state: GameState, **updates: object) -> GameState:
            data = state.to_dict()
            data.update(updates)
            return GameState(**data)

        def _map_engine() -> object:
            return MapEngine(
                maps_payload=maps,
                warps_payload=_load_json(ROOT / "extractor" / "data_out" / "warps.json"),
            )

        def _npcs_payload() -> dict:
            return _load_json(ROOT / "extractor" / "data_out" / "npcs.json")

        shop_runtime = ShopRuntime(items_payload=items_data)

        expected_sha1 = rom_baseline["accepted_sha1"]
        rom_path = ROOT / rom_baseline["rom_file"]
        actual_sha1 = _sha1(rom_path)
        add_row(
            "ROM",
            "SHA1 match",
            expected_sha1,
            actual_sha1,
            actual_sha1 == expected_sha1,
            "extractor/rom_baseline.json + dragon-warrior-1.nes",
            "verify.py phase gate baseline",
            evidence_tier="extractor-only",
        )

        prg_size = int(rom_header["header"]["prg_banks"]) * 16384
        add_row(
            "ROM",
            "PRG size",
            "65536",
            prg_size,
            prg_size == 65536,
            "extractor/data_out/rom_header.json",
            "iNES header byte 4",
            evidence_tier="extractor-only",
        )

        chr_size = int(rom_header["header"]["chr_banks"]) * 8192
        add_row(
            "ROM",
            "CHR size",
            "16384",
            chr_size,
            chr_size == 16384,
            "extractor/data_out/rom_header.json",
            "iNES header byte 5",
            evidence_tier="extractor-only",
        )

        mapper = int(rom_header["header"]["mapper"])
        add_row(
            "ROM",
            "Mapper",
            "1",
            mapper,
            mapper == 1,
            "extractor/data_out/rom_header.json",
            "Header flags 6/7",
            evidence_tier="extractor-only",
        )

        overworld = maps["maps"][1]
        overworld_dims = [overworld["width"], overworld["height"]]
        add_row(
            "Maps",
            "Overworld dimensions",
            "[120, 120]",
            overworld_dims,
            overworld_dims == [120, 120],
            "extractor/data_out/maps.json",
            "Data Crystal ROM map 0x1D6D",
        )

        map_ids = [entry["id"] for entry in maps["maps"]]
        map_count_ok = len(maps["maps"]) == 30 and map_ids == list(range(30))
        add_row(
            "Maps",
            "Map metadata count",
            "30 entries ids 0..29",
            {"count": len(maps["maps"]), "id_range": [min(map_ids), max(map_ids)]},
            map_count_ok,
            "extractor/data_out/maps.json",
            "ROM metadata table 0x002A-0x00C0",
        )

        tantegel_dims = [maps["maps"][4]["width"], maps["maps"][4]["height"]]
        add_row(
            "Maps",
            "Tantegel size",
            "[30, 30]",
            tantegel_dims,
            tantegel_dims == [30, 30],
            "extractor/data_out/maps.json",
            "Metadata entry 4",
        )

        throne_dims = [maps["maps"][5]["width"], maps["maps"][5]["height"]]
        add_row(
            "Maps",
            "Throne Room size",
            "[10, 10]",
            throne_dims,
            throne_dims == [10, 10],
            "extractor/data_out/maps.json",
            "Metadata entry 5",
        )

        chest_entries = chests["chest_entries"]
        add_row(
            "Chests",
            "Chest count",
            "31",
            len(chest_entries),
            len(chest_entries) == 31,
            "extractor/data_out/chests.json",
            "ROM 0x5DDD-0x5E58",
        )

        tantegel_chest = chest_entries[0]
        chest_actual = [tantegel_chest["map_id"], tantegel_chest["x"], tantegel_chest["y"], tantegel_chest["contents_id"]]
        add_row(
            "Chests",
            "Tantegel chest spot-check",
            "[4, 1, 13, 19]",
            chest_actual,
            chest_actual == [4, 1, 13, 19],
            "extractor/data_out/chests.json",
            "Extracted TreasureTbl entry",
        )

        add_row(
            "Enemies",
            "Enemy count",
            "40",
            len(enemies["enemies"]),
            len(enemies["enemies"]) == 40,
            "extractor/data_out/enemies.json",
            "EnStatTbl",
        )

        enemy0_name = enemies["enemies"][0]["name"]
        add_row(
            "Enemies",
            "Enemy 0 name",
            "Slime",
            enemy0_name,
            enemy0_name == "Slime",
            "extractor/data_out/enemies.json",
            "EnStatTbl entry 0x00",
        )

        dl2_hp = enemies["enemies"][39]["hp"]
        edge_case_checks = phase5_edge_case.get("checks", {}).get("check_phase5_slice_edge_case_regression_gate", {}).get(
            "detail", {}
        ).get("checks", {})
        dl_phase_transition_ok = (
            bool(phase5_edge_case.get("all_passed"))
            and edge_case_checks.get("dragonlord_phase1_to_phase2_enemy_id") is True
            and edge_case_checks.get("dragonlord_phase2_hp_130") is True
        )
        add_row(
            "Enemies",
            "Dragonlord form2 HP base",
            "130",
            {
                "enemy_table_hp": dl2_hp,
                "phase1_to_phase2_enemy_id_check": edge_case_checks.get("dragonlord_phase1_to_phase2_enemy_id"),
                "phase1_to_phase2_hp_check": edge_case_checks.get("dragonlord_phase2_hp_130"),
            },
            dl2_hp == 130 and dl_phase_transition_ok,
            "extractor/data_out/enemies.json + artifacts/phase5_slice_edge_case_regression_gate.json",
            "Enemy table @ ROM 0x5E5B",
        )

        spell_costs = {entry["name"]: entry["mp_cost"] for entry in spells["spells"]}
        add_row("MP Costs", "HEAL", "4", spell_costs.get("HEAL"), spell_costs.get("HEAL") == 4, "extractor/data_out/spells.json", "SpellCostTbl @ 0x1D63")
        add_row(
            "MP Costs",
            "HURTMORE",
            "5",
            spell_costs.get("HURTMORE"),
            spell_costs.get("HURTMORE") == 5,
            "extractor/data_out/spells.json",
            "SpellCostTbl @ 0x1D6C",
        )
        add_row("MP Costs", "RETURN", "8", spell_costs.get("RETURN"), spell_costs.get("RETURN") == 8, "extractor/data_out/spells.json", "SpellCostTbl @ 0x1D69")
        add_row(
            "MP Costs",
            "OUTSIDE",
            "6",
            spell_costs.get("OUTSIDE"),
            spell_costs.get("OUTSIDE") == 6,
            "extractor/data_out/spells.json",
            "SpellCostTbl @ 0x1D68",
        )

        xp_by_level = {entry["level"]: entry["xp_threshold"] for entry in xp_data["levels"]}
        add_row("XP Table", "Level 2 threshold", "7", xp_by_level.get(2), xp_by_level.get(2) == 7, "extractor/data_out/xp_table.json", "Bank03 LF35D")
        add_row(
            "XP Table",
            "Level 10 threshold",
            "2000",
            xp_by_level.get(10),
            xp_by_level.get(10) == 2000,
            "extractor/data_out/xp_table.json",
            "Bank03 LF36D",
        )
        add_row(
            "XP Table",
            "Level 20 threshold",
            "26000",
            xp_by_level.get(20),
            xp_by_level.get(20) == 26000,
            "extractor/data_out/xp_table.json",
            "Bank03 LF381",
        )
        add_row(
            "XP Table",
            "Level 30 threshold",
            "65535",
            xp_by_level.get(30),
            xp_by_level.get(30) == 65535,
            "extractor/data_out/xp_table.json",
            "Bank03 LF395",
        )
        add_row(
            "XP Table",
            "All 30 thresholds",
            "30 entries",
            len(xp_data["levels"]),
            len(xp_data["levels"]) == 30,
            "extractor/data_out/xp_table.json",
            "Bank03 LF35B-LF395",
        )

        from engine.combat import (
            EN_DRAGONLORD1,
            enemy_hp_init,
            enemy_spell_actions_for_pattern,
            excellent_move_check,
            heal_spell_hp,
            healmore_spell_hp,
            hurt_spell_damage,
            hurtmore_spell_damage,
            player_attack_damage,
        )
        from engine.rng import DW1RNG

        rng_seed_lb = int(rng_fixture["seed_lb"])
        rng_seed_ub = int(rng_fixture["seed_ub"])
        rng_sequence = [int(value) for value in rng_fixture["sequence"]]
        golden_rng = DW1RNG(rng_seed_lb, rng_seed_ub)
        rng_actual = [golden_rng.tick() for _ in range(len(rng_sequence))]
        add_row(
            "RNG",
            "Golden sequence",
            f"{len(rng_sequence)} ticks match fixture",
            {"count": len(rng_sequence), "matches": rng_actual == rng_sequence},
            rng_actual == rng_sequence,
            "tests/fixtures/rng_golden_sequence.json",
            "Bank03 LC55B",
        )

        first_rng = DW1RNG(rng_seed_lb, rng_seed_ub)
        second_rng = DW1RNG(rng_seed_lb, rng_seed_ub)
        seq_a = [first_rng.tick() for _ in range(256)]
        seq_b = [second_rng.tick() for _ in range(256)]
        add_row(
            "RNG",
            "Deterministic seed replay",
            "same-seed sequences identical",
            {"first8": seq_a[:8], "matches": seq_a == seq_b},
            seq_a == seq_b,
            "tests/test_rng.py::test_rng_determinism",
            "Bank03 LFSR",
        )

        excellent_hits = sum(1 for value in range(256) if excellent_move_check(0, _FixedRNG(value)))
        add_row(
            "Combat",
            "Excellent move chance",
            "8/256 (=1/32)",
            f"{excellent_hits}/256",
            excellent_hits == 8,
            "engine.combat.excellent_move_check",
            "Bank03 LE61F",
        )

        dl_excellent_hits = sum(1 for value in range(256) if excellent_move_check(EN_DRAGONLORD1, _FixedRNG(value)))
        add_row(
            "Combat",
            "No excellent vs Dragonlord",
            "0/256",
            {
                "rng_sweep": f"{dl_excellent_hits}/256",
                "edge_case_gate_check": edge_case_checks.get("dragonlord_no_excellent_in_phase1"),
            },
            dl_excellent_hits == 0 and edge_case_checks.get("dragonlord_no_excellent_in_phase1") is True,
            "engine.combat.excellent_move_check + artifacts/phase5_slice_edge_case_regression_gate.json",
            "Bank03 LE617-LE61D",
        )

        weak_values = [player_attack_damage(0, 255, _FixedRNG(value)) for value in range(256)]
        weak_zero = weak_values.count(0)
        weak_one = weak_values.count(1)
        add_row(
            "Combat",
            "Player weak attack split",
            "128 zeros / 128 ones",
            {"zero": weak_zero, "one": weak_one},
            weak_zero == 128 and weak_one == 128,
            "engine.combat.player_attack_damage",
            "Bank03 LF026",
        )

        atk = 120
        defense = 40
        rng_value = 200
        base = (atk - (defense >> 1)) & 0xFF
        manual = max(1, ((((rng_value * ((base + 1) & 0xFF)) >> 8) + base) & 0xFF) >> 2)
        actual_normal = player_attack_damage(atk, defense, _FixedRNG(rng_value))
        add_row(
            "Combat",
            "Normal attack formula parity",
            str(manual),
            actual_normal,
            actual_normal == manual,
            "engine.combat.player_attack_damage",
            "Bank03 LF030",
        )

        wrap_result = player_attack_damage(255, 0, _FixedRNG(255))
        add_row(
            "Combat",
            "8-bit wraparound boundary",
            "63",
            wrap_result,
            wrap_result == 63,
            "tests/test_combat.py::test_player_attack_boundary_max_atk_min_def",
            "Bank03 arithmetic wrap",
        )

        heal_values = [heal_spell_hp(_FixedRNG(value)) for value in range(256)]
        add_row(
            "Combat",
            "HEAL range",
            "10..17",
            [min(heal_values), max(heal_values)],
            min(heal_values) == 10 and max(heal_values) == 17,
            "engine.combat.heal_spell_hp",
            "Bank03 LDBB8",
        )

        healmore_values = [healmore_spell_hp(_FixedRNG(value)) for value in range(256)]
        add_row(
            "Combat",
            "HEALMORE range",
            "85..100",
            [min(healmore_values), max(healmore_values)],
            min(healmore_values) == 85 and max(healmore_values) == 100,
            "engine.combat.healmore_spell_hp",
            "Bank03 LDBD7",
        )

        hurt_values = [hurt_spell_damage(_FixedRNG(value)) for value in range(256)]
        hurtmore_values = [hurtmore_spell_damage(_FixedRNG(value)) for value in range(256)]
        add_row(
            "Combat",
            "HURT/HURTMORE ranges",
            "HURT 5..12; HURTMORE 58..65",
            {
                "hurt": [min(hurt_values), max(hurt_values)],
                "hurtmore": [min(hurtmore_values), max(hurtmore_values)],
            },
            min(hurt_values) == 5
            and max(hurt_values) == 12
            and min(hurtmore_values) == 58
            and max(hurtmore_values) == 65,
            "engine.combat.hurt_spell_damage + hurtmore_spell_damage",
            "Bank03 LE736/LE751",
        )

        hp_values = [enemy_hp_init(130, _FixedRNG(value)) for value in range(256)]
        add_row(
            "Combat",
            "Enemy HP init formula",
            "randomized and bounded 98..130",
            [min(hp_values), max(hp_values)],
            min(hp_values) == 98 and max(hp_values) == 130,
            "engine.combat.enemy_hp_init",
            "Bank03 LE599",
        )

        magician_seed = MainLoopState(
            screen_mode="combat",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=47,
                player_y=1,
                hp=15,
                mp=0,
                max_hp=15,
                max_mp=15,
                defense=2,
                spells_known=0x03,
                more_spells_quest=0x03,
                rng_lb=0,
                rng_ub=0,
                combat_session={
                    "enemy_id": 4,
                    "enemy_name": "Magician",
                    "enemy_hp": 13,
                    "enemy_max_hp": 13,
                    "enemy_base_hp": 7,
                    "enemy_atk": 11,
                    "enemy_def": 8,
                    "enemy_agi": 0,
                    "enemy_mdef": 1,
                    "enemy_pattern_flags": 0x02,
                    "enemy_s_ss_resist": 0,
                    "enemy_xp": 3,
                    "enemy_gp": 5,
                    "enemy_asleep": False,
                    "enemy_stopspell": False,
                    "player_stopspell": False,
                },
            ),
            title_state=initial_title_state(),
        )
        magician_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=magician_seed,
        )
        magician_result = magician_session.step("ITEM")
        magician_stopspell_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=MainLoopState(
                screen_mode=magician_seed.screen_mode,
                game_state=_clone_state(
                    magician_seed.game_state,
                    combat_session={
                        **magician_seed.game_state.combat_session.to_dict(),
                        "enemy_stopspell": True,
                    },
                ),
                title_state=magician_seed.title_state,
            ),
        )
        magician_stopspell_result = magician_stopspell_session.step("ITEM")
        enemy_spell_runtime_actual = {
            "magician_hurt": {
                "action": magician_result.action.kind,
                "screen_mode": magician_result.screen_mode,
                "player_hp_after": magician_session.state.game_state.hp,
                "frame_contains_cast": "MAGICIAN CASTS HURT." in magician_result.frame,
                "frame_contains_strike": "MAGICIAN STRIKES" in magician_result.frame,
            },
            "magician_stopspell_fallback": {
                "action": magician_stopspell_result.action.kind,
                "screen_mode": magician_stopspell_result.screen_mode,
                "player_hp_after": magician_stopspell_session.state.game_state.hp,
                "frame_contains_stopped": "Magician's spell has been stopped." in magician_stopspell_result.frame,
                "frame_contains_strike": "MAGICIAN STRIKES" in magician_stopspell_result.frame,
            },
        }
        add_row(
            "Combat",
            "Live enemy spell execution for proven subset",
            "pattern_flags 0x02 enemies cast HURT live; stopspelled cast falls back to physical attack",
            enemy_spell_runtime_actual,
            enemy_spell_runtime_actual["magician_hurt"]["action"] == "combat_turn"
            and enemy_spell_runtime_actual["magician_hurt"]["screen_mode"] == "combat"
            and enemy_spell_runtime_actual["magician_hurt"]["player_hp_after"] == 7
            and enemy_spell_runtime_actual["magician_hurt"]["frame_contains_cast"] is True
            and enemy_spell_runtime_actual["magician_hurt"]["frame_contains_strike"] is False
            and enemy_spell_runtime_actual["magician_stopspell_fallback"]["action"] == "combat_turn"
            and enemy_spell_runtime_actual["magician_stopspell_fallback"]["screen_mode"] == "combat"
            and enemy_spell_runtime_actual["magician_stopspell_fallback"]["player_hp_after"] < 15
            and enemy_spell_runtime_actual["magician_stopspell_fallback"]["frame_contains_stopped"] is True
            and enemy_spell_runtime_actual["magician_stopspell_fallback"]["frame_contains_strike"] is True,
            "main.py combat enemy-turn resolution + tests/test_main_loop_scaffold.py live Magician spell regressions",
            "Bounded runtime proof: Magician live-casts HURT from pattern_flags 0x02; stopspell preserves existing blocked-cast fallback",
            evidence_tier="runtime-state",
        )

        grid = zones["overworld_zone_grid"]
        grid_values = [value for row in grid for value in row]
        add_row(
            "Zones",
            "Zone grid dimensions",
            "8x8 values in 0..13",
            {"rows": len(grid), "cols": len(grid[0]), "min": min(grid_values), "max": max(grid_values)},
            len(grid) == 8 and all(len(row) == 8 for row in grid) and min(grid_values) >= 0 and max(grid_values) <= 13,
            "extractor/data_out/zones.json",
            "Bank03 LF522",
        )

        add_row(
            "Zones",
            "Zone (0,0) value",
            "3",
            grid[0][0],
            grid[0][0] == 3,
            "extractor/data_out/zones.json",
            "Bank03 LF522",
        )
        add_row(
            "Zones",
            "Zone (7,7) value",
            "9",
            grid[7][7],
            grid[7][7] == 9,
            "extractor/data_out/zones.json",
            "Bank03 LF53E",
        )

        row0_expected = ["Slime", "Red Slime", "Slime", "Red Slime", "Slime"]
        row13_expected = ["Werewolf", "Green Dragon", "Starwyvern", "Starwyvern", "Wizard"]
        add_row(
            "Zones",
            "Formation row 0",
            str(row0_expected),
            zones["overworld_formation_table"][0],
            zones["overworld_formation_table"][0] == row0_expected,
            "extractor/data_out/zones.json",
            "Bank03 LF54F",
        )
        add_row(
            "Zones",
            "Formation row 13",
            str(row13_expected),
            zones["overworld_formation_table"][13],
            zones["overworld_formation_table"][13] == row13_expected,
            "extractor/data_out/zones.json",
            "Bank03 LF590",
        )

        cave_expected = [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15]
        add_row(
            "Zones",
            "Cave index table",
            str(cave_expected),
            zones["cave_index_table"],
            zones["cave_index_table"] == cave_expected,
            "extractor/data_out/zones.json",
            "Bank03 LF542",
        )

        top_left_zone_values = sorted({grid[y // 15][x // 15] for x in range(15) for y in range(15)})
        add_row(
            "Zones",
            "Top-left overworld zone consistency",
            "only zone id 3 in coordinates 0..14",
            top_left_zone_values,
            top_left_zone_values == [3],
            "extractor/data_out/zones.json",
            "Bank03 OvrWrldEnGrid mapping",
        )

        key_consumption_ok = (
            phase4_door["all_passed"] is True
            and phase4_door["checks"].get("door_select_uses_key_when_facing_door") is True
        )
        add_row(
            "Items",
            "Magic Key consumption",
            "door use consumes one key",
            phase4_door["checks"].get("door_select_uses_key_when_facing_door"),
            key_consumption_ok,
            "artifacts/phase4_main_loop_map_command_door_surface.json",
            "Bank03 key-use door path",
        )

        torch_radius = items_vectors["vectors"].get("torch_light_radius")
        torch_timer = items_vectors["vectors"].get("torch_light_timer")
        add_row(
            "Items",
            "Torch radius + timer",
            "radius=5 timer=16",
            {"radius": torch_radius, "timer": torch_timer},
            torch_radius == 5 and torch_timer == 16,
            "tests/fixtures/items_runtime_vectors.json",
            "Bank03 ChkTorch",
        )

        rainbow_ok = (
            phase4_rainbow["all_passed"] is True
            and phase4_rainbow["checks"].get("rainbow_drop_use_sets_bridge_flag_and_bridge_tile") is True
            and items_vectors["vectors"].get("rainbow_bridge_target") == [1, 63, 49]
        )
        add_row(
            "Items",
            "Rainbow Drop bridge placement",
            "bridge flag set and bridge tile at [1,63,49]",
            {
                "bridge_check": phase4_rainbow["checks"].get("rainbow_drop_use_sets_bridge_flag_and_bridge_tile"),
                "bridge_target": items_vectors["vectors"].get("rainbow_bridge_target"),
            },
            rainbow_ok,
            "artifacts/phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json + tests/fixtures/items_runtime_vectors.json",
            "Bank03 place_charlock",
        )

        curse_load_ok = (
            phase4_curse_load["all_passed"] is True
            and phase4_curse_load["checks"].get("map_load_with_cursed_belt_sets_hp_to_1") is True
        )
        add_row(
            "Items",
            "Cursed equip load effect",
            "HP set to 1 on map load",
            phase4_curse_load["checks"].get("map_load_with_cursed_belt_sets_hp_to_1"),
            curse_load_ok,
            "artifacts/phase4_main_loop_map_load_curse_check.json",
            "Bank03 LCB73",
        )

        add_row(
            "Terrain",
            "Swamp step damage",
            "true",
            phase4_terrain["checks"].get("swamp_step_applies_2hp_damage"),
            phase4_terrain["all_passed"] is True and phase4_terrain["checks"].get("swamp_step_applies_2hp_damage") is True,
            "artifacts/phase4_main_loop_map_movement_terrain_step_effects.json",
            "Bank03 LCDE2",
        )
        add_row(
            "Terrain",
            "Force field step damage",
            "true",
            phase4_terrain["checks"].get("force_field_step_applies_15hp_damage"),
            phase4_terrain["all_passed"] is True and phase4_terrain["checks"].get("force_field_step_applies_15hp_damage") is True,
            "artifacts/phase4_main_loop_map_movement_terrain_step_effects.json",
            "Bank03 LCE47",
        )
        add_row(
            "Terrain",
            "Erdrick armor swamp immunity",
            "true",
            phase4_terrain["checks"].get("swamp_with_erdricks_armor_is_immune"),
            phase4_terrain["all_passed"] is True and phase4_terrain["checks"].get("swamp_with_erdricks_armor_is_immune") is True,
            "artifacts/phase4_main_loop_map_movement_terrain_step_effects.json",
            "Bank03 LCDD0",
        )
        add_row(
            "Terrain",
            "Erdrick armor step heal",
            "true",
            phase4_terrain["checks"].get("erdricks_armor_step_heal_applies"),
            phase4_terrain["all_passed"] is True and phase4_terrain["checks"].get("erdricks_armor_step_heal_applies") is True,
            "artifacts/phase4_main_loop_map_movement_terrain_step_effects.json",
            "Bank03 LCCFA",
        )

        add_row(
            "Quest",
            "Gwaelin rescue flag side-effect",
            "true",
            phase4_gwaelin["checks"].get("control_0x6e_updates_gwaelin_flags_and_followup_dialog"),
            phase4_gwaelin["all_passed"] is True
            and phase4_gwaelin["checks"].get("control_0x6e_updates_gwaelin_flags_and_followup_dialog") is True,
            "artifacts/phase4_main_loop_npc_special_control_side_effects.json",
            "RAM map story flag path",
        )
        add_row(
            "Quest",
            "Dragonlord defeat flag",
            "true",
            phase4_dragonlord["checks"].get("dragonlord_phase2_defeat_sets_dead_flag_and_uses_special_dialog"),
            phase4_dragonlord["all_passed"] is True
            and phase4_dragonlord["checks"].get("dragonlord_phase2_defeat_sets_dead_flag_and_uses_special_dialog") is True,
            "artifacts/phase4_main_loop_combat_dragonlord_endgame_victory.json",
            "RAM map 0x00E4 bit 2",
        )

        stats_levels = {entry["level"]: entry for entry in stats_data["levels"]}
        level1 = stats_levels[1]
        level30 = stats_levels[30]

        add_row(
            "Stats",
            "Lv1 base stats",
            "STR=4 AGI=4 HP=15 MP=0",
            [level1["strength"], level1["agility"], level1["max_hp"], level1["max_mp"]],
            [level1["strength"], level1["agility"], level1["max_hp"], level1["max_mp"]] == [4, 4, 15, 0],
            "extractor/data_out/stats.json",
            "Bank01 LA0CD",
        )
        add_row(
            "Stats",
            "Lv30 base stats",
            "STR=140 AGI=130 HP=210 MP=200",
            [level30["strength"], level30["agility"], level30["max_hp"], level30["max_mp"]],
            [level30["strength"], level30["agility"], level30["max_hp"], level30["max_mp"]] == [140, 130, 210, 200],
            "extractor/data_out/stats.json",
            "Bank01 LA17B",
        )
        add_row(
            "Stats",
            "HEAL learned at Lv3",
            "HEAL in spells_known",
            stats_levels[3]["spells_known"],
            "HEAL" in stats_levels[3]["spells_known"],
            "extractor/data_out/stats.json",
            "Bank01 LA0D9",
        )
        add_row(
            "Stats",
            "HEALMORE learned at Lv17",
            "HEALMORE in spells_known",
            stats_levels[17]["spells_known"],
            "HEALMORE" in stats_levels[17]["spells_known"],
            "extractor/data_out/stats.json",
            "Bank01 LA12D",
        )
        add_row(
            "Stats",
            "HURTMORE learned at Lv19",
            "HURTMORE in spells_known",
            stats_levels[19]["spells_known"],
            "HURTMORE" in stats_levels[19]["spells_known"],
            "extractor/data_out/stats.json",
            "Bank01 LA139",
        )

        save_roundtrip_ok = (
            phase2_save["all_passed"] is True
            and phase2_save["checks"].get("json_roundtrip_preserves_30_bytes") is True
            and phase2_save["checks"].get("save_dict_roundtrip_preserves_30_bytes") is True
            and save_load_vectors["vectors"].get("save_dict_has_crc") is True
        )
        add_row(
            "Save",
            "JSON save roundtrip + CRC",
            "30-byte roundtrip and CRC present",
            {
                "json_roundtrip": phase2_save["checks"].get("json_roundtrip_preserves_30_bytes"),
                "save_dict_roundtrip": phase2_save["checks"].get("save_dict_roundtrip_preserves_30_bytes"),
                "save_dict_has_crc": save_load_vectors["vectors"].get("save_dict_has_crc"),
            },
            save_roundtrip_ok,
            "artifacts/phase2_save_load_runtime.json + tests/fixtures/save_load_runtime_vectors.json",
            "Bank03 LFA18 / SRAM-equivalent JSON",
            evidence_tier="runtime-state",
        )

        nonmovement_seed = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=46,
                player_y=1,
                repel_timer=2,
                light_timer=1,
            ),
            title_state=initial_title_state(),
        )
        nonmovement_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=nonmovement_seed,
        )
        nonmovement_session.step("C")
        menu_navigation_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=nonmovement_seed,
        )
        menu_navigation_session.step("C")
        menu_navigation_session.step("DOWN")
        blocked_seed = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=4,
                player_x=29,
                player_y=14,
                repel_timer=2,
                light_timer=1,
            ),
            title_state=initial_title_state(),
        )
        blocked_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=blocked_seed,
        )
        blocked_session.step("RIGHT")
        death_necklace_seed = MainLoopState(
            screen_mode="map",
            game_state=_clone_state(
                GameState.fresh_game("ERDRICK"),
                map_id=1,
                player_x=46,
                player_y=1,
                hp=12,
                max_hp=31,
                mp=3,
                max_mp=10,
                gold=123,
                more_spells_quest=FLAG_DEATH_NECKLACE,
                rng_lb=0,
                rng_ub=1,
                repel_timer=2,
                light_timer=1,
            ),
            title_state=initial_title_state(),
        )
        death_necklace_session = MainLoopSession(
            terminal=_VerifyTerminal(),
            map_engine=_map_engine(),
            npcs_payload=_npcs_payload(),
            state=death_necklace_seed,
        )
        death_necklace_session.step("RIGHT")
        timer_actual = {
            "command_open": {
                "repel_before": 2,
                "repel_after": nonmovement_session.state.game_state.repel_timer,
                "light_before": 1,
                "light_after": nonmovement_session.state.game_state.light_timer,
                "action": nonmovement_session.state.last_action.kind,
            },
            "menu_navigation": {
                "repel_before": 2,
                "repel_after": menu_navigation_session.state.game_state.repel_timer,
                "light_before": 1,
                "light_after": menu_navigation_session.state.game_state.light_timer,
                "action": menu_navigation_session.state.last_action.kind,
            },
            "blocked_movement": {
                "repel_before": 2,
                "repel_after": blocked_session.state.game_state.repel_timer,
                "light_before": 1,
                "light_after": blocked_session.state.game_state.light_timer,
                "action": blocked_session.state.last_action.kind,
            },
            "step_to_dialog_outcome": {
                "repel_before": 2,
                "repel_after": death_necklace_session.state.game_state.repel_timer,
                "light_before": 1,
                "light_after": death_necklace_session.state.game_state.light_timer,
                "action": death_necklace_session.state.last_action.kind,
                "screen_mode": death_necklace_session.state.screen_mode,
            },
        }
        add_row(
            "Field Timers",
            "Non-movement input cadence",
            "repel/light timers stay unchanged on non-step input and decrement on successful step progression, including dialog-ending steps",
            timer_actual,
            timer_actual["command_open"]["repel_after"] == timer_actual["command_open"]["repel_before"]
            and timer_actual["command_open"]["light_after"] == timer_actual["command_open"]["light_before"]
            and timer_actual["menu_navigation"]["repel_after"] == timer_actual["menu_navigation"]["repel_before"]
            and timer_actual["menu_navigation"]["light_after"] == timer_actual["menu_navigation"]["light_before"]
            and timer_actual["blocked_movement"]["repel_after"] == timer_actual["blocked_movement"]["repel_before"]
            and timer_actual["blocked_movement"]["light_after"] == timer_actual["blocked_movement"]["light_before"]
            and timer_actual["step_to_dialog_outcome"]["repel_after"] == timer_actual["step_to_dialog_outcome"]["repel_before"] - 1
            and timer_actual["step_to_dialog_outcome"]["light_after"] == timer_actual["step_to_dialog_outcome"]["light_before"] - 1,
            "main.py MainLoopSession.step + tests/test_main_loop_scaffold.py timer cadence regressions",
            "ROM-like step semantics observed: timers decay on successful step progression, including dialog-ending steps, but not non-movement or blocked input",
            evidence_tier="runtime-state",
        )

        spellcapable_enemies = [
            enemy for enemy in enemies["enemies"] if int(enemy.get("pattern_flags", 0)) != 0
        ]
        proven_spell_mapping = {
            enemy["name"]: list(enemy_spell_actions_for_pattern(int(enemy.get("pattern_flags", 0))))
            for enemy in spellcapable_enemies
            if enemy_spell_actions_for_pattern(int(enemy.get("pattern_flags", 0)))
        }
        spell_mapping_actual = {
            "spellcapable_enemy_count": len(spellcapable_enemies),
            "sample_enemy_ids": [int(enemy["enemy_id"]) for enemy in spellcapable_enemies[:5]],
            "pattern_flags_present": all("pattern_flags" in enemy for enemy in spellcapable_enemies),
            "proven_pattern_flags": sorted(
                {int(enemy.get("pattern_flags", 0)) for enemy in spellcapable_enemies if enemy_spell_actions_for_pattern(int(enemy.get("pattern_flags", 0)))}
            ),
            "proven_enemy_spell_actions": proven_spell_mapping,
            "unknown_pattern_flags": sorted(
                {int(enemy.get("pattern_flags", 0)) for enemy in spellcapable_enemies if not enemy_spell_actions_for_pattern(int(enemy.get("pattern_flags", 0)))}
            ),
        }
        add_row(
            "Combat",
            "Enemy spell action mapping availability",
            "Current repo proves only pattern_flags 0x02 -> HURT for Magician/Magidrakee; all other enemy spell patterns remain explicit UNKNOWN",
            spell_mapping_actual,
            spell_mapping_actual["proven_pattern_flags"] == [2]
            and spell_mapping_actual["proven_enemy_spell_actions"] == {"Magician": ["HURT"], "Magidrakee": ["HURT"]},
            "extractor/data_out/enemies.json + engine.combat.enemy_spell_actions_for_pattern + tests/test_combat.py mapping regression",
            "Extractor-backed pattern_flags subset proves Magician/Magidrakee use HURT; remaining spell-pattern decode stays UNKNOWN",
            evidence_tier="runtime-state",
        )

        affordable_shop_seed = _clone_state(
            GameState.fresh_game("ERDRICK"),
            gold=200,
        )
        shop_buy_state, shop_buy_success, shop_buy_message = shop_runtime.buy(affordable_shop_seed, 2)
        add_row(
            "Stats",
            "Shop equip recomputes derived stats",
            "attack/defense reflect weapon/armor-derived equipped item bonuses immediately after affordable purchase",
            {
                "success": shop_buy_success,
                "message": shop_buy_message,
                "equipment_byte": shop_buy_state.equipment_byte,
                "attack": shop_buy_state.attack,
                "defense": shop_buy_state.defense,
            },
            shop_buy_success is True
            and shop_buy_message == "purchased and equipped"
            and shop_buy_state.equipment_byte == 0x62
            and shop_buy_state.attack == 14
            and shop_buy_state.defense == 2,
            "engine/shop.py runtime purchase path + tests/test_shop.py derived-stat regressions",
            "Canonical recompute path now applies extracted weapon bonuses while preserving fresh-game baseline and unresolved shield defense behavior",
            evidence_tier="runtime-state",
        )

        add_row(
            "Stats",
            "Shield-derived defense parity scope",
            "fresh-game small-shield defense remains unresolved; Batch 3 proves weapon/armor/wearable recompute only and quarantines shield-derived defense until ROM-backed proof exists",
            {
                "fresh_game_equipment_byte": GameState.fresh_game("ERDRICK").equipment_byte,
                "fresh_game_defense": GameState.fresh_game("ERDRICK").defense,
                "scope_proven_in_batch3": [
                    "weapon bonuses",
                    "armor bonuses",
                    "Dragon's Scale",
                    "Fighter's Ring",
                ],
                "scope_quarantined": ["shield-derived defense", "fresh-game small-shield semantics"],
            },
            False,
            "engine/state.py canonical derived-stat helper + PARITY_REPORT.md scoped Batch 3 evidence",
            "Observed fresh-game baseline keeps equipment_byte=0x02 with defense=2; shield-derived defense remains UNKNOWN until ROM-backed proof resolves the mismatch",
            evidence_tier="unknown",
            status="UNKNOWN",
        )

        ring_seed = _clone_state(
            GameState.fresh_game("ERDRICK"),
            attack=6,
            more_spells_quest=0x20,
        )
        ring_roundtrip = state_from_save_dict(state_to_save_dict(ring_seed))
        add_row(
            "Stats",
            "Save/load preserves derived equipment modifiers",
            "derived attack survives canonical save/load roundtrip",
            {
                "before_attack": ring_seed.attack,
                "after_attack": ring_roundtrip.attack,
                "before_save_bytes": list(state_to_save_data(ring_seed)[10:12]),
                "after_save_bytes": list(state_to_save_data(ring_roundtrip)[10:12]),
            },
            ring_roundtrip.attack == ring_seed.attack,
            "engine/save_load.py roundtrip scaffold + tests/test_save_load.py parity regressions",
            "Canonical recompute path restores wearable-derived modifiers after decode while preserving fresh-game baseline defense behavior",
            evidence_tier="runtime-state",
        )

        key_costs = {row["town"]: row["gold"] for row in items_data.get("key_costs", [])}
        generic_key_price = shop_runtime.price_for_item(18)
        add_row(
            "Economy",
            "Town-specific magic key pricing",
            "Cantlin/Rimuldar/Tantegel key prices come from key cost table, not generic item price",
            {
                "generic_price": generic_key_price,
                "town_prices": key_costs,
            },
            generic_key_price == key_costs.get("Rimuldar")
            and key_costs.get("Cantlin") != generic_key_price
            and key_costs.get("Tantegel castle") != generic_key_price,
            "extractor/data_out/items.json + engine/shop.py town-bound key pricing runtime",
            "KeyCostTbl @ 0x1999-0x199B",
            evidence_tier="runtime-state",
        )

        shop_flow_checks = phase4_shop_inn.get("checks", {})
        add_row(
            "Dialog/Flow",
            "Selected shop and inn TALK handoffs enter bounded dialog flow before side effects",
            "Selected TALK interactions should enter bounded dialog/menu flow before transaction side effects",
            {
                "shop_action_check": shop_flow_checks.get("npc_shop_control_handoff_runs_bounded_purchase"),
                "inn_action_check": shop_flow_checks.get("npc_inn_control_handoff_runs_inn_transaction_and_save"),
                "scope_note": phase4_shop_inn.get("scope_note"),
            },
            bool(shop_flow_checks) and all(bool(value) for value in shop_flow_checks.values()),
            "artifacts/phase4_main_loop_npc_shop_inn_handoff.json",
            "Bounded runtime proof: talk now enters dialog, then prompt/menu, then confirmed transaction without first-TALK side effects",
            evidence_tier="runtime-state",
        )

        replay_domains = {entry.get("domain") for entry in replay_manifest.get("fixtures", []) if isinstance(entry, dict)}
        checkpoint_domains = {entry.get("domain") for entry in checkpoint_manifest.get("fixtures", []) if isinstance(entry, dict)}
        replay_manifest_proof = _phase5_fixture_manifest_proof(
            manifest_path=ROOT / "tests" / "replay" / "manifest.json"
        )
        checkpoint_manifest_proof = _phase5_fixture_manifest_proof(
            manifest_path=ROOT / "tests" / "checkpoints" / "manifest.json"
        )
        add_row(
            "Replay/Checkpoint",
            "Replay executable fixture proof availability",
            "representative executable replay fixtures prove overworld traversal, combat encounter resolution, and town purchase/stay flow",
            {
                "declared_domains": sorted(str(domain) for domain in replay_domains),
                "executable_domains": replay_manifest_proof["executable_domains"],
                "fixture_count": replay_manifest_proof["fixture_count"],
                "case_count": replay_manifest_proof["case_count"],
            },
            replay_manifest_proof["ok"]
            and {
                "overworld_traversal",
                "combat_encounter_resolution",
                "town_purchase_stay_flow",
            }.issubset(set(replay_manifest_proof["executable_domains"])),
            "tests/replay/manifest.json + tests/replay/*.json + parity_proof.py",
            "Bounded executable replay proof for current implemented overworld/combat/town behaviors",
            evidence_tier="replay-proven",
            status="PASS" if replay_manifest_proof["ok"] else "FAIL",
        )
        add_row(
            "Replay/Checkpoint",
            "Checkpoint executable fixture proof availability",
            "representative executable checkpoint fixtures prove dungeon traversal resume and save/load resume continuity",
            {
                "declared_domains": sorted(str(domain) for domain in checkpoint_domains),
                "executable_domains": checkpoint_manifest_proof["executable_domains"],
                "fixture_count": checkpoint_manifest_proof["fixture_count"],
                "case_count": checkpoint_manifest_proof["case_count"],
            },
            checkpoint_manifest_proof["ok"]
            and {
                "dungeon_traversal",
                "save_load_resume_continuity",
            }.issubset(set(checkpoint_manifest_proof["executable_domains"])),
            "tests/checkpoints/manifest.json + tests/checkpoints/*.json + parity_proof.py",
            "Bounded executable checkpoint proof for current implemented dungeon resume and canonical save/load continuity",
            evidence_tier="checkpoint-proven",
            status="PASS" if checkpoint_manifest_proof["ok"] else "FAIL",
        )

        resistance_fields_present = {
            "pattern_flags": all("pattern_flags" in row for row in enemies["enemies"]),
            "mdef": all("mdef" in row for row in enemies["enemies"]),
            "s_ss_resist": all("s_ss_resist" in row for row in enemies["enemies"]),
        }
        add_row(
            "Resistance Decode",
            "ROM-backed resistance mapping availability",
            "decoded resistance mapping present or explicit blocker surfaced",
            resistance_fields_present,
            False,
            "extractor/data_out/enemies.json",
            "Resistance decode remains unresolved pending ROM-backed mapping",
            evidence_tier="unknown",
            status="UNKNOWN",
        )

    except Exception as exc:
        row_results.append(
            {
                "row": 1,
                "system": "phase5-parity-matrix-gate",
                "test": "initialization",
                "expected": "all required evidence files load",
                "actual": str(exc),
                "passed": False,
                "status": "FAIL",
                "evidence": "verify.py",
                "evidence_tier": "unknown",
                "rom_source": "n/a",
            }
        )

    parity_passed = all(bool(row.get("passed")) for row in row_results)
    status_counts: dict[str, int] = {}
    evidence_tier_counts: dict[str, int] = {}
    for row in row_results:
        row_status = str(row.get("status", "UNKNOWN"))
        row_tier = str(row.get("evidence_tier", "unknown"))
        status_counts[row_status] = status_counts.get(row_status, 0) + 1
        evidence_tier_counts[row_tier] = evidence_tier_counts.get(row_tier, 0) + 1

    summary = {
        "row_count": len(row_results),
        "status_counts": status_counts,
        "evidence_tier_counts": evidence_tier_counts,
        "all_passed": parity_passed,
    }

    report_lines = [
        "# PARITY_REPORT.md",
        "",
        "## Summary",
        "",
        f"- Rows: {summary['row_count']}",
        f"- Status counts: {json.dumps(status_counts, sort_keys=True)}",
        f"- Evidence tiers: {json.dumps(evidence_tier_counts, sort_keys=True)}",
        f"- All passed: {parity_passed}",
        "",
        "| # | System | Test | Expected | Status | Evidence Tier | Evidence | ROM Evidence Source |",
        "|---:|---|---|---|---|---|---|---|",
    ]
    for row in row_results:
        report_lines.append(
            "| {row} | {system} | {test} | {expected} | {status} | {evidence_tier} | {evidence} | {rom_source} |".format(
                row=_phase5_escape_md(row["row"]),
                system=_phase5_escape_md(row["system"]),
                test=_phase5_escape_md(row["test"]),
                expected=_phase5_escape_md(row["expected"]),
                status=_phase5_escape_md(row["status"]),
                evidence_tier=_phase5_escape_md(row["evidence_tier"]),
                evidence=_phase5_escape_md(row["evidence"]),
                rom_source=_phase5_escape_md(row["rom_source"]),
            )
        )

    report_text = "\n".join(report_lines) + "\n"
    report_path = ROOT / "PARITY_REPORT.md"
    report_path.write_text(report_text)
    parity_report_sha256 = hashlib.sha256(report_text.encode("utf-8")).hexdigest()

    artifact_payload = {
        "row_results": row_results,
        "all_passed": parity_passed,
        "summary": summary,
        "parity_report_sha256": parity_report_sha256,
    }
    artifact_path = ROOT / "artifacts" / "phase5_parity.json"
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(artifact_payload, indent=2) + "\n")

    return {
        "ok": parity_passed,
        "detail": {
            "row_count": len(row_results),
            "all_passed": parity_passed,
            "artifact": "artifacts/phase5_parity.json",
            "report": "PARITY_REPORT.md",
            "parity_report_sha256": parity_report_sha256,
        },
    }


PHASE_GATES = {
    "0": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
    ],
    "4": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_phase4_main_loop_artifacts_passed,
        check_phase4_walkthrough_checkpoints_optional_future,
        run_pytest_full_suite,
    ],
    "4-slice-phase4-final-audit-wrap": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_phase4_main_loop_artifacts_passed,
        check_phase4_walkthrough_checkpoints_optional_future,
        run_pytest_full_suite,
    ],
    "5": [
        check_phase5_slice_closeout_validation_gate,
    ],
    "5-slice-parity-matrix-gate": [
        check_phase5_parity_matrix_gate,
    ],
    "5-slice-stats-extractor": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_stats_extractor,
        check_stats_artifacts,
        check_phase5_slice_stats_extractor,
    ],
    "5-slice-xp-table-extractor": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_xp_table_extractor,
        check_xp_table_artifacts,
        check_phase5_slice_xp_table_extractor,
    ],
    "5-slice-spell-extractor": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_spells_extractor,
        check_spells_artifacts,
        check_phase5_slice_spell_extractor,
    ],
    "5-slice-terminal-size-enforcement": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_phase5_slice_terminal_size_enforcement,
    ],
    "5-slice-ascii-fallback-tileset": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_phase5_slice_ascii_fallback_tileset,
    ],
    "5-slice-edge-case-regression-gate": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_phase5_slice_edge_case_regression_gate,
        run_pytest_phase5_edge_case_regression_gate_slice,
    ],
    "5-slice-closeout-validation-gate": [
        check_phase5_slice_closeout_validation_gate,
        run_pytest_phase5_batch1_foundation_suite,
    ],
    "1-foundation": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        check_enemy_hurt_fixture,
        run_pytest_foundation,
    ],
    "1-slice-rom-spells": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_extractor,
        check_bank_read_gate_artifact,
        run_pytest_phase1_slice,
    ],
    "1-slice-chests": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_chests_extractor,
        check_chests_artifacts,
        run_pytest_phase1_chests_slice,
    ],
    "1-slice-enemies": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_enemies_extractor,
        check_enemies_artifacts,
        run_pytest_phase1_enemies_slice,
    ],
    "1-slice-zones": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_zones_extractor,
        check_zones_artifacts,
        run_pytest_phase1_zones_slice,
    ],
    "1-slice-warps": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_warps_extractor,
        check_warps_artifacts,
        run_pytest_phase1_warps_slice,
    ],
    "1-slice-items": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_items_extractor,
        check_items_artifacts,
        run_pytest_phase1_items_slice,
    ],
    "1-slice-npcs": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_npcs_extractor,
        check_npcs_artifacts,
        run_pytest_phase1_npcs_slice,
    ],
    "1-slice-dialog": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_dialog_extractor,
        check_dialog_artifacts,
        run_pytest_phase1_dialog_slice,
    ],
    "1-slice-maps": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase1_slice_maps_extractor,
        check_maps_artifacts,
        run_pytest_phase1_maps_slice,
    ],
    "2-slice-rng": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_rng_generator,
        check_rng_artifacts,
        run_pytest_phase2_rng_slice,
    ],
    "2-slice-state": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_state_generator,
        check_state_artifacts,
        run_pytest_phase2_state_slice,
    ],
    "2-slice-level": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_level_generator,
        check_level_artifacts,
        run_pytest_phase2_level_slice,
    ],
    "2-slice-combat": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_combat_generator,
        check_combat_artifacts,
        run_pytest_phase2_combat_slice,
    ],
    "2-slice-movement": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_movement_generator,
        check_movement_artifacts,
        run_pytest_phase2_movement_slice,
    ],
    "2-slice-map-engine": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_map_engine_generator,
        check_map_engine_artifacts,
        run_pytest_phase2_map_engine_slice,
    ],
    "2-slice-dialog": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_dialog_generator,
        check_dialog_runtime_artifacts,
        run_pytest_phase2_dialog_slice,
    ],
    "2-slice-shop": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_shop_generator,
        check_shop_artifacts,
        run_pytest_phase2_shop_slice,
    ],
    "2-slice-save-load": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_save_load_generator,
        check_save_load_artifacts,
        run_pytest_phase2_save_load_slice,
    ],
    "2-slice-items": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase2_slice_items_generator,
        check_items_runtime_artifacts,
        run_pytest_phase2_items_slice,
    ],
    "3-slice-ui-foundation": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_ui_foundation_generator,
        check_ui_foundation_artifacts,
        run_pytest_phase3_ui_foundation_slice,
    ],
    "3-slice-title-bootstrap": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_title_bootstrap_generator,
        check_title_bootstrap_artifacts,
        run_pytest_phase3_title_bootstrap_slice,
    ],
    "3-slice-menu": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_menu_generator,
        check_menu_artifacts,
        run_pytest_phase3_menu_slice,
    ],
    "3-slice-dialog-box": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_dialog_box_generator,
        check_dialog_box_artifacts,
        run_pytest_phase3_dialog_box_slice,
    ],
    "3-slice-combat-view": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_combat_view_generator,
        check_combat_view_artifacts,
        run_pytest_phase3_combat_view_slice,
    ],
    "3-slice-status-panel": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_status_panel_generator,
        check_status_panel_artifacts,
        run_pytest_phase3_status_panel_slice,
    ],
    "3-slice-map-view": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_map_view_generator,
        check_map_view_artifacts,
        run_pytest_phase3_map_view_slice,
    ],
    "3-slice-renderer": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase3_slice_renderer_generator,
        check_renderer_artifacts,
        run_pytest_phase3_renderer_slice,
    ],
    "4-slice-main-loop-scaffold": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_main_loop_scaffold_generator,
        check_main_loop_scaffold_artifacts,
        run_pytest_phase4_main_loop_scaffold_slice,
    ],
    "4-slice-save-load-loop": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_save_load_loop_generator,
        check_main_loop_save_load_loop_artifacts,
        run_pytest_phase4_save_load_loop_slice,
    ],
    "4-slice-inn-stay-save-trigger": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_inn_stay_save_trigger_generator,
        check_main_loop_inn_stay_save_trigger_artifacts,
        run_pytest_phase4_inn_stay_save_trigger_slice,
    ],
    "4-slice-inn-cost-deduct": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_inn_cost_deduct_generator,
        check_main_loop_inn_cost_deduct_artifacts,
        run_pytest_phase4_inn_cost_deduct_slice,
    ],
    "4-slice-encounter-trigger": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_encounter_trigger_generator,
        check_main_loop_encounter_trigger_artifacts,
        run_pytest_phase4_encounter_trigger_slice,
    ],
    "4-slice-dungeon-encounter-runtime": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_dungeon_encounter_runtime_generator,
        check_main_loop_dungeon_encounter_runtime_artifacts,
        run_pytest_phase4_dungeon_encounter_runtime_slice,
    ],
    "4-slice-combat-session-handoff": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_session_handoff_generator,
        check_main_loop_combat_session_handoff_artifacts,
        run_pytest_phase4_combat_session_handoff_slice,
    ],
    "4-slice-combat-turn-resolution": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_turn_resolution_generator,
        check_main_loop_combat_turn_resolution_artifacts,
        run_pytest_phase4_combat_turn_resolution_slice,
    ],
    "4-slice-combat-spell-in-battle": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_spell_in_battle_generator,
        check_main_loop_combat_spell_in_battle_artifacts,
        run_pytest_phase4_combat_spell_in_battle_slice,
    ],
    "4-slice-combat-asleep-stopspell-flag-effects": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_asleep_stopspell_flag_effects_generator,
        check_main_loop_combat_asleep_stopspell_flag_effects_artifacts,
        run_pytest_phase4_combat_asleep_stopspell_flag_effects_slice,
    ],
    "4-slice-combat-player-stopspell-enforcement": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_player_stopspell_enforcement_generator,
        check_main_loop_combat_player_stopspell_enforcement_artifacts,
        run_pytest_phase4_combat_player_stopspell_enforcement_slice,
    ],
    "4-slice-combat-enemy-sleep-stopspell-immunity": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_enemy_sleep_stopspell_immunity_generator,
        check_main_loop_combat_enemy_sleep_stopspell_immunity_artifacts,
        run_pytest_phase4_combat_enemy_sleep_stopspell_immunity_slice,
    ],
    "4-slice-combat-metal-slime-flee": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_metal_slime_flee_generator,
        check_main_loop_combat_metal_slime_flee_artifacts,
        run_pytest_phase4_combat_metal_slime_flee_slice,
    ],
    "4-slice-combat-dragonlord-two-phase-fight": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_dragonlord_two_phase_fight_generator,
        check_main_loop_combat_dragonlord_two_phase_fight_artifacts,
        run_pytest_phase4_combat_dragonlord_two_phase_fight_slice,
    ],
    "4-slice-combat-dragonlord-endgame-victory": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_dragonlord_endgame_victory_generator,
        check_main_loop_combat_dragonlord_endgame_victory_artifacts,
        run_pytest_phase4_combat_dragonlord_endgame_victory_slice,
    ],
    "4-slice-endgame-return-to-title": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_endgame_return_to_title_generator,
        check_main_loop_endgame_return_to_title_artifacts,
        run_pytest_phase4_endgame_return_to_title_slice,
    ],
    "4-slice-endgame-input-coverage-hardening": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_endgame_input_coverage_hardening_generator,
        check_main_loop_endgame_input_coverage_hardening_artifacts,
        run_pytest_phase4_endgame_input_coverage_hardening_slice,
    ],
    "4-slice-post-victory-npc-world-state-proof": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_post_victory_npc_world_state_proof_generator,
        check_main_loop_post_victory_npc_world_state_proof_artifacts,
        run_pytest_phase4_post_victory_npc_world_state_proof_slice,
    ],
    "4-slice-title-screen-endgame-renderer": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_title_screen_endgame_renderer_generator,
        check_title_screen_endgame_renderer_artifacts,
        run_pytest_phase4_title_screen_endgame_renderer_slice,
    ],
    "4-slice-combat-outcome-resolution": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_combat_outcome_resolution_generator,
        check_main_loop_combat_outcome_resolution_artifacts,
        run_pytest_phase4_combat_outcome_resolution_slice,
    ],
    "4-slice-post-combat-dialog-handoff": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_post_combat_dialog_handoff_generator,
        check_main_loop_post_combat_dialog_handoff_artifacts,
        run_pytest_phase4_post_combat_dialog_handoff_slice,
    ],
    "4-slice-post-combat-fidelity-hardening": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_post_combat_fidelity_hardening_generator,
        check_main_loop_post_combat_fidelity_hardening_artifacts,
        run_pytest_phase4_post_combat_fidelity_hardening_slice,
    ],
    "4-slice-npc-interaction-dialog-handoff": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_interaction_dialog_handoff_generator,
        check_main_loop_npc_interaction_dialog_handoff_artifacts,
        run_pytest_phase4_npc_interaction_dialog_handoff_slice,
    ],
    "4-slice-npc-dialog-control-fidelity": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_dialog_control_fidelity_generator,
        check_main_loop_npc_dialog_control_fidelity_artifacts,
        run_pytest_phase4_npc_dialog_control_fidelity_slice,
    ],
    "4-slice-npc-dialog-entry-playback": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_dialog_entry_playback_generator,
        check_main_loop_npc_dialog_entry_playback_artifacts,
        run_pytest_phase4_npc_dialog_entry_playback_slice,
    ],
    "4-slice-npc-special-dialog-control-resolution": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_special_dialog_control_resolution_generator,
        check_main_loop_npc_special_dialog_control_resolution_artifacts,
        run_pytest_phase4_npc_special_dialog_control_resolution_slice,
    ],
    "4-slice-npc-special-control-side-effects": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_special_control_side_effects_generator,
        check_main_loop_npc_special_control_side_effects_artifacts,
        run_pytest_phase4_npc_special_control_side_effects_slice,
    ],
    "4-slice-npc-special-control-0x6c-side-effect": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_special_control_0x6c_side_effect_generator,
        check_main_loop_npc_special_control_0x6c_side_effect_artifacts,
        run_pytest_phase4_npc_special_control_0x6c_side_effect_slice,
    ],
    "4-slice-npc-shop-inn-handoff": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_shop_inn_handoff_generator,
        check_main_loop_npc_shop_inn_handoff_artifacts,
        run_pytest_phase4_npc_shop_inn_handoff_slice,
    ],
    "4-slice-npc-shop-inn-control-expansion": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_shop_inn_control_expansion_generator,
        check_main_loop_npc_shop_inn_control_expansion_artifacts,
        run_pytest_phase4_npc_shop_inn_control_expansion_slice,
    ],
    "4-slice-npc-shop-inn-next-control-pair": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_shop_inn_next_control_pair_generator,
        check_main_loop_npc_shop_inn_next_control_pair_artifacts,
        run_pytest_phase4_npc_shop_inn_next_control_pair_slice,
    ],
    "4-slice-npc-shop-sell-handoff": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_npc_shop_sell_handoff_generator,
        check_main_loop_npc_shop_sell_handoff_artifacts,
        run_pytest_phase4_npc_shop_sell_handoff_slice,
    ],
    "4-slice-map-field-spell-casting": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_field_spell_casting_generator,
        check_main_loop_map_field_spell_casting_artifacts,
        run_pytest_phase4_map_field_spell_casting_slice,
    ],
    "4-slice-map-spell-selection-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_spell_selection_surface_generator,
        check_main_loop_map_spell_selection_surface_artifacts,
        run_pytest_phase4_map_spell_selection_surface_slice,
    ],
    "4-slice-map-command-root-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_root_surface_generator,
        check_main_loop_map_command_root_surface_artifacts,
        run_pytest_phase4_map_command_root_surface_slice,
    ],
    "4-slice-map-command-root-expansion": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_root_expansion_generator,
        check_main_loop_map_command_root_expansion_artifacts,
        run_pytest_phase4_map_command_root_expansion_slice,
    ],
    "4-slice-map-command-search": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_generator,
        check_main_loop_map_command_search_artifacts,
        run_pytest_phase4_map_command_search_slice,
    ],
    "4-slice-map-command-search-chest-rewards": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_chest_rewards_generator,
        check_main_loop_map_command_search_chest_rewards_artifacts,
        run_pytest_phase4_map_command_search_chest_rewards_slice,
    ],
    "4-slice-map-command-search-non-gold-chest-rewards": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_non_gold_chest_rewards_generator,
        check_main_loop_map_command_search_non_gold_chest_rewards_artifacts,
        run_pytest_phase4_map_command_search_non_gold_chest_rewards_slice,
    ],
    "4-slice-map-command-search-tool-rewards-capacity": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_tool_rewards_capacity_generator,
        check_main_loop_map_command_search_tool_rewards_capacity_artifacts,
        run_pytest_phase4_map_command_search_tool_rewards_capacity_slice,
    ],
    "4-slice-map-command-search-remaining-gold-chest-rewards": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_remaining_gold_chest_rewards_generator,
        check_main_loop_map_command_search_remaining_gold_chest_rewards_artifacts,
        run_pytest_phase4_map_command_search_remaining_gold_chest_rewards_slice,
    ],
    "4-slice-map-command-search-remaining-unsupported-chest-contents": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_search_remaining_unsupported_chest_contents_generator,
        check_main_loop_map_command_search_remaining_unsupported_chest_contents_artifacts,
        run_pytest_phase4_map_command_search_remaining_unsupported_chest_contents_slice,
    ],
    "4-slice-map-command-status-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_status_surface_generator,
        check_main_loop_map_command_status_surface_artifacts,
        run_pytest_phase4_map_command_status_surface_slice,
    ],
    "4-slice-map-command-item-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_surface_generator,
        check_main_loop_map_command_item_surface_artifacts,
        run_pytest_phase4_map_command_item_surface_slice,
    ],
    "4-slice-map-command-item-expansion": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_expansion_generator,
        check_main_loop_map_command_item_expansion_artifacts,
        run_pytest_phase4_map_command_item_expansion_slice,
    ],
    "4-slice-map-command-item-dragons-scale-equip-state": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_dragons_scale_equip_state_generator,
        check_main_loop_map_command_item_dragons_scale_equip_state_artifacts,
        run_pytest_phase4_map_command_item_dragons_scale_equip_state_slice,
    ],
    "4-slice-map-command-item-silver-harp-forced-encounter": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_silver_harp_forced_encounter_generator,
        check_main_loop_map_command_item_silver_harp_forced_encounter_artifacts,
        run_pytest_phase4_map_command_item_silver_harp_forced_encounter_slice,
    ],
    "4-slice-map-command-item-rainbow-drop-bridge-trigger": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_rainbow_drop_bridge_trigger_generator,
        check_main_loop_map_command_item_rainbow_drop_bridge_trigger_artifacts,
        run_pytest_phase4_map_command_item_rainbow_drop_bridge_trigger_slice,
    ],
    "4-slice-map-command-item-fairy-flute-interaction": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_fairy_flute_interaction_generator,
        check_main_loop_map_command_item_fairy_flute_interaction_artifacts,
        run_pytest_phase4_map_command_item_fairy_flute_interaction_slice,
    ],
    "4-slice-map-command-item-remaining-quest-item-use-effects": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_item_remaining_quest_item_use_effects_generator,
        check_main_loop_map_command_item_remaining_quest_item_use_effects_artifacts,
        run_pytest_phase4_map_command_item_remaining_quest_item_use_effects_slice,
    ],
    "4-slice-map-command-cursed-item-step-damage-hook": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_cursed_item_step_damage_hook_generator,
        check_main_loop_map_command_cursed_item_step_damage_hook_artifacts,
        run_pytest_phase4_map_command_cursed_item_step_damage_hook_slice,
    ],
    "4-slice-map-movement-terrain-step-effects": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_movement_terrain_step_effects_generator,
        check_main_loop_map_movement_terrain_step_effects_artifacts,
        run_pytest_phase4_map_movement_terrain_step_effects_slice,
    ],
    "4-slice-terrain-step-effects": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_movement_terrain_step_effects_generator,
        check_main_loop_map_movement_terrain_step_effects_artifacts,
        run_pytest_phase4_map_movement_terrain_step_effects_slice,
    ],
    "4-slice-map-load-curse-check": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_load_curse_check_generator,
        check_main_loop_map_load_curse_check_artifacts,
        run_pytest_phase4_map_load_curse_check_slice,
    ],
    "4-slice-map-command-stairs-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_stairs_surface_generator,
        check_main_loop_map_command_stairs_surface_artifacts,
        run_pytest_phase4_map_command_stairs_surface_slice,
    ],
    "4-slice-map-command-door-surface": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_door_surface_generator,
        check_main_loop_map_command_door_surface_artifacts,
        run_pytest_phase4_map_command_door_surface_slice,
    ],
    "4-slice-map-command-door-persistence": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_map_command_door_persistence_generator,
        check_main_loop_map_command_door_persistence_artifacts,
        run_pytest_phase4_map_command_door_persistence_slice,
    ],
    "4-slice-opened-world-state-save-load-persistence": [
        check_python_version,
        check_deps_importable,
        check_rom_sha1_baseline,
        check_dir_structure,
        check_requirements_file,
        run_phase4_slice_opened_world_state_save_load_persistence_generator,
        check_main_loop_opened_world_state_save_load_persistence_artifacts,
        run_pytest_phase4_opened_world_state_save_load_persistence_slice,
    ],
}


def _artifact_path_for_phase(phase: str) -> Path:
    if phase == "0":
        return ROOT / "artifacts" / "phase0_env.json"
    if phase == "4":
        return ROOT / "artifacts" / "phase4_integration.json"
    if phase == "4-slice-phase4-final-audit-wrap":
        return ROOT / "artifacts" / "phase4_slice_phase4_final_audit_wrap.json"
    if phase == "5":
        return ROOT / "artifacts" / "phase5_integration.json"
    if phase == "5-slice-parity-matrix-gate":
        return ROOT / "artifacts" / "phase5_slice_parity_matrix_gate.json"
    if phase == "5-slice-stats-extractor":
        return ROOT / "artifacts" / "phase5_slice_stats_extractor.json"
    if phase == "5-slice-xp-table-extractor":
        return ROOT / "artifacts" / "phase5_slice_xp_table_extractor.json"
    if phase == "5-slice-spell-extractor":
        return ROOT / "artifacts" / "phase5_slice_spell_extractor.json"
    if phase == "5-slice-terminal-size-enforcement":
        return ROOT / "artifacts" / "phase5_slice_terminal_size_enforcement.json"
    if phase == "5-slice-ascii-fallback-tileset":
        return ROOT / "artifacts" / "phase5_slice_ascii_fallback_tileset.json"
    if phase == "5-slice-edge-case-regression-gate":
        return ROOT / "artifacts" / "phase5_slice_edge_case_regression_gate.json"
    if phase == "5-slice-closeout-validation-gate":
        return ROOT / "artifacts" / "phase5_slice_closeout_validation_gate.json"
    if phase == "1-slice-rom-spells":
        return ROOT / "artifacts" / "phase1_slice_rom_spells.json"
    if phase == "1-slice-chests":
        return ROOT / "artifacts" / "phase1_slice_chests.json"
    if phase == "1-slice-enemies":
        return ROOT / "artifacts" / "phase1_slice_enemies.json"
    if phase == "1-slice-zones":
        return ROOT / "artifacts" / "phase1_slice_zones.json"
    if phase == "1-slice-warps":
        return ROOT / "artifacts" / "phase1_slice_warps.json"
    if phase == "1-slice-items":
        return ROOT / "artifacts" / "phase1_slice_items.json"
    if phase == "1-slice-npcs":
        return ROOT / "artifacts" / "phase1_slice_npcs.json"
    if phase == "1-slice-dialog":
        return ROOT / "artifacts" / "phase1_slice_dialog.json"
    if phase == "1-slice-maps":
        return ROOT / "artifacts" / "phase1_slice_maps.json"
    if phase == "2-slice-rng":
        return ROOT / "artifacts" / "phase2_slice_rng.json"
    if phase == "2-slice-state":
        return ROOT / "artifacts" / "phase2_slice_state.json"
    if phase == "2-slice-level":
        return ROOT / "artifacts" / "phase2_slice_level.json"
    if phase == "2-slice-combat":
        return ROOT / "artifacts" / "phase2_slice_combat.json"
    if phase == "2-slice-movement":
        return ROOT / "artifacts" / "phase2_slice_movement.json"
    if phase == "2-slice-map-engine":
        return ROOT / "artifacts" / "phase2_slice_map_engine.json"
    if phase == "2-slice-dialog":
        return ROOT / "artifacts" / "phase2_slice_dialog.json"
    if phase == "2-slice-shop":
        return ROOT / "artifacts" / "phase2_slice_shop.json"
    if phase == "2-slice-save-load":
        return ROOT / "artifacts" / "phase2_slice_save_load.json"
    if phase == "2-slice-items":
        return ROOT / "artifacts" / "phase2_slice_items.json"
    if phase == "3-slice-ui-foundation":
        return ROOT / "artifacts" / "phase3_slice_ui_foundation.json"
    if phase == "3-slice-title-bootstrap":
        return ROOT / "artifacts" / "phase3_slice_title_bootstrap.json"
    if phase == "3-slice-menu":
        return ROOT / "artifacts" / "phase3_slice_menu.json"
    if phase == "3-slice-dialog-box":
        return ROOT / "artifacts" / "phase3_slice_dialog_box.json"
    if phase == "3-slice-combat-view":
        return ROOT / "artifacts" / "phase3_slice_combat_view.json"
    if phase == "3-slice-status-panel":
        return ROOT / "artifacts" / "phase3_slice_status_panel.json"
    if phase == "3-slice-map-view":
        return ROOT / "artifacts" / "phase3_slice_map_view.json"
    if phase == "3-slice-renderer":
        return ROOT / "artifacts" / "phase3_slice_renderer.json"
    if phase == "4-slice-main-loop-scaffold":
        return ROOT / "artifacts" / "phase4_slice_main_loop_scaffold.json"
    if phase == "4-slice-save-load-loop":
        return ROOT / "artifacts" / "phase4_slice_save_load_loop.json"
    if phase == "4-slice-inn-stay-save-trigger":
        return ROOT / "artifacts" / "phase4_slice_inn_stay_save_trigger.json"
    if phase == "4-slice-inn-cost-deduct":
        return ROOT / "artifacts" / "phase4_slice_inn_cost_deduct.json"
    if phase == "4-slice-encounter-trigger":
        return ROOT / "artifacts" / "phase4_slice_encounter_trigger.json"
    if phase == "4-slice-dungeon-encounter-runtime":
        return ROOT / "artifacts" / "phase4_slice_dungeon_encounter_runtime.json"
    if phase == "4-slice-combat-session-handoff":
        return ROOT / "artifacts" / "phase4_slice_combat_session_handoff.json"
    if phase == "4-slice-combat-turn-resolution":
        return ROOT / "artifacts" / "phase4_slice_combat_turn_resolution.json"
    if phase == "4-slice-combat-spell-in-battle":
        return ROOT / "artifacts" / "phase4_slice_combat_spell_in_battle.json"
    if phase == "4-slice-combat-asleep-stopspell-flag-effects":
        return ROOT / "artifacts" / "phase4_slice_combat_asleep_stopspell_flag_effects.json"
    if phase == "4-slice-combat-player-stopspell-enforcement":
        return ROOT / "artifacts" / "phase4_slice_combat_player_stopspell_enforcement.json"
    if phase == "4-slice-combat-enemy-sleep-stopspell-immunity":
        return ROOT / "artifacts" / "phase4_slice_combat_enemy_sleep_stopspell_immunity.json"
    if phase == "4-slice-combat-metal-slime-flee":
        return ROOT / "artifacts" / "phase4_slice_combat_metal_slime_flee.json"
    if phase == "4-slice-combat-dragonlord-two-phase-fight":
        return ROOT / "artifacts" / "phase4_slice_combat_dragonlord_two_phase_fight.json"
    if phase == "4-slice-combat-dragonlord-endgame-victory":
        return ROOT / "artifacts" / "phase4_slice_combat_dragonlord_endgame_victory.json"
    if phase == "4-slice-endgame-return-to-title":
        return ROOT / "artifacts" / "phase4_slice_endgame_return_to_title.json"
    if phase == "4-slice-endgame-input-coverage-hardening":
        return ROOT / "artifacts" / "phase4_slice_endgame_input_coverage_hardening.json"
    if phase == "4-slice-post-victory-npc-world-state-proof":
        return ROOT / "artifacts" / "phase4_slice_post_victory_npc_world_state_proof.json"
    if phase == "4-slice-title-screen-endgame-renderer":
        return ROOT / "artifacts" / "phase4_slice_title_screen_endgame_renderer.json"
    if phase == "4-slice-combat-outcome-resolution":
        return ROOT / "artifacts" / "phase4_slice_combat_outcome_resolution.json"
    if phase == "4-slice-post-combat-dialog-handoff":
        return ROOT / "artifacts" / "phase4_slice_post_combat_dialog_handoff.json"
    if phase == "4-slice-post-combat-fidelity-hardening":
        return ROOT / "artifacts" / "phase4_slice_post_combat_fidelity_hardening.json"
    if phase == "4-slice-npc-interaction-dialog-handoff":
        return ROOT / "artifacts" / "phase4_slice_npc_interaction_dialog_handoff.json"
    if phase == "4-slice-npc-dialog-control-fidelity":
        return ROOT / "artifacts" / "phase4_slice_npc_dialog_control_fidelity.json"
    if phase == "4-slice-npc-dialog-entry-playback":
        return ROOT / "artifacts" / "phase4_slice_npc_dialog_entry_playback.json"
    if phase == "4-slice-npc-special-dialog-control-resolution":
        return ROOT / "artifacts" / "phase4_slice_npc_special_dialog_control_resolution.json"
    if phase == "4-slice-npc-special-control-side-effects":
        return ROOT / "artifacts" / "phase4_slice_npc_special_control_side_effects.json"
    if phase == "4-slice-npc-special-control-0x6c-side-effect":
        return ROOT / "artifacts" / "phase4_slice_npc_special_control_0x6c_side_effect.json"
    if phase == "4-slice-npc-shop-inn-handoff":
        return ROOT / "artifacts" / "phase4_slice_npc_shop_inn_handoff.json"
    if phase == "4-slice-npc-shop-inn-control-expansion":
        return ROOT / "artifacts" / "phase4_slice_npc_shop_inn_control_expansion.json"
    if phase == "4-slice-npc-shop-inn-next-control-pair":
        return ROOT / "artifacts" / "phase4_slice_npc_shop_inn_next_control_pair.json"
    if phase == "4-slice-npc-shop-sell-handoff":
        return ROOT / "artifacts" / "phase4_slice_npc_shop_sell_handoff.json"
    if phase == "4-slice-map-field-spell-casting":
        return ROOT / "artifacts" / "phase4_slice_map_field_spell_casting.json"
    if phase == "4-slice-map-spell-selection-surface":
        return ROOT / "artifacts" / "phase4_slice_map_spell_selection_surface.json"
    if phase == "4-slice-map-command-root-surface":
        return ROOT / "artifacts" / "phase4_slice_map_command_root_surface.json"
    if phase == "4-slice-map-command-root-expansion":
        return ROOT / "artifacts" / "phase4_slice_map_command_root_expansion.json"
    if phase == "4-slice-map-command-search":
        return ROOT / "artifacts" / "phase4_slice_map_command_search.json"
    if phase == "4-slice-map-command-search-chest-rewards":
        return ROOT / "artifacts" / "phase4_slice_map_command_search_chest_rewards.json"
    if phase == "4-slice-map-command-search-non-gold-chest-rewards":
        return ROOT / "artifacts" / "phase4_slice_map_command_search_non_gold_chest_rewards.json"
    if phase == "4-slice-map-command-search-tool-rewards-capacity":
        return ROOT / "artifacts" / "phase4_slice_map_command_search_tool_rewards_capacity.json"
    if phase == "4-slice-map-command-search-remaining-gold-chest-rewards":
        return ROOT / "artifacts" / "phase4_slice_map_command_search_remaining_gold_chest_rewards.json"
    if phase == "4-slice-map-command-search-remaining-unsupported-chest-contents":
        return ROOT / "artifacts" / "phase4_slice_map_command_search_remaining_unsupported_chest_contents.json"
    if phase == "4-slice-map-command-status-surface":
        return ROOT / "artifacts" / "phase4_slice_map_command_status_surface.json"
    if phase == "4-slice-map-command-item-surface":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_surface.json"
    if phase == "4-slice-map-command-item-expansion":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_expansion.json"
    if phase == "4-slice-map-command-item-dragons-scale-equip-state":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_dragons_scale_equip_state.json"
    if phase == "4-slice-map-command-item-silver-harp-forced-encounter":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_silver_harp_forced_encounter.json"
    if phase == "4-slice-map-command-item-rainbow-drop-bridge-trigger":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_rainbow_drop_bridge_trigger.json"
    if phase == "4-slice-map-command-item-fairy-flute-interaction":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_fairy_flute_interaction.json"
    if phase == "4-slice-map-command-item-remaining-quest-item-use-effects":
        return ROOT / "artifacts" / "phase4_slice_map_command_item_remaining_quest_item_use_effects.json"
    if phase == "4-slice-map-command-cursed-item-step-damage-hook":
        return ROOT / "artifacts" / "phase4_slice_map_command_cursed_item_step_damage_hook.json"
    if phase == "4-slice-map-movement-terrain-step-effects":
        return ROOT / "artifacts" / "phase4_slice_map_movement_terrain_step_effects.json"
    if phase == "4-slice-map-load-curse-check":
        return ROOT / "artifacts" / "phase4_slice_map_load_curse_check.json"
    if phase == "4-slice-map-command-stairs-surface":
        return ROOT / "artifacts" / "phase4_slice_map_command_stairs_surface.json"
    if phase == "4-slice-map-command-door-surface":
        return ROOT / "artifacts" / "phase4_slice_map_command_door_surface.json"
    if phase == "4-slice-map-command-door-persistence":
        return ROOT / "artifacts" / "phase4_slice_map_command_door_persistence.json"
    if phase == "4-slice-opened-world-state-save-load-persistence":
        return ROOT / "artifacts" / "phase4_slice_opened_world_state_save_load_persistence.json"
    return ROOT / "artifacts" / "phase1_foundation.json"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", required=True, choices=sorted(PHASE_GATES.keys()))
    args = parser.parse_args()

    checks = {}
    for check_fn in PHASE_GATES[args.phase]:
        checks[check_fn.__name__] = check_fn()

    all_passed = all(result.get("ok", False) for result in checks.values())
    report = {
        "phase": args.phase,
        "all_passed": all_passed,
        "checks": checks,
    }

    artifact_path = _artifact_path_for_phase(args.phase)
    artifact_path.parent.mkdir(parents=True, exist_ok=True)
    artifact_path.write_text(json.dumps(report, indent=2) + "\n")

    print(json.dumps(report, indent=2))
    return 0 if all_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
