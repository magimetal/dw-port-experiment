import json
from pathlib import Path

from extractor.items import (
    ARMOR_BONUS_TABLE_START,
    INN_COST_COUNT,
    INN_COST_TABLE_START,
    ITEM_COST_COUNT,
    ITEM_COST_TABLE_START,
    KEY_COST_COUNT,
    KEY_COST_TABLE_START,
    SHIELD_BONUS_TABLE_START,
    SHOP_ITEMS_TABLE_END,
    SHOP_ITEMS_TABLE_START,
    WEAPONS_BONUS_TABLE_START,
    extract_items_tables,
)
from extractor.rom import DW1ROM


ROOT = Path(__file__).resolve().parents[1]


def test_items_table_offsets_and_counts() -> None:
    assert ITEM_COST_TABLE_START == 0x1957
    assert ITEM_COST_COUNT == 33
    assert KEY_COST_TABLE_START == 0x1999
    assert KEY_COST_COUNT == 3
    assert INN_COST_TABLE_START == 0x199C
    assert INN_COST_COUNT == 5
    assert SHOP_ITEMS_TABLE_START == 0x19A1
    assert SHOP_ITEMS_TABLE_END == 0x19DE
    assert WEAPONS_BONUS_TABLE_START == 0x19DF
    assert ARMOR_BONUS_TABLE_START == 0x19E7
    assert SHIELD_BONUS_TABLE_START == 0x19EF


def test_item_costs_shop_and_bonus_tables_from_rom() -> None:
    rom = DW1ROM.from_baseline(ROOT)
    tables = extract_items_tables(rom)

    item_costs = tables["item_costs"]
    assert len(item_costs) == ITEM_COST_COUNT
    assert item_costs[0]["item_name"] == "Bamboo pole"
    assert item_costs[0]["gold"] == 10
    assert item_costs[5]["item_name"] == "Flame sword"
    assert item_costs[5]["gold"] == 9800
    assert item_costs[16]["item_name"] == "Silver shield"
    assert item_costs[16]["gold"] == 14800
    assert item_costs[-1]["item_name"] == "Rainbow drop"
    assert item_costs[-1]["gold"] == 0

    assert [row["gold"] for row in tables["key_costs"]] == [98, 53, 85]
    assert [row["gold"] for row in tables["inn_costs"]] == [20, 6, 25, 100, 55]

    shops = tables["shop_inventories"]
    assert len(shops) == 12
    assert shops[0]["item_ids"] == [2, 3, 10, 11, 14]
    assert shops[-1]["item_ids"] == [22, 21]

    bonuses = tables["equipment_bonuses"]
    assert bonuses["weapons"] == [0, 2, 4, 10, 15, 20, 28, 40]
    assert bonuses["armor"] == [0, 2, 4, 10, 16, 24, 24, 28]
    assert bonuses["shields"] == [0, 4, 10, 20]


def test_items_output_and_artifacts_exist() -> None:
    items_path = ROOT / "extractor" / "data_out" / "items.json"
    artifact_path = ROOT / "artifacts" / "phase1_items_extraction.json"
    read_gate_path = ROOT / "artifacts" / "phase1_items_read_gate.json"

    assert items_path.exists(), "run python3 -m extractor.run_phase1_slice_items first"
    assert artifact_path.exists(), "run python3 -m extractor.run_phase1_slice_items first"
    assert read_gate_path.exists(), "run python3 -m extractor.run_phase1_slice_items first"

    items_data = json.loads(items_path.read_text())
    artifact = json.loads(artifact_path.read_text())
    read_gate = json.loads(read_gate_path.read_text())

    assert len(items_data["item_costs"]) == ITEM_COST_COUNT
    assert len(items_data["shop_inventories"]) == 12
    assert artifact["slice"] == "phase1-items"
    assert artifact["item_cost_count"] == ITEM_COST_COUNT
    assert artifact["shop_count"] == 12

    assert read_gate["completed"] is True
    for label in [
        "ItemCostTbl",
        "InnCostTbl",
        "ShopItemsTbl",
        "WeaponsBonusTbl",
        "ArmorBonusTbl",
        "ShieldBonusTbl",
    ]:
        assert read_gate["files"]["Bank00.asm"]["labels_checked"][label] is True
        assert read_gate["files"]["Bank03.asm"]["labels_checked"][label] is True
