#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.dialog_engine import DialogEngine


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_dialog_read_gate(disassembly_root: Path) -> dict:
    bank02_path = disassembly_root / "Bank02.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank02_text = bank02_path.read_text()
    bank03_text = bank03_path.read_text()
    bank02_labels = [
        "TextBlock1",
        "TextBlock19",
    ]
    bank03_labels = [
        "DoDialogLoBlock",
        "DoDialogHiBlock",
        "SetDialogBytes",
    ]
    return {
        "completed": True,
        "slice": "phase2-dialog",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank02.asm": {
                "path": str(bank02_path),
                "bytes": len(bank02_text.encode("utf-8")),
                "lines": bank02_text.count("\n"),
                "labels_checked": {label: (label in bank02_text) for label in bank02_labels},
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in bank03_labels},
            },
        },
    }


def _count_pages(engine: DialogEngine, dialog_id: int) -> int:
    session = engine.start_dialog(dialog_id)
    page_count = 0
    while not session.is_done():
        session, _ = session.next_page()
        page_count += 1
    return page_count


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    dialog_path = root / "extractor" / "data_out" / "dialog.json"
    dialog_data = json.loads(dialog_path.read_text())
    engine = DialogEngine(dialog_data)

    read_gate = _collect_dialog_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_dialog_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    block1 = engine.start_dialog(1)
    block1, first_page = block1.next_page()

    custom_dialog_data = {
        "text_blocks": [
            {
                "block_index": 99,
                "block_name": "FixtureBlock",
                "decoded_tokens": [
                    "Hello ",
                    "<CTRL_F8>",
                    " costs ",
                    "<CTRL_GOLD_COST>",
                    "<CTRL_LINE_BREAK>",
                    "<CTRL_VARIABLE_STRING>",
                    "<CTRL_END_WAIT>",
                    "Bye",
                    "<CTRL_END_NO_LINEBREAK>",
                ],
            }
        ]
    }
    custom_engine = DialogEngine(custom_dialog_data)
    custom_session = custom_engine.start_dialog(
        99,
        player_name="ERDRICK",
        gold_cost=42,
        variable_string="[VAR]",
    )
    custom_session, custom_page_one = custom_session.next_page()
    custom_session, custom_page_two = custom_session.next_page()

    vectors = {
        "dialog_block_count": len(dialog_data.get("text_blocks", [])),
        "block1_first_page": first_page,
        "block1_is_done_after_one_page": block1.is_done(),
        "block1_page_count": _count_pages(engine, 1),
        "custom_page_one": custom_page_one,
        "custom_page_two": custom_page_two,
        "custom_done_after_two_pages": custom_session.is_done(),
    }
    (fixtures_dir / "dialog_runtime_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank02_labels": ["TextBlock1", "TextBlock19"],
                    "bank03_labels": [
                        "DoDialogLoBlock",
                        "DoDialogHiBlock",
                        "SetDialogBytes",
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
        "all_bank02_labels_present": all(
            read_gate["files"]["Bank02.asm"]["labels_checked"].values()
        ),
        "all_bank03_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "dialog_block_count_19": vectors["dialog_block_count"] == 19,
        "block1_first_page_expected": vectors["block1_first_page"] == "<CTRL_F4> hath woken up.",
        "block1_not_done_after_first_page": vectors["block1_is_done_after_one_page"] is False,
        "block1_has_multiple_pages": vectors["block1_page_count"] > 1,
        "custom_resolution_page_one": vectors["custom_page_one"] == "Hello ERDRICK costs 42\n[VAR]",
        "custom_resolution_page_two": vectors["custom_page_two"] == "Bye",
        "custom_session_done_after_two_pages": vectors["custom_done_after_two_pages"] is True,
    }

    artifact = {
        "slice": "phase2-dialog",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_dialog_read_gate.json",
            "report": "artifacts/phase2_dialog_runtime.json",
            "vectors_fixture": "tests/fixtures/dialog_runtime_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase2_dialog_runtime.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
