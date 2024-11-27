## GC root

将“GC Roots”对象作为起点，从这些节点开始向下搜索引用的对象，找到的对象都标记为非垃圾对象，其余未标记的对象都是垃圾对象
**GC Roots根节点：线程栈的本地变量、静态变量、本地方法栈的变量等等**



![Screenshot 2024-11-26 at 23.26.59](Screenshot 2024-11-26 at 23.26.59.png)



## 调优

<img src="Screenshot 2024-11-26 at 23.43.11.png" alt="Screenshot 2024-11-26 at 23.43.11" style="zoom: 50%;" />

如果jar包很大, 原空间调大一点, 不然启动时会fullGC.

xss 默认是 1M

