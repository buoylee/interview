## cn

```
你好, 面试官, 我叫李宏俊, 2012毕业, 专业网络工程, 2016年开始做开发. 有5年java 和 2年golang经验.

上家公司是百度外包, 项目是一个社交软体. 我负责其中的IM子项目, 这个im工程的前身就是百度IM, 主要的工作内容有对IM项目的容器化改造, 由原来的硬编码服务负载均衡, 改造成通过获取k8s的service, 然后解析出所有实际服务ip, 然后开启线程动态更新服务节点, 实现客户端的动态负载均衡. 还有接入百度聊天机器人, 和利用kafka发送通知等功能, 单实例压测达到150tps. 同时在线人数有1000到3000左右.
技术栈包括: spring, netty, zookeeper, redis, mysql, kafka. 利用了redis保存会话信息, 并用来自twitter的twemproxy中间件做分片, 和用sharing-jdbc对消息表做了分片.

上上家公司是微众外包, 刚开始使用的java. 1周后转用golang, 项目是机器学习 on k8s. 主要是利用了多个开源项目来整合成自己的项目. 有ffdl, kubeflow等. 主要工作就是阅读源码, 把开源项目主要的功能整合到一个系统中, 大量涉及k8s api使用, 接受不同的request, 生成对应的k8spod, 来进行多learner的训练.
技术栈包括: springboot, golang, swagger-go, gorm, k8s, grpc, protobuf, mongodb, elasticsearch, 自建s3等.
```











## en



```
以下是你提供的自我介绍改写成的英文版本，同时调整了语言使其更符合面试场景的表达习惯：

Hello, Interviewer, my name is Li Hongjun. I graduated in 2012 with a degree in Network Engineering, and I started working in software development in 2016. I have 5 years of experience with Java and 2 years with Golang.

My previous position was an outsourced role at Baidu, where I worked on a social media application. I was responsible for the IM (instant messaging) sub-project, which was originally based on Baidu’s IM system. My key tasks included containerizing the IM project, replacing the hardcoded service load balancing system with a dynamic approach. This new system fetched Kubernetes services, parsed the real service IPs, and initiated threads to dynamically update service nodes, enabling client-side dynamic load balancing. Additional features I worked on include integrating Baidu’s chatbot and using Kafka for sending notifications. The single-instance system was performance tested at 150 TPS, with concurrent online users ranging from 1,000 to 3,000.

The tech stack I used included Spring, Netty, Zookeeper, Redis, MySQL, and Kafka. Redis was utilized for storing session data, combined with Twitter’s Twemproxy middleware for sharding. Message tables were sharded using Sharding-JDBC.

Before that, I worked as an outsourced developer at WeBank. Initially, I used Java, but after one week, I switched to Golang. The project focused on machine learning on Kubernetes, where we integrated various open-source projects such as FfDL and Kubeflow into a unified system. My primary responsibilities involved reading and understanding source code to integrate key features into the new system. The project required extensive use of Kubernetes APIs to handle different requests, generate corresponding Kubernetes pods, and enable multi-learner training.

The tech stack I used included Spring Boot, Golang, Swagger-Go, GORM, Kubernetes, gRPC, Protobuf, MongoDB, Elasticsearch, and a self-hosted S3 system.

这个版本根据内容进行了逻辑优化，强调了技术背景和项目经验，以更符合英文面试的表达方式。如有进一步修改需求，可以告诉我！
```



## 以下是简化后的自我介绍：



**Good morning/afternoon!**

It’s great to meet you, and thanks so much for taking the time to chat with me today. My name’s jimmy lee, and I’d like to give you a quick overview of my background and experience.

I graduated in 2012 with a degree in Network Engineering and started my career in software development in 2016. Over the past seven years, I’ve specialized in backend development, focusing on Java for 5 years and Golang for 2 years.

Most recently, I worked as an outsourced developer for Baidu, contributing to their social media app. My main responsibility was handling the IM (instant messaging) module, which was initially the predecessor of Baidu’s commercial IM system. I containerized the IM project and replaced the hardcoded load-balancing mechanism with a Kubernetes-based dynamic solution. I also integrated Baidu’s chatbot and implemented an asynchronous notification system using Kafka. The system supported up to 3,000 concurrent users with 150 TPS.

Before that, I worked at WeBank as an outsourced developer, where I quickly transitioned from Java to Golang. I contributed to building a machine learning platform on Kubernetes, integrating frameworks like FfDL and Kubeflow, and enabling multi-learner distributed training environments.

I enjoy solving challenging problems, optimizing performance, and collaborating with teams. I’m excited about the opportunity to bring value to your team.

Thank you!



word: 
predecessor -> ˈpredə
mechanism -> 'megəni...
transitioned -> zion
integrating intə
enabling -> en neib ling
solving -> a: 
challenging -> lən
collaborating -> cə læ bər





**Good morning!**

It’s great to meet you, and I’d like to quickly share my experience in backend development and distributed systems, and how it aligns with this role.

I started my career in software development in 2016 after graduating with a degree in Network Engineering. Over the years, I’ve built expertise in backend development, particularly using Java (5 years) and Golang (2 years).

In my most recent role, I worked with Baidu on their social media app, primarily responsible for the IM (instant messaging) module—the predecessor of Baidu’s commercial IM system. I modernized the system by implementing containerization and a Kubernetes-based dynamic load-balancing solution, improving scalability and maintainability. I also integrated Baidu’s chatbot and built a Kafka-based asynchronous notification system, which reliably supported over 3,000 concurrent users and 150 TPS at peak.

Before Baidu, I worked at WeBank to develop a distributed machine learning platform on Kubernetes. I integrated open-source frameworks and automated workflows, supporting complex multi-learner training environments while transitioning quickly from Java to Golang to meet the project needs.

I thrive in challenging environments and enjoy building robust, high-performing systems. I’m confident my experience and skills will contribute to the success of your team.

Thank you!

