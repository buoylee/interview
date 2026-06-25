IMG     ?= echolab:dev
CLUSTER ?= svc-gov-lab

.PHONY: up build load deploy pinned spread scale status down all

all: up build load deploy ## 一鍵:建集群 → 打鏡像 → load → 部署

up: ## 建 kind 集群
	kind create cluster --config kind.yaml

build: ## 打鏡像
	docker build -t $(IMG) .

load: ## 把鏡像塞進 kind(不走 registry)
	kind load docker-image $(IMG) --name $(CLUSTER)

deploy: ## 部署 3 副本 + 兩個 Service,等就緒
	kubectl apply -f k8s/
	kubectl rollout status deploy/echo

pinned: ## demo 1:一條 H2 連接 → ClusterIP → 全釘一個 pod
	kubectl run echo-client --rm -i --restart=Never \
		--image=$(IMG) --image-pull-policy=Never -- \
		pinned http://echo-clusterip:8080/ 30

spread: ## demo 2:headless + 逐 IP round-robin → 分散到多 pod
	kubectl run echo-client --rm -i --restart=Never \
		--image=$(IMG) --image-pull-policy=Never -- \
		spread echo-headless 8080 30

scale: ## demo 3:擴到 6 副本(配合 pinned 觀察「擴容後老連接不重新均衡」)
	kubectl scale deploy/echo --replicas=6
	kubectl rollout status deploy/echo

status: ## 看 pod 落在哪
	kubectl get pods -l app=echo -o wide

down: ## 拆集群
	kind delete cluster --name $(CLUSTER)
