## select/poll/epoll 区别



<img src="image-20241204170642324.png" alt="image-20241204170642324" style="zoom: 50%;" />

select 是主动轮训, 数组最长1024
poll 链表, 无长度限制, 但还是遍历, 时间复杂度 O(n)
epoll hashtable, 基于时间通知回调, O(1)

## 同步/异步-阻塞非阻塞

<img src="image-20241204175229299.png" alt="image-20241204175229299" style="zoom: 33%;" />



## AIO

少人用是因为API不友好, 异常处理多/麻烦, 代码量大.
AIO的在linux底层还是epoll实现