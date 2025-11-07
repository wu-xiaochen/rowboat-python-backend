# 数据源处理问题诊断与修复

## 问题描述
用户创建了一个数据源"采购商知识"，状态一直处于 "processing"，说明数据源处理卡住了。

## 问题分析

### 1. rag-worker 未运行
- **现象**：`rag-worker` 容器已退出（Exited (1) 2 days ago）
- **原因**：
  - `docker-compose.yml` 中 `rag-worker` 服务引用了未定义的 `uploads` volume
  - `rag-worker` 无法连接到 MongoDB（`getaddrinfo ENOTFOUND mongo`），因为它需要在 Docker 网络中运行
- **影响**：数据源处理依赖 `rag-worker` 后台进程，它负责：
  - 从 MongoDB 轮询待处理的数据源任务
  - 加载文件/URL/文本
  - 切片处理
  - 生成嵌入向量
  - 存储到 Qdrant

### 2. Qdrant 端口配置错误
- **现象**：Python 后端配置的 `QDRANT_URL` 是 `http://localhost:6333`
- **实际**：Qdrant 容器映射到 `6334:6333`（外部端口 6334，内部端口 6333）
- **影响**：Python 后端无法连接到 Qdrant，导致无法存储嵌入向量
- **修复**：已更新 `python-backend/src/config.py` 中的 `qdrant_url` 为 `http://localhost:6334`

### 3. 向量维度可能不匹配
- **当前配置**：`create_collection` 使用默认的 `vector_size=1536`
- **BAAI/bge-m3 模型**：实际向量维度可能是 1024（需要确认）
- **影响**：如果维度不匹配，会导致嵌入向量无法正确存储

## 修复方案

### 修复 1: 启动 rag-worker
```bash
# 1. 修复 docker-compose.yml，添加 uploads volume 定义
# 2. 确保 rag-worker 在同一网络中运行
cd /Users/xiaochenwu/Desktop/rowboat
docker-compose --profile rag-worker up -d rag-worker
```

### 修复 2: 验证 Qdrant 连接
```bash
# 测试 Qdrant 连接
curl http://localhost:6334/collections
```

### 修复 3: 确认 BAAI/bge-m3 向量维度
- 需要测试 BAAI/bge-m3 模型的实际输出维度
- 如果维度是 1024，需要更新 `rag_manager.py` 中的 `create_collection` 默认值

## 原始实现流程

根据 `rag-worker.ts` 的实现，数据源处理流程：

1. **前端创建数据源**：
   - 调用 `createDataSource` Server Action
   - 数据源状态设置为 `"pending"`
   - 文档添加到 MongoDB

2. **rag-worker 轮询**：
   - 每 5 秒轮询一次 MongoDB
   - 查找状态为 `"pending"` 的数据源
   - 使用 `pollPendingJob()` 获取任务

3. **处理流程**：
   - 对于文件：使用 OpenAI/Gemini 提取文本 → 切片 → 嵌入 → 存储到 Qdrant
   - 对于 URL：使用 Firecrawl 抓取 → 切片 → 嵌入 → 存储到 Qdrant
   - 对于文本：直接切片 → 嵌入 → 存储到 Qdrant

4. **完成处理**：
   - 更新文档状态为 `"ready"`
   - 更新数据源状态为 `"ready"` 或 `"error"`

## 下一步

1. ✅ 修复 Python 后端的 Qdrant 端口配置
2. ⏳ 修复 docker-compose.yml 的 volume 定义
3. ⏳ 启动 rag-worker 服务
4. ⏳ 验证数据源处理流程
5. ⏳ 确认 BAAI/bge-m3 向量维度

