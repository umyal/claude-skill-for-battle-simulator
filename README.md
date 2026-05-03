# Battle Simulator — A Claude Skill for Game Design Prototyping

一個用 **Claude Skills + Python + YAML** 實作的戰鬥模擬器，目的是在正式寫遊戲程式之前，先驗證戰鬥規則好不好玩。

這個 repo 是 [LinkedIn 文章 〈文章標題〉](文章連結) 的隨附程式碼。

## 它在做什麼

模擬「兩支部隊在地圖某個地格相遇」的單場戰鬥，輸出完整戰報；也支援批次模擬（跑 N 場看勝率分布、分析平衡性）。

- **單場模擬**：完整戰報，每個數值都可追溯到公式
- **批次模擬**：100 場跑下來看勝率、戰力差、極端場次
- **可重現**：固定 seed → 固定結果，今天跑明天跑都一樣
- **規則可改**：技能、上下限、隊伍配置都在 YAML 裡,企劃自己改不用碰 Python

## 快速開始（5 分鐘）

### 方式 A：下載 zip 直接用（推薦）

1. 從本 repo 下載 [`battle-simulator.zip`](./battle-simulator.zip)
2. 打開 Claude（桌面 App 或 Web 版都可以），點頭像 → **Settings → Capabilities**
3. 確認 **Code Execution and File Creation** 已開啟
4. 在 **Skills** 區塊點 **Upload skill**，選擇剛剛下載的 zip
5. 上傳後在 Skills 列表把它打開
6. 開新的 chat，輸入：

   > 請使用 battle-simulator skill 用內建的範例隊伍打一場

完成。

### 方式 B：clone 後自行打包

```bash
git clone https://github.com/umyal/claude-skill-for-battle-simulator.git
cd claude-skill-for-battle-simulator
zip -r my-skill.zip ./battle-simulator
# 把 my-skill.zip 上傳到 Claude
```

## 怎麼跟它互動

幾個常見的 prompt 範例：

```
請用 battle-simulator 用內建範例打一場

請用 battle-simulator 跑 100 場，分析哪隊比較強

剛才那場 seed 12345 的戰鬥，幫我跑詳細戰報

如果把 ambush 技能的 value 從 25 改成 20，再跑 100 場看勝率怎麼變
```

更多範例在 [`battle-simulator/USAGE_EXAMPLES.md`](./battle-simulator/USAGE_EXAMPLES.md)。

## 專案結構

```
battle-simulator/
├── SKILL.md                 給 Claude 看的操作手冊（含「紀律」段落）
├── GAME_RULES.md            給人類看的遊戲規則文件（GDD）
├── USAGE_EXAMPLES.md        使用範例與情境劇本
├── rules/                   人類可讀的規則 YAML
├── data/                    runtime 設定（seed、上下限、技能圖鑑）
├── scripts/                 Python 計算邏輯（source of truth）
├── schemas/                 隊伍/技能格式 schema
└── examples/                範例隊伍 YAML
```

## 設計理念

這個 skill 示範了一個 4 層分工的 pattern：

- **YAML / JSON** 負責規則與資料——企劃自己讀寫
- **Python** 是 source of truth——做公式計算
- **SKILL.md** 是給 Claude 的操作守則與紀律——限定它的行為
- **Claude** 負責理解需求、調用工具、呈現結果——LLM 最擅長的事

最關鍵的紀律寫在 SKILL.md 裡：**禁止 Claude 用語言模型推論代替計算結果**。所有戰力、抽樣、減傷、傷害數值都必須來自 Python 腳本——這保證了結果可重現、可驗證、無幻覺。

詳細討論見配套的 LinkedIn 文章。

## License

MIT — 隨意使用、修改、傳播。如果這個 pattern 對你有幫助，歡迎在 LinkedIn 上 tag 我讓我看到你做了什麼。

## 問題回報

歡迎開 issue 討論規則設計、回報 bug、或分享你用這個 pattern 做了哪些其他應用。