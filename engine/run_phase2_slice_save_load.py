#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.save_load import (
    calculate_crc,
    decode_portable_token,
    encode_portable_token,
    load_json,
    save_json,
    state_from_save_dict,
    state_to_save_dict,
    state_to_save_data,
)
from engine.state import GameState


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_save_load_read_gate(disassembly_root: Path) -> dict:
    bank03_path = disassembly_root / "Bank03.asm"
    bank03_text = bank03_path.read_text()
    bank03_labels = [
        "SaveData",
        "Save10Times",
        "GetCRC",
        "DoCRC",
        "DoLFSR",
        "GetSaveGameBase",
    ]
    return {
        "completed": True,
        "slice": "phase2-save-load",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in bank03_labels},
            }
        },
        "notes": {
            "password_status": (
                "US ROM has no password encoder/decoder; canonical save is SRAM-equivalent "
                "30-byte JSON payload with CRC."
            )
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    read_gate = _collect_save_load_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_save_load_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    sample = GameState(
        player_name="Loto-7",
        map_id=16,
        player_x=42,
        player_y=51,
        hp=47,
        mp=18,
        level=12,
        str=48,
        agi=40,
        max_hp=63,
        max_mp=58,
        attack=65,
        defense=35,
        experience=5432,
        gold=3210,
        equipment_byte=0x5D,
        magic_keys=9,
        herbs=4,
        inventory_slots=(0x12, 0x34, 0x50, 0x00),
        spells_known=0x3F,
        more_spells_quest=0x81,
        player_flags=0x40,
        story_flags=0x12,
        quest_flags=0x09,
        rng_lb=0x34,
        rng_ub=0xA0,
        repel_timer=7,
        light_timer=11,
        light_radius=5,
        magic_armor_step_counter=3,
        display_level=12,
    )

    payload = state_to_save_data(sample)
    crc_lb, crc_ub = calculate_crc(payload)
    save_dict = state_to_save_dict(sample)
    save_dict_decoded = state_from_save_dict(save_dict)

    token = encode_portable_token(sample)
    decoded = decode_portable_token(token)

    tmp_save_path = artifacts_dir / "phase2_save_load_tmp.json"
    save_json(sample, slot=2, path=tmp_save_path)
    loaded = load_json(slot=2, path=tmp_save_path)

    vectors = {
        "payload_length": len(payload),
        "payload_exp": [payload[0], payload[1]],
        "payload_gold": [payload[2], payload[3]],
        "payload_keys_clamped": payload[8],
        "payload_name_bytes": list(payload[14:22]),
        "payload_spare_bytes": list(payload[26:30]),
        "crc": [crc_lb, crc_ub],
        "save_dict_has_crc": save_dict.get("crc") == [crc_lb, crc_ub],
        "save_dict_roundtrip_equal": state_to_save_data(save_dict_decoded) == payload,
        "json_roundtrip_save_data_equal": state_to_save_data(loaded) == payload,
        "portable_token_length": len(token),
        "portable_token_prefix": token[:8],
        "portable_decode_player_name": decoded.player_name,
        "portable_decode_experience": decoded.experience,
        "portable_decode_gold": decoded.gold,
        "portable_decode_magic_keys": decoded.magic_keys,
        "portable_decode_inventory_slots": list(decoded.inventory_slots),
        "portable_decode_player_flags": decoded.player_flags,
        "portable_decode_story_flags": decoded.story_flags,
        "json_file_exists": tmp_save_path.exists(),
    }

    (fixtures_dir / "save_load_runtime_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank03_labels": [
                        "SaveData",
                        "Save10Times",
                        "GetCRC",
                        "DoCRC",
                        "DoLFSR",
                        "GetSaveGameBase",
                    ],
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_bank03_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "save_payload_is_30_bytes": vectors["payload_length"] == 30,
        "save_keys_are_clamped_to_6": vectors["payload_keys_clamped"] == 6,
        "save_spare_bytes_are_c8": vectors["payload_spare_bytes"] == [0xC8, 0xC8, 0xC8, 0xC8],
        "save_dict_roundtrip_preserves_30_bytes": (
            vectors["save_dict_has_crc"] is True and vectors["save_dict_roundtrip_equal"] is True
        ),
        "json_roundtrip_preserves_30_bytes": vectors["json_roundtrip_save_data_equal"] is True,
        "portable_token_roundtrip_core_fields": (
            vectors["portable_decode_player_name"] == "LOTO-7"
            and vectors["portable_decode_experience"] == 5432
            and vectors["portable_decode_gold"] == 3210
            and vectors["portable_decode_magic_keys"] == 6
            and vectors["portable_decode_inventory_slots"] == [0x12, 0x34, 0x50, 0x00]
            and vectors["portable_decode_player_flags"] == 0x40
            and vectors["portable_decode_story_flags"] == 0x12
        ),
    }

    artifact = {
        "slice": "phase2-save-load",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_save_load_read_gate.json",
            "report": "artifacts/phase2_save_load_runtime.json",
            "vectors_fixture": "tests/fixtures/save_load_runtime_vectors.json",
            "json_tmp": "artifacts/phase2_save_load_tmp.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 2 save/load runtime slice: canonical JSON persistence for SRAM-equivalent "
            "30-byte SaveData+CRC and optional non-canonical portable token export."
        ),
    }

    (artifacts_dir / "phase2_save_load_runtime.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
