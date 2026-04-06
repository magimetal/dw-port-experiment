#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.renderer import GameRenderer, RenderFrameRequest


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


class _FakeStream:
    def __init__(self) -> None:
        self.writes: list[str] = []

    def write(self, payload: str) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        return None


class _FakeTerminal:
    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width = width
        self.height = height
        self.stream = _FakeStream()


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


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
    base_state = _clone_state(GameState.fresh_game("ERDRICK"), story_flags=0x04)
    endgame_request = RenderFrameRequest(screen_mode="endgame", game_state=base_state)

    endgame_frame = renderer.draw(endgame_request)
    render_vector = {
        "render_path": endgame_request.screen_mode,
        "frame_contains_legend_text": "THE LEGEND LIVES ON." in endgame_frame,
        "frame_contains_press_enter": "PRESS ENTER TO RETURN TO TITLE." in endgame_frame,
    }

    terminal = _FakeTerminal(80, 24)
    renderer = GameRenderer(terminal, map_engine, npcs_payload=npcs_payload)
    terminal.stream.writes.clear()
    renderer.draw(endgame_request)
    writes_after_first = len(terminal.stream.writes)
    renderer.draw(endgame_request)
    writes_after_second = len(terminal.stream.writes)

    small_frame = renderer.draw(endgame_request, force_size=(60, 20))
    small_terminal_vector = {
        "contains_notice": "TERMINAL TOO SMALL" in small_frame,
        "contains_current": "CURRENT:  60x20" in small_frame,
    }

    vectors = {
        "endgame_render": render_vector,
        "double_buffer": {
            "writes_after_first": writes_after_first,
            "writes_after_second": writes_after_second,
        },
        "small_terminal": small_terminal_vector,
    }
    (fixtures_dir / "title_screen_endgame_renderer_vectors.json").write_text(
        json.dumps({"vectors": vectors}, indent=2) + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "endgame_render_path_is_explicit": render_vector["render_path"] == "endgame",
        "endgame_frame_contains_required_text": render_vector["frame_contains_legend_text"] is True
        and render_vector["frame_contains_press_enter"] is True,
        "endgame_double_buffer_skips_identical_frame": writes_after_first == 1
        and writes_after_second == writes_after_first,
        "endgame_small_terminal_guard_renders_notice": small_terminal_vector["contains_notice"] is True
        and small_terminal_vector["contains_current"] is True,
    }

    artifact = {
        "slice": "phase4-title-screen-endgame-renderer",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "report": "artifacts/phase4_title_screen_endgame_renderer.json",
            "vectors_fixture": "tests/fixtures/title_screen_endgame_renderer_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }
    (artifacts_dir / "phase4_title_screen_endgame_renderer.json").write_text(json.dumps(artifact, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
