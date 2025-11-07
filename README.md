# Rowboat Python Backend

完整的 Rowboat AI Agent 管理平台 Python 后端实现，基于 FastAPI 和 CrewAI 构建。

## 📋 项目简介

这是一个完全用 Python 重写的 Rowboat 后端系统，实现了原项目的所有核心功能，包括：

- 🤖 AI 智能体管理和交互
- 🔧 Composio 工具集成
- 📚 RAG 知识库管理
- 💬 对话系统
- 🔐 简化认证系统
- 📊 基础监控和指标

## ✨ 主要特性

### 1. 智能体管理
- 创建、更新、删除智能体
- 支持多种智能体类型（custom、template、copilot）
- 优化的 CrewAI 集成，快速初始化
- 流式响应支持

### 2. Composio 工具集成
- 完整的 Composio SDK 集成
- 支持 800+ 工具包
- LangChain Provider 支持
- 工具分类和搜索

### 3. RAG 知识库
- Qdrant 向量数据库集成
- 硅基流动 BAAI/bge-m3 嵌入模型
- 文档切片和索引
- 语义搜索

### 4. 数据源处理
- 支持文本、URL、文件数据源
- 异步处理工作流
- 自动切片和嵌入
- 状态管理

## 🚀 快速开始

### 环境要求

- Python 3.10+
- Qdrant (可选，用于 RAG)
- MongoDB (可选，用于数据源)
- Redis (可选)

### 安装

```bash
cd python-backend
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
venv\Scripts\activate  # Windows

pip install -r requirements.txt
```

### 配置

创建 `.env` 文件：

```bash
# API 配置
PROVIDER_BASE_URL=https://api.siliconflow.cn/v1
PROVIDER_API_KEY=your-api-key
PROVIDER_DEFAULT_MODEL=deepseek-ai/DeepSeek-V3.2-Exp
PROVIDER_COPILOT_MODEL=deepseek-ai/DeepSeek-V3.2-Exp

# 服务器配置
HOST=0.0.0.0
PORT=8000
DEBUG=false

# 数据库配置
DATABASE_URL=sqlite:///./rowboat.db
REDIS_URL=redis://localhost:6379/0

# 安全配置
SECRET_KEY=your-secret-key
JWT_SECRET=your-jwt-secret

# RAG 配置
QDRANT_URL=http://localhost:6334
EMBEDDING_MODEL=BAAI/bge-m3
EMBEDDING_BASE_URL=https://api.siliconflow.cn/v1
EMBEDDING_API_KEY=your-api-key

# Composio 配置（可选）
COMPOSIO_API_KEY=your-composio-api-key
```

### 运行

```bash
# 开发模式
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用启动脚本
./restart_server.sh
```

### 访问

- API 文档: http://localhost:8000/docs
- 健康检查: http://localhost:8000/health
- Composio 状态: http://localhost:8000/api/tools/composio/status

## 📁 项目结构

```
python-backend/
├── src/                      # 源代码
│   ├── main.py              # FastAPI 应用入口
│   ├── models.py            # 数据模型
│   ├── config.py            # 配置管理
│   ├── database.py          # 数据库管理
│   ├── crew_manager.py      # CrewAI 管理器
│   ├── crew_manager_optimized.py  # 优化的 CrewAI 管理器
│   ├── composio_integration.py    # Composio 集成
│   ├── rag_manager.py       # RAG 管理器
│   ├── copilot_stream.py    # Copilot 流式响应
│   ├── simplified_auth.py   # 简化认证系统
│   └── websocket_manager.py # WebSocket 管理
├── requirements.txt         # Python 依赖
├── README.md               # 项目说明
└── .env                    # 环境配置（需创建）
```

## 🔧 核心功能

### 智能体管理 API

- `POST /api/agents` - 创建智能体
- `GET /api/agents` - 列出智能体
- `GET /api/agents/{id}` - 获取智能体详情
- `PUT /api/agents/{id}` - 更新智能体
- `DELETE /api/agents/{id}` - 删除智能体
- `POST /api/agents/create` - 快速创建智能体
- `POST /api/agents/{id}/interact` - 与智能体交互

### Composio 工具 API

- `GET /api/tools/composio/status` - 获取 Composio 状态
- `GET /api/tools/composio/toolkits` - 列出所有工具包
- `GET /api/tools/composio/apps/{app_name}` - 获取应用工具
- `GET /api/tools/composio/category/{category}` - 按分类获取工具

### Copilot 流式响应

- `POST /api/copilot/stream` - 创建流式响应任务
- `GET /api/copilot-stream-response/{stream_id}` - 获取流式响应（SSE）

### 认证 API

- `GET /auth/profile` - 获取用户信息（支持可选认证）

## 🔐 认证

项目使用简化的认证系统，支持：

- JWT Token 认证
- 可选认证（某些端点）
- 默认用户支持

## 📊 监控

- 基础指标收集
- 健康检查端点
- 系统统计端点

## 🛠️ 开发

### 添加新功能

1. 在 `src/` 目录下创建新模块
2. 在 `src/main.py` 中注册路由
3. 更新 `requirements.txt` 如果需要新依赖

### 测试

```bash
# 运行基础测试
python -m pytest tests/

# 运行特定测试
python -m pytest tests/test_agents.py
```

## 🐳 Docker 部署

```bash
docker-compose up -d
```

## 📝 注意事项

1. **Qdrant 配置**：确保 Qdrant 运行在正确端口（默认 6334）
2. **嵌入模型**：使用硅基流动的 BAAI/bge-m3 模型
3. **API Key**：确保所有必需的 API Key 已配置
4. **数据源处理**：需要运行 rag-worker 服务来处理数据源

## 🔗 相关资源

- [Rowboat 官方文档](https://docs.rowboatlabs.com)
- [CrewAI 文档](https://docs.crewai.com)
- [Composio 文档](https://docs.composio.dev)
- [FastAPI 文档](https://fastapi.tiangolo.com)

## 📄 许可证

MIT License

## 👤 作者

wu-xiaochen

## 🙏 致谢

- Rowboat Labs 团队
- CrewAI 项目
- Composio 团队

