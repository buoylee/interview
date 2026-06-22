# 13 · 收口:選型總圖 + 變遷總對照 + 一頁心智地圖

> **一句話定位**:把整張同心圓收成**一頁可隨時調出的全局視圖**——每環的本質一句話、2026 該選什麼、2019→2026 變了什麼、以及貫穿全書的「**何時不該上**」架構師判斷。這章是備考和架構評審前翻的那一頁。

---

## 1. 一頁心智地圖:每環一句話本質

由內而外,背下這 13 句,你就有了完整骨架:

| 環 | 一句話本質 |
|---|---|
| **00 雲原生 ≠ k8s** | k8s 是圓心,雲原生是「高頻、安全、可觀測地交付可演進系統」的一整套同心圓實踐 |
| **01 內核** | 聲明期望狀態,一群 level-triggered 控制器不斷把世界收斂過去;一切過 API Server,etcd 是唯一真相源 |
| **02 運行時** | 節點上沒 Docker 也照跑:kubelet→CRI→containerd→runc,把容器跑成一個被隔離的普通進程 |
| **03 網絡** | 數據面從 iptables 下沉到 eBPF;入口從 Ingress 升級到 Gateway API;底層不再默認 nginx |
| **04 服務間** | 把 mTLS/重試/熔斷/遙測從業務庫下沉到網格代理;sidecar → ambient 無 sidecar |
| **05 可觀測** | OpenTelemetry 統一採集層,用 trace context 把三支柱縫成可導航的圖;後端可換(逃生票) |
| **06 交付** | GitOps 把 reconcile 擴到「Git ↔ 集群」,回滾即 revert;配漸進發布讓高頻上線安全 |
| **07 安全** | 供應鏈可證明(簽名/SBOM/溯源)+ 規則即代碼(准入 enforce)+ 零信任,分層縱深 |
| **08 平台** | 把前七環複雜度產品化成開發者自助黃金路徑;CRD+控制器把意圖展開成底層 |
| **09 AI 訓練** | 昂貴稀缺的 GPU 怎麼調度得不死鎖(gang)、高利用率(MIG/DRA)、多團隊公平(Kueue) |
| **10 AI 推理** | 在線突發按 token 計費的服務;vLLM 連續批處理填滿 GPU,瓶頸是 KV cache 顯存 |
| **11 彈性與成本** | 彈性兩軸(Pod 級 HPA/VPA/KEDA + 節點級 Karpenter consolidation);成本核心旋鈕是 requests,疊 spot/Kubecost |
| **12 前沿** | serverless/WASM/多集群/邊緣,是 k8s 模型往新場景外擴的按需岔路 |

---

## 2. 2019-2020 → 2026 變遷總對照(完整版)

| 環 | 維度 | 2019-2020 | 2026 主流 | 一句話為什麼 |
|---|---|---|---|---|
| 02 | 容器運行時 | Docker | **containerd / CRI-O** | dockershim 1.24 移除,去掉多餘適配層 |
| 03 | 入口 | Ingress + ingress-nginx | **Gateway API** | Ingress 表達力弱;ingress-nginx 2026-03 退役 |
| 03 | Service LB | iptables/kube-proxy | **eBPF / Cilium** | iptables 規則線性爆炸 |
| 03 | 網絡策略 | 基於 IP | 基於**身份** | Pod IP 易變,身份才穩定 |
| 04 | 服務治理 | 業務代碼接 SDK | **服務網格** | 橫切關注點下沉到基礎設施 |
| 04 | 網格形態 | sidecar | **ambient 無 sidecar** | 砍掉 per-Pod 代理開銷 |
| 05 | 遙測採集 | 各信號各 SDK | **OpenTelemetry** | 統一採集 + 免廠商鎖定 |
| 06 | 部署 | CI push `kubectl apply` | **GitOps pull** | 可審計/可回滾/憑證不外流 |
| 06 | 發布 | 滾動更新 | **金絲雀 + 自動回滾** | 高頻發布要可觀測可回滾 |
| 07 | 鏡像信任 | 掃描 | **簽名 + SBOM + 溯源** | 供應鏈攻擊倒逼「可證明」 |
| 07 | 策略 | 人工/PSP | **Policy as Code**(VAP/Kyverno) | PSP 移除;規則要代碼化自動 enforce |
| 08 | 使用姿勢 | 人人寫 YAML | **平台工程 / IDP** | 認知負荷到頂,要黃金路徑 |
| 09 | AI 訓練 | VM 手工排 GPU | **gang 調度 + DRA/MIG + Kueue** | GPU 昂貴稀缺,要防死鎖/提利用率/公平 |
| 10 | AI 推理 | Flask + 單卡 | **KServe + vLLM + 推理網關** | 在線突發,要批處理/彈性/LLM 感知路由 |
| 11 | 彈性/成本 | 固定副本 + 預留機器 | **autoscaling + Karpenter + FinOps** | 高頻彈性 + 雲成本治理成核心責任 |
| 01/12 | k8s 定位 | 跑微服務 | **一切 workload 的底座** | AI/serverless/邊緣都往 k8s 收斂 |

---

## 3. 選型總圖:每環 2026 的默認答案

| 環 | 決策 | 默認選 | 備選 / 條件 |
|---|---|---|---|
| 01 | 控制面 | **託管(EKS/GKE/AKS)** | 自管僅強合規/離線 |
| 02 | 運行時 | **containerd** | CRI-O(OpenShift);gVisor/Kata(強隔離) |
| 03 | CNI / LB | **Cilium(eBPF)** | Calico;雲 CNI |
| 03 | 入口 | **Gateway API** + Envoy Gateway / Istio / Cilium | ~~ingress-nginx~~(已退役) |
| 04 | 網格 | **Istio ambient**(真需要才上) | Linkerd(輕);Cilium mesh;或不上 |
| 05 | 可觀測 | **OTel** + Prometheus/Loki/Tempo/Grafana | 商業平台(但埋點仍用 OTel) |
| 06 | 交付 | **GitOps**(Argo CD / Flux)+ 漸進發布 | — |
| 07 | 安全 | cosign 簽名 + SBOM + **VAP/Kyverno** + PSA | OPA(跨域複雜策略);Falco/Tetragon 運行時 |
| 08 | 平台 | 小團隊用模板+GitOps;規模到了才 **Backstage + Crossplane** | — |
| 09 | AI 訓練 | **Volcano(gang)+ Kueue(配額)+ DRA/MIG** | KubeRay / Kubeflow;RDMA 多機 |
| 10 | AI 推理 | **KServe + vLLM + 推理網關** | Triton(通用);Knative/KEDA 擴縮 |
| 11 | 彈性/成本 | **Karpenter + HPA/KEDA + Kubecost**;先校準 requests | VPA recommend;混 spot + PDB |
| 12 | 前沿 | 按需:Knative / WASM / Cluster API+Karmada / K3s | 有明確驅動才上 |

---

## 4. 架構師判斷清單:「何時**不該**上」(全書最值錢的部分)

新手加組件,資深**先質疑**。把全書的 YAGNI 判斷收在這裡:

| 別急著上 | 先問自己 | 簡單夠用時用 |
|---|---|---|
| **服務網格** | 我真需要 mTLS + L7 治理嗎? | Gateway API + ambient L4(僅 mTLS)/ 少量庫 |
| **平台工程 IDP** | 我的開發認知負荷真到頂了嗎? | Helm/Kustomize 模板 + GitOps + 規範文檔 |
| **多集群** | 我撞到單集群上限或隔離/合規硬需求了嗎? | 單集群 + 多 namespace |
| **WASM** | 容器冷啟動/沙箱真的不夠嗎? | 容器 + RuntimeClass |
| **Operator/CRD** | 我有需要持續 reconcile 的領域對象嗎? | ConfigMap + Helm |
| **自管控制面** | 我有強合規/離線理由嗎? | 託管 k8s |
| **scale-to-zero(大模型)** | 我能接受分鐘級冷啟動嗎? | 保 warm 最小副本 |
| **大比例 spot** | 我的 workload 能容忍隨時被回收嗎? | on-demand 底座 + PDB,先校準 requests 再省 |

> **核心心法**:每個組件都是「能力 ↔ 複雜度」的交易。**先確認有明確驅動力,再上**——這正是資深/架構師和「會堆組件」的分水嶺。

---

## 5. 三句話總綱(背誦版)

> 1. **雲原生 ≠ k8s**:k8s 是圓心(聲明式 + 控制器 + reconcile),雲原生是圓心外「運行時→網絡→服務間→可觀測→交付→安全→平台→AI→彈性成本→前沿」一整圈為了「高頻、安全、可觀測地交付」而生的實踐。
> 2. **2020 後的變化幾乎全在外環**:containerd 取代 Docker、eBPF/Gateway API 取代 iptables/Ingress、服務網格/GitOps/供應鏈安全/平台工程從無到主流、k8s 成 AI 底座——底層也不再默認 nginx。
> 3. **資深的標誌是「先質疑再上」**:每個組件先問「我真需要嗎」,簡單夠用就別堆複雜度。

---

## 6. 怎麼用這份收口

- **面試前**:背第 1 節(13 句本質)+ 第 5 節(三句總綱);被追問深度就調對應章的「🏛 架構師視角」。
- **架構評審前**:翻第 3 節(選型總圖)+ 第 4 節(何時不該上)。
- **更新陳舊認知**:第 2 節(變遷總對照)就是你從 2019 跳到 2026 的 diff。
- **深挖某環**:回對應章 → 再順「🔬 深挖出口」跳進 `cloud-native/`(內環機制 + debug)、`observability/`、`system-design/`、`ai/`。

---

## 一句收口 + 地圖完成

> 你開始時的心智模型是「**k8s = pod/service/deployment**(2019)」;走完這 13 章,它變成「**一張以 k8s 為圓心、外擴十環的現代雲原生同心圓,每環都知道本質、選型、變遷與何時不該上**(2026)」。

**🗺 地圖完成 ✅** —— 認知面從「圓心一個點」擴成「完整同心圓 + 架構師深度」。
**接下來**:想把某一環從「能對話」練到「能落地/能扛深挖」,順該環的「🔬 深挖出口」進既有 deep track;或把這套地圖用在你的 robotics/AI 邊緣方向(09-10 AI + 12 前沿的邊緣直接相關)。
