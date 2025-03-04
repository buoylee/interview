[toc]

## top

```
top - 10:32:47 up 12 days,  4:35,  2 users,  load average: 0.12, 0.16, 0.18
Tasks: 234 total,   1 running, 233 sleeping,   0 stopped,   0 zombie
%Cpu(s):  1.1 us,  0.4 sy,  0.0 ni, 98.5 id,  0.0 wa,  0.0 hi,  0.0 si,  0.0 st
MiB Mem :   8000.0 total,   4200.0 free,   2500.0 used,   1300.0 buff/cache
MiB Swap:   2048.0 total,   1800.0 free,    248.0 used.   6000.0 avail Mem

  PID USER      PR  NI    VIRT    RES    SHR S %CPU %MEM    TIME+ COMMAND
 1234 myuser    20   0  100000  12000   5000 S  2.0  0.1   0:02.34 java
```

**系统时间**, **运行時長**, **用户数**, 过去 1 分钟、5 分钟和 15 分钟内的平均负载

进程相關, 

**us (User CPU Time)**, 
**sy (System CPU Time)**, 
**ni (Nice CPU Time )**: 花费在 **调整过优先级的进程**（通过 nice 命令调整进程优先级）上的时间百分比, 
**id (Idle CPU Time)**, 
**wa (I/O Wait CPU Time)**, 
**hi (Hardware Interrupt CPU Time)**, CPU 花费在 **硬件中断** 的时间百分比
**si (Software Interrupt CPU Time)**, 
**st (Steal Time)**: 虚拟机（VM）由于共享物理 CPU 资源而未能获得预期 CPU 时间的时间百分比

mem相關

**交换空间**(就是作爲Swap的硬盤劃分出來的大小), 基本和mem一樣

**PR**：进程的优先级（Priority）。
**NI**：进程的 nice 值（调整进程优先级）。
**VIRT**：进程的虚拟内存大小（包括所有的内存映射文件、堆栈、共享库等）。
**RES**：进程实际占用的物理内存（不包括交换空间）。
**SHR**：进程与其他进程共享的内存大小（Shared memory）。
**S**：进程的状态。
**%CPU**：进程的 CPU 占用百分比。
**%MEM**：进程的内存占用百分比。
**TIME+**：进程的累计 CPU 时间。
**COMMAND**：启动该进程的命令及其参数。



```
ps -p xxx

  PID  VSZ   RSS   COMMAND
  1234 23456  7890 /usr/bin/java
```

**VSZ**：进程的虚拟内存大小。
**RSS**：进程实际占用的物理内存。



## 虛擬內存

**包含**:

**进程实际使用的内存**（物理内存和交换空间）。
**分配的内存空间**（即使当前没有使用，系统分配给它的空间）。
**映射的文件内存**（如共享库、内存映射文件等）。



## VIRT 和 VSZ 區別

VSZ 是 **虚拟内存大小** 的一个较早的术语, 描述**进程的总虚拟内存**（与 VIRT 近似）, 某些操作系统和工具中，VSZ 和 VIRT **可能是相同**的,
VSZ 通常**不包括**文件映射、共享库或内存映射等**内存映射(mmap())**区域的开销



## **文件映射（Memory Mapped Files）**

将**文件内容**直接**映射**到进程的**虚拟内存中**的技术.
**映射到进程的地址空间**中，使得进程可以**像访问内存一样**访问文件内容