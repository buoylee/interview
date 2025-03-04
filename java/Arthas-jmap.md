[toc]

## 查看class反编译内容



## 执行命令

hasMap.add...



## 查看方法栈信息



## heap dump





## jmap

### -histo

实例数量, 占用字节, class



<img src="Screenshot 2024-12-09 at 00.28.02.png" alt="Screenshot 2024-12-09 at 00.28.02" style="zoom:50%;" />



### -heap

堆信息, config, 占用情况





### -dump

 导出heap



## jstack

堆栈信息



### -gc [processId]

实时GC



## jstat

```
S0C    S1C    S0U    S1U    EC     EU     OC     OU     MC     MU     CCSC   CCSU   YGC   YGCT   FGC   FGCT  GCT  
```

S: **Survivor**
C: **Capacity**
U: **Utilization**
E: **Eden**
O: **Old**
M: **Metaspace**
CCS: **Compressed Class Space**
YG: **Young** Generation **GC Count**
T: time
**FGC**: **Full GC Count**




## jinfo -flags [pId]

jvm参数



## visualVM

可以检测死锁
