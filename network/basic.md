# base

- [为什么没有会话层和表示层？] https://juejin.cn/post/6868555674901708814

- [聊聊 TCP 长连接和心跳那些事] https://www.cnkirito.moe/tcp-talk/

- [TCP连接的TIME_WAIT和CLOSE_WAIT 状态解说] https://www.cnblogs.com/kevingrace/p/9988354.html

  > 1) 主动关闭连接的一方，调用close()；协议层发送FIN包 ;
  > 2) 被动关闭的一方收到FIN包后，协议层回复ACK；然后被动关闭的一方，进入CLOSE_WAIT状态，主动关闭的一方等待对方关闭，则进入FIN_WAIT_2状态；此时，主动关闭的一方等待被动关闭一方的应用程序，调用close操作 ;
  > 3) 被动关闭的一方在完成所有数据发送后，调用close()操作；此时，协议层发送FIN包给主动关闭的一方，等待对方的ACK，被动关闭的一方进入LAST_ACK状态；
  > 4) 主动关闭的一方收到FIN包，协议层回复ACK；此时，主动关闭连接的一方，进入TIME_WAIT状态；而被动关闭的一方，进入CLOSED状态 ;
  > 5) 等待2MSL时间，主动关闭的一方，结束TIME_WAIT，进入CLOSED状态 ;

  所以说这里凭直觉看，TIME_WAIT并不可怕，CLOSE_WAIT才可怕，因为CLOSE_WAIT很多，表示说要么是你的应用程序写的有问题，没有合适的关闭socket；要么是说，你的服务器CPU处理不过来（CPU太忙）或者你的应用程序一直睡眠到其它地方(锁，或者文件I/O等等)，你的应用程序获得不到合适的调度时间，造成你的程序没法真正的执行close操作。

- [HTTP、TCP、UDP详解] https://www.huaweicloud.com/articles/504398259dd1b30886d1498e3c35c142.html

- [TCP/UDP 区别详解]  https://juejin.cn/post/6928030205982277646



# 面试

- [建议收藏！TCP协议面试灵魂12 问] https://segmentfault.com/a/1190000023565467
- [一文搞定 UDP 和 TCP 高频面试题！] https://zhuanlan.zhihu.com/p/108822858
- [建议收藏！TCP协议面试灵魂12 问] https://segmentfault.com/a/1190000023565467



# 额外

- [Golang 网络编程] https://www.cnblogs.com/ZhuChangwu/p/13198872.html