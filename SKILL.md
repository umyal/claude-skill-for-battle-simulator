---
name: battle-simulator
description: 模擬國戰類遊戲中兩支部隊在同一地格交戰的戰鬥流程，依靜態規則檔與 Python 公式計算，輸出戰報與完整戰鬥 log。支援單場詳細模擬與批次統計分析。當使用者提供雙方隊伍配置並要求「模擬戰鬥」「打一場」「跑 N 場」「統計勝率」「測試平衡性」時觸發此 skill。
---

# Battle Simulator

模擬兩支隊伍的單場戰鬥（Before Combat → Combat → After Combat），輸出 JSON log 與 Markdown 戰報。同時支援批次模擬與統計分析。

## 紀律（必讀）

1. **必須**呼叫 `scripts/simulate.py`（單場）或 `scripts/batch_simulate.py`（批次）進行模擬。**禁止**用語言模型推論代替計算結果。所有戰力、抽樣、減傷、傷害、治療數值都必須來自 Python 腳本的輸出。
2. **必須**使用 `scripts/report.py`（單場）或 `scripts/batch_report.py`（批次）從 JSON log 渲染戰報，不可自行編造戰報內容。
3. 規則寫在 `rules/` 下的 YAML，公式寫在 `scripts/formulas.py`。**規則檔只是文件給人看，公式才是 source of truth**——若兩者不一致，以 Python 為準並提醒使用者。
4. 隨機種子來自 `data/global_config.yaml` 的 `seed` 欄位（單場）或 `data/analysis_config.yaml` 的 `seed_strategy`（批次），所有 RNG 共用同一個 seed 序列。同樣的輸入 + 同樣的 seed → 結果完全一致。
5. 當使用者詢問「這套規則怎麼運作」「公式是什麼」「為什麼這樣設計」這類**規則本身**的問題時，請以 `GAME_RULES.md` 為準回答，不要憑空生成解釋。當使用者詢問「怎麼用這個 skill」「能做什麼」「有哪些範例」時，以 `USAGE_EXAMPLES.md` 為準。

## 單場 vs 批次：判斷規則

依使用者用詞決定使用哪個工具：

| 使用者說法 | 判斷 | 場數 |
|---|---|---|
| 「模擬一場」「打一場」「跑一次戰鬥」 | 單場 | 1 |
| 「模擬戰鬥」（無數量詞） | 單場 | 1 |
| 「為什麼這場 B 贏了」「分析這場戰報」「看 seed=X 的詳細過程」 | 單場（指定 seed） | 1 |
| 「模擬 N 場」「跑 N 場」「打 N 次」 | 批次 | N |
| 「跑批次」「批次模擬」「統計分析」 | 批次 | 用 `default_count` |
| 「看看勝率」「測試平衡性」「分析這個對戰」 | 批次 | 用 `default_count` |
| 「模擬幾場看看」（模糊） | **反問**使用者 | — |

**批次完成後的後續引導**：批次戰報會列出極端場次的 seed。Claude **應主動詢問**使用者是否想看某一場的詳細戰報，並用 `simulate.py --seed <值>` 重現該場。

## 標準作業流程

### 單場模擬

1. 確認使用者提供雙方隊伍配置（YAML 或對話文字）。若只給對話文字，先轉成符合 `schemas/team.schema.json` 的 YAML 並存到 `examples/` 下。
2. 確認 `data/global_config.yaml` 中的 seed 是使用者要的；若使用者想要不同 seed，用 `--seed` 參數覆寫。
3. 執行：`python scripts/simulate.py <team_a.yaml> <team_b.yaml> -o <log.json>`
4. 執行：`python scripts/report.py <log.json> -o <report.md>`
5. 在對話中呈現戰報，並用 `present_files` 提供 log.json 與 report.md 下載。

### 批次模擬

1. 確認使用者提供雙方隊伍配置。
2. 確認場數：使用者明說（「跑 100 場」）→ 用 `--count`；模糊（「跑批次」）→ 用 `analysis_config.yaml` 的 `default_count`。
3. 確認 seed 策略：使用者沒指定 → 預設 `sequential`（等差數列，可重現）；明確要求隨機 → 用 `--seed-mode random`。
4. 執行：`python scripts/batch_simulate.py <team_a.yaml> <team_b.yaml> --output-dir <dir>/ [--count N] [--seed-mode MODE]`
5. 執行：`python scripts/batch_report.py <dir>/batch_summary.json -o <dir>/batch_report.md`
6. 在對話中呈現批次戰報，並用 `present_files` 提供 `batch_summary.json`、`batch_report.md`、`seeds.json` 下載。`batch_log.json`（完整 N 場 log）通常很大，**只在使用者要求時才提供**。
7. 在回應結尾提示使用者可選的後續動作：「想看某一場的詳細戰報嗎？」「想換 A 隊配置再跑一次比較嗎？」

## 檔案結構

```
battle-simulator/
├── SKILL.md                       本檔（給 Claude 看的操作手冊）
├── GAME_RULES.md                  給人看的遊戲規則文件（GDD）
├── USAGE_EXAMPLES.md              給人看的使用範例與情境劇本
├── rules/
│   ├── battle_flow.yaml           戰鬥流程的高層描述（人類可讀）
│   ├── combat_formulas.yaml       公式的人類可讀版本與範例
│   └── team_constraints.yaml      編隊限制
├── schemas/
│   ├── team.schema.json           隊伍輸入 schema
│   └── skill.schema.json          技能定義 schema
├── data/
│   ├── global_config.yaml         單場 seed、mitigation 上下限、穩定度上限
│   ├── analysis_config.yaml       批次模擬設定（seed 策略、指標、閾值）
│   └── skill_library.yaml         所有技能的圖鑑
├── scripts/
│   ├── formulas.py                純數學函式（單元可測）
│   ├── skill_engine.py            BC/AC 段技能結算
│   ├── simulate.py                單場主控制器
│   ├── report.py                  單場 Markdown 戰報
│   ├── batch_simulate.py          批次模擬主控制器
│   └── batch_report.py            批次 Markdown 戰報
└── examples/
    ├── team_a_sample.yaml         範例 A 隊
    └── team_b_sample.yaml         範例 B 隊
```

## 規則速查

- 一場戰鬥 = 一次 Before Combat → Combat → After Combat
- 隊伍：1～3 個手下，每人有 `power`、`stability`、`skills[]`
- 穩定度 σ ∈ [0, 0.99]
- 抽樣戰力：`Σ minion.power · U(1−σ, 1+σ)`
- 減傷比例：`sampled / (raw_power_A + raw_power_B)`，獨立夾在 [0.1, 0.9]
- 實際傷害：`raw_power · (1 − 對方 mitigation)`
- BC/AC：雙方同時結算（無先後手），按進入該段的當下戰力比例分攤
- 治療上限為手下原始戰力（溢出捨棄），下限 0
- 技能每場最多觸發一次；若有 `activation_rate` 則先擲骰

## Seed 策略（批次）

| 模式 | 描述 | 重現性 | 適用場景 |
|---|---|---|---|
| `sequential`（預設） | 等差數列 base, base+step, ... | 整批可重現 | 平衡性測試、規則 debug、跨日對比 |
| `derived` | master_seed 衍生子 seed | 整批可重現 | 大批量、避免相鄰 seed 疑慮 |
| `random` | 真隨機 | 不可重現（單場仍可重現） | 純探索、不需重跑 |

**強烈建議使用預設 sequential。** 改用 random 時，務必先警告使用者「這批結果無法重現」。

## 輸入格式範例

```yaml
# team_a.yaml
team_id: alpha
team_name: 鐵衛軍團
minions:
  - id: A1
    name: 重裝步兵
    power: 80
    stability: 0.10
    skills: [shield_bash, recover]
  - id: A2
    name: 弓手
    power: 50
    stability: 0.20
    skills: [arrow_volley]
```

技能 ID 對應 `data/skill_library.yaml` 中的條目。
