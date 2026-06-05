# Kubernetes Autoscaling

Horizontal Pod Autoscaler (HPA) scales the number of pods based on CPU,
memory, or custom metrics. The Cluster Autoscaler adds or removes nodes
when pods cannot be scheduled. For latency-sensitive workloads, prefer
custom metrics over CPU to react earlier.
