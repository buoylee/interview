## 第N高 / IFNULL() / RANK() OVER (ORDER BY



```
CREATE FUNCTION getNthHighestSalary(N INT) RETURNS INT
BEGIN
  RETURN (
      SELECT IFNULL(
        (select salary  
        	from(
        		select salary,
        		rank() over(order by salary desc) rk
        		from Employee
        		group by salary # 因为了出现相同的salary, 需要 group
        	)t1
        where rk=N
        ),NULL
      ) SecondHighestSalary
  );
END
```

```
IFNULL(expression, NULL)
```

返回 expression 的值，如果 expression 为 NULL，则返回 NULL。