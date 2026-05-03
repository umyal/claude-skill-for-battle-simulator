#!/usr/bin/env python3
"""
batch_simulate.py — 批次戰鬥模擬

用法：
    python batch_simulate.py team_a.yaml team_b.yaml \
        --output-dir output/ \
        [--count 100] \
        [--seed-mode sequential|derived|random] \
        [--analysis-config data/analysis_config.yaml]

輸出：
    output/batch_log.json       完整 N 場 log
    output/batch_summary.json   彙總統計（給程式 / Claude 讀）
    output/seeds.json           本批次使用的所有 seed（方便重現單場）
"""

import argparse
import json
import random
import secrets
import statistics
import sys
from pathlib import Path
from typing import Dict, List, Any

import yaml

sys.path.insert(0, str(Path(__file__).parent))

from simulate import (
    load_skill_library,
    load_global_config,
    normalize_team,
    run_battle,
)


SCRIPT_DIR = Path(__file__).parent
ROOT_DIR = SCRIPT_DIR.parent


# ============ Seed 產生策略 ============

def generate_seeds(strategy_cfg: dict, count: int, mode_override: str = None) -> List[int]:
    """根據策略產生 count 個 seed。"""
    mode = mode_override or strategy_cfg.get("mode", "sequential")

    if mode == "sequential":
        base = strategy_cfg["sequential"]["base"]
        step = strategy_cfg["sequential"]["step"]
        return [base + step * i for i in range(count)]

    elif mode == "derived":
        master = strategy_cfg["derived"]["master_seed"]
        rng = random.Random(master)
        # 產生 count 個 32-bit 子 seed
        return [rng.randrange(0, 2**31) for _ in range(count)]

    elif mode == "random":
        return [secrets.randbits(31) for _ in range(count)]

    else:
        raise ValueError(f"Unknown seed mode: {mode}")


# ============ 從 log 抽出指標 ============

def get_by_path(d: dict, path: str):
    """支援 'a.b.c' 形式的巢狀取值。"""
    cur = d
    for key in path.split("."):
        cur = cur[key]
    return cur


def evaluate_formula(d: dict, formula: str) -> float:
    """支援極簡的 'path1 / path2' 與 'path1 - path2' 形式。"""
    formula = formula.strip()
    for op, fn in [(" / ", lambda a, b: a / b if b != 0 else 0.0),
                   (" - ", lambda a, b: a - b),
                   (" + ", lambda a, b: a + b),
                   (" * ", lambda a, b: a * b)]:
        if op in formula:
            left, right = formula.split(op, 1)
            return fn(get_by_path(d, left.strip()), get_by_path(d, right.strip()))
    # 單純路徑
    return get_by_path(d, formula)


def extract_metric(log: dict, metric_def: dict) -> float:
    if "path" in metric_def:
        return float(get_by_path(log, metric_def["path"]))
    elif "formula" in metric_def:
        return float(evaluate_formula(log, metric_def["formula"]))
    else:
        raise ValueError(f"Metric {metric_def['name']} has neither path nor formula")


# ============ 統計量計算 ============

def aggregate(values: List[float], aggregations: List[str]) -> Dict[str, float]:
    if not values:
        return {a: None for a in aggregations}
    sorted_v = sorted(values)
    n = len(sorted_v)
    result = {}
    for agg in aggregations:
        if agg == "mean":
            result[agg] = statistics.fmean(values)
        elif agg == "median":
            result[agg] = statistics.median(values)
        elif agg == "stddev":
            result[agg] = statistics.stdev(values) if n > 1 else 0.0
        elif agg == "min":
            result[agg] = sorted_v[0]
        elif agg == "max":
            result[agg] = sorted_v[-1]
        elif agg.startswith("p"):
            # P10, P90 等百分位
            pct = int(agg[1:])
            idx = max(0, min(n - 1, int(round((pct / 100.0) * (n - 1)))))
            result[agg] = sorted_v[idx]
        else:
            result[agg] = None
    # 四捨五入
    return {k: (round(v, 4) if v is not None else None) for k, v in result.items()}


# ============ 極端場次挑選 ============

def pick_extremes(records: List[dict], analysis_cfg: dict) -> Dict[str, List[dict]]:
    per = analysis_cfg["extreme_picks"]["per_category"]
    cats = analysis_cfg["extreme_picks"]["categories"]
    result = {}

    sort_keys = {
        "max_team_a_advantage": ("power_diff", True),       # 大到小
        "max_team_b_advantage": ("power_diff", False),      # 小到大（最負）
        "lowest_mitigation_a": ("mitigation_a", False),
        "highest_mitigation_a": ("mitigation_a", True),
        "lowest_mitigation_b": ("mitigation_b", False),
        "highest_mitigation_b": ("mitigation_b", True),
    }

    for cat in cats:
        if cat not in sort_keys:
            continue
        key, descending = sort_keys[cat]
        sorted_records = sorted(records, key=lambda r: r["metrics"][key], reverse=descending)
        result[cat] = [
            {
                "seed": r["seed"],
                "battle_index": r["battle_index"],
                "outcome": r["outcome"],
                "metrics": {k: round(v, 3) for k, v in r["metrics"].items()},
            }
            for r in sorted_records[:per]
        ]

    return result


# ============ 主流程 ============

def run_batch(
    team_a_raw: dict,
    team_b_raw: dict,
    config: dict,
    skill_lib: dict,
    seeds: List[int],
    analysis_cfg: dict,
) -> Dict[str, Any]:
    """執行批次，回傳 {full_logs, summary}"""
    full_logs = []
    records = []
    outcome_counter = {}

    for i, seed in enumerate(seeds):
        cfg = dict(config)
        cfg["seed"] = seed
        team_a = normalize_team(team_a_raw, cfg)
        team_b = normalize_team(team_b_raw, cfg)
        log = run_battle(team_a, team_b, cfg, skill_lib)
        full_logs.append(log)

        # 抽指標
        metrics = {}
        for m_def in analysis_cfg["metrics"]:
            try:
                metrics[m_def["name"]] = extract_metric(log, m_def)
            except (KeyError, ZeroDivisionError):
                metrics[m_def["name"]] = None

        outcome = log["final_state"]["outcome"]
        outcome_counter[outcome] = outcome_counter.get(outcome, 0) + 1

        records.append({
            "battle_index": i,
            "seed": seed,
            "outcome": outcome,
            "metrics": metrics,
        })

    # 計算彙總統計
    aggs = analysis_cfg["aggregations"]
    metric_stats = {}
    for m_def in analysis_cfg["metrics"]:
        name = m_def["name"]
        values = [r["metrics"][name] for r in records if r["metrics"][name] is not None]
        metric_stats[name] = {
            "description": m_def.get("description", ""),
            "stats": aggregate(values, aggs),
            "sample_count": len(values),
        }

    # 勝負分布
    total = len(seeds)
    outcome_distribution = {
        k: {"count": v, "percentage": round(v / total * 100, 2)}
        for k, v in outcome_counter.items()
    }

    # 挑極端場次
    extremes = pick_extremes(records, analysis_cfg)

    summary = {
        "batch_size": total,
        "seed_strategy_used": analysis_cfg.get("_seed_mode_used", "sequential"),
        "first_seed": seeds[0] if seeds else None,
        "last_seed": seeds[-1] if seeds else None,
        "input_snapshot": full_logs[0]["input_snapshot"] if full_logs else None,
        "config": full_logs[0]["config"] if full_logs else None,
        "outcome_distribution": outcome_distribution,
        "metrics": metric_stats,
        "extreme_battles": extremes,
        "all_records": records,  # 每場簡要紀錄（含 seed），檔案不大
    }

    return {"full_logs": full_logs, "summary": summary}


def main():
    parser = argparse.ArgumentParser(description="批次戰鬥模擬器")
    parser.add_argument("team_a", type=Path)
    parser.add_argument("team_b", type=Path)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--count", type=int, default=None,
                        help="覆寫 analysis_config 的 default_count")
    parser.add_argument("--seed-mode", type=str, default=None,
                        choices=["sequential", "derived", "random"],
                        help="覆寫 seed 策略模式")
    parser.add_argument("--analysis-config", type=Path, default=None)
    parser.add_argument("--global-config", type=Path, default=None)
    args = parser.parse_args()

    global_cfg = load_global_config(args.global_config)
    skill_lib = load_skill_library()

    analysis_path = args.analysis_config or (ROOT_DIR / "data" / "analysis_config.yaml")
    with open(analysis_path, "r", encoding="utf-8") as f:
        analysis_cfg = yaml.safe_load(f)

    count = args.count or analysis_cfg["default_count"]
    seeds = generate_seeds(analysis_cfg["seed_strategy"], count, args.seed_mode)
    analysis_cfg["_seed_mode_used"] = args.seed_mode or analysis_cfg["seed_strategy"]["mode"]

    with open(args.team_a, "r", encoding="utf-8") as f:
        team_a_raw = yaml.safe_load(f)
    with open(args.team_b, "r", encoding="utf-8") as f:
        team_b_raw = yaml.safe_load(f)

    result = run_batch(team_a_raw, team_b_raw, global_cfg, skill_lib, seeds, analysis_cfg)

    args.output_dir.mkdir(parents=True, exist_ok=True)

    # 完整 log
    with open(args.output_dir / "batch_log.json", "w", encoding="utf-8") as f:
        json.dump(result["full_logs"], f, ensure_ascii=False, indent=2)

    # 摘要
    with open(args.output_dir / "batch_summary.json", "w", encoding="utf-8") as f:
        json.dump(result["summary"], f, ensure_ascii=False, indent=2)

    # seeds 清單（單獨存方便引用）
    with open(args.output_dir / "seeds.json", "w", encoding="utf-8") as f:
        json.dump({"seeds": seeds, "mode": analysis_cfg["_seed_mode_used"]}, f, indent=2)

    print(f"Batch complete: {count} battles")
    print(f"  Full log: {args.output_dir / 'batch_log.json'}")
    print(f"  Summary:  {args.output_dir / 'batch_summary.json'}")

    od = result["summary"]["outcome_distribution"]
    print("Outcome distribution:")
    for k, v in od.items():
        print(f"  {k}: {v['count']} ({v['percentage']}%)")


if __name__ == "__main__":
    main()
