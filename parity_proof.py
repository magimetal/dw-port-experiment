from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

from engine.map_engine import MapEngine
from engine.save_load import load_json_with_world_state, save_json
from engine.state import GameState
from main import MainLoopSession, MainLoopState, initial_title_state


class _ProofStream:
    def write(self, payload: str) -> None:
        return None

    def flush(self) -> None:
        return None


class _ProofTerminal:
    def __init__(self) -> None:
        self.width = 80
        self.height = 24
        self.stream = _ProofStream()


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text())


def _map_engine(root: Path) -> MapEngine:
    return MapEngine(
        maps_payload=_load_json(root / "extractor" / "data_out" / "maps.json"),
        warps_payload=_load_json(root / "extractor" / "data_out" / "warps.json"),
    )


def _npcs_payload(root: Path) -> dict[str, Any]:
    return _load_json(root / "extractor" / "data_out" / "npcs.json")


def _build_game_state(payload: dict[str, Any]) -> GameState:
    base = GameState.fresh_game(str(payload.get("fresh_game_name", "ERDRICK")))
    updates = dict(payload.get("game_state_updates", {}))
    data = base.to_dict()
    data.update(updates)
    return GameState(**data)


def _build_loop_state(payload: dict[str, Any]) -> MainLoopState:
    opened_doors = frozenset(
        tuple(int(value) for value in door)
        for door in payload.get("opened_doors", [])
    )
    return MainLoopState(
        screen_mode=str(payload.get("screen_mode", "map")),
        game_state=_build_game_state(payload),
        title_state=initial_title_state(),
        player_facing=str(payload.get("player_facing", "down")),
        opened_chest_indices=frozenset(int(value) for value in payload.get("opened_chest_indices", [])),
        opened_doors=opened_doors,
    )


def _build_session(root: Path, payload: dict[str, Any], *, save_path: Path | None = None) -> MainLoopSession:
    return MainLoopSession(
        terminal=_ProofTerminal(),
        map_engine=_map_engine(root),
        npcs_payload=_npcs_payload(root),
        save_path=save_path,
        state=_build_loop_state(payload),
    )


def _as_list(value: object) -> list[object]:
    if isinstance(value, list):
        return value
    return [value]


def _sorted_opened_doors(opened_doors: frozenset[tuple[int, int, int]]) -> list[list[int]]:
    return [list(door) for door in sorted(opened_doors)]


def _summarize_step(session: MainLoopSession, *, save_path: Path | None, frame: str, action_kind: str, action_detail: str) -> dict[str, Any]:
    combat = session.state.game_state.combat_session
    return {
        "action_kind": action_kind,
        "action_detail": action_detail,
        "screen_mode": session.state.screen_mode,
        "player_x": session.state.game_state.player_x,
        "player_y": session.state.game_state.player_y,
        "repel_timer": session.state.game_state.repel_timer,
        "light_timer": session.state.game_state.light_timer,
        "gold": session.state.game_state.gold,
        "hp": session.state.game_state.hp,
        "mp": session.state.game_state.mp,
        "equipment_byte": session.state.game_state.equipment_byte,
        "quit_requested": session.state.quit_requested,
        "save_exists": save_path.exists() if save_path is not None else False,
        "combat_enemy_id": None if combat is None else combat.enemy_id,
        "combat_enemy_name": None if combat is None else combat.enemy_name,
        "opened_chest_indices": sorted(session.state.opened_chest_indices),
        "opened_doors": _sorted_opened_doors(session.state.opened_doors),
        "frame": frame,
    }


def _check_expected_values(observed: dict[str, Any], expected: dict[str, Any]) -> dict[str, bool]:
    checks: dict[str, bool] = {}
    for key, value in expected.items():
        if key == "action_detail_contains":
            detail = str(observed.get("action_detail", ""))
            checks[key] = all(str(fragment) in detail for fragment in _as_list(value))
            continue
        if key == "frame_contains":
            frame = str(observed.get("frame", ""))
            checks[key] = all(str(fragment) in frame for fragment in _as_list(value))
            continue
        if key == "frame_not_contains":
            frame = str(observed.get("frame", ""))
            checks[key] = all(str(fragment) not in frame for fragment in _as_list(value))
            continue
        if key == "loaded_fields":
            checks[key] = observed.get(key) == value
            continue
        checks[key] = observed.get(key) == value
    return checks


def run_main_loop_fixture(fixture_path: Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(fixture_path)
    case_results: list[dict[str, Any]] = []
    overall_ok = True

    for case in payload.get("cases", []):
        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / f"{case['id']}.json" if case.get("use_temp_save_path") else None
            session = _build_session(root, case["state"], save_path=save_path)
            step_results: list[dict[str, Any]] = []
            case_ok = True
            for step in case.get("steps", []):
                result = session.step(str(step["input"]))
                observed = _summarize_step(
                    session,
                    save_path=save_path,
                    frame=result.frame,
                    action_kind=result.action.kind,
                    action_detail=result.action.detail,
                )
                checks = _check_expected_values(observed, dict(step.get("expected", {})))
                step_ok = all(checks.values())
                case_ok = case_ok and step_ok
                step_results.append(
                    {
                        "input": step["input"],
                        "ok": step_ok,
                        "checks": checks,
                        "observed": {key: value for key, value in observed.items() if key != "frame"},
                    }
                )
            case_results.append({"id": case["id"], "ok": case_ok, "steps": step_results})
            overall_ok = overall_ok and case_ok

    return {
        "id": payload.get("id", fixture_path.stem),
        "kind": payload.get("kind", "main_loop_sequence_cases"),
        "ok": overall_ok,
        "case_results": case_results,
    }


def run_save_load_fixture(fixture_path: Path, *, root: Path) -> dict[str, Any]:
    _ = root
    payload = _load_json(fixture_path)
    case_results: list[dict[str, Any]] = []
    overall_ok = True

    for case in payload.get("cases", []):
        with TemporaryDirectory() as tmpdir:
            save_path = Path(tmpdir) / f"{case['id']}.json"
            state = _build_game_state(case["state"])
            opened_chest_indices = frozenset(int(value) for value in case.get("opened_chest_indices", []))
            opened_doors = frozenset(tuple(int(value) for value in door) for door in case.get("opened_doors", []))
            save_json(
                state,
                slot=0,
                path=save_path,
                opened_chest_indices=opened_chest_indices,
                opened_doors=opened_doors,
            )
            loaded, loaded_chests, loaded_doors = load_json_with_world_state(slot=0, path=save_path)
            expected = dict(case.get("expected", {}))
            loaded_field_expectations = dict(expected.get("loaded_fields", {}))
            observed = {
                "save_exists": save_path.exists(),
                "save_data_equal": loaded.to_save_dict() == state.to_save_dict(),
                "opened_chest_indices": sorted(loaded_chests),
                "opened_doors": [list(door) for door in sorted(loaded_doors)],
                "loaded_fields": {
                    field: getattr(loaded, field)
                    for field in loaded_field_expectations
                },
            }
            checks = _check_expected_values(observed, expected)
            case_ok = all(checks.values())
            case_results.append(
                {
                    "id": case["id"],
                    "ok": case_ok,
                    "checks": checks,
                    "observed": observed,
                }
            )
            overall_ok = overall_ok and case_ok

    return {
        "id": payload.get("id", fixture_path.stem),
        "kind": payload.get("kind", "save_load_roundtrip_cases"),
        "ok": overall_ok,
        "case_results": case_results,
    }


def run_fixture(fixture_path: Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(fixture_path)
    kind = str(payload.get("kind", ""))
    if kind == "main_loop_sequence_cases":
        return run_main_loop_fixture(fixture_path, root=root)
    if kind == "save_load_roundtrip_cases":
        return run_save_load_fixture(fixture_path, root=root)
    raise ValueError(f"unsupported parity fixture kind: {kind}")


def evaluate_manifest(manifest_path: Path, *, root: Path) -> dict[str, Any]:
    payload = _load_json(manifest_path)
    fixture_entries = payload.get("fixtures", [])
    fixture_results: list[dict[str, Any]] = []
    executable_domains: set[str] = set()
    declared_domains: set[str] = set()
    overall_ok = True
    total_cases = 0

    for entry in fixture_entries:
        if not isinstance(entry, dict):
            overall_ok = False
            continue
        domain = str(entry.get("domain", ""))
        if domain:
            declared_domains.add(domain)
        fixture_file = entry.get("fixture_file")
        if not isinstance(fixture_file, str) or not fixture_file:
            fixture_results.append(
                {
                    "id": entry.get("id"),
                    "domain": domain,
                    "ok": False,
                    "error": "missing fixture_file",
                }
            )
            overall_ok = False
            continue
        fixture_path = manifest_path.parent / fixture_file
        if not fixture_path.exists():
            fixture_results.append(
                {
                    "id": entry.get("id"),
                    "domain": domain,
                    "ok": False,
                    "error": f"missing fixture file: {fixture_file}",
                }
            )
            overall_ok = False
            continue
        result = run_fixture(fixture_path, root=root)
        total_cases += len(result.get("case_results", []))
        fixture_results.append(
            {
                "id": entry.get("id"),
                "domain": domain,
                "fixture_file": fixture_file,
                "ok": bool(result.get("ok")),
                "result": result,
            }
        )
        if result.get("ok"):
            executable_domains.add(domain)
        else:
            overall_ok = False

    return {
        "ok": overall_ok,
        "declared_domains": sorted(domain for domain in declared_domains if domain),
        "executable_domains": sorted(domain for domain in executable_domains if domain),
        "fixture_count": len([entry for entry in fixture_entries if isinstance(entry, dict)]),
        "case_count": total_cases,
        "fixture_results": fixture_results,
    }
