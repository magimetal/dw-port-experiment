import json
from pathlib import Path

import pytest

from engine.dialog_engine import DialogEngine


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_dialog first: {path}"
    return json.loads(path.read_text())


def test_start_dialog_unknown_id_raises() -> None:
    engine = DialogEngine({"text_blocks": [{"block_index": 1, "block_name": "TextBlock1", "decoded_tokens": []}]})
    with pytest.raises(KeyError):
        engine.start_dialog(2)


def test_dialog_session_paging_and_control_resolution() -> None:
    engine = DialogEngine(
        {
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
                        "Unknown marker ",
                        "<CTRL_F4>",
                        "<CTRL_END_NO_LINEBREAK>",
                    ],
                }
            ]
        }
    )
    session = engine.start_dialog(
        99,
        player_name="ERDRICK",
        gold_cost=42,
        variable_string="[VAR]",
    )

    session, page_one = session.next_page()
    assert page_one == "Hello ERDRICK costs 42\n[VAR]"
    assert session.is_done() is False

    session, page_two = session.next_page()
    assert page_two == "Unknown marker <CTRL_F4>"
    assert session.is_done() is True

    session, page_three = session.next_page()
    assert page_three == ""
    assert session.is_done() is True


def test_dialog_session_preserves_unresolved_machine_markers() -> None:
    engine = DialogEngine(
        {
            "text_blocks": [
                {
                    "block_index": 5,
                    "block_name": "PreserveBlock",
                    "decoded_tokens": [
                        "<CTRL_GOLD_COST>",
                        " ",
                        "<CTRL_VARIABLE_STRING>",
                        " ",
                        "<CTRL_F1>",
                        "<CTRL_END_WAIT>",
                    ],
                }
            ]
        }
    )

    session = engine.start_dialog(5)
    session, page = session.next_page()
    assert page == "<CTRL_GOLD_COST> <CTRL_VARIABLE_STRING> <CTRL_F1>"
    assert session.is_done() is True


def test_dialog_engine_with_extracted_dialog_data() -> None:
    engine = DialogEngine.from_file(ROOT / "extractor" / "data_out" / "dialog.json")
    session = engine.start_dialog(1)
    session, first_page = session.next_page()

    assert first_page == "<CTRL_F4> hath woken up."
    assert session.is_done() is False


def test_start_dialog_entry_selects_single_entry_by_index() -> None:
    engine = DialogEngine.from_file(ROOT / "extractor" / "data_out" / "dialog.json")
    session = engine.start_dialog_entry(10, 11)
    session, first_page = session.next_page()

    assert "Princess Gwaelin" in first_page
    assert "DIALOG 98 ->" not in first_page
    assert "<BYTE_0x" not in first_page


def test_start_dialog_entry_unknown_index_raises() -> None:
    engine = DialogEngine(
        {
            "text_blocks": [
                {
                    "block_index": 1,
                    "block_name": "TextBlock1",
                    "decoded_tokens": ["A", "<CTRL_END_WAIT>"],
                }
            ]
        }
    )
    with pytest.raises(KeyError):
        engine.start_dialog_entry(1, 1)


def test_dialog_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_dialog_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_dialog_runtime.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "dialog_runtime_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-dialog"
    assert all(read_gate["files"]["Bank02.asm"]["labels_checked"].values())
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-dialog"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["dialog_block_count"] == 19
    assert fixture_vectors["block1_first_page"] == "<CTRL_F4> hath woken up."
    assert fixture_vectors["block1_is_done_after_one_page"] is False
    assert fixture_vectors["custom_page_one"] == "Hello ERDRICK costs 42\n[VAR]"
    assert fixture_vectors["custom_page_two"] == "Bye"
    assert fixture_vectors["custom_done_after_two_pages"] is True
