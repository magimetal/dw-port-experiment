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


def _run_search_flow(session: MainLoopSession) -> tuple[str, str, str, bool, bool]:
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    result = session.step("ENTER")
    return (
        result.action.kind,
        result.action.detail,
        result.screen_mode,
        "THOU DIDST FIND NOTHING." in result.frame,
        "THOU HAST FOUND 120 GOLD." in result.frame,
    )


def _run_chest_reopen_flow(session: MainLoopSession) -> tuple[str, str, str, bool, int]:
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

    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)

    terminal = _FakeTerminal()

    no_chest_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=1, player_x=10, player_y=10),
    )
    no_chest = _run_search_flow(no_chest_session)

    chest_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=4, player_x=1, player_y=13),
    )
    chest = _run_search_flow(chest_session)

    chest_reopen_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=4, player_x=1, player_y=13),
    )
    chest_reopen = _run_chest_reopen_flow(chest_reopen_session)

    vectors = {
        "search_no_chest": {
            "action": no_chest[0],
            "action_detail": no_chest[1],
            "screen_mode": no_chest[2],
            "frame_contains_nothing": no_chest[3],
        },
        "search_chest": {
            "action": chest[0],
            "action_detail": chest[1],
            "screen_mode": chest[2],
            "frame_contains_gold": chest[4],
            "gold_after": chest_session.state.game_state.gold,
        },
        "search_chest_reopen": {
            "action": chest_reopen[0],
            "action_detail": chest_reopen[1],
            "screen_mode": chest_reopen[2],
            "frame_contains_empty": chest_reopen[3],
            "gold_after": chest_reopen[4],
        },
    }
    (fixtures_dir / "main_loop_map_command_search_chest_rewards_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "search_no_chest_returns_deterministic_nothing_dialog": (
            vectors["search_no_chest"]["action"] == "map_search"
            and vectors["search_no_chest"]["action_detail"] == "none"
            and vectors["search_no_chest"]["screen_mode"] == "dialog"
            and vectors["search_no_chest"]["frame_contains_nothing"] is True
        ),
        "search_chest_applies_gold_reward_and_marks_opened": (
            vectors["search_chest"]["action"] == "map_search"
            and vectors["search_chest"]["action_detail"] == "chest:index:0;contents:19;reward:gold:120;opened:true"
            and vectors["search_chest"]["screen_mode"] == "dialog"
            and vectors["search_chest"]["frame_contains_gold"] is True
            and vectors["search_chest"]["gold_after"] == 240
        ),
        "search_chest_reopen_is_empty_and_does_not_grant_again": (
            vectors["search_chest_reopen"]["action"] == "map_search"
            and vectors["search_chest_reopen"]["action_detail"]
            == "chest:index:0;contents:19;opened:true;reward:none"
            and vectors["search_chest_reopen"]["screen_mode"] == "dialog"
            and vectors["search_chest_reopen"]["frame_contains_empty"] is True
            and vectors["search_chest_reopen"]["gold_after"] == 240
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-search-chest-rewards",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_search_chest_rewards.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_search_chest_rewards_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded SEARCH chest-reward integration: apply deterministic gold reward for supported "
            "chest content, track opened chest state, and prevent repeat collection."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_search_chest_rewards.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
