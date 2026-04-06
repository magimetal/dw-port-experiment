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

    wings_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=6, player_x=11, player_y=12),
    )
    wings = _run_search_flow(wings_session)

    dragons_scale_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=5, player_x=4, player_y=4),
    )
    dragons_scale = _run_search_flow(dragons_scale_session)

    fairy_flute_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=29, player_x=9, player_y=3),
    )
    fairy_flute = _run_search_flow(fairy_flute_session)

    herb_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=16, player_x=5, player_y=5, herbs=6),
    )
    herb_full = _run_search_flow(herb_full_session)

    key_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=24, player_x=12, player_y=0, magic_keys=6),
    )
    key_full = _run_search_flow(key_full_session)

    tool_full_session = MainLoopSession(
        terminal=terminal,
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=_search_seed_state(map_id=9, player_x=8, player_y=5, inventory_slots=(0x11, 0x11, 0x11, 0x11)),
    )
    tool_full = _run_search_flow(tool_full_session)

    vectors = {
        "search_wings_chest": {
            "action": wings[0],
            "action_detail": wings[1],
            "screen_mode": wings[2],
            "frame_contains_wings": "THOU HAST FOUND WINGS." in wings[3],
            "inventory_slots_after": list(wings_session.state.game_state.inventory_slots),
        },
        "search_dragons_scale_chest": {
            "action": dragons_scale[0],
            "action_detail": dragons_scale[1],
            "screen_mode": dragons_scale[2],
            "frame_contains_dragons_scale": "THOU HAST FOUND DRAGON'S SCALE." in dragons_scale[3],
            "inventory_slots_after": list(dragons_scale_session.state.game_state.inventory_slots),
        },
        "search_fairy_flute_chest": {
            "action": fairy_flute[0],
            "action_detail": fairy_flute[1],
            "screen_mode": fairy_flute[2],
            "frame_contains_fairy_flute": "THOU HAST FOUND FAIRY FLUTE." in fairy_flute[3],
            "inventory_slots_after": list(fairy_flute_session.state.game_state.inventory_slots),
        },
        "search_herb_full_guard": {
            "action": herb_full[0],
            "action_detail": herb_full[1],
            "screen_mode": herb_full[2],
            "frame_contains_herb_full": "THY HERBS ARE FULL." in herb_full[3],
            "herbs_after": herb_full_session.state.game_state.herbs,
        },
        "search_key_full_guard": {
            "action": key_full[0],
            "action_detail": key_full[1],
            "screen_mode": key_full[2],
            "frame_contains_key_full": "THY MAGIC KEYS ARE FULL." in key_full[3],
            "magic_keys_after": key_full_session.state.game_state.magic_keys,
        },
        "search_tool_full_guard": {
            "action": tool_full[0],
            "action_detail": tool_full[1],
            "screen_mode": tool_full[2],
            "frame_contains_inventory_full": "THY INVENTORY IS FULL." in tool_full[3],
            "inventory_slots_after": list(tool_full_session.state.game_state.inventory_slots),
        },
    }
    (fixtures_dir / "main_loop_map_command_search_tool_rewards_capacity_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "search_wings_chest_applies_reward": (
            vectors["search_wings_chest"]["action"] == "map_search"
            and vectors["search_wings_chest"]["action_detail"]
            == "chest:index:12;contents:21;reward:item:WINGS;opened:true"
            and vectors["search_wings_chest"]["screen_mode"] == "dialog"
            and vectors["search_wings_chest"]["frame_contains_wings"] is True
            and vectors["search_wings_chest"]["inventory_slots_after"] == [3, 0, 0, 0]
        ),
        "search_dragons_scale_chest_applies_reward": (
            vectors["search_dragons_scale_chest"]["action"] == "map_search"
            and vectors["search_dragons_scale_chest"]["action_detail"]
            == "chest:index:4;contents:22;reward:item:DRAGONS_SCALE;opened:true"
            and vectors["search_dragons_scale_chest"]["screen_mode"] == "dialog"
            and vectors["search_dragons_scale_chest"]["frame_contains_dragons_scale"] is True
            and vectors["search_dragons_scale_chest"]["inventory_slots_after"] == [4, 0, 0, 0]
        ),
        "search_fairy_flute_chest_applies_reward": (
            vectors["search_fairy_flute_chest"]["action"] == "map_search"
            and vectors["search_fairy_flute_chest"]["action_detail"]
            == "chest:index:30;contents:23;reward:item:FAIRY_FLUTE;opened:true"
            and vectors["search_fairy_flute_chest"]["screen_mode"] == "dialog"
            and vectors["search_fairy_flute_chest"]["frame_contains_fairy_flute"] is True
            and vectors["search_fairy_flute_chest"]["inventory_slots_after"] == [5, 0, 0, 0]
        ),
        "search_herb_full_guard_rejects_without_state_change": (
            vectors["search_herb_full_guard"]["action"] == "map_search"
            and vectors["search_herb_full_guard"]["action_detail"] == "chest:index:24;contents:17;reward:herb:full"
            and vectors["search_herb_full_guard"]["screen_mode"] == "dialog"
            and vectors["search_herb_full_guard"]["frame_contains_herb_full"] is True
            and vectors["search_herb_full_guard"]["herbs_after"] == 6
        ),
        "search_key_full_guard_rejects_without_state_change": (
            vectors["search_key_full_guard"]["action"] == "map_search"
            and vectors["search_key_full_guard"]["action_detail"] == "chest:index:20;contents:18;reward:key:full"
            and vectors["search_key_full_guard"]["screen_mode"] == "dialog"
            and vectors["search_key_full_guard"]["frame_contains_key_full"] is True
            and vectors["search_key_full_guard"]["magic_keys_after"] == 6
        ),
        "search_tool_full_guard_rejects_without_state_change": (
            vectors["search_tool_full_guard"]["action"] == "map_search"
            and vectors["search_tool_full_guard"]["action_detail"] == "chest:index:8;contents:20;reward:item:full"
            and vectors["search_tool_full_guard"]["screen_mode"] == "dialog"
            and vectors["search_tool_full_guard"]["frame_contains_inventory_full"] is True
            and vectors["search_tool_full_guard"]["inventory_slots_after"] == [17, 17, 17, 17]
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-search-tool-rewards-capacity",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_search_tool_rewards_capacity.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_search_tool_rewards_capacity_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded SEARCH remaining non-gold tool chest rewards (contents_id 21/22/23) and "
            "deterministic herb/key/tool full-capacity rejection guards."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_search_tool_rewards_capacity.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
