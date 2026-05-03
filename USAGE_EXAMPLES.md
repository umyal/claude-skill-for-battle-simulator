# 戰鬥模擬器 — 使用範例

> 本文件示範如何使用這個 skill。從最簡單的「跑一場」到「批次平衡性測試」逐步說明。

---

## 1. 安裝（每台裝置一次）

1. 打開 Claude 桌面 App，左下角頭像 → **Settings → Capabilities**
2. 確認 **Code Execution and File Creation** 已開啟
3. 設定頁面找到 **Skills** 區塊，點 **+ Create skill** 或 **Upload skill**
4. 選擇 `battle-simulator.zip`
5. 上傳後在 Skills 列表把開關打開

完成。**注意**：不同裝置需各自上傳一次（桌面、手機、web 不同步）。

---

## 2. 隊伍 YAML 格式

隊伍定義很單純，一個範例值千言：

```yaml
# team_a.yaml
team_id: alpha            # 必填，內部識別
team_name: 鐵衛軍團        # 可選，戰報顯示用
minions:
  - id: A1                # 必填，手下識別（戰報引用）
    name: 重裝步兵         # 可選，戰報顯示用
    power: 80             # 必填，原始戰力 1~9999
    stability: 0.10       # 必填，穩定度 0.0~0.99
    skills:               # 可選，技能 ID 列表
      - shield_bash
      - recover
  - id: A2
    name: 弓手
    power: 50
    stability: 0.20
    skills: [arrow_volley]
  - id: A3
    name: 醫療兵
    power: 30
    stability: 0.05
    skills: [rally]
```

**規則速記**：

- `minions` 至少 1 個、最多 3 個
- `skills` 可以是空陣列 `[]` 或省略
- 技能 ID 必須對應 `data/skill_library.yaml` 中的條目，否則戰報會標註「skill_not_found」

## 3. 技能定義格式

技能寫在 `data/skill_library.yaml`，新增技能不需要改任何 Python 程式碼：

```yaml
skills:
  - id: shield_bash
    name: 盾擊
    phase: before_combat        # 或 after_combat
    effect_type: damage_enemy   # 或 heal_self
    value: 15                   # 數值
    # activation_rate 省略 → 100% 必發動
    description: 戰鬥開始前以盾撞擊敵方陣型，造成 15 點傷害

  - id: ambush
    name: 伏擊
    phase: before_combat
    effect_type: damage_enemy
    value: 25
    activation_rate: 0.5        # 50% 發動機率
    description: 50% 機率在戰鬥開始前伏擊敵方，造成 25 點傷害
```

## 4. 在 Claude Chat 中使用

### 4.1 最簡單的開場：用內建範例打一場

```
請用 battle-simulator skill 用內建的 team_a_sample 和 team_b_sample 打一場
```

Claude 會：
1. 讀取 `examples/team_a_sample.yaml` 和 `team_b_sample.yaml`
2. 執行 `simulate.py`
3. 執行 `report.py`
4. 在對話中呈現完整戰報，並提供 JSON log 與 Markdown 戰報下載

### 4.2 直接在對話中描述隊伍

不必先寫 yaml，描述清楚 Claude 會幫你轉成檔案：

```
用 battle-simulator 模擬以下對戰：

A 隊（鐵衛軍團）：
- A1 重裝步兵 戰力 80 穩定度 0.1，技能：盾擊、急救
- A2 弓手 戰力 50 穩定度 0.2，技能：箭雨

B 隊（暗影刺客團）：
- B1 刺客頭目 戰力 90 穩定度 0.25，技能：伏擊、毒箭
- B2 遊俠 戰力 60 穩定度 0.15，技能：箭雨、急救
```

### 4.3 上傳 yaml 檔案

寫好 yaml 後直接拖進對話：

```
這是兩個隊伍配置，用 battle-simulator 打一場
[拖入 team_a.yaml]
[拖入 team_b.yaml]
```

### 4.4 指定 seed

想看「同樣對戰、不同運氣」：

```
剛才那場用 seed 12345 再打一次，看會不會結果不同
```

### 4.5 批次模擬（看勝率）

```
用 battle-simulator 跑 100 場批次，A 隊和 B 隊配置同上
```

Claude 會：
1. 執行 `batch_simulate.py --count 100`（預設 sequential seed 10000~10099）
2. 執行 `batch_report.py`
3. 呈現勝率分布、數值統計、極端場次
4. 提示你「想看某一場詳細戰報嗎？」

### 4.6 從批次中重現單場

批次戰報會列出極端場次的 seed。要重現某場：

```
seed=10076 那場 A 隊大勝，幫我跑那一場的詳細戰報
```

Claude 會用 `simulate.py --seed 10076` 重跑那場戰鬥（單場模式），呈現完整的階段細節。

### 4.7 平衡性測試：規則改變的影響

這是 design-before-coding 的核心應用：

```
先用當前規則跑 100 場批次當基準
然後把減傷上限從 0.9 改成 0.85，再跑 100 場批次
比較兩個結果，告訴我這個規則改動對勝率分布的影響
```

或者測試隊伍配置的影響：

```
A 隊現在勝率 78%。如果把 A1 戰力從 80 降到 70，
跑 100 場看勝率會變成多少？
```

---

## 5. 常見情境劇本

### 劇本 A：企劃調整技能數值

> 「伏擊技能太強了，想調整看看」

```
1. 用當前規則跑 100 場基準批次
2. 把 ambush 的 value 從 25 改成 20，再跑 100 場
3. 把 ambush 的 activation_rate 從 0.5 改成 0.4，再跑 100 場
4. 比較三組結果，看哪個調整對勝率影響較合理
```

Claude 會逐次操作並呈現比較表格。

### 劇本 B：玩家選擇隊伍配置

> 「我有 5 個手下可選，要編 3 人隊。哪個組合對戰 X 隊伍勝率最高？」

```
我的可選手下：
- M1 戰士 戰力 70 σ=0.1 技能[盾擊]
- M2 弓手 戰力 50 σ=0.2 技能[箭雨]
- M3 法師 戰力 60 σ=0.3 技能[伏擊]
- M4 醫者 戰力 40 σ=0.05 技能[急救]
- M5 刺客 戰力 55 σ=0.25 技能[毒箭]

對手是固定的 X 隊伍：（略）
從 5 取 3 共有 10 種組合，各跑 50 場批次，列出勝率排名
```

### 劇本 C：理解某場為什麼這樣打

> 「seed=10080 那場為什麼 B 贏了？」

```
跑單場 simulate.py --seed 10080，呈現完整戰報
然後 Claude 解釋：「BC 段 A 隊的箭雨沒發動（roll 0.92 ≥ 0.8），
而 B 隊的伏擊發動了（roll 0.31 < 0.5），導致 B 在 BC 段就建立優勢...」
```

---

## 6. 規則調整的位置速查

修改規則只需要改設定檔，**不要動 Python 腳本**（除非要改公式本身）：

| 想調整什麼 | 改哪裡 |
|---|---|
| 單場 seed | `data/global_config.yaml` 的 `seed` |
| 減傷上下限 | `data/global_config.yaml` 的 `mitigation` |
| 穩定度合法上限 | `data/global_config.yaml` 的 `stability_max` |
| 批次 seed 策略 | `data/analysis_config.yaml` 的 `seed_strategy` |
| 批次預設場數 | `data/analysis_config.yaml` 的 `default_count` |
| 批次要統計什麼指標 | `data/analysis_config.yaml` 的 `metrics` |
| 戰報詳細度閾值 | `data/analysis_config.yaml` 的 `report_thresholds` |
| 新增技能 | `data/skill_library.yaml` 的 `skills` 列表 |
| 編隊限制（人數、戰力上限） | `rules/team_constraints.yaml` |
| 戰鬥公式本身 | `scripts/formulas.py`（謹慎，會改變所有結果） |

改完規則檔後，重新打包 zip 上傳到 Claude App 即可。**不需要重新訓練、不需要清空對話**——下次新 chat 觸發 skill 時就會用新規則。

---

## 7. 偵錯技巧

**Claude 沒走 skill 路徑，自己編戰報？**
明確要求：「**用 battle-simulator skill 模擬**...」第一句話就把 skill 名稱寫出來。

**戰報數值看起來怪？**
要求 Claude 提供 `log.json` 完整檔下載，裡面有每個階段的所有中間值，可以人工驗算公式。

**規則改了但結果沒變？**
最常見原因：忘記重新上傳 zip。在 Claude App 的 Skills 列表，舊版要先刪除再上傳新版。

**批次跑太久？**
不可能，100 場約 10 毫秒、1000 場約 100 毫秒（Python 計算）。如果感覺慢，是 Claude 在 chat 裡呈現結果的時間，跟模擬本身無關。

**結果不可重現？**
檢查 seed 策略是否設成 `random` 模式。預設應該是 `sequential`。

---

## 8. 進階：擴充 skill

想新增功能（例如新增 buff 技能、加入地形效果）的流程：

1. 在 `GAME_RULES.md` 描述新規則的設計理念
2. 在 `rules/` 下對應的 YAML 補充人類可讀說明
3. 在 `data/` 下對應的設定檔加新欄位
4. 修改 `schemas/` 下的 schema 描述新格式
5. 修改 `scripts/formulas.py`（公式）或 `skill_engine.py`（技能流程）實作
6. 修改 `scripts/report.py` 與 `batch_report.py` 加入新指標的呈現
7. 跑單場測試確認 determinism
8. 重新打包 zip 上傳

每一步都對應 design-before-coding 的精神：**先寫規則文件、再改設定、最後改程式碼**。
