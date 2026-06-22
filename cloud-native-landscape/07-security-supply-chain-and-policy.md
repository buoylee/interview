# 07 · 安全環:供應鏈安全 + Policy as Code

> **一句話定位**:你交付的鏡像**可信嗎**(沒被掉包、依賴沒投毒)?集群裡**誰能做什麼、什麼能跑**?這一環講 2020 後爆發的兩塊:**供應鏈安全**(SBOM/簽名/SLSA)和 **Policy as Code**(把安全規則寫成代碼自動 enforce)。

> **本章深度層**:外環,**寫滿深度**。RBAC/ServiceAccount/Secret 機制細部在 `cloud-native/07`,本章寫供應鏈與策略這兩塊新內容 + 架構師視角。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 鏡像安全 | 跑個 CVE 掃描就算數 | **簽名(cosign)+ SBOM + 構建溯源(SLSA/provenance)** |
| 「你跑的東西可信嗎」 | 基本沒人問 | 准入時**驗簽 + 驗來源**,不可信不准跑 |
| 策略 enforce | 人工 review / 散落腳本 / PSP | **Policy as Code**(Kyverno / OPA / 內建 CEL),准入自動攔 |
| Pod 安全基線 | PodSecurityPolicy(PSP) | PSP **1.25 移除** → **Pod Security Admission** + 策略引擎 |
| 運行時 | 幾乎不管 | **eBPF 運行時檢測**(Falco / Tetragon) |
| 信任模型 | 內網即信任 | **零信任**:工作負載身份 + mTLS + 最小權限 |

**一句話**:SolarWinds 等事件後,安全焦點從「我的代碼有沒有漏洞」擴展到「**從源碼到運行,整條鏈每一環可不可信、可不可證明**」——而 enforce 這一切的方式,是把規則寫成代碼掛在**准入控制(admission)**上。

---

## 1. 核心敘事

### 1.1 供應鏈安全:從「掃描」到「可證明」

威脅變了:不只是你的代碼有 CVE,而是**基礎鏡像被投毒、依賴包被劫持、構建流水線被攻破、鏡像在倉庫被掉包**。對策是給整條鏈加「可證明的信任」:

- **SBOM(軟件物料清單)**:鏡像裡到底有哪些組件/版本(格式 SPDX / CycloneDX)。出了 CVE(如 Log4Shell)能**秒查「我哪些鏡像中招」**。
- **簽名(sigstore / cosign)**:給鏡像簽名,准入時驗簽,確保**跑的就是我構建的那個**,沒被掉包。`cosign` 支持 **keyless**(用 CI 的 OIDC 身份簽,不用管私鑰)。
- **構建溯源(provenance / SLSA)**:用 **in-toto attestation** 證明「這鏡像由哪條流水線、從哪個 commit、怎麼構建出來的」。**SLSA** 是分級框架(L1→L3+),級別越高對「構建不可篡改、來源可證明」要求越嚴。
- **准入驗證**:在 admission 處強制「只跑**簽名 + 來源可信 + 掃描通過**的鏡像」。

```
源碼 ─build─▶ 鏡像 ─sign(cosign)+SBOM+provenance─▶ 倉庫
                                                      │ 部署
                                                      ▼
                                      准入控制:驗簽? 驗來源? 通過才准跑
```

### 1.2 Policy as Code:把規則掛在准入控制上

k8s 的 **admission control** 是「對象寫進 etcd 前的最後一道關卡」,分兩類:**mutating**(改對象,如自動注入 sidecar)和 **validating**(放行/拒絕)。Policy as Code 就是把組織規則寫成策略,掛在 validating 准入上自動 enforce:

常見策略:禁特權容器、必須設 resource limits、只准簽名鏡像、禁 `:latest` tag、必須帶 owner label、禁掛 hostPath、必須非 root 運行……

三種主流寫法:

- **內建 ValidatingAdmissionPolicy(VAP)**:用 **CEL** 表達式,**k8s 內建、不需要外部 webhook**(GA 1.30)——快、少一個故障點,適合「字段級」規則。
- **Kyverno**:策略就是 **k8s YAML**,k8s 原生心智、上手最快,能 validate/mutate/generate。
- **OPA / Gatekeeper**:用 **Rego** 語言,最強最通用(還能管 k8s 之外的策略),但 Rego 有學習曲線。

外加 **Pod Security Admission**(PSP 的繼任,內建):用 `baseline`/`restricted` 三檔基線一鍵約束 namespace。

### 1.3 運行時安全:跑起來之後

准入只管「能不能跑」,跑起來後的異常行為靠 **eBPF 運行時檢測**:**Falco / Tetragon** 在內核觀察 syscall,發現「容器裡突然 spawn shell、讀 /etc/shadow、連可疑 IP」就告警/阻斷。

### 1.4 零信任:把信任建在身份上

不再「在內網就信任」,而是:**工作負載身份**(SPIFFE,回扣 04 網格)+ **mTLS 雙向認證** + **最小權限 RBAC**(回扣 `cloud-native/07`)。每次調用都要證明「我是誰、我被允許」。

---

## 🏛 架構師視角

### 🔬 黑盒內幕

- **admission 鏈**:API 寫入流程是 認證 → 鑑權 → **mutating admission** → schema 校驗 → **validating admission** → 寫 etcd。策略引擎就掛在 admission webhook(Kyverno/Gatekeeper)或內建 CEL(VAP)。
- **cosign 簽名存哪**:簽名/attestation 作為 OCI artifact **存在鏡像倉庫旁邊**(同 repo,特定 tag 約定);驗簽就是去倉庫取簽名 + 驗 OIDC 身份。
- **VAP vs webhook**:VAP 的 CEL 在 API Server **進程內**求值(無網絡跳、無外部 SPOF);Gatekeeper/Kyverno 是**外部 webhook**(更靈活但多一個故障點 + 延遲)。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因 / 架構含義 |
|---|---|---|
| **admission webhook 掛** | **所有 API 寫入被阻塞 / 或安全被繞過** | fail-closed(掛了全擋,業務停)vs fail-open(掛了放行,安全失效)兩難;webhook 是關鍵路徑 |
| **webhook 本身被攻破** | 未授權 RCE | **IngressNightmare(CVE-2025-1974)就是 admission webhook 漏洞**——webhook 是高危攻擊面 |
| RBAC 過寬 | 一個被黑的 Pod 能讀全集群 Secret / 提權 | `cluster-admin` 亂給、通配符權限;最小權限沒做 |
| 明文 Secret / 鏡像帶密鑰 | 憑證洩漏 | Secret 進環境變量/鏡像層;要 External Secrets(回扣 06) |
| 供應鏈盲區 | 傳遞依賴中招卻不知道 | 沒 SBOM,出 CVE 時無法定位影響面 |

### 📈 規模化極限

- **webhook 在每次 API 寫的關鍵路徑上**:每個 Pod 創建都過策略校驗,**webhook 延遲直接加到部署/擴容延遲**;大規模下要控制策略數量與 webhook 性能,優先把「字段級」規則用內建 VAP(進程內、無網絡跳)。
- **策略庫治理**:幾百條策略要版本化(放 Git,回扣 06 GitOps)、分環境、可測試,否則自己把自己鎖死。
- **SBOM/簽名數據量**:每個鏡像每次構建都產 SBOM + 簽名,倉庫要能存與查。

### ⚖️ 選型論證

| 維度 | 選項 | 怎麼選 |
|---|---|---|
| 策略引擎 | **VAP(CEL,內建)** / **Kyverno(YAML)** / **OPA-Gatekeeper(Rego)** | 簡單字段規則用 VAP;要好上手用 Kyverno;跨域複雜策略用 OPA |
| Pod 基線 | **Pod Security Admission**(baseline/restricted) | 內建、零依賴,先開起來 |
| 簽名 | **cosign / sigstore**(keyless) | 事實標準;CI OIDC keyless 免管私鑰 |
| SBOM | Syft / Trivy(生成),Grype/Trivy(掃描) | 構建期生成 + 持續掃 |
| 運行時檢測 | **Falco**(成熟、規則多)/ **Tetragon**(eBPF、可阻斷) | 要 eBPF 深度 + 阻斷選 Tetragon;要成熟生態選 Falco |

> **架構師判斷**:安全要**分層縱深**,沒有銀彈——准入擋「不該跑的」、簽名/SBOM 保「跑的可信且可追溯」、RBAC/mTLS 限「能做什麼」、運行時檢測抓「跑歪了」。且**安全組件自己也是攻擊面**(webhook 漏洞、過寬 RBAC),要對它們同樣上心。

### 🧭 演進路徑

1. **掃描 → 簽名 + SBOM + 溯源**:CI 裡加 cosign 簽名、生成 SBOM 與 provenance。
2. **PSP → PSA + 策略引擎**:PSP 已移除,用 Pod Security Admission 打底 + Kyverno/VAP 補細則。
3. **准入驗簽**:策略強制「只跑簽名 + 來自我方倉庫的鏡像」。
4. **加運行時檢測**:上 Falco/Tetragon,把「跑起來之後」也納入。
5. **策略入 Git**:所有策略版本化、走 GitOps(06)。

### 🏭 生產事故 / 教訓

- **IngressNightmare**:入口的 **admission webhook** 被未授權 RCE。教訓:**安全/准入組件本身是最高危攻擊面**,要最小暴露、勤打補丁(也是 ingress-nginx 退役主因,回扣 03)。
- **過寬 RBAC 導致橫向移動**:一個被黑的低權限 Pod 因 SA 權限過大,讀到全集群 Secret。教訓:**最小權限 + 禁通配符 + 定期審計 RBAC**。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 鏡像信任 | **cosign 簽名 + SBOM + SLSA provenance**,准入驗簽 |
| 策略引擎 | VAP(內建字段規則)+ Kyverno/OPA(複雜策略) |
| Pod 基線 | Pod Security Admission(restricted) |
| Secret | External Secrets / SOPS,**絕不明文**(回扣 06) |
| 運行時 | Falco / Tetragon(eBPF) |
| 信任模型 | 零信任:SPIFFE 身份 + mTLS(04)+ 最小權限 RBAC |
| 策略管理 | 全部入 Git,GitOps enforce(06) |

---

## 🧵 示例服務在這一環

`order-api` 的安全鏈:

1. **構建期**:CI 用 `cosign` **keyless 簽名**鏡像(用 CI 的 OIDC 身份),生成 **SBOM** 與 **provenance**。
2. **准入**:策略「只准跑**我方倉庫 + 已簽名**的鏡像;必須**非 root + 設 limits + 禁 `:latest` + 禁特權**」——不滿足直接拒,壞鏡像進不了集群。
3. **權限**:order-api 的 ServiceAccount 只給「讀自己那個 Secret + 調 inventory」的最小 RBAC,絕不 `cluster-admin`。
4. **通信**:order→inventory 走網格 mTLS + 身份策略(04);DB 密碼由 External Secrets 從 Vault 拉。
5. **運行時**:Tetragon 監控,若 order-api 容器裡突然有人 spawn shell → 告警/阻斷。

對比 2019:當年頂多在 CI 跑個鏡像掃描,簽名/SBOM/准入驗證/運行時檢測基本都沒有。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| RBAC / ServiceAccount / Secret / ConfigMap 機制 | `cloud-native/07-config-and-security` |
| Secret 在 GitOps 下怎麼管 | 本線 `06-delivery-gitops` |
| mTLS / 工作負載身份 / 零信任通信 | 本線 `04-service-mesh` |
| 網路分區與認證授權(理論側) | `system-design/10-安全-網路分區與認證授權` |

---

## 一句收口 + 地圖更新

> **2026 的雲原生安全 = 供應鏈可證明(簽名 + SBOM + 溯源)+ 規則即代碼(准入自動 enforce)+ 零信任(身份 + mTLS + 最小權限)+ 運行時檢測**,分層縱深,沒有銀彈。且別忘了:**安全組件自己也是攻擊面**。

**🗺 地圖更新**:你補上「可信與管控」這一環,知道供應鏈四件套(SBOM/簽名/溯源/驗證)、准入策略三選一、以及 webhook 是雙刃劍。
**下一站**:`08 平台環` —— 到這裡外圈組件已經一大堆(網格/GitOps/策略/可觀測),**怎麼別讓每個開發都重學這一切**?答案是 **平台工程 / IDP**。
