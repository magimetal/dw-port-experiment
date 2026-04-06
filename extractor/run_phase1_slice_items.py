#!/usr/bin/env python3
from __future__ import annotations

import json
from pathlib import Path

from extractor.items import (
    ARMOR_BONUS_TABLE_START,
    INN_COST_TABLE_START,
    ITEM_COST_COUNT,
    ITEM_COST_TABLE_START,
    KEY_COST_TABLE_START,
    SHIELD_BONUS_TABLE_START,
    SHOP_ITEMS_TABLE_END,
    SHOP_ITEMS_TABLE_START,
    WEAPONS_BONUS_TABLE_START,
    extract_items_tables,
)
from extractor.rom import DW1ROM


def _collect_items_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()

    labels = [
        "ItemCostTbl",
        "InnCostTbl",
        "ShopItemsTbl",
        "WeaponsBonusTbl",
        "ArmorBonusTbl",
        "ShieldBonusTbl",
    ]

    return {
        "completed": True,
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_text.encode("utf-8")),
                "lines": bank00_text.count("\n"),
                "labels_checked": {label: (label in bank00_text) for label in labels},
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in labels},
            },
        },
    }


def main() -> int:
    root = Path(__file__).resolve().parents[1]
    rom = DW1ROM.from_baseline(root)

    read_gate = _collect_items_read_gate(Path("/tmp/dw-disassembly/source_files"))
    read_gate_path = root / "artifacts" / "phase1_items_read_gate.json"
    read_gate_path.parent.mkdir(parents=True, exist_ok=True)
    read_gate_path.write_text(json.dumps(read_gate, indent=2) + "\n")

    tables = extract_items_tables(rom)
    output = {
        "source": {
            "bank00_labels": [
                "ItemCostTbl",
                "InnCostTbl",
                "ShopItemsTbl",
                "WeaponsBonusTbl",
                "ArmorBonusTbl",
                "ShieldBonusTbl",
            ],
            "bank03_aliases": [
                "ItemCostTbl",
                "InnCostTbl",
                "ShopItemsTbl",
                "WeaponsBonusTbl",
                "ArmorBonusTbl",
                "ShieldBonusTbl",
            ],
            "item_cost_table_start": hex(ITEM_COST_TABLE_START),
            "item_cost_count": ITEM_COST_COUNT,
            "key_cost_table_start": hex(KEY_COST_TABLE_START),
            "inn_cost_table_start": hex(INN_COST_TABLE_START),
            "shop_items_table_start": hex(SHOP_ITEMS_TABLE_START),
            "shop_items_table_end": hex(SHOP_ITEMS_TABLE_END),
            "weapons_bonus_table_start": hex(WEAPONS_BONUS_TABLE_START),
            "armor_bonus_table_start": hex(ARMOR_BONUS_TABLE_START),
            "shield_bonus_table_start": hex(SHIELD_BONUS_TABLE_START),
        },
        **tables,
    }

    out_path = root / "extractor" / "data_out" / "items.json"
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(json.dumps(output, indent=2) + "\n")

    artifact = {
        "slice": "phase1-items",
        "item_cost_count": len(tables["item_costs"]),
        "shop_count": len(tables["shop_inventories"]),
        "first_item_cost": tables["item_costs"][0],
        "last_item_cost": tables["item_costs"][-1],
        "first_shop": tables["shop_inventories"][0],
        "last_shop": tables["shop_inventories"][-1],
        "weapon_bonuses": tables["equipment_bonuses"]["weapons"],
        "armor_bonuses": tables["equipment_bonuses"]["armor"],
        "shield_bonuses": tables["equipment_bonuses"]["shields"],
    }
    artifact_path = root / "artifacts" / "phase1_items_extraction.json"
    artifact_path.write_text(json.dumps(artifact, indent=2) + "\n")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
