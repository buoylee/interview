# 02 · 運行時環:dockershim 之後(containerd / CRI / OCI / 沙箱)

> **一句話定位**:第 01 章 spec 收斂到節點後,kubelet 到底**怎麼把容器真的跑起來**?這一環講「kubelet → 運行時」這條鏈在 2022 之後徹底換了長相——Docker 不再是節點運行時。

> **本章深度層**:內環(架構師視角 + 指進)。容器底層(namespace/cgroup/「容器只是進程」)在 `linux-handson/09`、運行時內幕全鏈在 `cloud-native/03a`;本章寫**為什麼這樣變、怎麼崩、怎麼選**,機制細部指進。

---

## 🕰 變遷盒

| | 舊世界(2019-2020) | 新世界(2026) |
|---|---|---|
| 節點上跑容器的是 | **Docker**(kubelet 經 dockershim 調 Docker) | **containerd / CRI-O**(kubelet 經 **CRI** 直接調) |
| dockershim | kubelet 內建的 Docker 適配層 | **k8s 1.24(2022)移除** |
| 「Docker 沒了我鏡像怎麼辦」 | —— | **照用**:鏡像是 **OCI** 標準,containerd 一樣拉一樣跑 |
| 強隔離需求 | 只有 runc(共享內核) | **沙箱運行時**:gVisor(用戶態內核)、Kata(輕量 VM),用 `RuntimeClass` 選 |

**一句話**:2022 年「Docker 被 k8s 拋棄」的大新聞,真相是——**只拋棄了 dockershim 這個適配層**。Docker 拿來**構建鏡像**完全沒問題;只是節點上**跑**容器的活,交給了更輕、原生實現 CRI 的 containerd。

---

## 1. 核心敘事:從「kubelet 調 Docker」到「kubelet 調 CRI」

### 為什麼當初要有 dockershim,後來又要砍掉它

k8s 早期只支持 Docker,kubelet 裡硬編碼了一段「怎麼跟 Docker 說話」的代碼。後來要支持別的運行時,k8s 定義了 **CRI(Container Runtime Interface)**——一個 gRPC 接口,只要運行時實現它,kubelet 就能用。

但 **Docker 不原生實現 CRI**,所以 kubelet 裡留了一段「把 CRI 翻譯成 Docker API」的墊片,叫 **dockershim**。這段墊片:在 kubelet 代碼裡、只為 Docker 一家服務、Docker 自己每次升級它就可能壞。維護它純屬負擔——而且諷刺的是,**Docker 內部本來就是用 containerd 跑容器的**,等於 `kubelet → dockershim → dockerd → containerd → runc`,中間兩跳全是多餘的。

於是 1.24 砍掉 dockershim,鏈條變成乾淨的:

```
舊:  kubelet ──dockershim──▶ dockerd ──▶ containerd ──▶ runc ──▶ 容器
新:  kubelet ─────CRI──────▶ containerd ──────────────▶ runc ──▶ 容器
                  (gRPC)
```

### 現在這條鏈的每一環

```
kubelet
  │  CRI（gRPC：RunPodSandbox / CreateContainer / ...）
  ▼
containerd（CRI plugin）              ← 高層運行時:管鏡像、快照、生命週期
  │  創建 shim
  ▼
containerd-shim-runc-v2              ← 每個 Pod 一個 shim,常駐;containerd 重啟容器不死
  │  調
  ▼
runc                                ← 低層 OCI 運行時:真正 clone() + 配 namespace/cgroup,然後退出
  │
  ▼
你的容器進程（被 namespace 隔離、被 cgroup 限制的普通進程）
```

- **CRI**:kubelet 和運行時之間的 gRPC 合約。換運行時不用改 kubelet。
- **containerd**:高層運行時(CNCF 畢業)。管鏡像拉取、解壓成快照(overlayfs)、容器生命週期。
- **shim**:每個 Pod 一個常駐進程,持有容器的 stdio、上報退出碼;**containerd/節點上的 containerd 重啟,容器照跑不誤**(解耦)。
- **runc**:低層 OCI 運行時。真正執行 `clone()` 開 namespace、寫 cgroup、`pivot_root`,然後**自己退出**(容器由 shim 托管)。
- **OCI 三規範**:**image-spec**(鏡像長啥樣)、**runtime-spec**(怎麼跑)、**distribution-spec**(怎麼推拉)。Docker 構建的鏡像就是 OCI image,所以「換掉 Docker」不影響鏡像。

### pause 容器:Pod 的「沙箱」

一個 Pod 裡多個容器**共享網絡/IPC namespace**,誰來持有這些 namespace?答案是 **pause 容器**(`RunPodSandbox` 建的沙箱):它幾乎不做事,只負責**持有 Pod 的 namespace**,其他容器加入它的 namespace。所以 Pod 裡的容器能 `localhost` 互通、共享一個 IP。

---

## 🏛 架構師視角

### 🔬 黑盒內幕(概要,細部指進 03a)

- **「容器只是進程」**:runc 沒有「容器」這種實體——它只是用 `clone(CLONE_NEWNS|NEWNET|NEWPID|...)` 開了一組 namespace、把進程塞進 cgroup、換了根文件系統的**普通 Linux 進程**。底層機制見 `linux-handson/09`。
- **鏡像 = 分層 + overlayfs**:鏡像是只讀層疊加,容器啟動時加一個可寫層,用 overlayfs 聯合掛載。所以「同節點多容器共享底層」省磁盤、拉取可增量。
- **shim 的存在意義**:把容器生命週期和 containerd 解耦——這樣升級/重啟 containerd 不會殺掉所有容器。

### 💥 失敗模式 / 故障域

| 故障 | 現象 | 根因(架構含義) |
|---|---|---|
| 鏡像拉不下來 | `ImagePullBackOff` | registry 不可達 / 認證失敗 / tag 不存在 / 限流 |
| 運行時掛了 | 節點 `NotReady`,Pod 無法啟動 | containerd down;但**已跑的容器靠 shim 還在**(解耦救命) |
| 磁盤壓力 | Pod 被驅逐、新容器起不來 | 鏡像層 + 可寫層撐爆節點磁盤;kubelet 觸發 image GC / eviction |
| shim 洩漏 | 殭屍 shim 進程堆積 | 異常退出路徑沒清理;節點長期不重啟時暴露 |
| PID 1 信號問題 | 容器收不到 SIGTERM、優雅退出失敗 | 應用沒處理信號 / 沒用 init;graceful shutdown 失效(指進 `linux-handson/09` PID1) |

### 📈 規模化極限

- **鏡像大小 → 冷啟動延遲**:鏡像越大,拉取 + 解壓越久,Pod 冷啟動越慢。突發擴容(HPA、節點擴容)時,**大鏡像會拖垮彈性**——這是 06 章「漸進發布」和彈性的隱性瓶頸。
- **registry 限流**:大規模滾動更新時,幾百個節點同時拉同一鏡像 → 打爆 registry / 觸發 Docker Hub 限流。對策:鏡像倉庫就近緩存(pull-through cache)、鏡像瘦身(指進 `cloud-native/01`)。
- **層緩存**:同基礎層的鏡像在節點上共享,合理分層能大幅減少拉取量。

### ⚖️ 選型論證

| 運行時 | 定位 | 何時選 |
|---|---|---|
| **containerd** | 默認、輕、CNCF 畢業 | **絕大多數場景**(EKS/GKE 默認) |
| **CRI-O** | 只為 k8s 而生、更精簡 | OpenShift 默認;想要「只服務 k8s」的最小面 |
| **Docker(作為節點運行時)** | 已退場 | ❌ 不再是選項;但構建鏡像照用 |
| **gVisor(runsc)** | 用戶態內核攔截 syscall | 多租戶 / 跑不可信代碼;**有性能代價**(syscall 密集型掉速) |
| **Kata Containers** | 每容器一個輕量 VM | 要 **VM 級隔離** 又想要容器體驗;開銷比 runc 大 |

**核心取捨**:runc 共享宿主內核(快,但一個內核漏洞可能橫向逃逸);gVisor/Kata 用「多一層」換**強隔離**,代價是性能與複雜度。用 `RuntimeClass` 讓不同 Pod 選不同運行時(可信業務用 runc、跑用戶上傳代碼用 gVisor)。

### 🧭 演進路徑

1. **dockershim → CRI**:1.24 已強制;託管集群(EKS/GKE)早就默認 containerd,你多半已經在用,只是沒意識到。
2. **檢查依賴 Docker socket 的東西**:CI in-cluster build(掛 `/var/run/docker.sock`)、用 `docker` CLI 的 DaemonSet——這些在 containerd 節點上會壞,要改用 `nerdctl`/`crictl`,或用 **Kaniko/Buildah/BuildKit** 做無 daemon 構建。
3. **按隔離需求引入 RuntimeClass**:多租戶場景逐步把不可信 workload 切到 gVisor/Kata。

### 🏭 生產事故 / 教訓

- **2022「Docker is deprecated」恐慌**:大量團隊誤以為要重做一切。教訓:**分清「構建鏡像的 Docker」和「節點運行時的 Docker」**——前者沒事,後者被 containerd 取代。
- **掛 `docker.sock` 的 CI 在升級後全壞**:節點換 containerd 後沒有 Docker daemon。教訓:in-cluster 構建早該脫離 Docker daemon(用 BuildKit/Kaniko)。

---

## 2. 現在主流怎麼選

| 決策 | 2026 主流答案 |
|---|---|
| 節點運行時 | **containerd**(默認);OpenShift 用 CRI-O |
| 構建鏡像 | BuildKit / Kaniko / Buildah(無 daemon);本機開發仍可 Docker |
| 容器調試 CLI | `crictl`(CRI 層)、`nerdctl`(containerd) |
| 強隔離 | `RuntimeClass` + gVisor / Kata,按 workload 信任度切 |
| 鏡像瘦身 | 多階段構建、distroless(指進 `cloud-native/01`) |

---

## 🧵 示例服務在這一環

`order-api` 的 Pod 被調度到節點後:kubelet 先 `RunPodSandbox` 建 **pause** 容器持有網絡 namespace(於是 order-api 拿到 Pod IP)→ containerd 拉 `order-api:1.4.2` 鏡像、overlayfs 掛載 → `CreateContainer`/`StartContainer` → shim 拉起 runc → runc 開 namespace/cgroup 跑起 order-api 進程,加入 pause 的網絡 namespace。

**冷啟動慢的鍋**:如果 `order-api` 鏡像 1.2GB(把整個構建鏈和測試依賴打進去了),HPA 擴容時每個新節點都要拉 1.2GB → 擴容滯後幾十秒。瘦到 80MB(多階段 + distroless)後,擴容秒級——**鏡像大小是彈性的隱形天花板**。

---

## 🔬 深挖出口

| 想深挖 | 去哪 |
|---|---|
| 運行時內幕全鏈(kubelet→CRI→containerd→runc→OCI、pause、dockershim、沙箱) | `cloud-native/03a-container-runtime-internals` |
| 容器底層(namespace/cgroup/overlayfs/「容器只是進程」/PID1 信號) | `linux-handson/09-containers-from-linux` |
| 鏡像分層、Dockerfile、多階段、瘦身與安全 | `cloud-native/01-images-and-dockerfile` |
| 容器/k8s 性能 | `performance-tuning-roadmap/12-container` |

---

## 一句收口 + 地圖更新

> **節點上沒有「Docker」也照樣跑容器**:kubelet 經 CRI 調 containerd,containerd 經 shim 調 runc,runc 開 namespace/cgroup 跑起一個普通進程;鏡像是 OCI 標準所以與運行時解耦。強隔離靠 RuntimeClass 換 gVisor/Kata。

**🗺 地圖更新**:你現在知道「Pod 落地」這條鏈在 2022 後的真實長相,以及鏡像大小怎麼偷偷限制彈性。
**下一站**:`03 網絡環` —— 容器跑起來了,**Pod 之間、外部進來怎麼連**?這一環是變化最大的:iptables/kube-proxy → eBPF/Cilium,Ingress → Gateway API(ingress-nginx 已退役)。
