# DoR / DoD 检查单

> 两道闸门。**放行的勾必须由人来点,AI 不点。**

---

## 🚪 DoR — Definition of Ready(进 Build 前)
治"需求→开发对不齐"。全勾才放行:

- [ ] spec 有:problem + 业务规则 + AC + scope 边界(in/out)
- [ ] 原型**已冻结**,且标注 normative vs incidental
- [ ] 已拆成胃口 ≤L 的任务
- [ ] **工程看过并点头:"我看得懂、能做、没有大歧义"**（灵魂条)
- [ ] 有 AC 能判定"做完算对"
- [ ] (Shaping Review 已做:挑过刺、砍过范围)

---

## 🚪 DoD — Definition of Done(上线前)
治"质量没保障 + 沉淀乱"。全勾才算完成:

- [ ] 代码合并、CI 绿、已上线(或在 feature flag 后)
- [ ] **AC 逐条验收通过**
- [ ] 关键路径有测试覆盖
- [ ] happy path + 关键边界(空/错/越权)手动走过一遍
- [ ] 重要决策写了 ADR
- [ ] 文档已更新,PR ↔ spec ↔ 卡片互相链接(可追溯)
