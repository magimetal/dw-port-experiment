#!/usr/bin/env python3
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from engine.shop import ShopRuntime
from engine.state import GameState


def _sha1(path: Path) -> str:
    digest = hashlib.sha1()
    with path.open("rb") as handle:
        while chunk := handle.read(65536):
            digest.update(chunk)
    return digest.hexdigest()


def _collect_shop_read_gate(disassembly_root: Path) -> dict:
    bank00_path = disassembly_root / "Bank00.asm"
    bank03_path = disassembly_root / "Bank03.asm"
    bank00_text = bank00_path.read_text()
    bank03_text = bank03_path.read_text()

    bank00_labels = ["ItemCostTbl", "InnCostTbl", "ShopItemsTbl"]
    bank03_labels = [
        "ItemCostTbl",
        "InnCostTbl",
        "ShopItemsTbl",
        "CheckBuyWeapon",
        "GetBuybackPrice",
        "ApplyPurchase",
        "DoToolPurchase",
        "ChkToolPurchase",
        "AddInvItem",
        "DoToolSell",
        "KeysDialog",
        "InnDialog",
    ]
    return {
        "completed": True,
        "slice": "phase2-shop",
        "source_directory": str(disassembly_root),
        "files": {
            "Bank00.asm": {
                "path": str(bank00_path),
                "bytes": len(bank00_text.encode("utf-8")),
                "lines": bank00_text.count("\n"),
                "labels_checked": {label: (label in bank00_text) for label in bank00_labels},
            },
            "Bank03.asm": {
                "path": str(bank03_path),
                "bytes": len(bank03_text.encode("utf-8")),
                "lines": bank03_text.count("\n"),
                "labels_checked": {label: (label in bank03_text) for label in bank03_labels},
            },
        },
    }


def _clone_state(state: GameState, **updates: int | tuple[int, int, int, int]) -> GameState:
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

    runtime = ShopRuntime.from_file(root / "extractor" / "data_out" / "items.json")
    read_gate = _collect_shop_read_gate(Path("/tmp/dw-disassembly/source_files"))
    (artifacts_dir / "phase2_shop_read_gate.json").write_text(
        json.dumps(read_gate, indent=2) + "\n"
    )

    base = GameState.fresh_game("ERDRICK")
    buy_weapon_state = _clone_state(base, gold=200, equipment_byte=0x40)
    buy_weapon_result, buy_weapon_success, _ = runtime.buy(buy_weapon_state, 2)

    buy_herb_cap_state = _clone_state(base, herbs=6)
    buy_herb_cap_result, buy_herb_cap_success, buy_herb_cap_message = runtime.buy(
        buy_herb_cap_state, 17
    )

    buy_torch_result, buy_torch_success, _ = runtime.buy(base, 19)
    full_inventory_state = _clone_state(base, inventory_slots=(0x11, 0x11, 0x11, 0x11))
    buy_torch_full_result, buy_torch_full_success, buy_torch_full_message = runtime.buy(
        full_inventory_state, 19
    )

    sell_tool_state = _clone_state(base, gold=0, inventory_slots=(0x01, 0x00, 0x00, 0x00))
    sell_tool_result, sell_tool_gold = runtime.sell(sell_tool_state, 19)
    sell_herb_state = _clone_state(base, gold=0, herbs=1)
    sell_herb_result, sell_herb_gold = runtime.sell(sell_herb_state, 17)

    vectors = {
        "shop_0_item_ids": [row["item_id"] for row in runtime.shop_inventory(0)],
        "shop_0_prices": [row["price"] for row in runtime.shop_inventory(0)],
        "inn_costs": [runtime.inn_cost(index) for index in range(5)],
        "is_shop0_selling_copper_sword": runtime.is_item_sold_in_shop(0, 2),
        "is_shop0_selling_flame_sword": runtime.is_item_sold_in_shop(0, 5),
        "can_afford_120_gold_bamboo": runtime.can_afford(base, 0),
        "can_afford_120_gold_copper": runtime.can_afford(base, 2),
        "buy_copper_from_club_success": buy_weapon_success,
        "buy_copper_from_club_gold": buy_weapon_result.gold,
        "buy_copper_from_club_equipment": buy_weapon_result.equipment_byte,
        "buy_herb_cap_success": buy_herb_cap_success,
        "buy_herb_cap_message": buy_herb_cap_message,
        "buy_herb_cap_state_unchanged": buy_herb_cap_result.to_dict() == buy_herb_cap_state.to_dict(),
        "buy_torch_success": buy_torch_success,
        "buy_torch_gold": buy_torch_result.gold,
        "buy_torch_inventory_slots": list(buy_torch_result.inventory_slots),
        "buy_torch_full_success": buy_torch_full_success,
        "buy_torch_full_message": buy_torch_full_message,
        "buy_torch_full_state_unchanged": buy_torch_full_result.to_dict() == full_inventory_state.to_dict(),
        "sell_torch_gold_gain": sell_tool_gold,
        "sell_torch_new_gold": sell_tool_result.gold,
        "sell_torch_inventory_slots": list(sell_tool_result.inventory_slots),
        "sell_herb_gold_gain": sell_herb_gold,
        "sell_herb_new_gold": sell_herb_result.gold,
        "sell_herb_new_count": sell_herb_result.herbs,
    }

    (fixtures_dir / "shop_runtime_vectors.json").write_text(
        json.dumps(
            {
                "source": {
                    "bank00_labels": ["ItemCostTbl", "InnCostTbl", "ShopItemsTbl"],
                    "bank03_labels": [
                        "CheckBuyWeapon",
                        "GetBuybackPrice",
                        "ApplyPurchase",
                        "DoToolPurchase",
                        "ChkToolPurchase",
                        "AddInvItem",
                        "DoToolSell",
                        "KeysDialog",
                        "InnDialog",
                    ],
                },
                "vectors": vectors,
            },
            indent=2,
        )
        + "\n"
    )

    checks = {
        "rom_baseline_match": rom_sha1 == baseline["accepted_sha1"],
        "all_bank00_labels_present": all(
            read_gate["files"]["Bank00.asm"]["labels_checked"].values()
        ),
        "all_bank03_labels_present": all(
            read_gate["files"]["Bank03.asm"]["labels_checked"].values()
        ),
        "shop0_inventory_matches_items_json": vectors["shop_0_item_ids"] == [2, 3, 10, 11, 14],
        "shop0_prices_match_item_costs": vectors["shop_0_prices"] == [180, 560, 1000, 3000, 90],
        "inn_costs_match_table": vectors["inn_costs"] == [20, 6, 25, 100, 55],
        "weapon_buyback_applies_half_price": (
            vectors["buy_copper_from_club_success"] is True
            and vectors["buy_copper_from_club_gold"] == 50
            and vectors["buy_copper_from_club_equipment"] == 0x60
        ),
        "herb_cap_blocks_purchase": (
            vectors["buy_herb_cap_success"] is False
            and vectors["buy_herb_cap_message"] == "cannot hold more herbs"
            and vectors["buy_herb_cap_state_unchanged"] is True
        ),
        "tool_purchase_adds_inventory_nibble": (
            vectors["buy_torch_success"] is True
            and vectors["buy_torch_gold"] == 112
            and vectors["buy_torch_inventory_slots"] == [1, 0, 0, 0]
        ),
        "full_inventory_blocks_tool_purchase": (
            vectors["buy_torch_full_success"] is False
            and vectors["buy_torch_full_message"] == "inventory full"
            and vectors["buy_torch_full_state_unchanged"] is True
        ),
        "tool_sell_returns_half_price": (
            vectors["sell_torch_gold_gain"] == 4
            and vectors["sell_torch_new_gold"] == 4
            and vectors["sell_torch_inventory_slots"] == [0, 0, 0, 0]
        ),
        "herb_sell_updates_counter_and_gold": (
            vectors["sell_herb_gold_gain"] == 12
            and vectors["sell_herb_new_gold"] == 12
            and vectors["sell_herb_new_count"] == 0
        ),
    }

    artifact = {
        "slice": "phase2-shop",
        "all_passed": all(checks.values()),
        "checks": checks,
        "outputs": {
            "read_gate": "artifacts/phase2_shop_read_gate.json",
            "report": "artifacts/phase2_shop_runtime.json",
            "vectors_fixture": "tests/fixtures/shop_runtime_vectors.json",
        },
        "rom": {
            "path": baseline["rom_file"],
            "sha1": rom_sha1,
            "accepted_sha1": baseline["accepted_sha1"],
            "baseline_match": rom_sha1 == baseline["accepted_sha1"],
        },
    }

    (artifacts_dir / "phase2_shop_runtime.json").write_text(
        json.dumps(artifact, indent=2) + "\n"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
