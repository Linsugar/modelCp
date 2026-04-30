# Lottery LLM API

Python/FastAPI 彩票号码服务，支持：

- 查询今日彩票开奖
- 单模型或多模型生成彩票号码
- 历史号码兑奖校验
- 前端密钥校验

详细接口见 [接口文档.md](D:/PythonProjects/Agent/接口文档.md)。

## 本地运行

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

## 环境变量

复制配置模板：

```powershell
Copy-Item .env.example .env
```

常用配置：

```env
API_ACCESS_KEY=demo-frontend-key
CORS_ALLOWED_ORIGINS=*
LLM_BASE_URL=https://api.openai.com/v1
LLM_API_KEY=your-model-api-key
LLM_MODEL=gpt-4o-mini
```

多模型配置使用 `LLM_PROVIDERS`，格式见 `.env.example`。

## Docker 部署

构建镜像：

```bash
docker build -t lottery-api:latest .
```

运行容器：

```bash
docker run -d --name lottery-api \
  -p 8000:8000 \
  --env-file .env \
  -v ./data:/app/data \
  lottery-api:latest
```

也可以使用 compose：

```bash
docker compose up -d --build
```

健康检查：

```bash
curl http://127.0.0.1:8000/health
```

## 常用接口

```text
GET  /health
GET  /api/v1/lottery/today?game=ssq
POST /api/v1/chat/generate
POST /api/v1/lottery/check
```
