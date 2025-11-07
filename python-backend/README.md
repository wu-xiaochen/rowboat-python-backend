# Rowboat Python Backend

完整的 Rowboat AI Agent 管理平台 Python 后端实现。

## 🚀 快速开始

### 安装依赖

```bash
pip install -r requirements.txt
```

### 配置环境变量

创建 `.env` 文件并配置必要的环境变量（参考根目录 README.md）。

### 启动服务

```bash
# 开发模式
python -m uvicorn src.main:app --host 0.0.0.0 --port 8000 --reload

# 或使用启动脚本
./restart_server.sh
```

## 📁 核心模块

- `src/main.py` - FastAPI 应用主入口
- `src/models.py` - 数据模型定义
- `src/config.py` - 配置管理
- `src/database.py` - 数据库管理
- `src/crew_manager*.py` - CrewAI 智能体管理
- `src/composio_integration.py` - Composio 工具集成
- `src/rag_manager.py` - RAG 知识库管理
- `src/copilot_stream.py` - Copilot 流式响应
- `src/simplified_auth.py` - 认证系统

## 🔧 功能特性

- ✅ 智能体管理和交互
- ✅ Composio 工具集成（800+ 工具包）
- ✅ RAG 知识库（Qdrant + BAAI/bge-m3）
- ✅ 流式响应支持
- ✅ 数据源处理
- ✅ 简化认证系统

详细信息请参考根目录 README.md。
