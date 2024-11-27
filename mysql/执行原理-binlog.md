## 概述



## binlog

有 ... ,statement, mix

<img src="Screenshot 2024-11-22 at 03.35.45.png" alt="Screenshot 2024-11-22 at 03.35.45" style="zoom:33%;" />

<img src="Screenshot 2024-11-22 at 03.44.56.png" alt="Screenshot 2024-11-22 at 03.44.56" style="zoom:33%;" />



## binlog复制机制

### 半同步

(多线程, 有超时), 

### 异步



## 词法分析/语法分析

**词法分析**将原始文本**拆分为 Token 流**，不检查语法逻辑。

```
[
    {type: "KEYWORD", value: "SELECT"},
    {type: "IDENTIFIER", value: "name"},
    {type: "KEYWORD", value: "FROM"},
    {type: "IDENTIFIER", value: "users"},
    {type: "KEYWORD", value: "WHERE"},
    {type: "IDENTIFIER", value: "age"},
    {type: "OPERATOR", value: ">"},
    {type: "NUMBER", value: "18"}
]
```

**语法分析**负责**检查 Token 流的语法规则**，并**生成语法树**，表示 SQL 的逻辑结构。

```
SELECT
├── Columns: ["name"]
├── FROM
│   └── Table: "users"
└── WHERE
    ├── Condition
    │   ├── Column: "age"
    │   ├── Operator: ">"
    │   └── Value: 18
```

