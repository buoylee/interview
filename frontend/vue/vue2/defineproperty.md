# 回顾Object.defineproperty





```
let number = 18
Let person ={
  name：'张三',
  sex：'男',
  age:number
}
```

如果继续 number = 19, 并不会影响 age. 需要用到 Object.defineproperty 来 创建 getter

![image-20251010134837421](/Users/buoy/Development/gitrepo/interview/frontend/vue/vue2/assets/image-20251010134837421.png)



## 可以用来实现对象代理

![image-20251010135144157](/Users/buoy/Development/gitrepo/interview/frontend/vue/vue2/assets/image-20251010135144157.png)

