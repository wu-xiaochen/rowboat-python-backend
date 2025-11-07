# GitHub 仓库设置指南

## 创建仓库

### 步骤 1: 在 GitHub 上创建新仓库

1. 访问 https://github.com/new
2. 填写以下信息：
   - **Repository name**: `rowboat-python-backend`
   - **Description**: `Rowboat AI Agent Management Platform - Complete Python Backend Implementation`
   - **Visibility**: Public
   - **不要**勾选以下选项：
     - ❌ Add a README file
     - ❌ Add .gitignore
     - ❌ Choose a license
   （这些文件我们已经准备好了）

3. 点击 **Create repository**

### 步骤 2: 连接本地仓库到 GitHub

创建仓库后，GitHub 会显示推送命令。运行以下命令：

```bash
cd /Users/xiaochenwu/rowboat-py

# 添加远程仓库
git remote add origin https://github.com/wu-xiaochen/rowboat-python-backend.git

# 重命名分支为 main（如果需要）
git branch -M main

# 推送代码
git push -u origin main
```

### 步骤 3: 验证

访问 https://github.com/wu-xiaochen/rowboat-python-backend 确认代码已上传。

## 或者使用 SSH

如果配置了 SSH 密钥：

```bash
git remote add origin git@github.com:wu-xiaochen/rowboat-python-backend.git
git push -u origin main
```

## 后续更新

```bash
git add -A
git commit -m "更新说明"
git push
```
