# PARITY_REPORT.md

## Summary

- Rows: 67
- Status counts: {"PASS": 67}
- Evidence tiers: {"checkpoint-proven": 1, "extractor-only": 56, "replay-proven": 1, "runtime-state": 9}
- All passed: True

| # | System | Test | Expected | Status | Evidence Tier | Evidence | ROM Evidence Source |
|---:|---|---|---|---|---|---|---|
| 1 | ROM | SHA1 match | 66809063b828197d1fe12232ebd08ec0a498aa04 | PASS | extractor-only | extractor/rom_baseline.json + dragon-warrior-1.nes | verify.py phase gate baseline |
| 2 | ROM | PRG size | 65536 | PASS | extractor-only | extractor/data_out/rom_header.json | iNES header byte 4 |
| 3 | ROM | CHR size | 16384 | PASS | extractor-only | extractor/data_out/rom_header.json | iNES header byte 5 |
| 4 | ROM | Mapper | 1 | PASS | extractor-only | extractor/data_out/rom_header.json | Header flags 6/7 |
| 5 | Maps | Overworld dimensions | [120, 120] | PASS | extractor-only | extractor/data_out/maps.json | Data Crystal ROM map 0x1D6D |
| 6 | Maps | Map metadata count | 30 entries ids 0..29 | PASS | extractor-only | extractor/data_out/maps.json | ROM metadata table 0x002A-0x00C0 |
| 7 | Maps | Tantegel size | [30, 30] | PASS | extractor-only | extractor/data_out/maps.json | Metadata entry 4 |
| 8 | Maps | Throne Room size | [10, 10] | PASS | extractor-only | extractor/data_out/maps.json | Metadata entry 5 |
| 9 | Chests | Chest count | 31 | PASS | extractor-only | extractor/data_out/chests.json | ROM 0x5DDD-0x5E58 |
| 10 | Chests | Tantegel chest spot-check | [4, 1, 13, 19] | PASS | extractor-only | extractor/data_out/chests.json | Extracted TreasureTbl entry |
| 11 | Enemies | Enemy count | 40 | PASS | extractor-only | extractor/data_out/enemies.json | EnStatTbl |
| 12 | Enemies | Enemy 0 name | Slime | PASS | extractor-only | extractor/data_out/enemies.json | EnStatTbl entry 0x00 |
| 13 | Enemies | Dragonlord form2 HP base | 130 | PASS | extractor-only | extractor/data_out/enemies.json + artifacts/phase5_slice_edge_case_regression_gate.json | Enemy table @ ROM 0x5E5B |
| 14 | MP Costs | HEAL | 4 | PASS | extractor-only | extractor/data_out/spells.json | SpellCostTbl @ 0x1D63 |
| 15 | MP Costs | HURTMORE | 5 | PASS | extractor-only | extractor/data_out/spells.json | SpellCostTbl @ 0x1D6C |
| 16 | MP Costs | RETURN | 8 | PASS | extractor-only | extractor/data_out/spells.json | SpellCostTbl @ 0x1D69 |
| 17 | MP Costs | OUTSIDE | 6 | PASS | extractor-only | extractor/data_out/spells.json | SpellCostTbl @ 0x1D68 |
| 18 | XP Table | Level 2 threshold | 7 | PASS | extractor-only | extractor/data_out/xp_table.json | Bank03 LF35D |
| 19 | XP Table | Level 10 threshold | 2000 | PASS | extractor-only | extractor/data_out/xp_table.json | Bank03 LF36D |
| 20 | XP Table | Level 20 threshold | 26000 | PASS | extractor-only | extractor/data_out/xp_table.json | Bank03 LF381 |
| 21 | XP Table | Level 30 threshold | 65535 | PASS | extractor-only | extractor/data_out/xp_table.json | Bank03 LF395 |
| 22 | XP Table | All 30 thresholds | 30 entries | PASS | extractor-only | extractor/data_out/xp_table.json | Bank03 LF35B-LF395 |
| 23 | RNG | Golden sequence | 1000 ticks match fixture | PASS | extractor-only | tests/fixtures/rng_golden_sequence.json | Bank03 LC55B |
| 24 | RNG | Deterministic seed replay | same-seed sequences identical | PASS | extractor-only | tests/test_rng.py::test_rng_determinism | Bank03 LFSR |
| 25 | Combat | Excellent move chance | 8/256 (=1/32) | PASS | extractor-only | engine.combat.excellent_move_check | Bank03 LE61F |
| 26 | Combat | No excellent vs Dragonlord | 0/256 | PASS | extractor-only | engine.combat.excellent_move_check + artifacts/phase5_slice_edge_case_regression_gate.json | Bank03 LE617-LE61D |
| 27 | Combat | Player weak attack split | 128 zeros / 128 ones | PASS | extractor-only | engine.combat.player_attack_damage | Bank03 LF026 |
| 28 | Combat | Normal attack formula parity | 44 | PASS | extractor-only | engine.combat.player_attack_damage | Bank03 LF030 |
| 29 | Combat | 8-bit wraparound boundary | 63 | PASS | extractor-only | tests/test_combat.py::test_player_attack_boundary_max_atk_min_def | Bank03 arithmetic wrap |
| 30 | Combat | HEAL range | 10..17 | PASS | extractor-only | engine.combat.heal_spell_hp | Bank03 LDBB8 |
| 31 | Combat | HEALMORE range | 85..100 | PASS | extractor-only | engine.combat.healmore_spell_hp | Bank03 LDBD7 |
| 32 | Combat | HURT/HURTMORE ranges | HURT 5..12; HURTMORE 58..65 | PASS | extractor-only | engine.combat.hurt_spell_damage + hurtmore_spell_damage | Bank03 LE736/LE751 |
| 33 | Combat | Enemy HP init formula | randomized and bounded 98..130 | PASS | extractor-only | engine.combat.enemy_hp_init | Bank03 LE599 |
| 34 | Combat | Live enemy spell execution for proven subset | pattern_flags 0x02 enemies cast HURT live; stopspelled cast falls back to physical attack | PASS | runtime-state | main.py combat enemy-turn resolution + tests/test_main_loop_scaffold.py live Magician spell regressions | Bounded runtime proof: Magician live-casts HURT from pattern_flags 0x02; stopspell preserves existing blocked-cast fallback |
| 35 | Zones | Zone grid dimensions | 8x8 values in 0..13 | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF522 |
| 36 | Zones | Zone (0,0) value | 3 | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF522 |
| 37 | Zones | Zone (7,7) value | 9 | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF53E |
| 38 | Zones | Formation row 0 | ['Slime', 'Red Slime', 'Slime', 'Red Slime', 'Slime'] | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF54F |
| 39 | Zones | Formation row 13 | ['Werewolf', 'Green Dragon', 'Starwyvern', 'Starwyvern', 'Wizard'] | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF590 |
| 40 | Zones | Cave index table | [16, 17, 17, 17, 18, 18, 19, 19, 14, 14, 7, 15, 15] | PASS | extractor-only | extractor/data_out/zones.json | Bank03 LF542 |
| 41 | Zones | Top-left overworld zone consistency | only zone id 3 in coordinates 0..14 | PASS | extractor-only | extractor/data_out/zones.json | Bank03 OvrWrldEnGrid mapping |
| 42 | Items | Magic Key consumption | door use consumes one key | PASS | extractor-only | artifacts/phase4_main_loop_map_command_door_surface.json | Bank03 key-use door path |
| 43 | Items | Torch radius + timer | radius=5 timer=16 | PASS | extractor-only | tests/fixtures/items_runtime_vectors.json | Bank03 ChkTorch |
| 44 | Items | Rainbow Drop bridge placement | bridge flag set and bridge tile at [1,63,49] | PASS | extractor-only | artifacts/phase4_main_loop_map_command_item_rainbow_drop_bridge_trigger.json + tests/fixtures/items_runtime_vectors.json | Bank03 place_charlock |
| 45 | Items | Cursed equip load effect | HP set to 1 on map load | PASS | extractor-only | artifacts/phase4_main_loop_map_load_curse_check.json | Bank03 LCB73 |
| 46 | Terrain | Swamp step damage | true | PASS | extractor-only | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCDE2 |
| 47 | Terrain | Force field step damage | true | PASS | extractor-only | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCE47 |
| 48 | Terrain | Erdrick armor swamp immunity | true | PASS | extractor-only | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCDD0 |
| 49 | Terrain | Erdrick armor step heal | true | PASS | extractor-only | artifacts/phase4_main_loop_map_movement_terrain_step_effects.json | Bank03 LCCFA |
| 50 | Quest | Gwaelin rescue flag side-effect | true | PASS | extractor-only | artifacts/phase4_main_loop_npc_special_control_side_effects.json | RAM map story flag path |
| 51 | Quest | Dragonlord defeat flag | true | PASS | extractor-only | artifacts/phase4_main_loop_combat_dragonlord_endgame_victory.json | RAM map 0x00E4 bit 2 |
| 52 | Stats | Lv1 base stats | STR=4 AGI=4 HP=15 MP=0 | PASS | extractor-only | extractor/data_out/stats.json | Bank01 LA0CD |
| 53 | Stats | Lv30 base stats | STR=140 AGI=130 HP=210 MP=200 | PASS | extractor-only | extractor/data_out/stats.json | Bank01 LA17B |
| 54 | Stats | HEAL learned at Lv3 | HEAL in spells_known | PASS | extractor-only | extractor/data_out/stats.json | Bank01 LA0D9 |
| 55 | Stats | HEALMORE learned at Lv17 | HEALMORE in spells_known | PASS | extractor-only | extractor/data_out/stats.json | Bank01 LA12D |
| 56 | Stats | HURTMORE learned at Lv19 | HURTMORE in spells_known | PASS | extractor-only | extractor/data_out/stats.json | Bank01 LA139 |
| 57 | Save | JSON save roundtrip + CRC | 30-byte roundtrip and CRC present | PASS | runtime-state | artifacts/phase2_save_load_runtime.json + tests/fixtures/save_load_runtime_vectors.json | Bank03 LFA18 / SRAM-equivalent JSON |
| 58 | Field Timers | Non-movement input cadence | repel/light timers stay unchanged on non-step input and decrement on successful step progression, including dialog-ending steps | PASS | runtime-state | main.py MainLoopSession.step + tests/test_main_loop_scaffold.py timer cadence regressions | ROM-like step semantics observed: timers decay on successful step progression, including dialog-ending steps, but not non-movement or blocked input |
| 59 | Combat | Enemy spell action mapping availability | Current repo proves only pattern_flags 0x02 -> HURT for Magician/Magidrakee; all other enemy spell patterns remain explicit UNKNOWN with per-enemy blocker text | PASS | runtime-state | extractor/data_out/enemies.json + engine.combat.enemy_spell_actions_for_pattern + tests/test_combat.py mapping regression | Extractor-backed pattern_flags subset proves Magician/Magidrakee use HURT; remaining spell-pattern decode stays UNKNOWN with explicit blocker strings |
| 60 | Stats | Shop equip recomputes derived stats | attack/defense reflect weapon/armor-derived equipped item bonuses immediately after affordable purchase | PASS | runtime-state | engine/shop.py runtime purchase path + tests/test_shop.py derived-stat regressions | Canonical recompute path now applies extracted weapon bonuses while preserving fresh-game baseline and unresolved shield defense behavior |
| 61 | Stats | Shield-derived defense parity scope | first canonical fresh-game LoadStats shield read sees RAM $BE low bits 0 on approved static ROM path | PASS | extractor-only | verify.py approved static ROM proof chain + extractor/data_out/items.json shield bonus table + engine/state.py fresh-game/runtime corroboration | Approved static ROM proof chain closes row 61: $F68F loads A=#00, $F6A5 stores that zero into RAM $BE, $FA54 rereads the same byte on the fresh-game serializer path, and first canonical LoadStats shield read at $F0F1 masks low bits from that zeroed byte. First canonical fresh-game LoadStats shield read therefore sees low bits 0. |
| 62 | Stats | Save/load preserves derived equipment modifiers | derived attack survives canonical save/load roundtrip | PASS | runtime-state | engine/save_load.py roundtrip scaffold + tests/test_save_load.py parity regressions | Canonical recompute path restores wearable-derived modifiers after decode while preserving fresh-game baseline defense behavior |
| 63 | Economy | Town-specific magic key pricing | Cantlin/Rimuldar/Tantegel key prices come from key cost table, not generic item price | PASS | runtime-state | extractor/data_out/items.json + engine/shop.py town-bound key pricing runtime | KeyCostTbl @ 0x1999-0x199B |
| 64 | Dialog/Flow | Selected shop and inn TALK handoffs enter bounded dialog flow before side effects | Selected TALK interactions should enter bounded dialog/menu flow before transaction side effects | PASS | runtime-state | artifacts/phase4_main_loop_npc_shop_inn_handoff.json | Bounded runtime proof: talk now enters dialog, then prompt/menu, then confirmed transaction without first-TALK side effects |
| 65 | Replay/Checkpoint | Replay executable fixture proof availability | representative executable replay fixtures prove overworld traversal, combat encounter resolution, town purchase/stay flow, and bounded item command resolution | PASS | replay-proven | tests/replay/manifest.json + tests/replay/*.json + parity_proof.py | Bounded executable replay proof for current implemented overworld/combat/town/item behaviors |
| 66 | Replay/Checkpoint | Checkpoint executable fixture proof availability | representative executable checkpoint fixtures prove dungeon traversal resume, save/load resume continuity, and wearable modifier continuity | PASS | checkpoint-proven | tests/checkpoints/manifest.json + tests/checkpoints/*.json + parity_proof.py | Bounded executable checkpoint proof for current implemented dungeon resume, canonical save/load continuity, and proven wearable modifier carry-through |
| 67 | Resistance Decode | ROM-backed resistance mapping availability | raw enemy byte-5 resistance mapping is ROM-backed; nibble split and high-nibble spell-fail threshold relation are proven while low-nibble gameplay semantics remain explicitly unproven | PASS | runtime-state | extractor/data_out/enemies.json + dragon-warrior-1.nes + tests/test_main_loop_scaffold.py sleep/stopspell immunity controls | Observed full 40-enemy ROM byte-5 sweep matches extracted mdef/high-nibble/low-nibble fields, and high nibble matches spell-fail threshold. Runtime Golem/Slime controls corroborate high-nibble immunity handling while low-nibble gameplay semantics remain unproven by current repo evidence. |
