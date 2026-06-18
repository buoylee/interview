# 第 7 章 · 配置与安全:ConfigMap/Secret、RBAC、Operator/CRD

> 🔬 配置怎么注入容器、密钥怎么管、谁能操作集群——这章是 k8s 的配置与权限,直接接 `system-design` 的 **L1 配置中心 + L7 安全**。再把 **Operator/CRD** 讲清(它就是把 `03b` 的 reconcile 机制开放给你)。

---

## Part A · ConfigMap / Secret 🔬

- **ConfigMap**:非敏感配置,注入为**环境变量**或**挂载为文件**。
- **Secret**:敏感(密码/证书)。**关键坑** 🔬:**Secret 默认只是 base64 编码,不是加密!** 谁能读 etcd 或有权限就能看明文。要真安全:
  - 开 **etcd 静态加密**(encryption at rest);
  - **RBAC 严格限制**谁能读 Secret;
  - 敏感的外置到 **Vault** 等(回扣用户偏好:可自托管)。
- **热更** 🔬:挂载为**文件**的 ConfigMap 会自动更新(有延迟),注入为 **env 的不会**(要重启 Pod)。对比 **L1 配置中心**的动态推送——这是 k8s 原生配置的短板,所以很多团队仍用 Nacos/Apollo 做动态配置。

---

## Part B · 认证 vs 授权 + RBAC 🔬(回扣 L7)

k8s 的权限体系正好是 L7「认证 vs 授权」的实例:
- **认证(你是谁)**:证书 / token / **ServiceAccount**。
- **授权(你能干什么)**:**RBAC**。

**RBAC 模型**:
```
Role(一组权限:能 get/list/create 哪些资源)
   │ RoleBinding 绑定
   ▼
User / Group / ServiceAccount
（ClusterRole / ClusterRoleBinding = 跨 namespace 的版本）
```

- **ServiceAccount**:**Pod 的身份**——Pod 要调 API Server(如 Operator、需要读配置的应用)时用它认证。
- **最小权限(回扣 L7)** 🔬:别给 Pod `cluster-admin`;不需要 API 访问的 Pod 关掉默认 SA token 自动挂载;按需授权。**这是 k8s 里「最小权限」最常被忽视、也最常被面试问的落地点。**

---

## Part C · Operator / CRD 🔬(回扣 03b reconcile)

- **CRD(CustomResourceDefinition)**:让你**自定义资源类型**,比如 `kind: MySQLCluster`、`kind: KafkaTopic`——k8s 的 API 被你扩展了。
- **Operator** = **CRD + 自定义控制器**:把「**运维某个有状态应用的知识**」写成 reconcile 逻辑,让 k8s **自动管理**它(回扣 `03b`:reconcile 模式开放给用户)。
  ```
  你声明:kind: MySQLCluster, replicas: 3
  MySQL Operator 的控制器 reconcile:建主从、配复制、故障时自动切主、定时备份…
  ```
- 例:**Prometheus Operator**、各家**数据库 Operator**。
- **架构师视角**:**Operator = 把 SRE 的运维经验代码化、声明式化。** 它是「有状态应用上 k8s」的关键拼图(回扣第 6 章)——StatefulSet 给原语,Operator 给运维大脑。

---

## Part D · 集群安全清单(接 L7)🔬

| 层面 | 做法 | 回扣 |
|---|---|---|
| **Pod 安全** | 非 root、只读根文件系统、SecurityContext、seccomp/AppArmor、Pod Security Standards | `03a` 容器隔离 + L7 |
| **网络** | NetworkPolicy 白名单(默认全通!) | 第 5 章 + L7 网络分区 |
| **镜像** | 扫描漏洞、签名、可信仓库、非 root | 第 1 章 |
| **密钥** | etcd 静态加密 + Vault 外置 | Part A |
| **权限** | RBAC 最小权限、SA token 按需 | Part B + L7 |
| **审计** | API Server audit log(谁在何时做了什么) | L8 + `observability/` |

---

## 交叉引用

- **配置动态推送对比 → L1 `05` 配置中心**(Nacos/Apollo)
- **认证 vs 授权 / RBAC / 最小权限 → L7 `system-design/10`**
- **Operator = reconcile 的开放 → `03b`**;**管有状态 → 第 6 章**
- **Secret 外置 Vault(可自托管)→ 用户偏好**
- **审计日志 → L8 `perf/13` + `observability/`**

---

## 本章小结

- **ConfigMap(非敏感)/ Secret(敏感,但默认只 base64 非加密!)**;要 etcd 加密 + RBAC + Vault;**env 注入不热更、文件挂载才热更**(k8s 配置短板,故仍用 Nacos/Apollo)。
- **认证(SA/证书/token)vs 授权(RBAC)** = L7 的实例;**RBAC = Role + RoleBinding**;**ServiceAccount 是 Pod 身份**;**最小权限别给 cluster-admin**。
- **CRD + Operator** = 把 reconcile 开放给你,**将运维知识代码化**,是有状态上 k8s 的关键。
- **集群安全清单**:Pod 安全 / NetworkPolicy / 镜像 / 密钥加密 / RBAC / 审计——全部回扣 L7。
- **k8s 知识块至此完整**(架构+内幕+资源+网络+存储+配置安全)。下面进 **debug 三章(重头戏)**。

---

## 章末问答(复习自检,答案要点都在前面正文)

1. ConfigMap 和 Secret 的区别?Secret「默认 base64」有什么安全陷阱、怎么真安全?
2. k8s 配置和 L1 的配置中心(Nacos)比,热更新上有什么短板?
3. k8s 的认证和授权分别靠什么?RBAC 的 Role / RoleBinding 是什么关系?
4. ServiceAccount 是给谁用的?「最小权限」在 k8s 里具体怎么落地?
5. CRD 和 Operator 各是什么?Operator 和 `03b` 的 reconcile 什么关系?
6. 为什么说 Operator 是「有状态应用上 k8s 的关键拼图」?
7. **综合题**:列一份「k8s 集群上线前的安全检查清单」,并说明每条对应 L7 的哪个原则。
```
