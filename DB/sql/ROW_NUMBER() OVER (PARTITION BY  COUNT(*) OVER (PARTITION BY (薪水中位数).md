[TOC]

## ROW_NUMBER() OVER (PARTITION BY / COUNT(*) OVER (PARTITION BY (薪水中位数)

```
select Id,Company,Salary
from (
select Id,Company,Salary,
ROW_NUMBER() over(partition by Company order by Salary) rk,
count(*) over(partition by Company) cnt
from Employee
)t1
where rk IN (FLOOR((cnt + 1)/2), FLOOR((cnt + 2)/2))
```

``````
ROW_NUMBER() OVER (PARTITION BY Company ORDER BY Salary) rk
``````

**放在 select 里的.**是一个窗口函数，用来为结果集中的每一行分配一个唯一的行号。

PARTITION BY Company：将结果集按 Company（公司）进行分区，这意味着每个公司单独计算行号。

``````
COUNT(*) OVER (PARTITION BY Company)
``````

COUNT(*) 是一个窗口函数，用来计算每个公司中员工的总数。

PARTITION BY Company：按 Company 列分区计算每个公司的总员工数。

```
SELECT Id, Company, Salary,
  ROW_NUMBER() OVER (PARTITION BY Company ORDER BY Salary) rk,
  COUNT(*) OVER (PARTITION BY Company) cnt
FROM Employee
```

```FLOOR((cnt + 1)/2) 和 FLOOR((cnt + 2)/2)
FLOOR((cnt + 1)/2) 和 FLOOR((cnt + 2)/2)
```

向下取整

![Screenshot 2024-08-28 at 19.16.41](/Users/buoy/Library/Application Support/typora-user-images/Screenshot 2024-08-28 at 19.16.41.png)

后:

![Screenshot 2024-08-28 at 19.17.24](/Users/buoy/Library/Application Support/typora-user-images/Screenshot 2024-08-28 at 19.17.24.png) 

