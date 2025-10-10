# 概述

relative/absolute



# 配合 属性 left/right/top/bottom: 10px; (left是左边空出来)

只有在相同位置时, margin-xxx 才能生效



# *包含块

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008153605813.png" alt="image-20251008153605813" style="zoom:50%;" />



# relative

参考点(原点)是原来的位置.

如果是行内元素, 仍然不能设置宽高.



## absolute

变成定位元素. 可以设置宽高.

参考点是包含块



和float一样飘起来了, 不同的是, 文本不会多开遮挡的元素(直接被遮挡).





不能和 float 共用, 



## fixed

参考点是 视口, 所以即使出现滚动条也会一直出现在视口相同位置. 也就和包含块没有关系了. 



# sticky

就是有个title栏的固定的顶部, 滚动到新的title时, 就会顶掉.



<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20251008161113903.png" alt="image-20251008161113903" style="zoom:33%;" />



# 定位的层级 (z-index 来调整)

后写样式(不是后写的div)的压着前边的





## 特殊用法

子充满父, 

```
left: 0(px);
right: 0(px);
top:...
bottom:...
```

