# 06 · 交付環:GitOps + 漸進發布

> **一句話定位**:系統能跑、能看見了,**怎麼把變更安全地推上去、出事能秒回**?這一環講 **GitOps**(Git 為唯一真相源,集群自己拉取收斂)和**漸進發布**(金絲雀/藍綠 + 自動分析),又一個 2019 沒有的格子。

> **本章深度層**:外環,**寫滿深度**。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 部署模型 | CI 跑 `kubectl apply`(**push**,CI 握集群憑證) | **GitOps**(**pull**,集群內 agent 拉 Git 收斂) |
| 真相源 | 「線上實際狀態」(可能被人手改過) | **Git**(聲明式、版本化、不可變) |
| 回滾 | 重跑舊流水線 / 手工 | **`git revert`**,秒級回到已知good |
| 配置漂移 | 沒人知道線上和倉庫差多少 | **drift detection**:agent 持續比對並糾偏 |
| 發布策略 | 滾動更新 | **漸進發布**:金絲雀/藍綠 + **指標驅動自動晉級/回滾** |

**一句話**:GitOps 把第 01 章的 reconcile 模型**從集群內擴展到「Git ↔ 集群」之間**——Argo CD/Flux 本質就是一個「watch Git → 把集群收斂到 Git 描述」的控制器。

---

## 1. 核心敘事

### 1.1 GitOps 四原則(OpenGitOps)

1. **聲明式**:整個系統的期望狀態用聲明式描述(k8s YAML 本就如此)。
2. **版本化 + 不可變**:狀態存在 Git,有完整歷史、可審計、可回滾。
3. **自動拉取**:集群內的 agent **主動從 Git 拉**期望狀態(pull),而非外部 push 進來。
4. **持續收斂**:agent 不斷比對「Git(期望)vs 集群(實際)」並糾偏——**又是 reconcile**。

### 1.2 Push vs Pull:為什麼 Pull 更安全

```
Push(舊):  CI ──握著集群 admin 憑證── kubectl apply ──▶ 集群
            風險:CI 系統成了集群的鑰匙;憑證外洩 = 集群淪陷

Pull(GitOps): 集群內 Argo CD/Flux ──拉──▶ Git
              CI 只負責「構建鏡像 + 改 Git 裡的 tag」,從不碰集群
              集群憑證不出集群;CI 被黑也碰不到生產集群
```

Pull 模型的好處:**集群憑證不外流**、**Git 是唯一入口(所有變更可審計、可 review、可回滾)**、**drift 自動糾正**。

### 1.3 GitOps agent 在做什麼

Argo CD / Flux 持續做三件事:

- **比對(diff)**:Git 裡的期望 vs 集群裡的實際。
- **同步(sync)**:把集群改成 Git 的樣子(可手動批准或自動)。
- **修剪(prune)**:Git 裡刪了的對象,集群裡也刪。

外加 **drift detection**(有人 `kubectl edit` 改了線上 → agent 發現偏離 → 告警或自動改回)和 **health 評估**(對象是否真的健康)。

### 1.4 漸進發布:別再「一把全換」

滾動更新只是「逐個換 Pod」,**它不看新版本好不好**就一路換完。漸進發布(Argo Rollouts / Flagger)把發布變成**可觀測、可自動回滾**的過程:

```
金絲雀:  v2 接 5% 流量 → 看指標(p99/錯誤率,來自 05 OTel)
         好 → 25% → 50% → 100%
         壞 → 自動回滾到 v1,人都不用醒
```

- **流量切分**靠第 04 章的網格 / 第 03 章的 Gateway。
- **晉級/回滾判據**靠第 05 章的指標(automated analysis)。
- 三環在這裡合流:**交付(06)用 網格(04)切流、用 可觀測(05)做判據**。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **Argo CD reconcile**:watch Git(輪询或 webhook)+ watch 集群對象 → 算 diff → sync/prune;`Application` 是它的 CRD,**App-of-Apps** 用一個 App 管理一堆 App(管理規模化)。
- **Flux**:一組 CRD(GitRepository / Kustomization / HelmRelease),更「GitOps toolkit」、可組合,適合嵌進更大平台(回扣 08 平台環)。
- **健康與 sync wave**:用 annotation 控制部署順序(先 DB migration 後 app),用健康檢查決定 sync 是否成功。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **明文 Secret 進 Git** | 憑證洩漏 | GitOps 要求一切進 Git,但 Secret **不能明文**;用 Sealed Secrets / External Secrets / SOPS |
| auto-sync 推了壞 manifest | 壞配置**自動**全量生效 | 自動同步 = 自動傳播錯誤;必須配**漸進發布 + 健康門禁**兜底 |
| drift 拉鋸 | 手改線上一直被改回 / 衝突 | GitOps 下**禁止手改線上**,否則和 agent 打架 |
| Git 不可用 | **不能發新版**(但集群照跑) | Git 成了交付路徑的依賴;已運行 workload 不受影響(數據面解耦) |
| 倉庫/App 膨脹 | reconcile 慢、API Server 壓力 | 成百上千 App 同時 reconcile;要調間隔 + 分片 + App-of-Apps |

### 📈 規模化極限

- **App 數量 × reconcile 頻率 → API Server 負載**:幾百個 Application 高頻 reconcile 會給 API Server 壓力,要調 reconcile 間隔、用 webhook 觸發替代輪询、分片(多 Argo CD 實例 / shard)。
- **mono-repo vs multi-repo**:單倉庫好審計但易衝突、CI 慢;多倉庫好隔離但治理散。大組織常按團隊/環境拆 + App-of-Apps 聚合。
- **Secret 規模化**:External Secrets Operator 從外部 KMS/Vault 拉,避免把加密 secret 也堆進 Git。

### ⚖️ 選型論證

| 維度 | 選項 | 怎麼選 |
|---|---|---|
| GitOps 引擎 | **Argo CD**(UI 強、App 中心、上手快)vs **Flux**(toolkit、可組合、嵌平台) | 要好用 UI/可視化選 Argo CD;要做平台底座、可編排選 Flux |
| 漸進發布 | **Argo Rollouts** vs **Flagger** | 用 Argo 全家桶選 Rollouts;Flagger 與多種網格整合好 |
| Secret | Sealed Secrets / External Secrets / SOPS | 有 Vault/雲 KMS 用 External Secrets;純 Git 用 SOPS/Sealed |
| 還要不要 push CI | 簡單項目 push 也行 | 但生產多人協作、要審計/回滾 → **GitOps pull** |

> **架構師判斷**:GitOps 的最大價值是**把「生產變更」變成「一個可 review、可 revert 的 Git commit」**——審計、回滾、權限全落在 Git 上。但它要求紀律:**線上禁手改**、**Secret 不明文**、**auto-sync 必須配健康門禁**,否則「自動」會放大事故。

### 🧭 演進路徑

1. **push → pull**:CI 只構建鏡像 + 提交 Git 裡的鏡像 tag;部署交給 Argo CD/Flux,撤掉 CI 的集群憑證。
2. **手工回滾 → git revert**:回滾 = 回退 commit。
3. **滾動 → 金絲雀**:接入 Rollouts/Flagger,用 OTel 指標做自動晉級/回滾。
4. **散落 Secret → External Secrets**:從 Vault/KMS 拉,Git 裡只留引用。

### 🏭 生產事故 / 教訓

- **明文 Secret 進公開倉庫**:GitOps 推「一切進 Git」,有人把 DB 密碼也提交了。教訓:**Secret 是 GitOps 的頭號坑**,上 External Secrets/SOPS 並掃描倉庫(回扣 07 供應鏈)。
- **auto-sync 把壞配置秒級全量推上線**:沒有金絲雀兜底。教訓:**自動化必須配漸進發布 + 健康門禁**,讓壞變更在 5% 流量處被指標攔下並自動回滾。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 部署模型 | **GitOps(pull)**,CI 不碰集群 |
| 引擎 | Argo CD(應用團隊友好)/ Flux(平台底座) |
| 發布策略 | **漸進發布**(金絲雀),指標驅動自動回滾 |
| 流量切分 | 網格(04)/ Gateway(03) |
| 晉級判據 | OTel 指標(05):錯誤率 / p99 |
| Secret | External Secrets / SOPS / Sealed Secrets,**絕不明文** |

---

## 🧵 示例服務在這一環

發 `order-api:1.5.0`:

1. CI 構建並**簽名**鏡像(簽名見 07 章),把 Git 裡 `order-api` 的 tag 從 `1.4.2` 改成 `1.5.0`,開 PR。
2. PR 合併 → **Argo CD** 檢測到 Git 變化 → 對比集群 → 觸發 **Rollouts** 金絲雀。
3. v1.5.0 先接 **5% 流量**(網格切流,04)→ Rollouts 拉 **OTel 指標**(05):錯誤率、p99。
4. 指標健康 → 自動 25% → 50% → 100%;**任一步 SLO 破線 → 自動回滾到 1.4.2**,無需人工。
5. Secret(DB 密碼)不在 Git,由 **External Secrets** 從 Vault 拉。

對比 2019:CI 直接 `kubectl set image` 一把全換,壞了靠人盯告警手工回滾,且 CI 握著生產集群憑證。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| 金絲雀的流量切分機制 | 本線 `04-service-mesh`、`03-networking`(Gateway) |
| 自動晉級判據的指標 | 本線 `05-observability` |
| 鏡像簽名 / Secret / 供應鏈 | 本線 `07-security` |
| 發布與變更管理(理論側:RPO/RTO、變更窗口) | `system-design/09-發布與變更管理` |

---

## 一句收口 + 地圖更新

> **GitOps = 把 reconcile 擴展到「Git ↔ 集群」**:Git 是唯一真相源,集群內 agent 持續拉取糾偏,部署從「CI push」變成「commit + 自動同步」,回滾就是 `git revert`。配上**漸進發布**(網格切流 + 指標自動回滾),高頻發布才安全。但要守紀律:禁手改、Secret 不明文、auto-sync 配門禁。

**🗺 地圖更新**:你補上「怎麼安全交付」這一環,看到 04/05/06 三環如何在一次金絲雀裡合流。
**下一站**:`07 安全環` —— 你交付的鏡像**可信嗎**、誰能在集群裡做什麼?這一環講 2020 後爆發的 **供應鏈安全 + Policy as Code**。
