# base

- [golang面试题：reflect（反射包）如何获取字段tag？为什么json包不能导出私有变量的tag？] https://mp.weixin.qq.com/s/WK9StkC3Jfy-o1dUqlo7Dg

  > 反射可以获得tag信息.
  >
  > Json包不能导, 是因为他认为 私有变量 是 Unexported的.