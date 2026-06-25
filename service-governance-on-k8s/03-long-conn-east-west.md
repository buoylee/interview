# 03 · 長連接 LB ①:服務內部 / 東西向 —— 為什麼 gRPC 會釘在一個 pod 上

> 🔬 LB 下沉到 kube-proxy(`02` 的「LB 行」)之後,短連接 HTTP/1.1 沒事,但 **gRPC、資料庫連接池**這種**長連接**會出事:請求**全打到同一個 pod**,你把副本從 3 擴到 10,流量一點都不分散。
>
> 這章的前提:**東西向 = 自家服務調自家服務,你控制兩端**(client 和 server 都是你的)。「你能改 client」是這章所有修法成立的根本 —— 下一章(南北向,client 是瀏覽器)就沒這個前提了。

---

## Part A · 機制:為什麼會釘住 🔬

兩件事疊起來,就釘住了:

**(1) gRPC 是 HTTP/2,一條 TCP 連接多路復用成千上萬個請求。**
HTTP/1.1 通常一個請求一個連接(或短 keep-alive),請求結束連接就還;gRPC/HTTP/2 不一樣 —— client 和 server 之間**開一條長期 TCP 連接**,所有 RPC 都當作 stream **複用這一條連接**。

**(2) kube-proxy 是 L4,在「握手那一刻」選一次 pod,之後整條連接釘死。**

```
  gRPC client ──一條 H2 長連接──► [kube-proxy 在握手時 DNAT 選 pod-1] ──► pod-1  ◄─ 所有 RPC 全到這
                                                                          pod-2  ◄─ 餓死
                                                                          pod-3  ◄─ 餓死
```

kube-proxy 做的是**連接級**負載均衡:TCP 三次握手時,它把目標 VIP(ClusterIP)DNAT 成某一個 pod IP,**這條連接後續所有封包都去同一個 pod**。對 HTTP/1.1 短連接,連接多、各自握手、自然分散;對一條複用的 H2 長連接,**選一次就再也不換**,於是上面跑的所有 RPC 全壓在一個 pod 上。

**兩個直接後果:**
- **負載不均**:3 個 client × 各一條連接 → 最多壓到 3 個 pod;但常見是流量集中,大部分打在少數 pod。
- **scale up 不起作用**:新擴出來的 pod **沒有任何存量連接**,而老連接不會主動斷 → 新 pod **收不到流量**,擴了等於沒擴。

### 🔬 為什麼換 IPVS / Cilium(eBPF)也不解決?

因為它們**全是 L4**。kube-proxy 的 iptables 模式、IPVS 模式、乃至 Cilium 的 eBPF kube-proxy-free —— 它們看到的都是「**連接 / 封包**」這個層次,**看不到 HTTP/2 的 stream**。IPVS 的那些調度算法(rr / lc / sh)也是**對連接**調度,不是對請求。所以:

> **這是 L4 的結構性限制,不是實現好壞的問題。** 想按「請求」分,你只有兩條路:把 LB 抬到**看得懂 H2 的 L7**(mesh / L7 代理),或者把 LB **挪到 client 自己**(client 懂自己在發什麼 RPC)。

---

## Part B · 三種修法(按真實使用排序)🔬

### ① headless Service + 客戶端 `round_robin` + `MaxConnectionAge`(無 mesh 首選)

把 LB 挪回 client 自己做。三個零件缺一不可:

- **headless Service(`clusterIP: None`)**:普通 Service 的 DNS 回**一個 VIP**(然後 kube-proxy 釘你);headless 的 DNS **直接回所有 ready pod 的 IP 列表**。於是 client 拿到的是 `[pod1, pod2, pod3]`,不是一個 VIP。
- **客戶端 `round_robin` 策略**:client 對列表裡**每個 pod IP 各開一條連接**,逐請求輪詢。
  > ⚠️ **這是 load-bearing 的一步,最容易漏**:gRPC 客戶端**默認是 `pick_first`**——它只連列表第一個、把所有請求都發給它,**根本不分散**。你必須顯式設成 `round_robin`(Go:`grpc.WithDefaultServiceConfig(`​`{"loadBalancingConfig":[{"round_robin":{}}]}`​`)`)。光換 headless 不改策略 = 白搞。
- **`MaxConnectionAge`**:headless 的 DNS 重解析是 **lazy 的** —— client 連上後不會主動再去解析 DNS,所以**新擴的 pod 還是進不來**。解法:server 端設**連接最大壽命**(Go:`keepalive.ServerParameters{MaxConnectionAge: ...}`),server 定期主動優雅關閉連接 → client 重連 → 重新解析 DNS → **撿到新 pod**。Jamf 那篇「三行配置解決 gRPC 擴容問題」說的就是這招。

```
headless DNS 回 [pod1,pod2,pod3] ─► client 各開一條連接,round_robin 輪詢
                                    + server MaxConnectionAge 定期逼重連 → 撿新 pod
```

### ② Service Mesh L7(Linkerd / Istio,有 mesh / polyglot 首選)

sidecar(Envoy / linkerd2-proxy)**解析 HTTP/2 幀**,在**請求級**把每個 RPC 分散到不同後端。好處:**零 client 代碼改動、語言無關**,還順手給你 mTLS / 重試 / 可觀測。Linkerd 最常被點名「最簡單的修法」—— 注入 sidecar 就好,連 headless 都不用配。代價是 mesh 那一整套運維 / 資源 / 延遲(見 `cloud-native-landscape/04`)。

### ③ proxyless gRPC / xDS(前瞻,別當主流)

gRPC 進程**直接跟 istiod 講 xDS 協議**,把 Envoy 的 LB 智能塞進 gRPC client,既無 sidecar 一跳、又有 L7 LB。但 **Istio 仍標 experimental**:只支持 `round_robin`、TLS 受限、沒有 fault injection / retry / mirroring。**知道它存在、別在生產當主流答案。**

### 三法對照

| | 改 client 代碼? | polyglot? | 額外能力 | 成熟度 |
|---|---|---|---|---|
| ① headless + round_robin + MaxConnAge | **要**(設策略)| 每語言各配一次 | 無 | 成熟、最常見的無 mesh 解 |
| ② mesh L7 | 不用 | ✅ 透明 | mTLS / 重試 / 觀測 | 成熟(sidecar);ambient GA |
| ③ proxyless xDS | 要(接 xDS)| gRPC 限定 | 少 | ⚠️ experimental |

> **DB 連接池同理**:連接池長期持有到資料庫的連接,一樣會被釘在一個後端。讀寫分離 / 分片要均衡,靠的是 **DB proxy**(ProxySQL / 中間件)在 L7 解析 SQL,而不是指望 kube-proxy。

---

## Part C · 怎麼選 + 去 lab 親眼看

- **沒上 mesh** → **①**(headless + `round_robin` + `MaxConnectionAge`),記住 `round_robin` 那一步。
- **已有 mesh / 多語言** → **②**(Linkerd / Istio),省 client 改動。
- **③** 觀望,別寫進生產方案。

口說無憑,這個現象**讀十遍不如看一次**。`lab/` 在 kind 上把它跑出來:部署一個回傳 pod hostname 的服務、用一條長連接打它,看**請求全打一個 pod**;再換 headless + 逐 IP 輪詢,看**請求分散到三個**——數字你自己跑出來。

---

## 交叉引用

- **kube-proxy / Service / ClusterIP 怎麼運作 → `cloud-native/05-networking`**
- **mesh sidecar / Envoy / ambient 內幕 → `cloud-native-landscape/04-service-mesh`**
- **L4 vs L7、LB 算法 → `system-design/05` Part C、`gateway/03`**
- **南北向(client 是瀏覽器)的長連接 → `04`**
- **動手看現象 → `lab/`**

---

## 本章小結

- **釘住 = HTTP/2 一條長連接複用 + kube-proxy L4 握手時選一次 pod 釘死**。後果:負載不均、**scale up 不起作用**(新 pod 無存量連接)。
- **L4 解不了**:iptables / IPVS / Cilium 都看不到 H2 stream,換哪個 L4 都沒用 —— 是結構性限制。
- **三修法**:① headless + 客戶端 `round_robin`(默認 `pick_first` 不分散,必改!)+ `MaxConnectionAge`(逼重連撿新 pod);② mesh L7(透明、polyglot、帶 mTLS);③ proxyless xDS(experimental,觀望)。
- **DB 連接池同理**,靠 DB proxy 不靠 kube-proxy。
- **前提是你控兩端能改 client** —— 下一章 client 變成瀏覽器,這些招大半失效。

---

## 章末問答(複習自檢,答案要點都在前面正文)

1. 為什麼短連接 HTTP/1.1 在 kube-proxy 下不會出問題,gRPC 卻會?(兩個機制疊加)
2. 「scale up 不起作用」具體是怎麼發生的?
3. 為什麼換成 IPVS 或 Cilium eBPF 也解決不了 gRPC 不均衡?
4. headless Service 和普通 ClusterIP Service 在 DNS 解析上差在哪?
5. 為什麼說 `round_robin` 是「load-bearing 的一步」?不改它會怎樣?
6. headless 配好了,新擴的 pod 還是收不到流量,為什麼?`MaxConnectionAge` 怎麼解?
7. mesh L7 修法相比客戶端修法,多了什麼好處、付了什麼代價?
8. proxyless gRPC / xDS 現在能當生產主流答案嗎?為什麼?
9. 資料庫連接池會不會有同樣問題?靠什麼均衡?
10. **綜合題**:面試官說「我們 gRPC 服務擴容了但新實例沒流量」——從機制(L4 釘連接)講到修法(headless+round_robin+MaxConnAge 或 mesh),並說清為什麼這是 L4 的結構性限制。
