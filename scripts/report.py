#!/usr/bin/env python3
"""
report.py — 從 JSON log 渲染 Markdown 戰報。
"""

import argparse
import json
from pathlib import Path


OUTCOME_TEXT = {
    "team_a_wins": "🏆 **A 隊獲勝**（B 隊全滅）",
    "team_b_wins": "🏆 **B 隊獲勝**（A 隊全滅）",
    "draw_both_eliminated": "💀 **兩敗俱傷**（雙方全滅）",
    "team_a_advantage": "**A 隊取得優勢**",
    "team_b_advantage": "**B 隊取得優勢**",
    "draw_equal_power": "**戰況膠著，雙方剩餘戰力相同**",
}


def fmt_team_state(snap: dict) -> str:
    lines = [f"- **{snap['team_name']}**（總戰力 {snap['total_power']}）"]
    for m in snap["minions"]:
        ratio = m["current_power"] / m["original_power"] if m["original_power"] > 0 else 0
        bar = "█" * int(ratio * 10) + "░" * (10 - int(ratio * 10))
        status = "💀" if m["current_power"] <= 0 else ""
        lines.append(
            f"  - {m['name']}（{m['id']}）{bar} {m['current_power']:.1f}/{m['original_power']:.0f} {status}"
        )
    return "\n".join(lines)


def fmt_skill_activations(acts: list, team_name: str) -> str:
    if not acts:
        return f"  - {team_name}：無 BC/AC 階段技能"
    lines = []
    for a in acts:
        if not a.get("activated"):
            roll_str = f"（擲骰 {a['roll']:.3f} ≥ 發動率 {a['activation_rate']}）" if a.get("roll") is not None else ""
            lines.append(f"  - ❌ {a.get('skill_name', a['skill_id'])} 未發動 {roll_str}")
        else:
            roll_str = f"（擲骰 {a['roll']:.3f} < 發動率 {a['activation_rate']}）" if a.get("roll") is not None else ""
            effect = "對敵造成傷害" if a["effect_type"] == "damage_enemy" else "為己方治療"
            lines.append(
                f"  - ✅ {a['skill_name']}（{a['minion_id']}）：{effect} {a['value']} {roll_str}"
            )
    return f"  - {team_name}：\n" + "\n".join(["    " + l[2:] for l in lines])


def render(log: dict) -> str:
    lines = []
    lines.append("# 戰鬥報告\n")
    lines.append(f"- 隨機種子：`{log['seed']}`")
    lines.append(f"- 減傷夾值範圍：[{log['config']['mitigation_min']}, {log['config']['mitigation_max']}]")
    lines.append(f"- 穩定度上限：{log['config']['stability_max']}\n")

    # 初始狀態
    lines.append("## 初始隊伍\n")
    lines.append(fmt_team_state(log["input_snapshot"]["team_a"]))
    lines.append("")
    lines.append(fmt_team_state(log["input_snapshot"]["team_b"]))
    lines.append("")

    # Before Combat
    bc = log["phases"]["before_combat"]
    lines.append("## 階段一：Before Combat\n")
    lines.append("**技能發動：**\n")
    lines.append(fmt_skill_activations(bc["team_a_skill_activations"], "A 隊"))
    lines.append("")
    lines.append(fmt_skill_activations(bc["team_b_skill_activations"], "B 隊"))
    lines.append("")
    lines.append("**結算：**\n")
    lines.append(f"- A 隊對敵造成 {bc['team_a_damage_dealt']:.1f} 點傷害；自療 {bc['team_a_self_heal']:.1f} 點")
    lines.append(f"- B 隊對敵造成 {bc['team_b_damage_dealt']:.1f} 點傷害；自療 {bc['team_b_self_heal']:.1f} 點\n")
    lines.append("**階段結束狀態：**\n")
    lines.append(fmt_team_state(bc["state_after"]["team_a"]))
    lines.append("")
    lines.append(fmt_team_state(bc["state_after"]["team_b"]))
    lines.append("")

    # Combat
    c = log["phases"]["combat"]
    lines.append("## 階段二：Combat\n")
    lines.append("**抽樣戰力：**\n")
    samples_a_str = "、".join(f"{mid}={v:.1f}" for mid, v in c["samples_a"])
    samples_b_str = "、".join(f"{mid}={v:.1f}" for mid, v in c["samples_b"])
    lines.append(f"- A 隊：{samples_a_str} → 抽樣總和 **{c['sampled_total_a']:.1f}**（原始 {c['raw_power_a']:.1f}）")
    lines.append(f"- B 隊：{samples_b_str} → 抽樣總和 **{c['sampled_total_b']:.1f}**（原始 {c['raw_power_b']:.1f}）\n")
    lines.append("**減傷比例：**\n")
    lines.append(f"- A 隊 mitigation = {c['mitigation_a']:.3f} = clamp({c['sampled_total_a']:.1f} / {c['raw_power_a'] + c['raw_power_b']:.1f})")
    lines.append(f"- B 隊 mitigation = {c['mitigation_b']:.3f} = clamp({c['sampled_total_b']:.1f} / {c['raw_power_a'] + c['raw_power_b']:.1f})\n")
    lines.append("**傷害交換：**\n")
    lines.append(f"- A → B 造成 **{c['damage_a_to_b']:.1f}** 點傷害（{c['raw_power_a']:.1f} × (1 − {c['mitigation_b']:.3f})）")
    lines.append(f"- B → A 造成 **{c['damage_b_to_a']:.1f}** 點傷害（{c['raw_power_b']:.1f} × (1 − {c['mitigation_a']:.3f})）\n")
    lines.append("**Combat 結束狀態：**\n")
    lines.append(fmt_team_state(c["state_after"]["team_a"]))
    lines.append("")
    lines.append(fmt_team_state(c["state_after"]["team_b"]))
    lines.append("")

    # After Combat
    ac = log["phases"]["after_combat"]
    lines.append("## 階段三：After Combat\n")
    lines.append("**技能發動：**\n")
    lines.append(fmt_skill_activations(ac["team_a_skill_activations"], "A 隊"))
    lines.append("")
    lines.append(fmt_skill_activations(ac["team_b_skill_activations"], "B 隊"))
    lines.append("")
    lines.append("**結算：**\n")
    lines.append(f"- A 隊對敵造成 {ac['team_a_damage_dealt']:.1f} 點傷害；自療 {ac['team_a_self_heal']:.1f} 點")
    lines.append(f"- B 隊對敵造成 {ac['team_b_damage_dealt']:.1f} 點傷害；自療 {ac['team_b_self_heal']:.1f} 點\n")

    # Final
    lines.append("## 最終結果\n")
    lines.append(OUTCOME_TEXT.get(log["final_state"]["outcome"], log["final_state"]["outcome"]))
    lines.append("")
    lines.append(fmt_team_state(log["final_state"]["team_a"]))
    lines.append("")
    lines.append(fmt_team_state(log["final_state"]["team_b"]))
    lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="戰報渲染器")
    parser.add_argument("log_path", type=Path, help="JSON log 檔路徑")
    parser.add_argument("-o", "--output", type=Path, required=True, help="輸出 Markdown 檔")
    args = parser.parse_args()

    with open(args.log_path, "r", encoding="utf-8") as f:
        log = json.load(f)

    md = render(log)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, "w", encoding="utf-8") as f:
        f.write(md)

    print(f"Report written to {args.output}")


if __name__ == "__main__":
    main()
