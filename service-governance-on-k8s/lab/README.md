# lab · 親眼看 k8s 長連接 pinning(東西向)

> 配套 `03-long-conn-east-west.md`。**讀十遍不如看一次**:這個 lab 在 kind 上把「一條 HTTP/2 長連接被 kube-proxy 釘在一個 pod 上 → 換 headless + round-robin 就分散」跑出來,**數字你自己填**。

---

## 先說清楚:為什麼是 h2c 不是 gRPC

要看的現象是**連接級**的:**一條 TCP / HTTP-2 連接被 kube-proxy(L4)釘在一個 pod**,連接上多路復用的所有請求都跟著去同一個 pod。**gRPC 就是跑在 HTTP/2 上**,所以用 h2c(HTTP/2 cleartext)能**一模一樣**地重現,還省掉 protobuf 那一堆 codegen。每一步都對得上 gRPC 的旋鈕:

| 這個 lab | 對應 gRPC |
|---|---|
| `pinned`:一條 H2 連接打 **ClusterIP** | 默認 **`pick_first`** 打 ClusterIP Service —— 全釘一個 pod(壞) |
| `spread`:**headless** 解析出所有 pod IP,逐 IP 開連接輪詢 | **`round_robin`** over `dns:///headless`(修好) |
| `scale` 後 `pinned` 仍不動 | DNS 重解析是 lazy 的,要靠 **`MaxConnectionAge`** 逼重連才撿到新 pod |

---

## 前置

- **Docker**(要在跑)、**kubectl**、**kind**。
  - `kind` 多半沒裝:`go install sigs.k8s.io/kind@latest` 或 `brew install kind`。
- (可選)**Go 1.25**:想本機先跑一遍不進集群,見最後「不進 k8s 的快速版」。

---

## 走一遍

```bash
cd service-governance-on-k8s/lab

make all        # = up + build + load + deploy:建 kind、打鏡像、塞進去、起 3 副本
make status     # 看 3 個 echo pod 各自的名字(等下 tally 裡會出現這些名字)
```

### demo 1 —— pinned(壞掉的樣子)

```bash
make pinned     # 一條 H2 連接打 echo-clusterip,發 30 個請求
```

你會看到 **30 個請求全打到同一個 pod**:

```
=== PINNED — one H2 conn to http://echo-clusterip:8080/ ===
30 requests →
  echo-xxxxxxxxx-aaaaa                          30
(1 distinct pod[s] hit)
```

> 連跑幾次 `make pinned`:每次可能釘到**不同**的 pod(握手時隨機選一個),但**單次內 30 個一定全在一個** —— 這就是 kube-proxy L4 連接級的鐵證。

### demo 2 —— spread(修好的樣子)

```bash
make spread     # headless 解析出 3 個 pod IP,逐 IP 開連接,round-robin 發 30 個
```

```
resolved 3 pod IP(s) from echo-headless: [10.x.x.a 10.x.x.b 10.x.x.c]
=== SPREAD — one conn per pod IP, round-robin ===
30 requests →
  echo-xxxxxxxxx-aaaaa                          10
  echo-xxxxxxxxx-bbbbb                          10
  echo-xxxxxxxxx-ccccc                          10
(3 distinct pod[s] hit)
```

### demo 3 —— 擴容後不重新均衡(MaxConnectionAge 的必要性)

```bash
make pinned     # 記下打到哪個 pod
make scale      # 擴到 6 副本
make pinned     # 還是打到「老」pod —— 新擴的 4 個一個請求都收不到
```

> 這就是 `03` 講的「scale up 不起作用」:老連接不會自己斷,DNS 不會自己重解析。生產上靠 server 端 **`MaxConnectionAge`** 定期逼客戶端重連,才會把新 pod 撈進來。

---

## 把你自己的數字填進來

| 觀察 | 我跑出來的 |
|---|---|
| `pinned` 30 個請求打到幾個 pod? | ___ |
| `spread` 30 個請求打到幾個 pod?分佈? | ___ |
| `scale` 到 6 後再 `pinned`,新 pod 收到請求了嗎? | ___ |
| 連跑 5 次 `pinned`,每次釘的 pod 一樣嗎? | ___ |

---

## 收尾

```bash
make down        # 刪掉 kind 集群
```

## (可選)不進 k8s 的快速版

只想看「一條連接 vs 多條連接」的客戶端行為,本機就能跑(無 kube-proxy,所以看的是客戶端側,不是 L4 釘連接):

```bash
go run . server &                       # 起服務在 :8080
go run . pinned http://127.0.0.1:8080/ 5
```

---

## 這個 lab 證明了什麼(回扣 `03`)

1. **長連接的負載不均不是配置錯,是 kube-proxy L4 的結構性行為** —— 它在連接上釘,不在請求上分。
2. **修法要嘛把 LB 挪到客戶端**(headless + 逐 IP + round-robin,= 本 lab 的 spread,= gRPC `round_robin`),**要嘛挪到 L7**(mesh,本 lab 沒演,見 `cloud-native-landscape/04`)。
3. **光換 headless 不夠**:客戶端得真的對多個 IP 各開連接、輪詢(gRPC 默認 `pick_first` 不會,要顯式 `round_robin`);擴容還要 `MaxConnectionAge` 配合。
