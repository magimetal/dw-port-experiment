#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from main import MainLoopSession, MainLoopState
from ui.title_screen import initial_title_state


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


class _FakeStream:
    def write(self, payload: str) -> None:  # pragma: no cover - render side-effect only
        return None

    def flush(self) -> None:  # pragma: no cover - render side-effect only
        return None


class _FakeTerminal:
    def __init__(self) -> None:
        self.width = 80
        self.height = 24
        self.stream = _FakeStream()


def _search_seed_state(*, map_id: int, player_x: int, player_y: int) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )


def _run_search_flow(session: MainLoopSession) -> tuple[str, str, str, bool, int]:
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    result = session.step("ENTER")
    return (
        result.action.kind,
        result.action.detail,
        result.screen_mode,
        "THOU HAST FOUND 120 GOLD." in result.frame,
        session.state.game_state.gold,
    )


def _run_reopen_flow(session: MainLoopSession) -> tuple[str, str, str, bool, int]:
    _run_search_flow(session)
    session.step("ENTER")
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    result = session.step("ENTER")
    return (
        result.action.kind,
        result.action.detail,
        result.screen_mode,
        "THE CHEST IS EMPTY." in result.frame,
        session.state.game_state.gold,
    )


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    chests_payload = json.loads((root / "extractor" / "data_out" / "chests.json").read_text())
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    terminal = _FakeTerminal()

    all_gold_indices = sorted(
        int(row.get("index", -1)) for row in chests_payload.get("chest_entries", []) if int(row.get("contents_id", 0)) == 19
    )
    remaining_gold_indices = [index for index in all_gold_indices if index != 0]

    index_1_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=4, player_x=1, player_y=15),
    )
    index_1 = _run_search_flow(index_1_session)

    index_2_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=4, player_x=2, player_y=14),
    )
    index_2 = _run_search_flow(index_2_session)

    index_3_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=4, player_x=3, player_y=15),
    )
    index_3 = _run_search_flow(index_3_session)

    index_21_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=24, player_x=13, player_y=0),
    )
    index_21 = _run_search_flow(index_21_session)

    index_21_reopen_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=24, player_x=13, player_y=0),
    )
    index_21_reopen = _run_reopen_flow(index_21_reopen_session)

    vectors = {
        "gold_chest_indices": {
            "all_indices": all_gold_indices,
            "remaining_indices": remaining_gold_indices,
        },
        "search_gold_chest_index_1": {
            "action": index_1[0],
            "action_detail": index_1[1],
            "screen_mode": index_1[2],
            "frame_contains_gold": index_1[3],
            "gold_after": index_1[4],
        },
        "search_gold_chest_index_2": {
            "action": index_2[0],
            "action_detail": index_2[1],
            "screen_mode": index_2[2],
            "frame_contains_gold": index_2[3],
            "gold_after": index_2[4],
        },
        "search_gold_chest_index_3": {
            "action": index_3[0],
            "action_detail": index_3[1],
            "screen_mode": index_3[2],
            "frame_contains_gold": index_3[3],
            "gold_after": index_3[4],
        },
        "search_gold_chest_index_21": {
            "action": index_21[0],
            "action_detail": index_21[1],
            "screen_mode": index_21[2],
            "frame_contains_gold": index_21[3],
            "gold_after": index_21[4],
        },
        "search_gold_chest_index_21_reopen": {
            "action": index_21_reopen[0],
            "action_detail": index_21_reopen[1],
            "screen_mode": index_21_reopen[2],
            "frame_contains_empty": index_21_reopen[3],
            "gold_after": index_21_reopen[4],
        },
    }
    (fixtures_dir / "main_loop_map_command_search_remaining_gold_chest_rewards_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "gold_chest_matrix_matches_extracted_data": all_gold_indices == [0, 1, 2, 3, 21] and remaining_gold_indices == [1, 2, 3, 21],
        "search_gold_chest_index_1_applies_reward": (
            vectors["search_gold_chest_index_1"]["action"] == "map_search"
            and vectors["search_gold_chest_index_1"]["action_detail"]
            == "chest:index:1;contents:19;reward:gold:120;opened:true"
            and vectors["search_gold_chest_index_1"]["screen_mode"] == "dialog"
            and vectors["search_gold_chest_index_1"]["frame_contains_gold"] is True
            and vectors["search_gold_chest_index_1"]["gold_after"] == 240
        ),
        "search_gold_chest_index_2_applies_reward": (
            vectors["search_gold_chest_index_2"]["action"] == "map_search"
            and vectors["search_gold_chest_index_2"]["action_detail"]
            == "chest:index:2;contents:19;reward:gold:120;opened:true"
            and vectors["search_gold_chest_index_2"]["screen_mode"] == "dialog"
            and vectors["search_gold_chest_index_2"]["frame_contains_gold"] is True
            and vectors["search_gold_chest_index_2"]["gold_after"] == 240
        ),
        "search_gold_chest_index_3_applies_reward": (
            vectors["search_gold_chest_index_3"]["action"] == "map_search"
            and vectors["search_gold_chest_index_3"]["action_detail"]
            == "chest:index:3;contents:19;reward:gold:120;opened:true"
            and vectors["search_gold_chest_index_3"]["screen_mode"] == "dialog"
            and vectors["search_gold_chest_index_3"]["frame_contains_gold"] is True
            and vectors["search_gold_chest_index_3"]["gold_after"] == 240
        ),
        "search_gold_chest_index_21_applies_reward": (
            vectors["search_gold_chest_index_21"]["action"] == "map_search"
            and vectors["search_gold_chest_index_21"]["action_detail"]
            == "chest:index:21;contents:19;reward:gold:120;opened:true"
            and vectors["search_gold_chest_index_21"]["screen_mode"] == "dialog"
            and vectors["search_gold_chest_index_21"]["frame_contains_gold"] is True
            and vectors["search_gold_chest_index_21"]["gold_after"] == 240
        ),
        "search_gold_chest_index_21_reopen_is_empty": (
            vectors["search_gold_chest_index_21_reopen"]["action"] == "map_search"
            and vectors["search_gold_chest_index_21_reopen"]["action_detail"]
            == "chest:index:21;contents:19;opened:true;reward:none"
            and vectors["search_gold_chest_index_21_reopen"]["screen_mode"] == "dialog"
            and vectors["search_gold_chest_index_21_reopen"]["frame_contains_empty"] is True
            and vectors["search_gold_chest_index_21_reopen"]["gold_after"] == 240
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-search-remaining-gold-chest-rewards",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_search_remaining_gold_chest_rewards.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_search_remaining_gold_chest_rewards_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded SEARCH hardening for remaining gold chest locations: verify every extracted "
            "contents_id=19 chest beyond index 0 applies +120 gold and remains empty on reopen."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_search_remaining_gold_chest_rewards.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
