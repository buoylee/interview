# Kubernetes Core Concepts

Kubernetes is a container orchestration platform that automates deployment, scaling, and management of containerized workloads. The control plane consists of the API server, etcd (the cluster state store), the scheduler, and controller managers. Worker nodes run the kubelet agent, a container runtime, and kube-proxy for network rules.

## Pod Health Probes

Kubernetes supports three probe types to monitor container health: liveness, readiness, and startup probes. Each probe can use an HTTP GET, a TCP socket check, or an exec command inside the container.

A liveness probe determines whether the container is alive. If it fails, the kubelet kills the container and restarts it according to the pod's restart policy. Use liveness probes for detecting deadlocks or unrecoverable error states where the process is still running but no longer functional.

A readiness probe determines whether the container is ready to serve traffic. If it fails, the pod is removed from the Endpoints list of any matching Service, so no new requests are routed to it — but the container is NOT restarted. Once the probe passes again, the pod is re-added to Endpoints. Use readiness probes to gate traffic during initialization or temporary overload.

A startup probe is designed for containers with slow startup times. While the startup probe is still running, liveness and readiness checks are suspended. Once the startup probe succeeds, normal liveness and readiness probing begins. This avoids false-positive liveness restarts during long boot sequences.

## Horizontal Pod Autoscaler (HPA)

Horizontal Pod Autoscaler (HPA) automatically scales the number of pod replicas in a Deployment or StatefulSet based on observed metrics. The default metric is CPU utilization, but HPA also supports memory and custom/external metrics via the Metrics API.

HPA runs a control loop (default 15-second interval) that queries current metric values, computes the desired replica count using the ratio of current to target, and updates the Deployment's replica field. The formula is: desiredReplicas = ceil(currentReplicas * currentMetricValue / targetMetricValue).

For HPA to function correctly, containers must declare resource requests. The CPU utilization percentage is calculated relative to the requested CPU, not the node's total capacity. Without resource requests, HPA cannot compute utilization and will not scale.

For latency-sensitive workloads, custom metrics (such as queue depth or requests-per-second from Prometheus) react faster than CPU, because CPU rises only after latency has already degraded. The Cluster Autoscaler complements HPA by adding or removing nodes when pods cannot be scheduled due to insufficient resources.

## Service Types

A Service provides a stable network endpoint to a dynamic set of pods selected by label. Kubernetes offers several Service types with different exposure scopes.

ClusterIP is the default type. It allocates a virtual IP address reachable only within the cluster. kube-proxy programs iptables or IPVS rules on every node to load-balance traffic across healthy pod Endpoints. Use ClusterIP for internal service-to-service communication.

NodePort extends ClusterIP by additionally opening a port (30000-32767 by default) on every node's external IP. External clients can reach the service at any-node-IP:nodePort. NodePort is simple but exposes every node to external traffic and is generally not recommended for production.

LoadBalancer extends NodePort by provisioning an external load balancer through the cloud provider. The load balancer forwards traffic to the NodePort on the nodes. This is the standard way to expose a service externally in managed Kubernetes environments (EKS, GKE, AKS).

ExternalName is a special type that maps a Service to a DNS CNAME record, used to give an in-cluster DNS name to an external service without proxying traffic.

## Rolling Updates and Deployment Strategy

Kubernetes Deployments use a rolling update strategy by default. When a new pod template is applied, Kubernetes incrementally replaces old pods with new ones without taking the application offline.

Two key parameters control the rollout pace. maxUnavailable defines the maximum number (or percentage) of pods that can be unavailable during the update — old pods are deleted before replacements are fully ready only up to this limit. maxSurge defines how many extra pods above the desired replica count can exist at once — new pods can be created before old ones are removed up to this limit. For example, with 10 replicas, maxUnavailable=1 and maxSurge=1 means at most 11 pods exist at any moment and at most 1 pod is unavailable (at least 9 of 10 are available) during the rollout, giving a smooth one-at-a-time replacement.

A rolling update is only considered complete when all new pods pass their readiness probes. If new pods fail readiness, the rollout pauses rather than continuing to replace healthy pods. This makes readiness probes critical for safe deployments. Rollbacks are performed by updating the Deployment spec back to a previous revision, which Kubernetes stores in its rollout history.
