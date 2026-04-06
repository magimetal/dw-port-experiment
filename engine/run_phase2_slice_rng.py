#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_rng_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()
    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {
                    "UpdateRandNum": "UpdateRandNum" in bank03_text,
                },
            }
        },
    }


def _generate_rng_sequence_py65(rom_bytes: bytes, count: int = 1000) -> list[int]:
    from py65.devices.mpu6502 import MPU

    mpu = MPU()
    bank3_data = rom_bytes[0xC010:0x10010]
    for i, value in enumerate(bank3_data):
        mpu.memory[0xC000 + i] = value

    mpu.memory[0x0094] = 0x00  # RandNumLB
    mpu.memory[0x0095] = 0x00  # RandNumUB

    sequence: list[int] = []
    for _ in range(count):
        mpu.pc = 0xC55B
        while mpu.pc != 0xC586:
            mpu.step()
        sequence.append(mpu.memory[0x0094])
    return sequence


def _generate_rng_sequence_fallback(count: int = 20) -> list[int]:
    rng_lb = 0
    rng_ub = 0
    sequence: list[int] = []

    for _ in range(count):
        original_ub = rng_ub
        original_lb = rng_lb

        carry = (rng_lb >> 7) & 0x01
        rng_lb = (rng_lb << 1) & 0xFF
        rng_ub = ((rng_ub << 1) | carry) & 0xFF

        total = rng_lb + original_lb
        rng_lb = total & 0xFF
        carry = 1 if total > 0xFF else 0

        total = rng_ub + original_ub + carry
        rng_ub = total & 0xFF

        rng_ub = (rng_lb + rng_ub) & 0xFF

        total = rng_lb + 0x81
        rng_lb = total & 0xFF
        carry = 1 if total > 0xFF else 0

        rng_ub = (rng_ub + carry) & 0xFF
        sequence.append(rng_lb)

    return sequence


def _is_py65_unavailable_error(error: Exception) -> bool:
    current: BaseException | None = error
    seen: set[int] = set()
    while current is not None and id(current) not in seen:
        seen.add(id(current))
        if isinstance(current, ModuleNotFoundError):
            if getattr(current, "name", None) == "py65" or "py65" in str(current):
                return True
        if isinstance(current, ImportError) and "py65" in str(current):
            return True
        current = current.__cause__ or current.__context__
    return False


def _load_existing_py65_fixture(fixture_path: Path) -> dict | None:
    if not fixture_path.exists():
        return None
    fixture = json.loads(fixture_path.read_text())
    sequence = fixture.get("sequence")
    if fixture.get("method") != "py65":
        return None
    if not isinstance(sequence, list) or len(sequence) < 1000:
        return None
    return fixture


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_bytes = rom_path.read_bytes()
    rom_sha1 = _sha1(rom_path)

    read_gate = _collect_rng_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase2_rng_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    fixture_path = root / "tests" / "fixtures" / "rng_golden_sequence.json"
    preserved_existing_fixture = False

    method: str
    sequence: list[int]
    fixture: dict
    try:
        sequence = _generate_rng_sequence_py65(rom_bytes, count=1000)
        method = "py65"
    except Exception as error:
        if not _is_py65_unavailable_error(error):
            raise
        existing_fixture = _load_existing_py65_fixture(fixture_path)
        if existing_fixture is not None:
            fixture = existing_fixture
            method = fixture["method"]
            sequence = fixture["sequence"]
            preserved_existing_fixture = True
        else:
            sequence = _generate_rng_sequence_fallback(count=20)
            method = "fallback-python-translation-20"

    if not preserved_existing_fixture:
        fixture = {
            "seed_lb": 0,
            "seed_ub": 0,
            "method": method,
            "routine": {
                "name": "UpdateRandNum",
                "bank03_label": "LC55B",
                "cpu_start": "0xC55B",
                "cpu_rts": "0xC586",
                "rom_bank3_range": "0xC010-0x1000F",
            },
            "rom": {
                "path": baseline["rom_file"],
                "sha1": rom_sha1,
                "accepted_sha1": baseline["accepted_sha1"],
                "baseline_match": rom_sha1 == baseline["accepted_sha1"],
            },
            "sequence": sequence,
        }

        fixture_path.parent.mkdir(parents=True, exist_ok=True)
        fixture_path.write_text(json.dumps(fixture, indent=2) + "\n")

    artifact = {
        "slice": "phase2-rng",
        "method": method,
        "sequence_count": len(sequence),
        "preserved_existing_fixture": preserved_existing_fixture,
        "seed": {"lb": 0, "ub": 0},
        "first_10": sequence[:10],
        "last_10": sequence[-10:],
        "fixture_path": str(fixture_path.relative_to(root)),
        "read_gate_path": str(read_gate_path.relative_to(root)),
        "rom_sha1": rom_sha1,
        "baseline_sha1": baseline["accepted_sha1"],
        "baseline_match": rom_sha1 == baseline["accepted_sha1"],
    }
    artifact_path = root / "artifacts" / "phase2_rng_fixture.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
