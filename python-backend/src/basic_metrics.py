"""
基础监控指标系统
简化版本的prometheus指标收集
"""

import psutil
import time
import json
from datetime import datetime
from typing import Dict, Any, Optional
import threading
from prometheus_client import Counter, Histogram, Gauge, generate_latest, CONTENT_TYPE_LATEST

class BasicMetricsCollector:
    """基础指标收集器"""

    def __init__(self):
        # HTTP请求指标
        self.http_requests_total = Counter(
            'http_requests_total',
            'Total HTTP requests',
            ['method', 'endpoint', 'status']
        )

        self.http_request_duration = Histogram(
            'http_request_duration_seconds',
            'HTTP request duration in seconds',
            ['method', 'endpoint']
        )

        # 应用指标
        self.active_agents = Gauge('rowboat_active_agents_total', 'Total number of active agents')
        self.active_conversations = Gauge('rowboat_active_conversations_total', 'Total number of active conversations')
        self.llm_requests_total = Counter('rowboat_llm_requests_total', 'Total LLM requests')
        self.database_queries_total = Counter('rowboat_database_queries_total', 'Total database queries')
        self.websocket_messages_total = Counter('rowboat_websocket_messages_total', 'Total WebSocket messages')
        self.errors_total = Counter('rowboat_errors_total', 'Total errors', ['error_type'])

        # 系统指标
        self.cpu_usage = Gauge('rowboat_cpu_usage_percent', 'CPU usage percentage')
        self.memory_usage = Gauge('rowboat_memory_usage_percent', 'Memory usage percentage')
        self.disk_usage = Gauge('rowboat_disk_usage_percent', 'Disk usage percentage')

        # 初始化系统监控线程
        self._start_system_monitoring()

    def _start_system_monitoring(self):
        """启动系统监控线程"""
        def monitor_system():
            while True:
                try:
                    # 更新系统指标
                    self.cpu_usage.set(psutil.cpu_percent(interval=1))
                    self.memory_usage.set(psutil.virtual_memory().percent)
                    self.disk_usage.set(psutil.disk_usage('/').percent)
                    time.sleep(30)  # 每30秒更新一次
                except Exception:
                    pass

        monitor_thread = threading.Thread(target=monitor_system, daemon=True)
        monitor_thread.start()

    def record_request(self, method: str, endpoint: str, status: int, duration: float):
        """记录HTTP请求"""
        self.http_requests_total.labels(method=method, endpoint=endpoint, status=status).inc()
        self.http_request_duration.labels(method=method, endpoint=endpoint).observe(duration)

    def record_llm_request(self, model: str = "unknown"):
        """记录LLM请求"""
        self.llm_requests_total.inc()

    def record_database_query(self, query_type: str = "select"):
        """记录数据库查询"""
        self.database_queries_total.inc()

    def record_websocket_message(self, message_type: str = "unknown"):
        """记录WebSocket消息"""
        self.websocket_messages_total.inc()

    def record_error(self, error_type: str = "unknown"):
        """记录错误"""
        self.errors_total.labels(error_type=error_type).inc()

    def update_active_agents(self, count: int):
        """更新活跃智能体数量"""
        self.active_agents.set(count)

    def update_active_conversations(self, count: int):
        """更新活跃对话数量"""
        self.active_conversations.set(count)

    def get_metrics_content(self) -> str:
        """获取指标内容"""
        try:
            return generate_latest().decode('utf-8')
        except Exception as e:
            # 如果prometheus客户端失败，返回基础文本格式
            return self._generate_basic_metrics()

    def _generate_basic_metrics(self) -> str:
        """生成基础文本格式的指标"""
        try:
            metrics = []

            # 基础服务状态
            metrics.append("# Rowboat Basic Metrics")
            metrics.append("rowboat_service_status{service=\"python-backend\"} 1.0")
            metrics.append(f"rowboat_uptime_seconds {int(time.time() - self._start_time)}")

            # 系统指标
            metrics.append(f"rowboat_cpu_usage_percent {psutil.cpu_percent()}")
            metrics.append(f"rowboat_memory_usage_percent {psutil.virtual_memory().percent}")
            metrics.append(f"rowboat_disk_usage_percent {psutil.disk_usage('/').percent}")

            # 基础应用指标
            metrics.append(f"# HTTP requests total")
            metrics.append("rowboat_http_requests_total 0")

            return "\n".join(metrics)
        except:
            return "# Error generating metrics\nrowboat_service_status 1.0"

    def get_system_stats(self) -> Dict[str, Any]:
        """获取系统统计信息"""
        try:
            return {
                "timestamp": datetime.utcnow().isoformat(),
                "service_status": "running",
                "cpu_percent": psutil.cpu_percent(),
                "memory_percent": psutil.virtual_memory().percent,
                "disk_percent": psutil.disk_usage('/').percent,
                "active_agents": self.active_agents._value,
                "active_conversations": self.active_conversations._value,
                "total_requests": sum([sample.value for sample in self.http_requests_total.collect()[0].samples]),
                "uptime_seconds": int(time.time() - self._start_time)
            }
        except Exception as e:
            return {
                "error": f"Failed to get system stats: {str(e)}",
                "timestamp": datetime.utcnow().isoformat()
            }

    def reset_system_data(self):
        """重置系统监控数据"""
        self.active_agents.set(0)
        self.active_conversations.set(0)
        self._start_time = time.time()

# 初始化全局基本指标收集器
basic_metrics = BasicMetricsCollector()

class BasicHealthChecker:
    """基础健康检查器"""

    def __init__(self):
        self.checks = []

    def add_check(self, name: str, check_func):
        """添加健康检查"""
        self.checks.append({"name": name, "func": check_func})

    async def check_all(self) -> Dict[str, Any]:
        """执行所有健康检查"""
        health_status = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "service": "rowboat-python-backend",
            "version": "1.0.0",
            "checks": {}
        }

        for check in self.checks:
            try:
                result = await check["func"]()
                health_status["checks"][check["name"]] = result
            except Exception as e:
                health_status["checks"][check["name"]] = {
                    "status": "error",
                    "error": str(e)
                }
                health_status["status"] = "unhealthy"

        return health_status

# 基础健康检查实例
basic_health_checker = BasicHealthChecker()