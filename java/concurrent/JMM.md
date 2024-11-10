JMM 即 **Java Memory Model**, 内存模型, 和 线程间通信有关(共享内存模型)

<img src="Screenshot 2024-11-09 at 22.18.56.png" alt="Screenshot 2024-11-09 at 22.18.56" style="zoom:50%;" />

变量移动到不同的区域, 有6个原子操作
注意, read 和 store 都只是读到特定的位置, 但是还没赋值给对应的变相, 所以还需要 load 和 write 这2个操作.

<img src="Screenshot 2024-11-09 at 23.26.59.png" alt="Screenshot 2024-11-09 at 23.26.59" style="zoom:50%;" />

## while(flag == true)

这种while true 执行的优先级很高, 可能会导致像死锁一样, 一直占用线程, 其他任务抢不到当前cpu.

cpu每次都会去本地内存读值, 再做运算, 
所以, 如何才能让当前线程读到更新后的flag? 让**本地内存副本消失**.

下边的等待时间, 如果是1ms是可以使得本地内存淘汰, 读到最新的值,
1000的不行,
上下文切换大概有 5-10ms, 所以可以读到最新内存

为什么?

<img src="Screenshot 2024-11-10 at 00.21.10.png" alt="Screenshot 2024-11-10 at 00.21.10" style="zoom:50%;" />

