# Lab · 最小 LLM 網關(對應 ch10)

一個前置的 LLM 網關,實作 ch10 兩個 LLM 特有能力,**離線可跑**(後端是 fake LLM,不需任何真實 API key):

1. **語義快取**(ch10 §3):近義問題命中歷史回答,省掉 LLM 調用、不計費。
2. **按 token 預算限流**(ch10 §2):每 client 累計 token,超 BUDGET 就 429。

## 拓撲

```
curl ─▶ gateway:9000 ──(快取 miss 才打)──▶ fake-llm:8000  (回 answer + usage.total_tokens)
            │
            └─▶ Redis:  llmcache(prompt+answer+向量)   tokens:{client}(累計 token)
```

- `fake_llm.py` — 離線假 LLM,回固定文本 + token 用量(字元數粗估)
- `gateway.py` — 網關:語義快取(字元 2-gram + 餘弦)+ token 預算限流
- 同一 image,靠 `APP` 環境變數決定起 gateway 還是 fake_llm

## 跑

```bash
docker compose up -d --build
bash test.sh          # (a) 語義快取命中  (b) token 預算 429
docker compose down
```

## 預期輸出(實測)

```
=== (a) 語義快取:近義兩問,第二次應命中(cached=true,不計費)===
Q1 「什麼是 API 網關」  → {"cached":false, ... "tokens_charged":58,"used":58}
Q2 「API 網關是什麼」  → {"cached":true,"similarity":0.707, ...回 Q1 的答案... "tokens_charged":0}

=== (b) token 預算:client=u2 連打不同主題,累計超 BUDGET(200)後 429 ===
第1問「什麼是負載均衡」     → ... "used":52  [HTTP 200]
第2問「解釋資料庫索引原理」 → ... "used":108 [HTTP 200]
第3問「TCP 三次握手是什麼」 → ... "used":168 [HTTP 200]
第4問「什麼是垃圾回收機制」 → ... "used":224 [HTTP 200]
第5問「解釋 CAP 定理」     → {"error":"token budget exceeded","used":224,"budget":200} [HTTP 429]
第6問「訊息佇列有什麼用」   → 429
```

**關鍵觀察**:
- (a) Q2 和 Q1 字不同、意思同 → `similarity=0.707 ≥ 0.6` 命中,**回 Q1 的答案且 tokens_charged=0**(精確快取會 miss,語義快取才命中——這就是它省成本的點)。
- (b) token 是按**用量**累計(52→224),不是按請求數;超 BUDGET 即 429。注意第 4 問把 used 推到 224 才過,**它之後**才開始擋(可略微超預算,符合「先扣再判」的現實)。
- (b) 的「TCP 三次握手是什麼」雖和 Q1 共享「是什麼」,**沒有誤命中**——2-gram 比純字符更能區分。

## ⚠️ 教學近似 vs 生產

- 本 lab 的語義匹配是 **字元 2-gram + 餘弦相似度**,純字面、零依賴、離線可跑,**只夠示範機制**。閾值 0.6 是配這個粗方法調的。
- **生產**用真 **embedding 模型**(sentence-transformers / OpenAI embeddings 等)把 prompt 映到語義向量空間,配**向量索引**(pgvector / Milvus / Redis 向量檢索)做近鄰搜索;那時餘弦閾值通常用 ~0.9,且能正確處理「同義不同字」(本 lab 的字面方法做不到真正的同義)。
- 快取查找這裡用 O(N) 全掃(lab 數據量小);生產用向量索引做 ANN 近鄰。

## 動手玩

- 調 `THRESHOLD`(compose 環境變數):調高 → 趨近精確快取、命中率低;調低 → 可能**誤命中**(把語義近但答案應不同的問題混淆,ch10 §3 的風險)。
- 調 `BUDGET`/`WINDOW` 觀察 token 預算行為。
- 連發同一個 prompt 多次:第二次起命中快取、`tokens_charged=0` —— 快取直接省掉了後端成本。

## 對應章節

ch10 §2(token 預算,= ch05 限流的 token 版)、§3(語義快取);快取命中不計費呼應「LLM 網關靠快取省成本」。
