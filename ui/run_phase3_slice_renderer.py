#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.combat_view import initial_combat_view_state
from ui.renderer import GameRenderer, RenderFrameRequest, SUPPORTED_SCREEN_MODES
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
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flush_count = 0

    def write(self, payload: str) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        self.flush_count += 1


class _FakeTerminal:
    def __init__(self, width: int, height: int) -> None:
        self.width = width
        self.height = height
        self.stream = _FakeStream()


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

    terminal = _FakeTerminal(80, 24)
    renderer = GameRenderer(terminal, map_engine, npcs_payload=npcs_payload)

    base_state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=4, player_x=11, player_y=11)

    requests = {
        "title": RenderFrameRequest(
            screen_mode="title",
            game_state=base_state,
            title_state=initial_title_state(),
        ),
        "map": RenderFrameRequest(screen_mode="map", game_state=base_state),
        "combat": RenderFrameRequest(
            screen_mode="combat",
            game_state=base_state,
            combat_state=initial_combat_view_state(combat_log=("The Slime draws near.",)),
            enemy_name="Slime",
            enemy_hp=3,
            enemy_max_hp=3,
            learned_spells=("HEAL",),
        ),
        "dialog": RenderFrameRequest(
            screen_mode="dialog",
            game_state=base_state,
            dialog_text="Welcome to Alefgard. Stay awhile and listen.",
        ),
        "endgame": RenderFrameRequest(
            screen_mode="endgame",
            game_state=base_state,
        ),
    }

    dispatch: dict[str, dict[str, object]] = {}
    dispatch_ok = True
    for mode in SUPPORTED_SCREEN_MODES:
        try:
            frame = renderer.draw(requests[mode])
            lines = frame.splitlines()
            dispatch[mode] = {
                "rendered": True,
                "line_count": len(lines),
                "col_count": max((len(line) for line in lines), default=0),
                "marker": {
                    "title": "W A R R I O R",
                    "map": "@",
                    "combat": "BATTLE",
                    "dialog": "╔",
                    "endgame": "THE LEGEND LIVES ON.",
                }[mode],
                "contains_marker": {
                    "title": "W A R R I O R" in frame,
                    "map": "@" in frame,
                    "combat": "BATTLE" in frame,
                    "dialog": "╔" in frame,
                    "endgame": "THE LEGEND LIVES ON." in frame,
                }[mode],
            }
        except Exception as exc:  # pragma: no cover - artifact emits failures
            dispatch_ok = False
            dispatch[mode] = {
                "rendered": False,
                "error": f"{type(exc).__name__}: {exc}",
            }

    terminal.stream.writes.clear()
    map_request = requests["map"]
    renderer.draw(map_request)
    writes_after_first = len(terminal.stream.writes)
    renderer.draw(map_request)
    writes_after_second = len(terminal.stream.writes)
    renderer.draw(requests["title"])
    writes_after_third = len(terminal.stream.writes)

    terminal.width = 60
    terminal.height = 20
    small_frame = renderer.draw(map_request)
    terminal.width = 80
    terminal.height = 24
    recovered_frame = renderer.draw(map_request)

    vectors = {
        "dispatch": dispatch,
        "double_buffer": {
            "writes_after_first": writes_after_first,
            "writes_after_second": writes_after_second,
            "writes_after_third": writes_after_third,
        },
        "resize": {
            "small_contains_notice": "TERMINAL TOO SMALL" in small_frame,
            "small_contains_current": "CURRENT:  60x20" in small_frame,
            "recover_contains_player": "@" in recovered_frame,
        },
        "write_behavior": {
            "flush_count": terminal.stream.flush_count,
            "last_write_line_count": len((renderer.last_written_frame or "").splitlines()),
            "last_write_col_count": max(
                (len(line) for line in (renderer.last_written_frame or "").splitlines()),
                default=0,
            ),
        },
    }

    (fixtures_dir / "ui_renderer_vectors.json").write_text(json.dumps({"vectors": vectors}, indent=2) + "\n")

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "dispatch_all_supported_modes_without_crash": dispatch_ok
        and all(item.get("rendered") is True for item in dispatch.values()),
        "dispatch_mode_markers_present": all(
            item.get("contains_marker") is True for item in dispatch.values() if item.get("rendered") is True
        ),
        "double_buffer_skips_identical_frame": writes_after_first == 1
        and writes_after_second == writes_after_first
        and writes_after_third == writes_after_second + 1,
        "resize_safety_notice_and_recovery": vectors["resize"]["small_contains_notice"] is True
        and vectors["resize"]["small_contains_current"] is True
        and vectors["resize"]["recover_contains_player"] is True,
        "single_write_per_emitted_frame": writes_after_third == 2,
    }

    artifact = {
        "slice": "phase3-renderer",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase3_renderer.json",
            "vectors_fixture": "tests/fixtures/ui_renderer_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
        "scope_note": "Phase 3 bounded renderer slice only: screen_mode dispatch, string-frame buffering/double-buffer write behavior, and resize-safe rendering.",
    }
    (artifacts_dir / "phase3_renderer.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
