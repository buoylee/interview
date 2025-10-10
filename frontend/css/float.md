# 概述 

以前用来做**文字环绕**图片, 现在**做布局**



2是float, 但是3的文字躲开了2的遮挡, **显示出了完整的文字**

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008011558158.png" alt="image-20251008011558158" style="zoom:33%;" />



# 浮动后

如果没有设置宽高, 容器默认只会被内容撑开. 都可以当作文字来处理.

margin/padding 没有塌陷, 完美设置宽高.

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008031953460.png" alt="image-20251008031953460" style="zoom:50%;" />







# 清除(后续)浮动(遮挡/父元素缩小问题)

clear: left/both/...

如果要解决浮动导致的父元素缩小, 行内元素不能用 clear, 因为高度设置无效.

## 最终解决方案: 但是还是解决不了 最后一个不是float元素的遮挡问题

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008105653296.png" alt="image-20251008105653296" style="zoom:50%;" />



# 总结 

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008110109347.png" alt="image-20251008110109347" style="zoom: 50%;" />



# 浮动布局常用样式

左右浮动/清除浮动

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008123741590.png" alt="image-20251008123741590" style="zoom:50%;" />

