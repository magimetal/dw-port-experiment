import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_bank_read_gate_artifact_exists_and_has_required_labels() -> None:
    artifact = ROOT / "artifacts" / "phase1_bank_read_gate.json"
    assert artifact.exists(), "run extractor/run_phase1_slice_rom_spells.py first"

    data = json.loads(artifact.read_text())
    assert data["completed"] is True

    bank00 = data["files"]["Bank00.asm"]
    bank03 = data["files"]["Bank03.asm"]

    assert bank00["bytes"] > 300_000
    assert bank03["bytes"] > 400_000

    assert bank00["labels_checked"]["WrldMapPtrTbl"] is True
    assert bank03["labels_checked"]["SpellCostTbl"] is True
    assert bank03["labels_checked"]["CheckMP"] is True
