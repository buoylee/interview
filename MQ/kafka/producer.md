## Producer 之初始化

<img src="FhfQy4bT-gCA7NUh0OcFacA8s-UI.png" alt="img" style="zoom:67%;" />

**Kafka Producer 初始化流程如下：**

<img src="Screenshot 2024-11-28 at 16.02.32.png" alt="Screenshot 2024-11-28 at 16.02.32" style="zoom:50%;" />

## Producer 拉取元数据过程

<img src="FtlsY0BUNnJfTdCi8yen7ztADMHs.png" alt="img" style="zoom:50%;" />

**Kafka Producer 拉取元数据流程如下：**

<img src="Screenshot 2024-11-28 at 16.04.04.png" alt="Screenshot 2024-11-28 at 16.04.04" style="zoom: 50%;" />

## Kafka Producer 之发送流程

![img](FmEcVGpSpG-CMJYg7kjG1-IasE39.png)



**Kafka Producer 发送消息流程如下：**

<img src="Screenshot 2024-11-28 at 16.05.23.png" alt="Screenshot 2024-11-28 at 16.05.23" style="zoom: 50%;" />



## Producer 内存池设计

<img src="FlnsGx1-5oYLTasR17hnfR1w83Vs-20241128160606995.png" alt="img" style="zoom:67%;" />

### 申请内存的过程





### 释放内存

如果释放的是一个**批次的大小（16K）**，则直接加到**已分配内存**(这里的已分配是指创建好的buffer)里面；内存放到可用内存里面，
如果不是，则把这部分内存等待虚拟机（JVM）垃圾回收。**因为1M太大, 不适合之前定义的batch大小/时间发送条件.**



## Kafka Producer 之网络存储架构

![img](FuP-NtYJHQrI5_z5zNeq2e4FoVWu.png)



