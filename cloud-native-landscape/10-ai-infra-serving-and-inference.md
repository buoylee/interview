# 10 · AI 基建環 II:推理/服務(KServe · vLLM · 推理網關 · LLM 特定)

> **一句話定位**:模型訓好了(ch09),**怎麼把它服務化**?推理和訓練截然不同:它是**在線、突發、要 scale-to-zero**,而 LLM 還帶來 KV cache、連續批處理、冷啟動慢、token 流式這些特有麻煩。這一環講推理側基建。

> **本章深度層**:外環,**寫滿深度**(AI 工程師/架構師向)。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 模型怎麼上線 | Flask + 單卡,自己包 HTTP | **KServe**(`InferenceService` CRD)標準化服務 |
| 推理運行時 | 自己調 TensorFlow Serving | **vLLM**(LLM)/ **Triton**(通用),連續批處理 |
| 擴縮 | 固定副本 | **按請求/GPU 指標擴縮**,**scale-to-zero** |
| 路由 | 普通 round-robin | **推理網關**:按模型名 + 負載(KV cache/隊列)智能路由 |
| LLM 特有問題 | (還沒 LLM 浪潮) | KV cache、連續批處理、冷啟動、token 流式 |

**一句話**:推理不是「把訓練容器掛個 HTTP」——它是延遲敏感、突發、按 token 計費的在線服務,逼出了 **vLLM 連續批處理、KServe 自動擴縮、scale-to-zero、推理網關**這套和微服務既像又不像的新基建。

---

## 1. 核心敘事

### 1.1 推理 vs 訓練:又一次「workload 不同」

| 維度 | 訓練(ch09) | 推理(本章) |
|---|---|---|
| 模式 | 離線批處理,跑完退 | **在線服務**,常駐但流量突發 |
| 延遲 | 不敏感(跑幾小時) | **敏感**(用戶等回答) |
| 擴縮 | gang,一次拿滿 | **彈性**,按負載增減,**閒時縮到 0** |
| 並發 | 一個大作業 | **高並發小請求** |
| GPU 利用 | 算力打滿 | **單請求填不滿 GPU → 要批處理** |

### 1.2 KServe:把「模型服務」標準化

**KServe** 用一個 CRD 把模型服務化:

```yaml
apiVersion: serving.kserve.io/v1beta1
kind: InferenceService
metadata: { name: risk-model }
spec:
  predictor:
    model:
      modelFormat: { name: vllm }
      storageUri: s3://models/risk-model/v2
```

它給你:多框架支持、**自動擴縮(含 scale-to-zero)**、金絲雀發布(回扣 06)、標準推理協議。底層常用 **Knative** 做請求驅動的擴縮與 scale-to-zero。又是「CRD + 控制器」(回扣 01)。

### 1.3 推理運行時:為什麼是 vLLM

直接用 PyTorch 跑推理**極度浪費 GPU**:一個請求填不滿算力、GPU 大量空轉。**vLLM** 成為 LLM 推理事實標準,靠兩招:

- **連續批處理(continuous batching)**:動態把多個請求拼成一批喂 GPU,不等湊滿固定 batch——吞吐量數倍提升。
- **PagedAttention**:把 **KV cache** 像操作系統分頁一樣管理(分塊、按需分配),大幅減少顯存碎片、提高並發。

通用/多框架場景用 **NVIDIA Triton**(也支持動態批處理)。

### 1.4 擴縮:scale-to-zero 與它的代價

推理流量突發,理想是**閒時縮到 0**(不燒 GPU),來請求再拉起。但——

- **冷啟動是大坑**:一個 70B 模型權重幾十~上百 GB,**加載要幾分鐘**。scale-from-zero 的第一個請求可能超時。
- 對策:小/實驗模型可 scale-to-zero(容忍冷啟動);**熱門模型保最小副本常駐**(warm pool);用模型緩存/快速加載減冷啟動;**KEDA** 按自定義指標(隊列深度、token 速率)驅動擴縮。

> 核心權衡:**scale-to-zero 省錢 vs 冷啟動延遲**。按模型流量特徵分別決策,不是一刀切。

### 1.5 LLM 特有的麻煩

- **KV cache = 並發上限**:每個進行中的會話佔顯存,**顯存決定能同時服務多少請求 / 多長上下文**——這是 LLM 服務的核心瓶頸,不是算力。
- **響應長且不定**:token 逐個生成,要 **流式(SSE/token streaming)** 改善體感。
- **大權重冷啟動慢**(見上)。
- **多模型 / 模型路由**:一個集群服務多個模型,要按模型名路由、按需加載。

### 1.6 推理網關:LLM-aware 路由

普通 Service 的 round-robin **對 LLM 很糟**:它不知道哪個副本 KV cache 快滿了、哪個隊列堵了,盲目輪詢會造成負載不均與 cache 抖動。**Gateway API Inference Extension**(2025 的 SIG 工作)和 **Envoy AI Gateway** 把入口(回扣 03 Gateway API)擴展成**推理感知**:按**模型名**路由、按**KV cache 佔用 / 隊列深度**做負載均衡、做 token 級限流與計費。這是「Gateway API 生態」往 AI 延伸的一格。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **KServe + Knative**:`InferenceService` → 一個 predictor Deployment(跑 serving runtime);Knative 監聽請求併發數做擴縮,0 副本時由 activator 緩衝第一個請求並拉起 Pod。
- **vLLM PagedAttention**:KV cache 切成固定大小 block,按需分配/釋放,像虛擬內存分頁;連續批處理在每個 decode step 動態增刪請求。
- **推理網關**:Envoy 數據面 + 推理感知的負載均衡策略(讀後端 KV/隊列指標),按模型名選後端池。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **冷啟動超時** | scale-from-zero 第一個請求超時 | 大模型加載幾分鐘;scale-to-zero 與延遲 SLO 衝突 |
| **KV cache OOM** | 高並發/長上下文下推理崩 | 顯存被 KV cache 撐爆;**並發 × 上下文長度**有硬上限 |
| **GPU 低利用** | 賬單高但 GPU 空轉 | 沒做連續批處理,單請求填不滿卡 |
| **擴縮滯後** | 流量突增時排隊、超時 | GPU 節點供給慢(分鐘級),HPA 反應不及;要預擴/緩衝 |
| **盲目 round-robin** | 部分副本過載、cache 抖動 | 普通 LB 不懂推理負載;要推理網關 |

### 📈 規模化極限

- **顯存 = 並發天花板**:LLM 能同時服務多少請求,主要由 **KV cache 顯存**而非算力決定。容量規劃要按「並發 × 平均上下文長度」算顯存。
- **批處理:吞吐 vs 延遲**:批越大吞吐越高、但單請求延遲越高;連續批處理在二者間動態平衡,仍要按 SLO 調。
- **冷啟動 vs 常駐成本**:warm 副本燒錢、cold 啟動慢——按模型流量畫像分配 warm pool。
- **token 計費/限流**:多租戶推理要按 token 限流與計費,普通 QPS 限流不夠。

### ⚖️ 選型論證

| 維度 | 選項 | 怎麼選 |
|---|---|---|
| 服務框架 | **KServe**(全 k8s 原生)/ 裸 vLLM Deployment / Triton | 要自動擴縮/金絲雀/標準化選 KServe;簡單場景裸跑 vLLM |
| LLM 運行時 | **vLLM**(LLM 事實標準)/ Triton(通用多框架)/ TGI | LLM 選 vLLM;多框架/傳統模型選 Triton |
| 擴縮 | Knative(scale-to-zero)/ **KEDA**(自定義指標) | 突發+可容忍冷啟動用 Knative;按 token/隊列指標用 KEDA |
| 路由 | **推理網關**(Gateway API Inference Ext / Envoy AI Gateway)/ 普通 Service | 多模型/LLM 負載敏感選推理網關 |
| 自管 vs 託管 | k8s 自管 vs 託管推理 API | 要可控/數據不出域/逃生選自管;省心選託管 |

> **架構師判斷**:LLM 推理的成本與性能,**主要被 KV cache(顯存)和批處理效率決定,不是算力**。架構目標是「**用連續批處理把 GPU 填滿、用推理網關把負載擺平、用 scale-to-zero/warm pool 平衡成本與延遲**」。把它當普通微服務(固定副本 + round-robin)會又貴又慢。

### 🧭 演進路徑

1. **Flask 單卡 → vLLM**:換上連續批處理,GPU 利用率與吞吐躍升。
2. **裸跑 → KServe**:標準化 + 自動擴縮 + 金絲雀。
3. **固定副本 → scale-to-zero / KEDA**:按負載彈性,閒時省 GPU。
4. **普通 Service → 推理網關**:多模型、LLM 負載感知路由 + token 計費。

### 🏭 生產事故 / 教訓

- **scale-to-zero 把大模型縮沒了,流量回來時集體超時**:冷啟動幾分鐘。教訓:**大模型保 warm 最小副本**,只對小/實驗模型 scale-to-zero。
- **流量尖峰 KV cache OOM 連環崩**:沒按「並發 × 上下文」限並發。教訓:**按顯存設並發上限 + 排隊**,別讓 cache 撐爆。
- **round-robin 導致個別副本 cache 抖動、p99 爆炸**:教訓:LLM 要**推理感知路由**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 服務框架 | **KServe**(`InferenceService`),自動擴縮 + 金絲雀 |
| LLM 運行時 | **vLLM**(連續批處理 + PagedAttention) |
| 擴縮 | Knative scale-to-zero(小模型)/ KEDA 按 token/隊列;大模型保 warm |
| 路由 | 推理網關(Gateway API Inference Extension / Envoy AI Gateway) |
| 核心瓶頸 | **KV cache 顯存**(= 並發上限) |
| 體驗 | token 流式(SSE) |

---

## 🧵 示例服務在這一環

`order-api` 調用 ch09 訓好的**風控模型**:

- 模型用 **KServe `InferenceService`** 部署,後端 **vLLM**;按請求量自動擴縮,流量低谷時這個實驗模型 **scale-to-zero**(容忍冷啟動)。
- order-api 不直連 Pod,而是經**推理網關**:按模型名路由到 `risk-model`,並感知各副本 KV cache 佔用做負載均衡。
- 升級到 `risk-model:v3` 時,KServe 金絲雀 + OTel 指標(回扣 05/06)自動晉級或回滾。

若 order 系統再加一個 **LLM 客服助手**(呼應你的 RAG/agent 方向):用 vLLM 連續批處理服務、token 流式返回、按「並發 × 上下文」設顯存上限、熱門時段保 warm 副本——把 ch03 的 Gateway、ch05 的可觀測、本章的推理基建全串起來。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| 訓練/GPU 調度側 | 本線 `09-ai-infra-training` |
| 推理網關的 Gateway API 基礎 | 本線 `03-networking` |
| LLM 應用層(RAG / agent / langchain) | `ai/langchain/`、`ai/` |
| 模型本身與動手訓練 | `ai/ml-labs/` |

---

## 一句收口 + 地圖更新

> **AI 推理上 k8s 的本質,是「延遲敏感、突發、按 token 計費的在線服務」**:用 vLLM 連續批處理把 GPU 填滿、用 KServe 自動擴縮與金絲雀、用 scale-to-zero/warm pool 平衡成本與冷啟動、用推理網關做 LLM 感知路由。記住核心瓶頸是 **KV cache 顯存,不是算力**。

**🗺 地圖更新**:AI 兩環(訓練 + 推理)補完——你現在能從架構師視角談「AI workload 為何特殊、GPU 怎麼調、模型怎麼服務」。
**下一站**:`11 彈性與成本環` —— 所有 workload(微服務 + AI)都講完了,**怎麼讓它們自動伸縮又不燒錢**?autoscaling 全景 + Karpenter + FinOps。
