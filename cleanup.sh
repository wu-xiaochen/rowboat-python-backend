#!/bin/bash
# 清理脚本：删除测试脚本和临时报告

echo "🧹 开始清理项目..."

# 删除根目录下的临时报告文件
echo "删除根目录临时报告..."
rm -f *_FIX*.md
rm -f *_ANALYSIS*.md
rm -f *_STATUS*.md
rm -f *_SUMMARY*.md
rm -f *_REPORT*.md
rm -f *_PLAN*.md
rm -f COMPARISON_*.md
rm -f ROOT_CAUSE_*.md
rm -f SKIPPER_*.md
rm -f RESTART_*.md
rm -f targeted_*.py
rm -f rowboat.tar.gz

# 删除 python-backend 中的测试脚本
echo "删除测试脚本..."
cd python-backend
rm -f test_*.py
rm -f *_test.py
rm -f debug_*.py
rm -f demo_*.py
rm -f example_*.py
rm -f simple_test.py
rm -f comprehensive_test.py
rm -f performance_*.py
rm -f final_*.py
rm -f core_*.py
rm -f agent_performance_test.py
rm -f monitor_requests.sh

# 删除测试报告
rm -f *test_report*.json
rm -f *.json.report

# 删除临时日志
rm -f *.log
rm -f *.pid
rm -f server*.log
rm -f python_backend.log

# 删除临时数据库
rm -f *.db

# 删除临时配置文件
rm -f config_auth_system.py
rm -f enable_*.py
rm -f setup_*.py
rm -f migrate_data.py

# 删除临时文档
rm -f *_FIX*.md
rm -f *_ANALYSIS*.md
rm -f *_STATUS*.md
rm -f *_SUMMARY*.md
rm -f *_REPORT*.md
rm -f COMPOSIO_*.md
rm -f DEPLOYMENT_*.md
rm -f MIGRATION_*.md
rm -f ROLLBACK_*.md
rm -f OPERATIONAL_*.md
rm -f PERFORMANCE_*.md
rm -f PROJECT_*.md
rm -f FRONTEND_*.md
rm -f ADVANCED_*.md
rm -f current_system_status.md

# 删除测试 HTML
rm -f test_frontend_integration.html

cd ..

# 删除 rowboat-main 目录（如果只是备份）
# rm -rf rowboat-main

echo "✅ 清理完成！"
