#!/usr/bin/env python3
"""
batch_report.py — 從批次摘要 JSON 產生 Markdown 戰報

戰報詳細度依 batch_size 自動調整：
  ≤ 10 場：逐場列出簡要結果 + 匯總統計
  ≤ 1000 場：純匯總統計 + 極端場次列表
  > 1000 場：純匯總統計
"""

import argparse
import json
from pathlib import Path


OUTCOME_TEXT = {
    "team_a_wins": "A 隊獲勝（B 全滅）",
    "team_b_wins": "B 隊獲勝（A 全滅）",
    "draw_both_eliminated": "兩敗俱傷",
    "team_a_advantage": "A 隊優勢",
    "team_b_advantage": "B 隊優勢",
    "draw_equal_power": "戰況膠著（戰力相同）",
}


def fmt_team_init(snap: dict) -> str:
    lines = [f"- **{snap['team_name']}**（總戰力 {snap['total_power']}）"]
    for m in snap["minions"]:
        lines.append(f"  - {m['name']}（{m['id']}）戰力 {m['original_power']:.0f}")
    return "\n".join(lines)


def fmt_outcome_distribution(od: dict) -> str:
    lines = ["| 結果 | 場次 | 占比 |", "|---|---|---|"]
    # 固定排序，讓報告穩定
    order = ["team_a_wins", "team_a_advantage", "draw_equal_power",
             "team_b_advantage", "team_b_wins", "draw_both_eliminated"]
    for k in order:
        if k in od:
            v = od[k]
            lines.append(f"| {OUTCOME_TEXT.get(k, k)} | {v['count']} | {v['percentage']}% |")
    return "\n".join(lines)


def fmt_metric_table(metrics: dict, aggs_to_show: list = None) -> str:
    if aggs_to_show is None:
        aggs_to_show = ["mean", "median", "stddev", "min", "max", "p10", "p90"]

    header = ["| 指標 | 說明 |"] + [f" {a} |" for a in aggs_to_show]
    lines = ["".join(header).replace("| ", "| ", 1)]
    sep = "|---|---|" + "---|" * len(aggs_to_show)
    lines.append(sep)

    for name, info in metrics.items():
        stats = info["stats"]
        row = [f"| `{name}`", f" {info['description']} "]
        for a in aggs_to_show:
            v = stats.get(a)
            row.append(f" {v} " if v is not None else " — ")
        lines.append("|".join(row) + "|")
    return "\n".join(lines)


def fmt_extreme_battles(extremes: dict) -> str:
    cat_titles = {
        "max_team_a_advantage": "A 隊勝幅最大的場次",
        "max_team_b_advantage": "B 隊勝幅最大的場次",
        "lowest_mitigation_a": "A 隊運氣最差的場次（mitigation_a 最低）",
        "highest_mitigation_a": "A 隊運氣最好的場次（mitigation_a 最高）",
        "lowest_mitigation_b": "B 隊運氣最差的場次",
        "highest_mitigation_b": "B 隊運氣最好的場次",
    }
    lines = []
    for cat, title in cat_titles.items():
        if cat not in extremes:
            continue
        lines.append(f"### {title}\n")
        lines.append("| 排名 | seed | 結果 | A 終戰力 | B 終戰力 | 戰力差 | mit_A | mit_B |")
        lines.append("|---|---|---|---|---|---|---|---|")
        for i, b in enumerate(extremes[cat], 1):
            m = b["metrics"]
            lines.append(
                f"| {i} | {b['seed']} | {OUTCOME_TEXT.get(b['outcome'], b['outcome'])} "
                f"| {m.get('team_a_final_power', '—')} | {m.get('team_b_final_power', '—')} "
                f"| {m.get('power_diff', '—')} | {m.get('mitigation_a', '—')} | {m.get('mitigation_b', '—')} |"
            )
        lines.append("")
    return "\n".join(lines)


def fmt_per_battle_brief(records: list) -> str:
    lines = ["| # | seed | 結果 | A 終戰力 | B 終戰力 | 戰力差 |",
             "|---|---|---|---|---|---|"]
    for r in records:
        m = r["metrics"]
        lines.append(
            f"| {r['battle_index'] + 1} | {r['seed']} "
            f"| {OUTCOME_TEXT.get(r['outcome'], r['outcome'])} "
            f"| {m.get('team_a_final_power', '—'):.1f} "
            f"| {m.get('team_b_final_power', '—'):.1f} "
            f"| {m.get('power_diff', '—'):.1f} |"
        )
    return "\n".join(lines)


def render(summary: dict, thresholds: dict) -> str:
    n = summary["batch_size"]
    show_each = thresholds.get("show_each_battle", 10)
    show_extremes = thresholds.get("highlight_extremes", 1000)

    lines = []
    lines.append(f"# 批次模擬報告（{n} 場）\n")
    lines.append(f"- Seed 策略：`{summary['seed_strategy_used']}`")
    lines.append(f"- Seed 範圍：{summary['first_seed']} ~ {summary['last_seed']}")
    cfg = summary.get("config", {})
    if cfg:
        lines.append(f"- 減傷夾值範圍：[{cfg.get('mitigation_min')}, {cfg.get('mitigation_max')}]")
        lines.append(f"- 穩定度上限：{cfg.get('stability_max')}")
    lines.append("")

    # 隊伍配置
    snap = summary.get("input_snapshot")
    if snap:
        lines.append("## 隊伍配置\n")
        lines.append(fmt_team_init(snap["team_a"]))
        lines.append("")
        lines.append(fmt_team_init(snap["team_b"]))
        lines.append("")

    # 勝負分布
    lines.append("## 勝負分布\n")
    lines.append(fmt_outcome_distribution(summary["outcome_distribution"]))
    lines.append("")

    # 數值統計
    lines.append("## 數值統計\n")
    lines.append(fmt_metric_table(summary["metrics"]))
    lines.append("")

    # 逐場列表（小批量）
    if n <= show_each:
        lines.append(f"## 逐場結果（共 {n} 場）\n")
        lines.append(fmt_per_battle_brief(summary["all_records"]))
        lines.append("")

    # 極端場次（中批量）
    if n <= show_extremes and summary.get("extreme_battles"):
        lines.append("## 極端場次\n")
        lines.append(fmt_extreme_battles(summary["extreme_battles"]))

    lines.append("---\n")
    lines.append(f"💡 想看某一場的完整戰報？告訴 Claude 你想看的 seed，"
                 f"它會用 `simulate.py --seed <值>` 重現該場戰鬥。")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="批次戰報渲染器")
    parser.add_argument("summary_path", type=Path, help="batch_summary.json 路徑")
    parser.add_argument("-o", "--output", type=Path, required=True)
    parser.add_argument("--analysis-config", type=Path, default=None)
    args = parser.parse_args()

    with open(args.summary_path, "r", encoding="utf-8") as f:
        summary = json.load(f)

    # 讀閾值設定
    import yaml
    cfg_path = args.analysis_config or (Path(__file__).parent.parent / "data" / "analysis_config.yaml")
    with open(cfg_path, "r", encoding="utf-8") as f:
        analysis_cfg = yaml.safe_load(f)
    thresholds = analysis_cfg.get("report_thresholds", {})

    md = render(summary, thresholds)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)
    print(f"Batch report written to {args.output}")


if __name__ == "__main__":
    main()
