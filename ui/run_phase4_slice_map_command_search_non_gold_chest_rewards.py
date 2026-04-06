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


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
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


def _search_seed_state(
    *,
    map_id: int,
    player_x: int,
    player_y: int,
    herbs: int = 0,
    magic_keys: int = 0,
    inventory_slots: tuple[int, int, int, int] = (0, 0, 0, 0),
) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=player_x,
            player_y=player_y,
            herbs=herbs,
            magic_keys=magic_keys,
            inventory_slots=inventory_slots,
            hp=9,
            mp=10,
            spells_known=0x01,
        ),
        title_state=initial_title_state(),
    )


def _run_search_flow(session: MainLoopSession) -> tuple[str, str, str, str]:
    session.step("C")
    session.step("DOWN")
    session.step("DOWN")
    result = session.step("ENTER")
    return result.action.kind, result.action.detail, result.screen_mode, result.frame


def _run_key_reopen_flow(session: MainLoopSession) -> tuple[str, str, str, str, int]:
    _run_search_flow(session)
    session.step("ENTER")
    action, detail, screen_mode, frame = _run_search_flow(session)
    return action, detail, screen_mode, frame, session.state.game_state.magic_keys


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

    herb_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=16, player_x=5, player_y=5),
    )
    herb = _run_search_flow(herb_session)

    key_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=24, player_x=12, player_y=0),
    )
    key = _run_search_flow(key_session)

    tool_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=9, player_x=8, player_y=5),
    )
    tool = _run_search_flow(tool_session)

    key_reopen_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=24, player_x=12, player_y=0),
    )
    key_reopen = _run_key_reopen_flow(key_reopen_session)

    vectors = {
        "search_herb_chest": {
            "action": herb[0],
            "action_detail": herb[1],
            "screen_mode": herb[2],
            "frame_contains_herb": "THOU HAST FOUND A HERB." in herb[3],
            "herbs_after": herb_session.state.game_state.herbs,
        },
        "search_key_chest": {
            "action": key[0],
            "action_detail": key[1],
            "screen_mode": key[2],
            "frame_contains_key": "THOU HAST FOUND A MAGIC KEY." in key[3],
            "magic_keys_after": key_session.state.game_state.magic_keys,
        },
        "search_tool_chest": {
            "action": tool[0],
            "action_detail": tool[1],
            "screen_mode": tool[2],
            "frame_contains_tool": "THOU HAST FOUND FAIRY WATER." in tool[3],
            "inventory_slots_after": list(tool_session.state.game_state.inventory_slots),
        },
        "search_key_chest_reopen": {
            "action": key_reopen[0],
            "action_detail": key_reopen[1],
            "screen_mode": key_reopen[2],
            "frame_contains_empty": "THE CHEST IS EMPTY." in key_reopen[3],
            "magic_keys_after": key_reopen[4],
        },
    }
    (fixtures_dir / "main_loop_map_command_search_non_gold_chest_rewards_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "search_herb_chest_applies_reward": (
            vectors["search_herb_chest"]["action"] == "map_search"
            and vectors["search_herb_chest"]["action_detail"]
            == "chest:index:24;contents:17;reward:herb:+1;opened:true"
            and vectors["search_herb_chest"]["screen_mode"] == "dialog"
            and vectors["search_herb_chest"]["frame_contains_herb"] is True
            and vectors["search_herb_chest"]["herbs_after"] == 1
        ),
        "search_key_chest_applies_reward": (
            vectors["search_key_chest"]["action"] == "map_search"
            and vectors["search_key_chest"]["action_detail"]
            == "chest:index:20;contents:18;reward:key:+1;opened:true"
            and vectors["search_key_chest"]["screen_mode"] == "dialog"
            and vectors["search_key_chest"]["frame_contains_key"] is True
            and vectors["search_key_chest"]["magic_keys_after"] == 1
        ),
        "search_tool_chest_applies_reward": (
            vectors["search_tool_chest"]["action"] == "map_search"
            and vectors["search_tool_chest"]["action_detail"]
            == "chest:index:8;contents:20;reward:item:FAIRY_WATER;opened:true"
            and vectors["search_tool_chest"]["screen_mode"] == "dialog"
            and vectors["search_tool_chest"]["frame_contains_tool"] is True
            and vectors["search_tool_chest"]["inventory_slots_after"] == [2, 0, 0, 0]
        ),
        "search_non_gold_reopen_is_empty": (
            vectors["search_key_chest_reopen"]["action"] == "map_search"
            and vectors["search_key_chest_reopen"]["action_detail"]
            == "chest:index:20;contents:18;opened:true;reward:none"
            and vectors["search_key_chest_reopen"]["screen_mode"] == "dialog"
            and vectors["search_key_chest_reopen"]["frame_contains_empty"] is True
            and vectors["search_key_chest_reopen"]["magic_keys_after"] == 1
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-search-non-gold-chest-rewards",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_search_non_gold_chest_rewards.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_search_non_gold_chest_rewards_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded SEARCH non-gold reward integration: apply deterministic herb/key/tool chest rewards, "
            "preserve opened state, and prevent repeat collection in-session."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_search_non_gold_chest_rewards.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
