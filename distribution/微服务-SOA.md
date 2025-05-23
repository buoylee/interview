[toc]

## 概述

### SOA（Service-Oriented Architecture，**面向服务的架构**）

一种高层级的架构设计理念, 基于通信语言接口，让组件可重用.
所有业务功能都可以定义为一项服务，意味着对外提供开放的能力，当其他系统需要使用这项功能时，无须定制化开发。
**例如**，商品管理可以是一项服务，包括商品基本信息管理、供应商管理、入库管理等功能. 
是划分为粗粒度还是细粒度服务，根据企业实际情况判断。
SOA 集成了独立部署和维护的服务，允许它们相互通信/协同工作，构建一个跨不同系统的软件应用。

ESB（Enterprise Service Bus，**企业服务总线**）把企业中各个不同的服务连接在一起。就像计算机总线一样，把计算机的各个不同的设备连接在一起。
不同的服务使用不同的技术实现，即各个独立的服务是异构的，异构系统对外提供的接口是各式各样的。
SOA 使用 ESB 来屏蔽异构系统对外提供各种不同的接口方式，来达到服务间高效的互联。ESB通过使用标准网络协议（如 SOAP、XML、JSON、MQ ）来开放服务以发送请求或访问数据，实现与各种系统间的协议转换、数据转换、透明的动态路由等功能，消除了开发人员必须从头开始进行集成的困扰。



### 微服务（Microservices）

一种软件架构风格, 以专注于单一责任与功能的小型功能区块 (Small Building Blocks) 为基础，模块化的方式组合出复杂的大型应用程序，各功能区块使用与语言无关 (Language-Independent/Language agnostic）的API集相互通信。

## 对比

##### 服务粒度

SOA 服务粒度要粗, 
例如: 电商企业来说，
商品管理系统是一个 SOA 架构中的服务,
微服务架构，商品管理系统会被拆分为更多的服务，比如, 商品基本信息管理、供应商管理、入库管理等更多服务。

##### 服务通信

SOA 采用了 ESB 作为服务间通信的关键组件, 负责服务定义、服务路由、消息转换、消息传递，一般情况下都是**重量级的实现**。
微服务, 则使用统一的协议和格式，例如：HTTP RESTful 协议、TCP RPC 协议.

##### 服务交付

微服务的架构理念, 要求快速交付，要求采取自动化测试、持续集成、自动化部署、自动化运维等。

##### 应用场景

**SOA总结**, 老系统的架构和技术原因, 异构性, 无法大规模重构, 所以采用兼容的方式处理, 就是ESB.
SOA 更加适合于庞大、复杂、异构的企业级系统。因为很多系统已经发展多年，各个服务具有异构性，比如：采用不同的企业级技术、有的是内部开发的、有的是外部购买的，无法完全推倒重来或者进行大规模的优化和重构。因为成本和影响太大，只能采用兼容的方式进行处理，而承担兼容任务的就是 ESB。

**微服务总结**, Web 的互联网新系统, 轻量级(http), 快速.
微服务更加适合于快速、轻量级、基于 Web 的互联网系统，这类系统业务变化快，需要快速尝试、快速交付；同时基本都是基于 Web，虽然开发技术可能差异很大（例如，Java、.NET、PHP 等），但对外接口基本都是提供 HTTP RESTful 风格的接口，无须考虑在接口层进行类似 SOA 的 ESB 那样的处理。

<img src="Screenshot 2024-11-04 at 14.45.35.png" alt="Screenshot 2024-11-04 at 14.45.35"  />
