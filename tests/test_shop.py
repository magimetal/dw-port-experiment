import json
from pathlib import Path

from engine.shop import ShopRuntime
from engine.state import GameState


ROOT = Path(__file__).resolve().parents[1]


def _load_fixture(path: Path) -> dict:
    assert path.exists(), f"run python3 -m engine.run_phase2_slice_shop first: {path}"
    return json.loads(path.read_text())


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
    data = state.to_dict()
    data.update(updates)
    return GameState(**data)


def test_shop_inventory_prices_and_inn_costs_match_extracted_tables() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    inv = runtime.shop_inventory(0)

    assert [row["item_id"] for row in inv] == [2, 3, 10, 11, 14]
    assert [row["price"] for row in inv] == [180, 560, 1000, 3000, 90]
    assert [runtime.inn_cost(index) for index in range(5)] == [20, 6, 25, 100, 55]


def test_weapon_purchase_applies_buyback_and_equips_new_weapon() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    state = _clone_state(GameState.fresh_game("ERDRICK"), gold=200, equipment_byte=0x40)

    updated, success, message = runtime.buy(state, 2)

    assert success is True
    assert message == "purchased and equipped"
    assert updated.gold == 50
    assert updated.equipment_byte == 0x60


def test_herb_cap_and_inventory_full_block_purchase() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")

    herb_cap = _clone_state(GameState.fresh_game("ERDRICK"), herbs=6)
    herb_result, herb_ok, herb_msg = runtime.buy(herb_cap, 17)
    assert herb_ok is False
    assert herb_msg == "cannot hold more herbs"
    assert herb_result.to_dict() == herb_cap.to_dict()

    full = _clone_state(GameState.fresh_game("ERDRICK"), inventory_slots=(0x11, 0x11, 0x11, 0x11))
    full_result, full_ok, full_msg = runtime.buy(full, 19)
    assert full_ok is False
    assert full_msg == "inventory full"
    assert full_result.to_dict() == full.to_dict()


def test_tool_buy_and_sell_use_nibble_inventory_and_half_price_sale() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")

    purchased, ok, _ = runtime.buy(GameState.fresh_game("ERDRICK"), 19)
    assert ok is True
    assert purchased.gold == 112
    assert purchased.inventory_slots == (0x01, 0x00, 0x00, 0x00)

    sold, gold_gain = runtime.sell(_clone_state(purchased, gold=0), 19)
    assert gold_gain == 4
    assert sold.gold == 4
    assert sold.inventory_slots == (0x00, 0x00, 0x00, 0x00)


def test_sell_herb_decrements_counter_and_adds_half_price() -> None:
    runtime = ShopRuntime.from_file(ROOT / "extractor" / "data_out" / "items.json")
    state = _clone_state(GameState.fresh_game("ERDRICK"), gold=0, herbs=1)

    sold, gold_gain = runtime.sell(state, 17)
    assert gold_gain == 12
    assert sold.gold == 12
    assert sold.herbs == 0


def test_shop_slice_artifacts_exist_and_are_consistent() -> None:
    read_gate = _load_fixture(ROOT / "artifacts" / "phase2_shop_read_gate.json")
    report = _load_fixture(ROOT / "artifacts" / "phase2_shop_runtime.json")
    vectors = _load_fixture(ROOT / "tests" / "fixtures" / "shop_runtime_vectors.json")

    assert read_gate["completed"] is True
    assert read_gate["slice"] == "phase2-shop"
    assert all(read_gate["files"]["Bank00.asm"]["labels_checked"].values())
    assert all(read_gate["files"]["Bank03.asm"]["labels_checked"].values())

    assert report["slice"] == "phase2-shop"
    assert report["all_passed"] is True
    assert all(report["checks"].values())

    fixture_vectors = vectors["vectors"]
    assert fixture_vectors["shop_0_item_ids"] == [2, 3, 10, 11, 14]
    assert fixture_vectors["shop_0_prices"] == [180, 560, 1000, 3000, 90]
    assert fixture_vectors["inn_costs"] == [20, 6, 25, 100, 55]
    assert fixture_vectors["buy_copper_from_club_gold"] == 50
    assert fixture_vectors["buy_torch_inventory_slots"] == [1, 0, 0, 0]
    assert fixture_vectors["sell_torch_gold_gain"] == 4
