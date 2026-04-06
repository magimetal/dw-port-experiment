import json
from pathlib import Path

from engine.map_engine import MapEngine
from engine.state import GameState
from ui.combat_view import initial_combat_view_state
from ui.renderer import GameRenderer, RenderFrameRequest, SUPPORTED_SCREEN_MODES, is_supported_screen_mode
from ui.title_screen import initial_title_state


ROOT = Path(__file__).resolve().parents[1]


def _clone_state(state: GameState, **updates: int) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m ui.run_phase3_slice_renderer first: {path}"
    return json.loads(path.read_text())


def _is_ascii_only(text: str) -> bool:
    return all(ch == "\n" or ord(ch) < 128 for ch in text)


def _map_engine() -> MapEngine:
    maps_payload = json.loads((ROOT / "extractor" / "data_out" / "maps.json").read_text())
    warps_payload = json.loads((ROOT / "extractor" / "data_out" / "warps.json").read_text())
    return MapEngine(maps_payload=maps_payload, warps_payload=warps_payload)


def _npcs_payload() -> dict:
    return json.loads((ROOT / "extractor" / "data_out" / "npcs.json").read_text())


class _FakeStream:
    def __init__(self) -> None:
        self.writes: list[str] = []
        self.flush_count = 0

    def write(self, payload: str) -> None:
        self.writes.append(payload)

    def flush(self) -> None:
        self.flush_count += 1


class _FakeTerminal:
    def __init__(self, width: int = 80, height: int = 24) -> None:
        self.width = width
        self.height = height
        self.stream = _FakeStream()


def _renderer() -> tuple[GameRenderer, _FakeTerminal, GameState]:
    terminal = _FakeTerminal()
    state = _clone_state(GameState.fresh_game("ERDRICK"), map_id=4, player_x=11, player_y=11)
    renderer = GameRenderer(terminal, _map_engine(), npcs_payload=_npcs_payload())
    return renderer, terminal, state


def test_supported_screen_modes_predicate_is_consistent() -> None:
    for mode in SUPPORTED_SCREEN_MODES:
        assert is_supported_screen_mode(mode) is True
    assert is_supported_screen_mode("unknown") is False


def test_renderer_dispatches_all_supported_modes_without_crash() -> None:
    renderer, _terminal, state = _renderer()
    requests = (
        RenderFrameRequest(screen_mode="title", game_state=state, title_state=initial_title_state()),
        RenderFrameRequest(screen_mode="map", game_state=state),
        RenderFrameRequest(
            screen_mode="combat",
            game_state=state,
            combat_state=initial_combat_view_state(combat_log=("A Slime appears.",)),
            enemy_name="Slime",
            enemy_hp=3,
            enemy_max_hp=3,
            learned_spells=("HEAL",),
        ),
        RenderFrameRequest(screen_mode="dialog", game_state=state, dialog_text="Hello there."),
        RenderFrameRequest(screen_mode="endgame", game_state=state),
    )

    outputs = [renderer.draw(request) for request in requests]
    assert "W A R R I O R" in outputs[0]
    assert "@" in outputs[1]
    assert "BATTLE" in outputs[2]
    assert "╔" in outputs[3]
    assert "THE LEGEND LIVES ON. PRESS ENTER TO RETURN TO TITLE." in outputs[4]


def test_renderer_double_buffer_skips_identical_frame_writes() -> None:
    renderer, terminal, state = _renderer()
    request = RenderFrameRequest(screen_mode="map", game_state=state)
    renderer.draw(request)
    first = len(terminal.stream.writes)
    renderer.draw(request)
    second = len(terminal.stream.writes)
    renderer.draw(RenderFrameRequest(screen_mode="title", game_state=state, title_state=initial_title_state()))
    third = len(terminal.stream.writes)

    assert first == 1
    assert second == 1
    assert third == 2


def test_renderer_handles_resize_without_exception_and_recovers() -> None:
    renderer, terminal, state = _renderer()
    request = RenderFrameRequest(screen_mode="map", game_state=state)

    terminal.width = 60
    terminal.height = 20
    small_frame = renderer.draw(request)
    assert "TERMINAL TOO SMALL" in small_frame
    assert "CURRENT:  60x20" in small_frame

    terminal.width = 80
    terminal.height = 24
    recovered_frame = renderer.draw(request)
    assert "@" in recovered_frame


def test_small_terminal_notice_enforced_when_cols_below_minimum() -> None:
    renderer, _terminal, state = _renderer()
    frame = renderer.draw(RenderFrameRequest(screen_mode="map", game_state=state), force_size=(79, 24))

    assert "TERMINAL TOO SMALL" in frame
    assert "REQUIRED: 80x24" in frame
    assert "CURRENT:  79x24" in frame
    assert "@" not in frame
    assert "NAME:" not in frame
    assert "┌" not in frame


def test_small_terminal_notice_enforced_when_rows_below_minimum() -> None:
    renderer, _terminal, state = _renderer()
    frame = renderer.draw(RenderFrameRequest(screen_mode="map", game_state=state), force_size=(80, 23))

    assert "TERMINAL TOO SMALL" in frame
    assert "REQUIRED: 80x24" in frame
    assert "CURRENT:  80x23" in frame
    assert "@" not in frame
    assert "NAME:" not in frame
    assert "┌" not in frame


def test_ascii_fallback_map_frame_is_ascii_only_and_preserves_layout_markers() -> None:
    renderer, _terminal, state = _renderer()
    frame = renderer.draw(RenderFrameRequest(screen_mode="map", game_state=state, ascii_fallback=True))

    assert _is_ascii_only(frame) is True
    assert "@" in frame
    assert "NAME " in frame
    assert " DIALOG " in frame
    assert "|" in frame
    assert "┌" not in frame
    assert "░" not in frame


def test_ascii_fallback_combat_and_dialog_frames_are_ascii_only() -> None:
    renderer, _terminal, state = _renderer()
    combat_frame = renderer.draw(
        RenderFrameRequest(
            screen_mode="combat",
            game_state=state,
            combat_state=initial_combat_view_state(combat_log=("A Slime appears.",)),
            enemy_name="Slime",
            enemy_hp=3,
            enemy_max_hp=3,
            learned_spells=("HEAL",),
            ascii_fallback=True,
        )
    )
    dialog_frame = renderer.draw(
        RenderFrameRequest(
            screen_mode="dialog",
            game_state=state,
            dialog_text="Welcome to Alefgard.",
            ascii_fallback=True,
        )
    )

    assert _is_ascii_only(combat_frame) is True
    assert "BATTLE" in combat_frame
    assert ">" in combat_frame
    assert "┌" not in combat_frame

    assert _is_ascii_only(dialog_frame) is True
    assert "Welcome to Alefgard." in dialog_frame
    assert "+" in dialog_frame
    assert "|" in dialog_frame
    assert "╔" not in dialog_frame


def test_ui_renderer_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase3_renderer.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "ui_renderer_vectors.json")

    assert report["slice"] == "phase3-renderer"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["dispatch"]["title"]["contains_marker"] is True
    assert v["dispatch"]["map"]["contains_marker"] is True
    assert v["dispatch"]["combat"]["contains_marker"] is True
    assert v["dispatch"]["dialog"]["contains_marker"] is True
    assert v["double_buffer"]["writes_after_first"] == 1
    assert v["double_buffer"]["writes_after_second"] == 1
    assert v["double_buffer"]["writes_after_third"] == 2
    assert v["resize"]["small_contains_notice"] is True
    assert v["resize"]["recover_contains_player"] is True


def test_phase4_title_screen_endgame_renderer_artifacts_exist_and_are_consistent() -> None:
    report = _load_fixture(ROOT / "artifacts" / "phase4_title_screen_endgame_renderer.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "title_screen_endgame_renderer_vectors.json")

    assert report["slice"] == "phase4-title-screen-endgame-renderer"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    v = vectors["vectors"]
    assert v["endgame_render"]["render_path"] == "endgame"
    assert v["endgame_render"]["frame_contains_legend_text"] is True
    assert v["endgame_render"]["frame_contains_press_enter"] is True
    assert v["double_buffer"]["writes_after_first"] == 1
    assert v["double_buffer"]["writes_after_second"] == 1
    assert v["small_terminal"]["contains_notice"] is True
    assert v["small_terminal"]["contains_current"] is True
