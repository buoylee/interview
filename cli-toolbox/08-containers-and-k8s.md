# 08 · 容器與 k8s 排查

> 容器掛了 / 進不去 / 看日誌 / Pod 起不來。核心心法:**容器就是「被隔離 + 限額的進程」**,前幾章那套排查工具大半能直接套用。

---

## 收口地圖(一個原語通兩層)

**原語:容器 = 被 namespace 隔離 + cgroup 限額的「普通進程」。** 同一個內核,只是視野被框住了。推論:

- 宿主機 `ps` **看得到**容器內的進程(只是 PID 不同)。
- 容器裡沒裝 `ss`/`strace`?**從宿主機鑽進它的命名空間照樣查**(`nsenter`,見第 4 節)。
- 「容器 OOM / CPU 被限」其實是 **cgroup 在限額**,不是玄學。

兩層工具:**`docker`(單機)** / **`kubectl`(集群)**——子命令幾乎一一對應(`logs`/`exec`/`inspect|describe`)。

---

## 1. `docker` 排查

| 命令 | 作用 |
|---|---|
| 🔧 `docker ps` / `docker ps -a` | 跑著的 / **含已退出的**(查崩潰容器用 `-a`) |
| `docker logs -f --tail 100 容器` | 看日誌(跟隨 + 只看尾部) |
| `docker exec -it 容器 sh` | **進容器**裡敲命令 |
| `docker inspect 容器` | 完整配置/狀態(配 `jq` 取欄位) |
| `docker stats` | 即時 CPU/記憶體/網路 |
| `docker top 容器` | 容器內進程列表 |

> 容器一直退出?`docker ps -a` 看 **Exit Code** → `docker logs` 看原因 → `docker inspect 容器 \| jq '.[].State'` 看是不是 **OOMKilled**(超了記憶體 limit)。

---

## 2. `kubectl` 排查(高頻)

| 命令 | 作用 | 底層一兩句 |
|---|---|---|
| 🔧 `kubectl get pods -o wide -A` | 列所有 Pod(含節點/IP) | `-A`=所有 namespace |
| `kubectl describe pod x` | **看 Events** | **排查第一站**:調度/拉鏡像/探針失敗都在 Events |
| `kubectl logs -f x` | 跟隨日誌 | — |
| `kubectl logs --previous x` | **上一個**(已崩潰)容器的日誌 | CrashLoop 必用——崩了的才是真相 |
| `kubectl exec -it x -- sh` | 進 Pod | — |
| `kubectl get events --sort-by=.lastTimestamp` | 按時間看集群事件 | 揪「剛剛發生了什麼」 |
| `kubectl top pod / node` | 即時資源 | 需裝 metrics-server |
| `kubectl port-forward x 8080:80` | 本地端口轉發進 Pod | 不暴露 Service 也能本地連進去測 |

---

## 3. Pod 常見故障狀態(面試 + 實戰)

| 狀態 | 含義 | 怎麼查 |
|---|---|---|
| `CrashLoopBackOff` | 起來就崩、反覆重啟 | `logs --previous` + `describe`(看退出碼/探針) |
| `ImagePullBackOff` / `ErrImagePull` | 拉鏡像失敗 | `describe` 看 registry / tag 拼錯 / 拉取憑證 |
| `Pending` | **調度不上去** | `describe` 看資源不足 / 節點選擇器 / PVC 沒綁 |
| `OOMKilled` | 超過記憶體 limit 被殺 | `describe` 看 Last State;調高 limit 或修洩漏 |
| `Evicted` | 節點資源壓力,Pod 被驅逐 | 看節點磁碟/記憶體;清理或擴容 |

> 心法:**`describe` 的 Events 段 + `logs --previous`,解決一大半 Pod 問題。** 別一上來就 exec,先看這兩個。

---

## 4. 容器沒工具時:從宿主機鑽進去(架構師深度)

容器鏡像精簡,常常**沒有 `ss`/`tcpdump`/`strace`**。但容器只是宿主機上的進程——從宿主機進它的命名空間就能用宿主機的工具查:

```bash
# 1. 拿到容器在「宿主機」上的真實 PID
PID=$(docker inspect --format '{{.State.Pid}}' 容器名)

# 2. 鑽進它的「網路命名空間」,用宿主機的 ss 看容器的端口
sudo nsenter -t $PID -n ss -tlnp

# 3. 同理可進其他命名空間:-n 網路 -m 掛載 -p 進程 -u 主機名
sudo nsenter -t $PID -n tcpdump -i any -nn port 8080
```

> 這招是**容器網路排查的殺手鐧**:容器裡裝不裝工具無所謂,宿主機有就行。背後就是收口地圖那句——**容器是被 namespace 框住的進程,你從外面進那個 namespace 即可**。資源限額同理看 `/sys/fs/cgroup/...`。

---

## 🔧 主力命令深講 + 速驗

> ⚠️ **驗證環境不在沙盒內**:`docker` 那組在**你宿主機**跑(有 Docker/OrbStack 即可);`kubectl` 那組需一個**叢集**——本機快速起一個:`kind create cluster` 或 `minikube start`。

### docker

| 寫法 | 作用 |
|---|---|
| `docker ps` / `-a` | 跑著的 / 含已退出 |
| `docker logs -f --tail 100 容器` | 日誌(跟隨 + 尾部) |
| `docker exec -it 容器 sh` | 進容器 |
| `docker inspect -f '{{.State.Status}}' 容器` | 取單一欄位(配 `-f` 模板) |
| `docker stats --no-stream` | 資源快照(不刷屏) |
| `docker top 容器` | 容器內進程 |

**⚡ 驗證**(宿主機):
```bash
docker run -d --name demo nginx                    # 起一個 nginx
docker ps                                          # 預期:demo 在列,STATUS Up
docker logs demo 2>&1 | head -3                    # 預期:nginx 啟動日誌
docker exec demo nginx -v                          # 預期:nginx version: ...
docker inspect -f '{{.State.Status}}' demo         # 預期:running
docker stats --no-stream demo                      # 預期:CPU/MEM 一行
docker rm -f demo                                  # 清理
```

### kubectl

| 寫法 | 作用 |
|---|---|
| `kubectl get pods -o wide -A` | 所有 Pod(含節點/IP) |
| `kubectl describe pod x` | 看 Events(排查第一站) |
| `kubectl logs x` / `--previous` | 日誌 / 上次崩的 |
| `kubectl exec -it x -- sh` | 進 Pod |
| `kubectl get x -o yaml` / `-o json` | 完整定義(配 `jq`/`yq`) |
| `kubectl port-forward x 8080:80` | 本地轉發進 Pod |

**⚡ 驗證**(需叢集):
```bash
kubectl get nodes                                  # 預期:節點 Ready
kubectl run demo --image=nginx                     # 起一個 Pod
kubectl get pod demo -o wide                       # 預期:demo Running(稍等幾秒)
kubectl describe pod demo | sed -n '/Events/,$p'   # 預期:Events 段(Scheduled/Pulled/Started)
kubectl logs demo 2>&1 | head -3                   # 預期:nginx 日誌
kubectl delete pod demo                            # 清理
```

### nsenter — 從宿主機鑽進容器(架構師招)

**⚡ 驗證**(宿主機,需 root + 宿主機有 `ss`):
```bash
docker run -d --name webdemo nginx
PID=$(docker inspect -f '{{.State.Pid}}' webdemo)
sudo nsenter -t $PID -n ss -tlnp        # 預期:看到容器內 nginx 監聽 :80(即使容器裡沒裝 ss)
docker rm -f webdemo
```

### ⚡ 配角速驗(`docker top` / `docker diff` / `kubectl top` / `events`)

```bash
docker run -d --name d2 nginx
docker top d2                            # 預期:容器內進程(nginx master/worker)
docker diff d2 | head                    # 預期:容器相對鏡像改了哪些檔(C/A 開頭)
docker rm -f d2
kubectl get events --sort-by=.lastTimestamp | tail   # 預期:近期集群事件(需叢集)
kubectl top pod 2>/dev/null              # 預期:Pod CPU/記憶體(需 metrics-server)
```

---

## 5. 排查決策樹

```
Pod / 容器不正常
│
├─ kubectl get pods           什麼狀態?(對照第 3 節)
├─ kubectl describe pod x     Events 段:調度?拉鏡像?探針?OOM?
├─ kubectl logs --previous x  崩掉那次的日誌(真相在這)
├─ kubectl exec -it x -- sh   進去看(配置/環境變數/連通性)
│     └─ 容器沒工具？ → nsenter 從宿主機查(第 4 節)
└─ kubectl top pod / node     是不是資源打滿/被限
```

---

## 深挖

- 容器的底層(namespace / cgroup / overlayfs)從 Linux 視角拆解 → **`linux-handson/09-containers-from-linux`**
- k8s 全景、服務治理、東西向流量 → **`cloud-native`**、**`service-governance-on-k8s`**
- 容器日誌怎麼被收(sidecar / DaemonSet) → **`log-collection`**
