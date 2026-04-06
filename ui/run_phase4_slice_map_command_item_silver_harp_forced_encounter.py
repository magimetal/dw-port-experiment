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


def _pack_inventory_codes(*codes: int) -> tuple[int, int, int, int]:
    packed = [0, 0, 0, 0]
    for index, code in enumerate(codes[:8]):
        slot = index // 2
        nibble = code & 0x0F
        if (index % 2) == 0:
            packed[slot] = (packed[slot] & 0xF0) | nibble
        else:
            packed[slot] = (packed[slot] & 0x0F) | (nibble << 4)
    return packed[0], packed[1], packed[2], packed[3]


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


def _seed_state(*, map_id: int, rng_lb: int, rng_ub: int) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=map_id,
            player_x=46,
            player_y=1,
            rng_lb=rng_lb,
            rng_ub=rng_ub,
            inventory_slots=_pack_inventory_codes(0x0A),
        ),
        title_state=initial_title_state(),
    )


def _new_session(root: Path, state: MainLoopState) -> MainLoopSession:
    maps_payload = json.loads((root / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((root / "extractor" / "data_out" / "warps.json").read_text())
    npcs_payload = json.loads((root / "extractor" / "data_out" / "npcs.json").read_text())
    map_engine = MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)
    return MainLoopSession(
        terminal=_FakeTerminal(),
        map_engine=map_engine,
        npcs_payload=npcs_payload,
        state=state,
    )


def _open_item_menu(session: MainLoopSession) -> None:
    session.step("C")
    for _ in range(4):
        session.step("DOWN")


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    artifacts_dir = root / "artifacts"
    fixtures_dir = root / "tests" / "fixtures"
    artifacts_dir.mkdir(parents=True, exist_ok=True)
    fixtures_dir.mkdir(parents=True, exist_ok=True)

    baseline = json.loads((root / "extractor" / "rom_baseline.json").read_text())
    rom_path = root / baseline["rom_file"]
    rom_sha1 = _sha1(rom_path)

    menu_session = _new_session(root, _seed_state(map_id=1, rng_lb=0, rng_ub=0))
    _open_item_menu(menu_session)
    item_opened = menu_session.step("ENTER")

    forced_encounter_session = _new_session(root, _seed_state(map_id=1, rng_lb=0, rng_ub=0))
    _open_item_menu(forced_encounter_session)
    forced_encounter_session.step("ENTER")
    forced_encounter = forced_encounter_session.step("ENTER")
    forced_enemy = forced_encounter_session.state.game_state.combat_session

    rejected_session = _new_session(root, _seed_state(map_id=0x0D, rng_lb=0, rng_ub=0))
    _open_item_menu(rejected_session)
    rejected_session.step("ENTER")
    rejected = rejected_session.step("ENTER")

    vectors = {
        "item_menu_open": {
            "action": item_opened.action.kind,
            "action_detail": item_opened.action.detail,
            "screen_mode": item_opened.screen_mode,
            "frame_contains_item_title": "ITEM" in item_opened.frame,
            "frame_contains_silver_harp": "SILVER HARP" in item_opened.frame,
        },
        "item_use_silver_harp_forced_encounter": {
            "action": forced_encounter.action.kind,
            "action_detail": forced_encounter.action.detail,
            "screen_mode": forced_encounter.screen_mode,
            "enemy_id": None if forced_enemy is None else forced_enemy.enemy_id,
            "enemy_name": None if forced_enemy is None else forced_enemy.enemy_name,
            "rng_after": [
                forced_encounter_session.state.game_state.rng_lb,
                forced_encounter_session.state.game_state.rng_ub,
            ],
            "inventory_slots_after": list(forced_encounter_session.state.game_state.inventory_slots),
            "frame_contains_fight": "FIGHT" in forced_encounter.frame,
            "frame_contains_slime": "SLIME" in forced_encounter.frame,
        },
        "item_use_silver_harp_rejected": {
            "action": rejected.action.kind,
            "action_detail": rejected.action.detail,
            "screen_mode": rejected.screen_mode,
            "inventory_slots_after": list(rejected_session.state.game_state.inventory_slots),
            "frame_contains_rejected_text": "IT CANNOT BE USED HERE." in rejected.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_item_silver_harp_forced_encounter_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "item_menu_lists_silver_harp_target": (
            vectors["item_menu_open"]["action"] == "map_item_menu_opened"
            and vectors["item_menu_open"]["action_detail"] == "count:1"
            and vectors["item_menu_open"]["screen_mode"] == "map"
            and vectors["item_menu_open"]["frame_contains_item_title"] is True
            and vectors["item_menu_open"]["frame_contains_silver_harp"] is True
        ),
        "silver_harp_use_forces_overworld_encounter": (
            vectors["item_use_silver_harp_forced_encounter"]["action"] == "encounter_triggered"
            and vectors["item_use_silver_harp_forced_encounter"]["action_detail"] == "enemy:0;source:silver_harp"
            and vectors["item_use_silver_harp_forced_encounter"]["screen_mode"] == "combat"
            and vectors["item_use_silver_harp_forced_encounter"]["enemy_id"] == 0
            and vectors["item_use_silver_harp_forced_encounter"]["enemy_name"] == "Slime"
            and vectors["item_use_silver_harp_forced_encounter"]["inventory_slots_after"] == [10, 0, 0, 0]
            and vectors["item_use_silver_harp_forced_encounter"]["frame_contains_fight"] is True
            and vectors["item_use_silver_harp_forced_encounter"]["frame_contains_slime"] is True
        ),
        "silver_harp_use_rejects_off_overworld_without_consuming": (
            vectors["item_use_silver_harp_rejected"]["action"] == "map_item_rejected"
            and vectors["item_use_silver_harp_rejected"]["action_detail"]
            == "SILVER HARP:harp_only_works_on_overworld"
            and vectors["item_use_silver_harp_rejected"]["screen_mode"] == "dialog"
            and vectors["item_use_silver_harp_rejected"]["inventory_slots_after"] == [10, 0, 0, 0]
            and vectors["item_use_silver_harp_rejected"]["frame_contains_rejected_text"] is True
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-item-silver-harp-forced-encounter",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_item_silver_harp_forced_encounter.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_item_silver_harp_forced_encounter_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded ITEM Silver Harp forced-encounter slice: verifies overworld ITEM use enters the "
            "combat handoff deterministically via forced enemy selection and rejects deterministically off "
            "overworld with no inventory mutation."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_item_silver_harp_forced_encounter.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
