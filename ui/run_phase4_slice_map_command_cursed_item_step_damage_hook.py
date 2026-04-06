#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.items_engine import FLAG_CURSED_BELT, FLAG_DEATH_NECKLACE
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


def _seed_state(*, hp: int, max_hp: int, mp: int, max_mp: int, gold: int, more_spells_quest: int) -> MainLoopState:
    return MainLoopState(
        screen_mode="map",
        game_state=_clone_state(
            GameState.fresh_game("ERDRICK"),
            map_id=1,
            player_x=46,
            player_y=1,
            hp=hp,
            max_hp=max_hp,
            mp=mp,
            max_mp=max_mp,
            gold=gold,
            more_spells_quest=more_spells_quest,
            rng_lb=0,
            rng_ub=1,
            repel_timer=0,
            light_timer=0,
        ),
        title_state=initial_title_state(),
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

    cursed_belt_session = _new_session(
        root,
        _seed_state(hp=12, max_hp=31, mp=3, max_mp=10, gold=123, more_spells_quest=FLAG_CURSED_BELT),
    )
    cursed_belt_result = cursed_belt_session.step("RIGHT")

    death_necklace_session = _new_session(
        root,
        _seed_state(hp=12, max_hp=31, mp=3, max_mp=10, gold=123, more_spells_quest=FLAG_DEATH_NECKLACE),
    )
    death_necklace_result = death_necklace_session.step("RIGHT")
    death_necklace_page_two = death_necklace_session.step("ENTER")
    death_necklace_done = death_necklace_session.step("ENTER")

    no_curse_session = _new_session(
        root,
        _seed_state(hp=12, max_hp=31, mp=3, max_mp=10, gold=123, more_spells_quest=0),
    )
    no_curse_result = no_curse_session.step("RIGHT")

    vectors = {
        "cursed_belt_step_sets_hp_to_1": {
            "action": cursed_belt_result.action.kind,
            "action_detail": cursed_belt_result.action.detail,
            "screen_mode": cursed_belt_result.screen_mode,
            "map_after": [
                cursed_belt_session.state.game_state.map_id,
                cursed_belt_session.state.game_state.player_x,
                cursed_belt_session.state.game_state.player_y,
            ],
            "hp_after": cursed_belt_session.state.game_state.hp,
        },
        "death_necklace_step_triggers_death_outcome": {
            "action": death_necklace_result.action.kind,
            "action_detail": death_necklace_result.action.detail,
            "screen_mode": death_necklace_result.screen_mode,
            "map_after": [
                death_necklace_session.state.game_state.map_id,
                death_necklace_session.state.game_state.player_x,
                death_necklace_session.state.game_state.player_y,
            ],
            "hp_after": death_necklace_session.state.game_state.hp,
            "mp_after": death_necklace_session.state.game_state.mp,
            "gold_after": death_necklace_session.state.game_state.gold,
            "dialog_page_1_contains_slain": "THOU ART SLAIN." in death_necklace_result.frame,
            "dialog_page_2_action": death_necklace_page_two.action.kind,
            "dialog_page_2_contains_revive": "THOU ART RETURNED TO TANTEGEL." in death_necklace_page_two.frame,
            "dialog_done_action": death_necklace_done.action.kind,
            "dialog_done_screen_mode": death_necklace_done.screen_mode,
        },
        "step_without_curse_flags_has_no_side_effect": {
            "action": no_curse_result.action.kind,
            "action_detail": no_curse_result.action.detail,
            "screen_mode": no_curse_result.screen_mode,
            "map_after": [
                no_curse_session.state.game_state.map_id,
                no_curse_session.state.game_state.player_x,
                no_curse_session.state.game_state.player_y,
            ],
            "hp_after": no_curse_session.state.game_state.hp,
            "frame_contains_slain": "THOU ART SLAIN." in no_curse_result.frame,
        },
    }
    (fixtures_dir / "main_loop_map_command_cursed_item_step_damage_hook_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "cursed_belt_step_sets_hp_to_1": (
            vectors["cursed_belt_step_sets_hp_to_1"]["action"] == "move"
            and "cursed_belt:hp_set_to_1" in vectors["cursed_belt_step_sets_hp_to_1"]["action_detail"]
            and vectors["cursed_belt_step_sets_hp_to_1"]["screen_mode"] == "map"
            and vectors["cursed_belt_step_sets_hp_to_1"]["map_after"] == [1, 47, 1]
            and vectors["cursed_belt_step_sets_hp_to_1"]["hp_after"] == 1
        ),
        "death_necklace_step_triggers_death_outcome": (
            vectors["death_necklace_step_triggers_death_outcome"]["action"] == "combat_defeat"
            and vectors["death_necklace_step_triggers_death_outcome"]["action_detail"] == "revive"
            and vectors["death_necklace_step_triggers_death_outcome"]["screen_mode"] == "dialog"
            and vectors["death_necklace_step_triggers_death_outcome"]["map_after"] == [4, 5, 27]
            and vectors["death_necklace_step_triggers_death_outcome"]["hp_after"] == 31
            and vectors["death_necklace_step_triggers_death_outcome"]["mp_after"] == 10
            and vectors["death_necklace_step_triggers_death_outcome"]["gold_after"] == 61
            and vectors["death_necklace_step_triggers_death_outcome"]["dialog_page_1_contains_slain"] is True
            and vectors["death_necklace_step_triggers_death_outcome"]["dialog_page_2_action"] == "dialog_page_advance"
            and vectors["death_necklace_step_triggers_death_outcome"]["dialog_page_2_contains_revive"] is True
            and vectors["death_necklace_step_triggers_death_outcome"]["dialog_done_action"] == "dialog_done"
            and vectors["death_necklace_step_triggers_death_outcome"]["dialog_done_screen_mode"] == "map"
        ),
        "step_without_curse_flags_has_no_side_effect": (
            vectors["step_without_curse_flags_has_no_side_effect"]["action"] == "move"
            and vectors["step_without_curse_flags_has_no_side_effect"]["action_detail"] == "47,1"
            and vectors["step_without_curse_flags_has_no_side_effect"]["screen_mode"] == "map"
            and vectors["step_without_curse_flags_has_no_side_effect"]["map_after"] == [1, 47, 1]
            and vectors["step_without_curse_flags_has_no_side_effect"]["hp_after"] == 12
            and vectors["step_without_curse_flags_has_no_side_effect"]["frame_contains_slain"] is False
        ),
    }

    artifact = {
        "slice": "phase4-main-loop-map-command-cursed-item-step-damage-hook",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_main_loop_map_command_cursed_item_step_damage_hook.json",
            "vectors_fixture": "tests/fixtures/main_loop_map_command_cursed_item_step_damage_hook_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": (
            "Phase 4 bounded cursed movement hook slice: movement applies CURSED_BELT HP=1 per-step behavior, "
            "routes DEATH_NECKLACE movement death through existing defeat sequence, and preserves no-effect steps "
            "when no curse flags are set."
        ),
    }
    (artifacts_dir / "phase4_main_loop_map_command_cursed_item_step_damage_hook.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
