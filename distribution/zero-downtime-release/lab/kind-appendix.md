# 可选附录 — 用 kind 在本机真跑 k8s 的 preStop / endpoint 竞态

> docker-compose 那个 lab 演不了 k8s 特有的「endpoint 传播 vs SIGTERM」竞态(见主 lab README 的边界)。想**亲眼**看到"没 preStop 掉请求 → 加 preStop 不掉",用 [kind](https://kind.sigs.k8s.io/)(k8s-in-docker)在本机起个真集群。**这部分是选修**,不装 kind 也不影响理解——机制在 [`03 优雅下线`](../03-graceful-shutdown.md) 已讲透。

## 前置

```bash
# macOS:有 docker(OrbStack/Docker Desktop)后
brew install kind kubectl
kind create cluster --name zdr
```

## 1. 部署:先做一个「没有 preStop」的版本(会掉请求)

复用主 lab 的镜像,先 load 进 kind:

```bash
cd distribution/zero-downtime-release/lab
docker build -t zdr-app:1 ./app
kind load docker-image zdr-app:1 --name zdr
```

`k8s/deploy-naive.yaml`(无 preStop):

```yaml
apiVersion: apps/v1
kind: Deployment
metadata: { name: zdr }
spec:
  replicas: 4
  selector: { matchLabels: { app: zdr } }
  template:
    metadata: { labels: { app: zdr } }
    spec:
      terminationGracePeriodSeconds: 30
      containers:
      - name: app
        image: zdr-app:1
        imagePullPolicy: IfNotPresent
        ports: [ { containerPort: 8000 } ]
        env:
        - { name: INSTANCE, value: k8s }
        - { name: WORK_SECONDS, value: "1" }
        readinessProbe:
          httpGet: { path: /health/ready, port: 8000 }
          periodSeconds: 2
        # 注意:这里【故意没有】lifecycle.preStop
---
apiVersion: v1
kind: Service
metadata: { name: zdr }
spec:
  selector: { app: zdr }
  ports: [ { port: 80, targetPort: 8000 } ]
```

```bash
kubectl apply -f k8s/deploy-naive.yaml
kubectl port-forward svc/zdr 8080:80    # 另开终端保持
```

## 2. 压测下做滚动重启,数掉请求

```bash
# 终端1:压测
URL=http://localhost:8080/work bash load.sh 40
# 终端2:滚动重启(逐个替换 Pod)
kubectl rollout restart deploy/zdr
```

**预期:掉请求合计 > 0。** 根因正是 ch03 B 的竞态——Pod 收到 SIGTERM 关 socket 时,kube-proxy/Service 的 endpoint 还没摘干净,新连接打过来吃 RST。

## 3. 加上 preStop,再来一次

`k8s/deploy-graceful.yaml` 在容器里加:

```yaml
        lifecycle:
          preStop:
            exec:
              command: ["sh", "-c", "sleep 8"]   # 睡过 endpoint 传播窗口再让 SIGTERM 触发优雅关
```

```bash
kubectl apply -f k8s/deploy-graceful.yaml
# 重复第 2 步的压测 + rollout restart
```

**预期:掉请求合计 ≈ 0。** preStop 的 sleep 让 Pod 在"流量还没摘干净"的窗口里继续正常服务,等 endpoint 传播完,SIGTERM 才真正触发关 socket——拒连黑洞消失。

> 想更狠地证明竞态,把 `sleep 8` 调成 `sleep 0`(等于没 preStop),或把副本数、`WORK_SECONDS` 调大,掉请求会更明显。

## 4. 看一眼 endpoint 摘除的时序(竞态的直接证据)

```bash
kubectl get endpointslices -l kubernetes.io/service-name=zdr -w
# 另一个终端删一个 pod,观察它从 endpoints 里消失的时刻
kubectl delete pod <一个zdr的pod>
```

你会看到 endpoint 的更新**晚于**你删 pod 的瞬间——那段 lag 就是 preStop 要覆盖的窗口。

## 清理

```bash
kind delete cluster --name zdr
```
