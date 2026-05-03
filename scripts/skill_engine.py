"""
skill_engine.py — 處理 BC 與 AC 階段的技能結算。
"""

from typing import List, Dict, Tuple
import random
from formulas import (
    distribute_to_minions,
    apply_damage_to_minion,
    apply_heal_to_minion,
)


def resolve_phase_skills(
    team_attacker: List[dict],
    team_defender: List[dict],
    skill_lib: Dict[str, dict],
    phase: str,
    rng: random.Random,
) -> Tuple[List[dict], float, float]:
    """
    結算單隊在某階段（before_combat / after_combat）的技能。

    回傳：
      activations: [{skill_id, minion_id, activated, roll, value, effect_type}, ...]
      total_damage_to_enemy: 對敵總傷害
      total_heal_to_self:    對己總治療

    注意：本函式只「累計」效果，不直接套用。套用由呼叫者在雙方都算完後同時進行。
    rng 擲骰按手下順序、技能順序逐次抽，與 battle_flow.yaml 規定一致。
    """
    activations = []
    total_damage = 0.0
    total_heal = 0.0

    for minion in team_attacker:
        if minion["current_power"] <= 0:
            # 死亡的手下不發動技能
            continue
        for skill_id in minion.get("skills", []):
            skill = skill_lib.get(skill_id)
            if skill is None:
                activations.append({
                    "skill_id": skill_id,
                    "minion_id": minion["id"],
                    "activated": False,
                    "reason": "skill_not_found",
                })
                continue
            if skill["phase"] != phase:
                continue

            rate = skill.get("activation_rate", 1.0)
            if rate >= 1.0:
                roll = None
                activated = True
            else:
                roll = rng.random()
                activated = roll < rate

            record = {
                "skill_id": skill_id,
                "skill_name": skill["name"],
                "minion_id": minion["id"],
                "phase": phase,
                "effect_type": skill["effect_type"],
                "value": skill["value"],
                "activation_rate": rate,
                "roll": roll,
                "activated": activated,
            }

            if activated:
                if skill["effect_type"] == "damage_enemy":
                    total_damage += skill["value"]
                elif skill["effect_type"] == "heal_self":
                    total_heal += skill["value"]

            activations.append(record)

    return activations, total_damage, total_heal


def apply_phase_results(
    team_self: List[dict],
    damage_taken: float,
    heal_received: float,
) -> Tuple[List[Tuple[str, float]], List[Tuple[str, float]]]:
    """
    將某隊承受的傷害與治療同時套用到該隊手下身上。
    
    分攤規則：按進入該段時的當下戰力比例分配（formulas.distribute_to_minions）。
    傷害與治療各自獨立分攤——是的，這意味著如果同時又傷又治，
    會用「進入該段時的戰力」當基準算兩次分配。
    
    回傳 (damage_per_minion, heal_per_minion)
    """
    # 先記錄分配（基於進入該段的戰力）
    damage_dist = distribute_to_minions(damage_taken, team_self, is_heal=False)
    heal_dist = distribute_to_minions(heal_received, team_self, is_heal=True)

    # 同時套用：先計算淨變化，避免「先扣後補」與「先補後扣」結果不同
    # 既然 BC/AC 同時結算，淨變化 = heal − damage 是合理的
    minion_map = {m["id"]: m for m in team_self}
    actual_damage = []
    actual_heal = []

    for (mid, dmg), (mid2, hl) in zip(damage_dist, heal_dist):
        assert mid == mid2
        m = minion_map[mid]
        # 同時結算：淨變化
        net = hl - dmg
        if net >= 0:
            applied = apply_heal_to_minion(m, net)
            actual_heal.append((mid, applied))
            actual_damage.append((mid, 0.0))
        else:
            applied = apply_damage_to_minion(m, -net)
            actual_damage.append((mid, applied))
            actual_heal.append((mid, 0.0))

    return actual_damage, actual_heal
