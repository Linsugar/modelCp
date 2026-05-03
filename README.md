# Lottery LLM API

Python/FastAPI 彩票号码服务，支持：

- 查询今日彩票开奖
- 单模型或多模型生成彩票号码
- 历史号码兑奖校验
- 前端密钥校验
- Docker 部署

详细接口见 [接口文档.md](D:/PythonProjects/Agent/接口文档.md)。

## 配置

所有配置都在 [app/config.py](D:/PythonProjects/Agent/app/config.py) 里，不再使用 `.env`。

常用配置：

```python
app_port = 8549
cors_allowed_origins = "*"
api_access_key = "Tang"
llm_base_url = "https://zenmux.ai/api/v1"
llm_api_key = os.getenv("LLM_API_KEY", "")
llm_model = "deepseek/deepseek-v4-pro-free"
```

模型 key 不写进代码，启动容器时用系统环境变量传入：

```bash
docker run -d --name lottery-api \
  -p 8549:8549 \
  -e LLM_API_KEY="你的真实模型 key" \
  -v ./data:/app/data \
  lottery-api:latest
```

修改配置后需要重新 build 镜像。

## Docker 部署

构建镜像：

```bash
docker build -t lottery-api:latest .
```

停止旧容器：

```bash
docker stop lottery-api
docker rm lottery-api
```

启动新容器：

```bash
docker run -d --name lottery-api \
  -p 8549:8549 \
  -e LLM_API_KEY="你的真实模型 key" \
  -v ./data:/app/data \
  lottery-api:latest
```

查看日志：

```bash
docker logs -f --tail 100 lottery-api
```

请求日志格式：

```text
2026-05-03 14:22:01 182.150.57.90 GET /api/v1/lottery/today?game=ssq 200 35.20ms
```

## 常用接口

```text
GET  /health
GET  /api/v1/lottery/today?game=ssq
POST /api/v1/chat/generate
POST /api/v1/lottery/check
```
