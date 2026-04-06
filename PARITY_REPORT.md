# PARITY_REPORT.md

| # | System | Test | Expected | Status | Evidence | ROM Evidence Source |
|---:|---|---|---|---|---|---|
| 1 | ROM | SHA1 match | 66809063b828197d1fe12232ebd08ec0a498aa04 | PASS | extractor/rom_baseline.json + dragon-warrior-1.nes | verify.py phase gate baseline |
| 2 | ROM | PRG size | 65536 | PASS | extractor/data_out/rom_header.json | iNES header byte 4 |
| 3 | ROM | CHR size | 16384 | PASS | extractor/data_out/rom_header.json | iNES header byte 5 |
| 4 | ROM | Mapper | 1 | PASS | extractor/data_out/rom_header.json | Header flags 6/7 |
| 5 | Maps | Overworld dimensions | [120, 120] | PASS | extractor/data_out/maps.json | Data Crystal ROM map 0x1D6D |
| 6 | Maps | Map metadata count | 30 entries ids 0..29 | PASS | extractor/data_out/maps.json | ROM metadata table 0x002A-0x00C0 |
| 7 | Maps | Tantegel size | [30, 30] | PASS | extractor/data_out/maps.json | Metadata entry 4 |
| 8 | Maps | Throne Room size | [10, 10] | PASS | extractor/data_out/maps.json | Metadata entry 5 |
| 9 | Chests | Chest count | 31 | PASS | extractor/data_out/chests.json | ROM 0x5DDD-0x5E58 |
| 10 | Chests | Tantegel chest spot-check | [4, 1, 13, 19] | PASS | extractor/data_out/chests.json | Extracted TreasureTbl entry |
| 11 | Enemies | Enemy count | 40 | PASS | extractor/data_out/enemies.json | EnStatTbl |
| 12 | Enemies | Enemy 0 name | Slime | PASS | extractor/data_out/enemies.json | EnStatTbl entry 0x00 |
| 13 | Enemies | Dragonlord form2 HP base | 130 | PASS | extractor/data_out/enemies.json + artifacts/phase5_slice_edge_case_regression_gate.json | Enemy table @ ROM 0x5E5B |
| 14 | MP Costs | HEAL | 4 | PASS | extractor/data_out/spells.json | SpellCostTbl @ 0x1D63 |
| 15 | MP Costs | HURTMORE | 5 | PASS | extractor/data_out/spells.json | SpellCostTbl @ 0x1D6C |
| 16 | MP Costs | RETURN | 8 | PASS | extractor/data_out/spells.json | SpellCostTbl @ 0x1D69 |
| 17 | MP Costs | OUTSIDE | 6 | PASS | extractor/data_out/spells.json | SpellCostTbl @ 0x1D68 |
| 18 | XP Table | Level 2 threshold | 7 | PASS | extractor/data_out/xp_table.json | Bank03 LF35D |
| 19 | XP Table | Level 10 threshold | 2000 | PASS | extractor/data_out/xp_table.json | Bank03 LF36D |
| 20 | XP Table | Level 20 threshold | 26000 | PASS | extractor/data_out/xp_table.json | Bank03 LF381 |
| 21 | XP Table | Level 30 threshold | 65535 | PASS | extractor/data_out/xp_table.json | Bank03 LF395 |
| 22 | XP Table | All 30 thresholds | 30 entries | PASS | extractor/data_out/xp_table.json | Bank03 LF35B-LF395 |
| 23 | RNG | Golden sequence | 1000 ticks match fixture | PASS | tests/fixtures/rng_golden_sequence.json | Bank03 LC55B |
| 24 | RNG | Deterministic seed replay | same-seed sequences identical | PASS | tests/test_rng.py::test_rng_determinism | Bank03 LFSR |
| 25 | Combat | Excellent move chance | 8/256 (=1/32) | PASS | engine.combat.excellent_move_check | Bank03 LE61F |
| 26 | Combat | No excellent vs Dragonlord | 0/256 | PASS | engine.combat.excellent_move_check + artifacts/phase5_slice_edge_case_regression_gate.json | Bank03 LE617-LE61D |
| 27 | Combat | Player weak attack split | 128 zeros / 128 ones | PASS | engine.combat.player_attack_damage | Bank03 LF026 |
| 28 | Combat | Normal attack formula parity | 44 | PASS | engine.combat.player_attack_damage | Bank03 LF030 |
| 29 | Combat | 8-bit wraparound boundary | 63 | PASS | tests/test_combat.py::test_player_attack_boundary_max_atk_min_def | Bank03 arithmetic wrap |
| 30 | Combat | HEAL range | 10..17 | PASS | engine.combat.heal_spell_hp | Bank03 LDBB8 |
| 31 | Combat | HEALMORE range | 85..100 | PASS | engine.combat.healmore_spell_hp | Bank03 LDBD7 |
| 32 | Combat | HURT/HURTMORE ranges | HURT 5..12; HURTMORE 58..65 | PASS | engine.combat.hurt_spell_damage + hurtmore_spell_damage | Bank03 LE736/LE751 |
| 33 | Combat | Enemy HP init formula | randomized and bounded 98..130 | PASS | engine.combat.enemy_hp_init | Bank03 LE599 |
| 34 | Zones | Zone grid dimensions | 8x8 values in 0..13 | PASS | extractor/data_out/zones.json | Bank03 LF522 |
| 35 | Zones | Zone (0,0) value | 3 | PASS | extractor/data_out/zones.json | Bank03 LF522 |
| 36 | Zones | Zone (7,7) value | 9 | PASS | extractor/data_out/zones.json | Bank03 LF53E |
| 37 | Zones | Formation row 0 | ['Slime', 'Red Slime', 'Slime', 'Red Slime', 'Slime'] | PASS | extractor/data_out/zones.json | Bank03 LF54F |
| 38 | Zones | Formation row 13 | ['Werewolf', 'Green Dragon', 'Starwyvern', 'Starwyvern', 'Wizard'] | PASS | extractor/data_out/zones.json | Bank03 LF590 |
| 39 | Zones | Cave index table | [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15] | PASS | extractor/data_out/zones.json | Bank03 LF542 |
| 40 | Zones | Top-left overworld zone consistency | only zone id 3 in coordinates 0..14 | PASS | extractor/data_out/zones.json | Bank03 OvrWrldEnGrid mapping |
| 41 | Items | Magic Key consumption | door use consumes one key | PASS | artifacts/phase4_main_loop_map_command_door_surface.json | Bank03 key-use door path |
| 42 | Items | Torch radius + timer | radius=5 timer=16 | PASS | tests/fixtures/items_runtime_vectors.json | Bank03 ChkTorch |
| 43 | Items | Rainbow Drop bridge placement | bridge flag set and bridge tile at [1,63,49] | PASS | artifacts/phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json + tests/fixtures/items_runtime_vectors.json | Bank03 place_charlock |
| 44 | Items | Cursed equip load effect | HP set to 1 on map load | PASS | artifacts/phase4_main_loop_map_load_curse_check.json | Bank03 LCB73 |
| 45 | Terrain | Swamp step damage | true | PASS | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCDE2 |
| 46 | Terrain | Force field step damage | true | PASS | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCE47 |
| 47 | Terrain | Erdrick armor swamp immunity | true | PASS | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCDD0 |
| 48 | Terrain | Erdrick armor step heal | true | PASS | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCCFA |
| 49 | Quest | Gwaelin rescue flag side-effect | true | PASS | artifacts/phase4_main_loop_npc_special_control_side_effects.json | RAM map story flag path |
| 50 | Quest | Dragonlord defeat flag | true | PASS | artifacts/phase4_main_loop_combat_dragonlord_endgame_victory.json | RAM map 0x00E4 bit 2 |
| 51 | Stats | Lv1 base stats | STR=4 AGI=4 HP=15 MP=0 | PASS | extractor/data_out/stats.json | Bank01 LA0CD |
| 52 | Stats | Lv30 base stats | STR=140 AGI=130 HP=210 MP=200 | PASS | extractor/data_out/stats.json | Bank01 LA17B |
| 53 | Stats | HEAL learned at Lv3 | HEAL in spells_known | PASS | extractor/data_out/stats.json | Bank01 LA0D9 |
| 54 | Stats | HEALMORE learned at Lv17 | HEALMORE in spells_known | PASS | extractor/data_out/stats.json | Bank01 LA12D |
| 55 | Stats | HURTMORE learned at Lv19 | HURTMORE in spells_known | PASS | extractor/data_out/stats.json | Bank01 LA139 |
| 56 | Save | JSON save roundtrip + CRC | 30-byte roundtrip and CRC present | PASS | artifacts/phase2_save_load_runtime.json + tests/fixtures/save_load_runtime_vectors.json | Bank03 LFA18 / SRAM-equivalent JSON |
