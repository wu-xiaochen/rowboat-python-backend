# 修复数据源删除循环问题

## 问题根源

1. **Qdrant Collection 不存在**
   - Collection `embeddings` 不存在
   - 删除操作失败

2. **rag-worker 错误处理不当**
   - 删除失败后，将状态改回 `pending`
   - 导致数据源重新进入处理队列
   - 形成无限循环

3. **前端轮询**
   - 前端不断刷新 `pending` 状态的数据源
   - 导致数据源循环出现

## 解决方案

### 1. 创建 Qdrant Collection

首先需要创建 `embeddings` collection：

```bash
curl -X PUT "http://localhost:6334/collections/embeddings" \
  -H "Content-Type: application/json" \
  -d '{
    "vectors": {
      "size": 1024,
      "distance": "Cosine"
    }
  }'
```

### 2. 修复 rag-worker 错误处理

需要修改 `rag-worker.ts` 中的删除逻辑：
- 检查 collection 是否存在
- 如果不存在，跳过删除 embeddings 步骤
- 继续删除 MongoDB 中的数据
- 即使部分删除失败，也要完成删除操作

### 3. 清理卡住的数据源

需要手动清理状态异常的数据源。

