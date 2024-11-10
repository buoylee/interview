## main

<img src="Screenshot 2024-11-09 at 17.45.23.png" alt="Screenshot 2024-11-09 at 17.45.23" style="zoom:50%;" />

## pre-main

<img src="Screenshot 2024-11-09 at 17.47.24.png" alt="Screenshot 2024-11-09 at 17.47.24" style="zoom:50%;" />

## javaassist 方式

直接定位作为位置

<img src="Screenshot 2024-11-09 at 17.51.22.png" alt="Screenshot 2024-11-09 at 17.51.22" style="zoom:50%;" />

对原方法字节码形式得增强<img src="Screenshot 2024-11-09 at 17.54.34.png" alt="Screenshot 2024-11-09 at 17.54.34" style="zoom:50%;" />

## byteBuddy(对javassist增强)

拦截位置, 具体拦截处理class<img src="Screenshot 2024-11-09 at 18.00.03.png" alt="Screenshot 2024-11-09 at 18.00.03" style="zoom:50%;" />

上边拦截了所有, 这里明确指定了一次

<img src="Screenshot 2024-11-09 at 18.01.32.png" alt="Screenshot 2024-11-09 at 18.01.32" style="zoom:50%;" />

具体拦截处理

<img src="Screenshot 2024-11-09 at 18.03.20.png" alt="Screenshot 2024-11-09 at 18.03.20" style="zoom:50%;" />

