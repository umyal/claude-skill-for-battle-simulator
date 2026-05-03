#!/usr/bin/env python3
"""
simulate.py — 戰鬥模擬主控制器

用法：
    python simulate.py team_a.yaml team_b.yaml -o battle_log.json [-c global_config.yaml]
"""

import argparse
import json
import random
import sys
from pathlib import Path
from typing import Dict, List

import yaml

# 確保可以 import 同目錄的模組
sys.path.insert(0, str(Path(__file__).parent))

from formulas import (
    sample_team_power,
    compute_mitigation,
    compute_damage,
    distribute_to_minions,
    apply_damage_to_minion,
    team_raw_power,
    team_total_power,
    clamp,
)
from skill_engine import resolve_phase_skills, apply_phase_results


SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent


def load_yaml(path: Path) -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def load_skill_library() -> Dict[str, dict]:
    lib_path = ROOT_DIR / "data" / "skill_library.yaml"
    raw = load_yaml(lib_path)
    return {s["id"]: s for s in raw["skills"]}


def load_global_config(custom_path: Path = None) -> dict:
    path = custom_path or (ROOT_DIR / "data" / "global_config.yaml")
    return load_yaml(path)


def normalize_team(team_raw: dict, config: dict) -> dict:
    """把 YAML 載入的隊伍資料轉成內部使用的格式，加入 current/original power。"""
    stab_max = config.get("stability_max", 0.99)
    minions = []
    for m in team_raw["minions"]:
        stability = clamp(m.get("stability", 0.0), 0.0, stab_max)
        minions.append({
            "id": m["id"],
            "name": m.get("name", m["id"]),
            "original_power": float(m["power"]),
            "current_power": float(m["power"]),
            "stability": stability,
            "skills": m.get("skills", []),
        })
    return {
        "team_id": team_raw["team_id"],
        "team_name": team_raw.get("team_name", team_raw["team_id"]),
        "minions": minions,
    }


def snapshot_team(team: dict) -> dict:
    """快照當下隊伍狀態，用於 log。"""
    return {
        "team_id": team["team_id"],
        "team_name": team["team_name"],
        "total_power": round(team_total_power(team["minions"]), 3),
        "minions": [
            {
                "id": m["id"],
                "name": m["name"],
                "current_power": round(m["current_power"], 3),
                "original_power": m["original_power"],
            }
            for m in team["minions"]
        ],
    }


def run_battle(team_a: dict, team_b: dict, config: dict, skill_lib: Dict[str, dict]) -> dict:
    """執行一場完整戰鬥，回傳完整 log。"""
    seed = config["seed"]
    rng = random.Random(seed)
    mit_min = config["mitigation"]["min"]
    mit_max = config["mitigation"]["max"]

    log = {
        "seed": seed,
        "config": {
            "mitigation_min": mit_min,
            "mitigation_max": mit_max,
            "stability_max": config.get("stability_max", 0.99),
        },
        "input_snapshot": {
            "team_a": snapshot_team(team_a),
            "team_b": snapshot_team(team_b),
        },
        "phases": {},
    }

    # ============ Phase 1: Before Combat ============
    # 順序：A 隊技能擲骰 → B 隊技能擲骰 → 同時套用
    a_acts, a_dmg_to_b, a_heal_self = resolve_phase_skills(
        team_a["minions"], team_b["minions"], skill_lib, "before_combat", rng
    )
    b_acts, b_dmg_to_a, b_heal_self = resolve_phase_skills(
        team_b["minions"], team_a["minions"], skill_lib, "before_combat", rng
    )

    # 套用：A 收到 b_dmg_to_a 的傷、a_heal_self 的治療
    a_actual_dmg, a_actual_heal = apply_phase_results(
        team_a["minions"], b_dmg_to_a, a_heal_self
    )
    b_actual_dmg, b_actual_heal = apply_phase_results(
        team_b["minions"], a_dmg_to_b, b_heal_self
    )

    log["phases"]["before_combat"] = {
        "team_a_skill_activations": a_acts,
        "team_b_skill_activations": b_acts,
        "team_a_damage_dealt": round(a_dmg_to_b, 3),
        "team_a_self_heal": round(a_heal_self, 3),
        "team_b_damage_dealt": round(b_dmg_to_a, 3),
        "team_b_self_heal": round(b_heal_self, 3),
        "team_a_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in a_actual_dmg],
        "team_a_actual_heal_per_minion": [(mid, round(v, 3)) for mid, v in a_actual_heal],
        "team_b_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in b_actual_dmg],
        "team_b_actual_heal_per_minion": [(mid, round(v, 3)) for mid, v in b_actual_heal],
        "state_after": {
            "team_a": snapshot_team(team_a),
            "team_b": snapshot_team(team_b),
        },
    }

    # ============ Phase 2: Combat ============
    # raw_power 用「進入 Combat 時的當下戰力」（已被 BC 修正過）
    raw_a = team_total_power(team_a["minions"])
    raw_b = team_total_power(team_b["minions"])

    sampled_a, samples_a = sample_team_power(team_a["minions"], rng)
    sampled_b, samples_b = sample_team_power(team_b["minions"], rng)

    mit_a = compute_mitigation(sampled_a, raw_a, raw_b, mit_min, mit_max)
    mit_b = compute_mitigation(sampled_b, raw_a, raw_b, mit_min, mit_max)

    dmg_a_to_b = compute_damage(raw_a, mit_b)
    dmg_b_to_a = compute_damage(raw_b, mit_a)

    # 同時套用傷害（按比例分攤）
    dist_to_a = distribute_to_minions(dmg_b_to_a, team_a["minions"])
    dist_to_b = distribute_to_minions(dmg_a_to_b, team_b["minions"])

    a_combat_actual = []
    for mid, dmg in dist_to_a:
        m = next(x for x in team_a["minions"] if x["id"] == mid)
        applied = apply_damage_to_minion(m, dmg)
        a_combat_actual.append((mid, applied))

    b_combat_actual = []
    for mid, dmg in dist_to_b:
        m = next(x for x in team_b["minions"] if x["id"] == mid)
        applied = apply_damage_to_minion(m, dmg)
        b_combat_actual.append((mid, applied))

    log["phases"]["combat"] = {
        "raw_power_a": round(raw_a, 3),
        "raw_power_b": round(raw_b, 3),
        "samples_a": [(mid, round(v, 3)) for mid, v in samples_a],
        "samples_b": [(mid, round(v, 3)) for mid, v in samples_b],
        "sampled_total_a": round(sampled_a, 3),
        "sampled_total_b": round(sampled_b, 3),
        "mitigation_a": round(mit_a, 4),
        "mitigation_b": round(mit_b, 4),
        "damage_a_to_b": round(dmg_a_to_b, 3),
        "damage_b_to_a": round(dmg_b_to_a, 3),
        "team_a_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in a_combat_actual],
        "team_b_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in b_combat_actual],
        "state_after": {
            "team_a": snapshot_team(team_a),
            "team_b": snapshot_team(team_b),
        },
    }

    # ============ Phase 3: After Combat ============
    a_acts2, a_dmg_to_b2, a_heal_self2 = resolve_phase_skills(
        team_a["minions"], team_b["minions"], skill_lib, "after_combat", rng
    )
    b_acts2, b_dmg_to_a2, b_heal_self2 = resolve_phase_skills(
        team_b["minions"], team_a["minions"], skill_lib, "after_combat", rng
    )

    a_actual_dmg2, a_actual_heal2 = apply_phase_results(
        team_a["minions"], b_dmg_to_a2, a_heal_self2
    )
    b_actual_dmg2, b_actual_heal2 = apply_phase_results(
        team_b["minions"], a_dmg_to_b2, b_heal_self2
    )

    log["phases"]["after_combat"] = {
        "team_a_skill_activations": a_acts2,
        "team_b_skill_activations": b_acts2,
        "team_a_damage_dealt": round(a_dmg_to_b2, 3),
        "team_a_self_heal": round(a_heal_self2, 3),
        "team_b_damage_dealt": round(b_dmg_to_a2, 3),
        "team_b_self_heal": round(b_heal_self2, 3),
        "team_a_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in a_actual_dmg2],
        "team_a_actual_heal_per_minion": [(mid, round(v, 3)) for mid, v in a_actual_heal2],
        "team_b_actual_damage_per_minion": [(mid, round(v, 3)) for mid, v in b_actual_dmg2],
        "team_b_actual_heal_per_minion": [(mid, round(v, 3)) for mid, v in b_actual_heal2],
        "state_after": {
            "team_a": snapshot_team(team_a),
            "team_b": snapshot_team(team_b),
        },
    }

    # ============ Final ============
    final_a = team_total_power(team_a["minions"])
    final_b = team_total_power(team_b["minions"])
    if final_a > 0 and final_b == 0:
        outcome = "team_a_wins"
    elif final_b > 0 and final_a == 0:
        outcome = "team_b_wins"
    elif final_a == 0 and final_b == 0:
        outcome = "draw_both_eliminated"
    else:
        outcome = "team_a_advantage" if final_a > final_b else (
            "team_b_advantage" if final_b > final_a else "draw_equal_power"
        )

    log["final_state"] = {
        "team_a": snapshot_team(team_a),
        "team_b": snapshot_team(team_b),
        "outcome": outcome,
    }

    return log


def main():
    parser = argparse.ArgumentParser(description="戰鬥模擬器")
    parser.add_argument("team_a", type=Path, help="A 隊 YAML 檔")
    parser.add_argument("team_b", type=Path, help="B 隊 YAML 檔")
    parser.add_argument("-o", "--output", type=Path, required=True, help="輸出 JSON log 路徑")
    parser.add_argument("-c", "--config", type=Path, default=None, help="自訂 global_config.yaml")
    parser.add_argument("--seed", type=int, default=None, help="覆寫設定檔的 seed")
    args = parser.parse_args()

    config = load_global_config(args.config)
    if args.seed is not None:
        config["seed"] = args.seed

    skill_lib = load_skill_library()

    team_a_raw = load_yaml(args.team_a)
    team_b_raw = load_yaml(args.team_b)

    team_a = normalize_team(team_a_raw, config)
    team_b = normalize_team(team_b_raw, config)

    log = run_battle(team_a, team_b, config, skill_lib)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        json.dump(log, f, ensure_ascii=False, indent=2)

    print(f"Battle log written to {args.output}")
    print(f"Outcome: {log['final_state']['outcome']}")
    print(f"  Team A: {log['final_state']['team_a']['total_power']}")
    print(f"  Team B: {log['final_state']['team_b']['total_power']}")


if __name__ == "__main__":
    main()
