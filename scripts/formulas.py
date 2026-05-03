"""
formulas.py — 純數學函式，無 I/O，無副作用。
所有公式的 source of truth。任何規則調整在此處進行。
"""

from typing import List, Tuple
import random


def clamp(x: float, lo: float, hi: float) -> float:
    """夾值到 [lo, hi]。"""
    return max(lo, min(hi, x))


def sample_minion_power(power: float, stability: float, rng: random.Random) -> float:
    """
    對單一手下的戰力做穩定度抽樣。
    sampled = power · U(1 − σ, 1 + σ)
    """
    if stability == 0.0:
        return float(power)
    factor = rng.uniform(1.0 - stability, 1.0 + stability)
    return power * factor


def sample_team_power(
    minions: List[dict], rng: random.Random
) -> Tuple[float, List[Tuple[str, float]]]:
    """
    對整隊每個還活著的手下抽樣後加總。
    回傳 (隊伍抽樣總和, [(minion_id, sampled_power), ...])
    死亡（power=0）的手下不參與抽樣，sampled 記為 0。
    """
    samples = []
    total = 0.0
    for m in minions:
        if m["current_power"] <= 0:
            samples.append((m["id"], 0.0))
            continue
        s = sample_minion_power(m["current_power"], m["stability"], rng)
        samples.append((m["id"], s))
        total += s
    return total, samples


def compute_mitigation(
    sampled: float,
    raw_total_a: float,
    raw_total_b: float,
    mit_min: float,
    mit_max: float,
) -> float:
    """
    減傷比例 = sampled / (raw_total_a + raw_total_b)，獨立夾值。
    """
    denom = raw_total_a + raw_total_b
    if denom <= 0:
        return mit_min
    raw_mit = sampled / denom
    return clamp(raw_mit, mit_min, mit_max)


def compute_damage(attacker_raw_power: float, defender_mitigation: float) -> float:
    """
    傷害 = 攻方原始戰力 · (1 − 守方 mitigation)
    """
    return attacker_raw_power * (1.0 - defender_mitigation)


def distribute_to_minions(
    total_amount: float,
    minions: List[dict],
    is_heal: bool = False,
) -> List[Tuple[str, float]]:
    """
    依當下戰力比例分攤傷害或治療到手下。
    回傳 [(minion_id, amount_applied), ...]
    
    is_heal=False: 傷害，從 current_power 扣減，下限 0
    is_heal=True:  治療，加到 current_power，上限為原始 power
    
    注意：本函式只回傳分配量，不修改 minions。實際套用由呼叫者完成。
    """
    # 只考慮活著的手下參與分攤
    alive = [m for m in minions if m["current_power"] > 0]
    if not alive or total_amount <= 0:
        return [(m["id"], 0.0) for m in minions]

    alive_total = sum(m["current_power"] for m in alive)
    if alive_total <= 0:
        return [(m["id"], 0.0) for m in minions]

    result = []
    for m in minions:
        if m["current_power"] <= 0:
            result.append((m["id"], 0.0))
            continue
        share = total_amount * (m["current_power"] / alive_total)
        result.append((m["id"], share))
    return result


def apply_damage_to_minion(minion: dict, damage: float) -> float:
    """
    對單一手下套用傷害，戰力夾在 [0, original_power]。
    回傳實際扣減量。
    """
    before = minion["current_power"]
    minion["current_power"] = clamp(before - damage, 0.0, minion["original_power"])
    return before - minion["current_power"]


def apply_heal_to_minion(minion: dict, heal: float) -> float:
    """
    對單一手下套用治療，戰力夾在 [0, original_power]。
    回傳實際治療量（溢出捨棄）。
    """
    before = minion["current_power"]
    minion["current_power"] = clamp(before + heal, 0.0, minion["original_power"])
    return minion["current_power"] - before


def team_total_power(minions: List[dict]) -> float:
    """隊伍當下總戰力。"""
    return sum(m["current_power"] for m in minions)


def team_raw_power(minions: List[dict]) -> float:
    """隊伍原始總戰力（不變）。"""
    return sum(m["original_power"] for m in minions)
