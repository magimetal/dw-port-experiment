import json
from pathlib import Path

import pytest

from engine.rng import DW1RNG
import engine.run_phase2_slice_rng as rng_slice


ROOT = Path(__file__).resolve().parents[1]


def _load_rng_fixture() -> dict:
    fixture_path = ROOT / "tests" / "fixtures" / "rng_golden_sequence.json"
    assert fixture_path.exists(), "run python3 -m engine.run_phase2_slice_rng first"
    return json.loads(fixture_path.read_text())


def test_rng_output_domain_across_seed_grid() -> None:
    for seed_lb in range(0, 256, 17):
        for seed_ub in range(0, 256, 19):
            rng = DW1RNG(seed_lb, seed_ub)
            for _ in range(64):
                value = rng.tick()
                assert 0 <= value <= 0xFF
                assert 0 <= rng.rng_lb <= 0xFF
                assert 0 <= rng.rng_ub <= 0xFF


def test_rng_determinism() -> None:
    first = DW1RNG(0x12, 0x34)
    second = DW1RNG(0x12, 0x34)
    assert [first.tick() for _ in range(128)] == [second.tick() for _ in range(128)]


def test_rng_golden_fixture_sequence() -> None:
    fixture = _load_rng_fixture()
    sequence = fixture["sequence"]
    seed_lb = fixture["seed_lb"]
    seed_ub = fixture["seed_ub"]
    expected_len = 1000 if fixture.get("method") == "py65" else 20

    assert fixture.get("method")
    assert len(sequence) == expected_len

    rng = DW1RNG(seed_lb, seed_ub)
    produced = [rng.tick() for _ in range(len(sequence))]
    assert produced == sequence


def test_rng_range_uses_rng_ub_mod_n() -> None:
    rng = DW1RNG(0x00, 0x00)
    result = rng.range(5)
    assert result == 0


@pytest.mark.parametrize("n", [0, -1, -99])
def test_rng_range_rejects_non_positive_bounds(n: int) -> None:
    rng = DW1RNG(0x00, 0x00)
    with pytest.raises(ValueError):
        rng.range(n)


def test_rng_artifacts_exist_and_are_consistent() -> None:
    fixture = _load_rng_fixture()
    read_gate_path = ROOT / "artifacts" / "phase2_rng_read_gate.json"
    slice_artifact_path = ROOT / "artifacts" / "phase2_rng_fixture.json"

    assert read_gate_path.exists(), "run python3 -m engine.run_phase2_slice_rng first"
    assert slice_artifact_path.exists(), "run python3 -m engine.run_phase2_slice_rng first"

    read_gate = json.loads(read_gate_path.read_text())
    artifact = json.loads(slice_artifact_path.read_text())

    assert read_gate["completed"] is True
    assert read_gate["files"]["Bank03.asm"]["labels_checked"]["UpdateRandNum"] is True

    assert artifact["slice"] == "phase2-rng"
    assert artifact["method"] == fixture["method"]
    assert artifact["sequence_count"] == len(fixture["sequence"])
    assert artifact["baseline_match"] is True
    assert fixture["rom"]["baseline_match"] is True


def _setup_rng_slice_tmp_root(tmp_path: Path) -> Path:
    (tmp_path / "engine").mkdir(parents=True, exist_ok=True)
    module_path = tmp_path / "engine" / "run_phase2_slice_rng.py"
    module_path.write_text("# test placeholder\n")

    (tmp_path / "extractor").mkdir(parents=True, exist_ok=True)
    (tmp_path / "extractor" / "rom_baseline.json").write_text(
        json.dumps(
            {
                "rom_file": "dragon-warrior-1.nes",
                "accepted_sha1": "fixture-sha1",
            }
        )
    )
    (tmp_path / "dragon-warrior-1.nes").write_bytes(b"\x00" * 0x10020)
    return module_path


def test_rng_slice_raises_non_availability_py65_errors(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _setup_rng_slice_tmp_root(tmp_path)

    monkeypatch.setattr(rng_slice, "__file__", str(module_path))
    monkeypatch.setattr(rng_slice, "_sha1", lambda _path: "fixture-sha1")
    monkeypatch.setattr(
        rng_slice,
        "_collect_rng_read_gate",
        lambda _path: {
            "completed": True,
            "files": {"Bank03.asm": {"labels_checked": {"UpdateRandNum": True}}},
        },
    )
    monkeypatch.setattr(
        rng_slice,
        "_generate_rng_sequence_py65",
        lambda _rom_bytes, count=1000: (_ for _ in ()).throw(RuntimeError("bad opcode")),
    )

    with pytest.raises(RuntimeError, match="bad opcode"):
        rng_slice.main()


def test_rng_slice_preserves_existing_py65_fixture_when_py65_missing(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    module_path = _setup_rng_slice_tmp_root(tmp_path)

    fixture_path = tmp_path / "tests" / "fixtures" / "rng_golden_sequence.json"
    fixture_path.parent.mkdir(parents=True, exist_ok=True)
    existing_fixture = {
        "seed_lb": 0,
        "seed_ub": 0,
        "method": "py65",
        "rom": {
            "path": "dragon-warrior-1.nes",
            "sha1": "fixture-sha1",
            "accepted_sha1": "fixture-sha1",
            "baseline_match": True,
        },
        "sequence": [0] * 1000,
    }
    original_text = json.dumps(existing_fixture, indent=2) + "\n"
    fixture_path.write_text(original_text)

    monkeypatch.setattr(rng_slice, "__file__", str(module_path))
    monkeypatch.setattr(rng_slice, "_sha1", lambda _path: "fixture-sha1")
    monkeypatch.setattr(
        rng_slice,
        "_collect_rng_read_gate",
        lambda _path: {
            "completed": True,
            "files": {"Bank03.asm": {"labels_checked": {"UpdateRandNum": True}}},
        },
    )
    monkeypatch.setattr(
        rng_slice,
        "_generate_rng_sequence_py65",
        lambda _rom_bytes, count=1000: (_ for _ in ()).throw(
            ModuleNotFoundError("No module named 'py65'")
        ),
    )
    monkeypatch.setattr(
        rng_slice,
        "_generate_rng_sequence_fallback",
        lambda count=20: (_ for _ in ()).throw(AssertionError("fallback should not run")),
    )

    assert rng_slice.main() == 0

    assert fixture_path.read_text() == original_text
    artifact = json.loads((tmp_path / "artifacts" / "phase2_rng_fixture.json").read_text())
    assert artifact["method"] == "py65"
    assert artifact["sequence_count"] == 1000
