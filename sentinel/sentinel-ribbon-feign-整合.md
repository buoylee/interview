## 底层

也是AOP

实现了接口 ClientHttpRequestInterceptor的 SentinelProtectInterceptor
```
hostEntry = SphU.entry(...)
...

catch(){
 如果是blockingException, 打印trace;
 否则, return handleBlockException();
}
finally{
	hostEntry.exit();
}
```

## 使用

@SentinelRestTemplate()

@SentinelRestTemplate 属性支持限流（blockHandler, blockHandlerClass）和降级（fallback, fallbackClass）的处理。

<img src="Screenshot 2024-11-09 at 13.19.28.png" alt="Screenshot 2024-11-09 at 13.19.28" style="zoom: 50%;" />

## feign整合

<img src="Screenshot 2024-11-09 at 14.27.09.png" alt="Screenshot 2024-11-09 at 14.27.09" style="zoom:50%;" />

<img src="Screenshot 2024-11-09 at 14.33.06.png" alt="Screenshot 2024-11-09 at 14.33.06" style="zoom:50%;" />

<img src="Screenshot 2024-11-09 at 14.58.20.png" alt="Screenshot 2024-11-09 at 14.58.20" style="zoom:50%;" />

