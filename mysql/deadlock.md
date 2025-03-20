## 發現

### jvm 

堆棧信息 有 deadlock

### mysql

SHOW ENGINE INNODB STATUS

## 解決

適當減少 innodb_lock_wait_timeout

考慮開啓 死鎖自動檢測

各種可能減少鎖粒度(觸發 gap lock; update where條件失效; 鎖表)

單表: 按主鍵ID順序鎖定.

跨表: 按固定的業務邏輯順序處理.



## 參考

https://panda843.github.io/question/%E6%95%B0%E6%8D%AE%E5%BA%93/Mysql%E6%AD%BB%E9%94%81%E7%9A%84%E4%BA%A7%E7%94%9F&%E8%A7%A3%E5%86%B3%E6%96%B9%E6%A1%88.html



https://blog.csdn.net/qq_45038038/article/details/134580628