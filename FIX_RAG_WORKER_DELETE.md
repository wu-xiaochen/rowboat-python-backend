# 修复 rag-worker 删除逻辑

## 问题

rag-worker 在删除数据源时，如果 Qdrant collection 不存在，会抛出错误，导致删除操作失败，数据源状态被改回 `pending`，形成循环。

## 当前代码问题

```typescript
if (job.status === "deleted") {
    // delete all embeddings for this source
    logger.log("Deleting embeddings from Qdrant");
    await qdrantClient.delete("embeddings", {
        filter: {
            must: [
                { key: "projectId", match: { value: job.projectId } },
                { key: "sourceId", match: { value: job.id } },
            ],
        },
    });
    // ... 后续删除操作
}
```

如果 `qdrantClient.delete` 失败（例如 collection 不存在），会抛出异常，被外层的 catch 捕获，导致状态被改回 `error` 或 `pending`。

## 修复方案

需要修改删除逻辑，添加错误处理：

```typescript
if (job.status === "deleted") {
    // delete all embeddings for this source
    try {
        logger.log("Deleting embeddings from Qdrant");
        await qdrantClient.delete("embeddings", {
            filter: {
                must: [
                    { key: "projectId", match: { value: job.projectId } },
                    { key: "sourceId", match: { value: job.id } },
                ],
            },
        });
        logger.log("Embeddings deleted from Qdrant");
    } catch (e: any) {
        // 如果 collection 不存在或删除失败，记录警告但继续删除其他数据
        if (e.message?.includes("doesn't exist") || e.status === 404) {
            logger.log("Qdrant collection doesn't exist, skipping embeddings deletion");
        } else {
            logger.log("Error deleting embeddings (continuing with other deletions):", e.message);
        }
    }

    // delete all docs for this source
    logger.log("Deleting docs from db");
    await dataSourceDocsRepository.deleteBySourceId(job.id);

    // delete the source record from db
    logger.log("Deleting source record from db");
    await dataSourcesRepository.delete(job.id);

    logger.log("Job deleted");
    continue;
}
```

关键改进：
1. 将 Qdrant 删除操作包装在 try-catch 中
2. 如果 collection 不存在（404 错误），记录警告但继续执行
3. 即使 Qdrant 删除失败，也要继续删除 MongoDB 中的数据
4. 确保数据源记录被删除，避免循环

## 临时解决方案

由于无法直接修改 Docker 容器中的代码，可以：
1. 手动创建 Qdrant collection（已完成 ✅）
2. 手动清理卡住的数据源
3. 等待 rag-worker 处理完当前任务

