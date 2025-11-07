# 部署指南

## 本地开发

```bash
cd python-backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt

# 配置 .env 文件
cp .env.example .env
# 编辑 .env 文件

# 启动服务
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload
```

## Docker 部署

```bash
cd python-backend
docker-compose up -d
```

## 生产环境

参考 `python-backend/Dockerfile.production` 和 `docker-compose.production.yml`。

## 环境变量

详细的环境变量配置请参考根目录 `README.md`。

## 数据源处理

确保运行 rag-worker 服务来处理数据源：

```bash
docker-compose --profile rag-worker --profile qdrant up -d rag-worker
```

## Qdrant 配置

确保 Qdrant 服务运行在正确端口（默认 6334），并创建 `embeddings` collection。

