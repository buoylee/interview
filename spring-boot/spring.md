

## 概述



## BeanDefinition

**BeanDefinition**, **包含很多属性**来**描述**一个**Bean**.
class:表示Bean类型
scope: 表示Bean作用域，单例或原型等
lazyInit: 表示Bean是否是懒加载
initMethodName: 表示Bean初始化时要执行的方法
destroyMethodName: 表示Bean销毁时要执行的方法



**申明式定义Bean**

1. `<bean/>`
2. `@Bean`
3. `@Component(@Service,@Controller)`



beanDefinition
ClassLoader
beanfactory
都有post 前后置方法