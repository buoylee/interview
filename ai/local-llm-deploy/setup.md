# Mac 本地部署 LLM (Ollama + Qwen2.5:7B)

**环境**: M4 MacBook Air 16GB RAM

## 1. 安装 Ollama

```bash
brew install ollama
```

## 2. 启动 Ollama 服务

```bash
# 启动后台服务（首次安装后需要手动启动）
ollama serve
```

> 启动后 API 默认监听 `http://localhost:11434`

## 3. 拉取模型

```bash
# 下载 qwen2.5:7b（约 4.7GB）
ollama pull qwen2.5:7b
```

## 4. 验证模型

```bash
# 命令行对话测试
ollama run qwen2.5:7b "你好，请介绍一下你自己"

# 查看已下载的模型
ollama list
```

## 5. API 调用测试

```bash
# 基础对话
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "你好"}]
  }'
```

```bash
# Tool Calling 测试
curl http://localhost:11434/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{
    "model": "qwen2.5:7b",
    "messages": [{"role": "user", "content": "北京今天天气怎么样？"}],
    "tools": [{
      "type": "function",
      "function": {
        "name": "get_weather",
        "description": "获取指定城市的天气",
        "parameters": {
          "type": "object",
          "properties": {
            "city": {"type": "string", "description": "城市名"}
          },
          "required": ["city"]
        }
      }
    }]
  }'
```

## 6. 常用命令

```bash
# 查看运行状态
ollama ps

# 停止模型（释放内存）
ollama stop qwen2.5:7b

# 删除模型
ollama rm qwen2.5:7b

# 查看模型信息
ollama show qwen2.5:7b
```

## 资源占用

| 项目 | 数值 |
|------|------|
| 磁盘 | ~4.7GB |
| 运行内存 | ~6-7GB |
| 模型存储路径 | `~/.ollama/models/` |
