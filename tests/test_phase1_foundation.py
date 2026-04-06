import json
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_enemy_hurt_fixture_exists_and_matches_corrected_range() -> None:
    fixture = ROOT / "tests" / "fixtures" / "enemy_hurt_range.json"
    data = json.loads(fixture.read_text())

    assert data["min"] == 3
    assert data["max"] == 10
    assert "LEC23" in data["source"]


def test_foundation_directories_exist() -> None:
    required = [
        ROOT / "extractor" / "data_out",
        ROOT / "engine",
        ROOT / "ui",
        ROOT / "tests" / "fixtures",
        ROOT / "tests" / "replay",
        ROOT / "tests" / "checkpoints",
        ROOT / "artifacts",
    ]
    for path in required:
        assert path.is_dir(), f"Missing required directory: {path}"


def test_rom_baseline_configuration_present() -> None:
    baseline_path = ROOT / "extractor" / "rom_baseline.json"
    baseline = json.loads(baseline_path.read_text())

    assert baseline["rom_file"] == "dragon-warrior-1.nes"
    assert len(baseline["accepted_sha1"]) == 40
