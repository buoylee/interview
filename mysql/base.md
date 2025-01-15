

[toc]

## 全连接/交叉连接(笛卡尔集)



**全连接:**

```
SELECT * 
FROM tableA
CROSS JOIN tableB;

SELECT *
FROM tableA, tableB;
```



**交叉连接(笛卡尔集):**

```
SELECT * 
FROM tableA
LEFT JOIN tableB ON tableA.id = tableB.id
UNION
SELECT * 
FROM tableA
RIGHT JOIN tableB ON tableA.id = tableB.id;
```

 ### 区别

全连接后, 不存在的连接, **一方的字段会显示null**.

交叉连接, **不会显示不存在的关系**, 因为是左/右连接的union.

