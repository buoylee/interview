# display: flex



和flow很像, ,可以让块元素 **放在同一行**

不同于 flow, **flex不会飘起来**(仍然在文档流(在地上, 受其他div影响)中, 

flex **只影响子元素**. 子元素**全部变成block**元素.

有**inline-flex**, 但是**需要处理**子元素的**中间缝隙**, 一般在父div再加flex即可解决



## 调整主轴: 

flex-direction: 

row-reverse(水平反转)

column: 上到下



## 主动换行(不压缩)

flex-wrap: wrap[-reverse(从底向上换行)]；



## 主轴对齐

justify-content: 

flex-end；排列方式不变, 但是靠右对齐

center 

space-around 平分剩余空间(item左右固定距离, 会叠加)

space-betweem 平分剩余空间(左右边缘对齐)

space-evenly 完全平分



![image-20250930110723506](/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20250930110723506.png)



## 侧轴的行内(单行)对齐方式(align-items)
stretch (默认值, 无height时, 填满高度)

flex-start (其他默认情况下, 靠顶部)

flex-end(靠底部)

center(其他默认情况下, 垂直居中)

baseline(基线)

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20250930150732118.png" alt="image-20250930150732118" style="zoom:50%;" />

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20250930150802546.png" alt="image-20250930150802546" style="zoom:50%;" />





## 侧轴的堆叠(多行平分/紧靠)方式align-content

flex-start 

<img src="/Users/buoy/Development/gitrepo/interview/frontend/css/assets/image-20250930151752568.png" alt="image-20250930151752568" style="zoom:33%;" />



space-around/space-betweem 同 justify-content

stretch (默认) 同 align-items

## flex-flow(复合上边2个属性, 可以忽略)



## flex-basis(默认auto)

浏览器用来计算(主轴)剩余空间



## flex-grow(自动拉伸)作用于inner

所有 flex-grow value 总和就是总数, 所有inner各自的 value的比例就好, value/sum







## flex-shrink(同一行所有元素压缩比, 但是一般不写默认1)

同flex-grow的比例计算, 但是会被变量影响, 导致误差, 但是不影响观感.

但是如果有内容, 就不会压缩内容空间





## flex:1 1 100px；复合属性

拉伸比/收缩比/基准长度

flex:1 1 auto == flex:auto

flex:1 1 0 == flex:1  (全部拉伸)

flex:0 0 auto == flex:none (不能缩放)

flex: 0 1 auto == flex: 0 auto
