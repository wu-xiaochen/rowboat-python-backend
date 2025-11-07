"""
监控和指标收集模块
"""

import time
import logging
from functools import wraps
from typing import Callable, Any
from prometheus_client import Counter, Histogram, Gauge, generate_latest
from fastapi import Request, Response
from datetime import datetime

# 配置日志
logger = logging.getLogger(__name__)

# Prometheus指标
REQUEST_COUNT = Counter(
    'rowboat_requests_total',
    'Total requests',
    ['method', 'endpoint', 'status']
)

REQUEST_DURATION = Histogram(
    'rowboat_request_duration_seconds',
    'Request duration',
    ['method', 'endpoint']
)

ACTIVE_CONNECTIONS = Gauge(
    'rowboat_active_connections',
    'Number of active WebSocket connections'
)

AGENT_COUNT = Gauge(
    'rowboat_agents_total',
    'Total number of agents'
)

CONVERSATION_COUNT = Gauge(
    'rowboat_conversations_total',
    'Total number of conversations'
)

MESSAGE_COUNT = Counter(
    'rowboat_messages_total',
    'Total messages processed',
    ['role']  # user, assistant
)

LLM_REQUEST_DURATION = Histogram(
    'rowboat_llm_request_duration_seconds',
    'LLM API request duration',
    ['model', 'provider']
)

LLM_REQUEST_COUNT = Counter(
    'rowboat_llm_requests_total',
    'Total LLM API requests',
    ['model', 'provider', 'status']
)

DATABASE_QUERY_DURATION = Histogram(
    'rowboat_database_query_duration_seconds',
    'Database query duration',
    ['operation']  # select, insert, update, delete
)

WEBSOCKET_MESSAGE_COUNT = Counter(
    'rowboat_websocket_messages_total',
    'Total WebSocket messages',
    ['type']  # connection, message, response, error
)

ERROR_COUNT = Counter(
    'rowboat_errors_total',
    'Total errors',
    ['type', 'endpoint']
)


class MetricsCollector:
    """指标收集器"""

    def __init__(self):
        self.start_time = time.time()

    def record_request(self, method: str, endpoint: str, status_code: int, duration: float):
        """记录HTTP请求指标"""
        REQUEST_COUNT.labels(
            method=method,
            endpoint=endpoint,
            status=status_code
        ).inc()

        REQUEST_DURATION.labels(
            method=method,
            endpoint=endpoint
        ).observe(duration)

    def record_llm_request(self, model: str, provider: str, duration: float, success: bool):
        """记录LLM请求指标"""
        LLM_REQUEST_DURATION.labels(
            model=model,
            provider=provider
        ).observe(duration)

        LLM_REQUEST_COUNT.labels(
            model=model,
            provider=provider,
            status='success' if success else 'error'
        ).inc()

    def record_database_query(self, operation: str, duration: float):
        """记录数据库查询指标"""
        DATABASE_QUERY_DURATION.labels(
            operation=operation
        ).observe(duration)

    def record_websocket_message(self, message_type: str):
        """记录WebSocket消息指标"""
        WEBSOCKET_MESSAGE_COUNT.labels(
            type=message_type
        ).inc()

    def record_error(self, error_type: str, endpoint: str):
        """记录错误指标"""
        ERROR_COUNT.labels(
            type=error_type,
            endpoint=endpoint
        ).inc()

    def update_gauge(self, gauge: Gauge, value: float):
        """更新仪表盘指标"""
        gauge.set(value)

    def get_uptime(self) -> float:
        """获取服务运行时间"""
        return time.time() - self.start_time


def monitor_request(func: Callable) -> Callable:
    """请求监控装饰器"""
    @wraps(func)
    async def wrapper(*args, **kwargs):
        start_time = time.time()

        try:
            # 提取请求信息
            request = None
            for arg in args:
                if isinstance(arg, Request):
                    request = arg
                    break

            if request:
                method = request.method
                endpoint = request.url.path
            else:
                method = "UNKNOWN"
                endpoint = "UNKNOWN"

            # 执行函数
            result = await func(*args, **kwargs)

            # 计算持续时间
            duration = time.time() - start_time

            # 提取响应状态码
            status_code = 200
            if isinstance(result, Response):
                status_code = result.status_code
            elif hasattr(result, 'status_code'):
                status_code = result.status_code

            # 记录指标
            from src.monitoring import metrics_collector
            metrics_collector.record_request(method, endpoint, status_code, duration)

            return result

        except Exception as e:
            # 记录错误
            duration = time.time() - start_time
            endpoint = getattr(request, 'url', {}).get('path', 'UNKNOWN') if request else 'UNKNOWN'

            from src.monitoring import metrics_collector
            metrics_collector.record_request("ERROR", endpoint, 500, duration)
            metrics_collector.record_error(type(e).__name__, endpoint)

            logger.error(f"请求监控错误: {str(e)}")
            raise

    return wrapper


def monitor_llm_request(model: str, provider: str):
    """LLM请求监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()
            success = True

            try:
                result = await func(*args, **kwargs)
                return result

            except Exception as e:
                success = False
                logger.error(f"LLM请求错误: {str(e)}")
                raise

            finally:
                duration = time.time() - start_time
                from src.monitoring import metrics_collector
                metrics_collector.record_llm_request(model, provider, duration, success)

        return wrapper
    return decorator


def monitor_database_query(operation: str):
    """数据库查询监控装饰器"""
    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            start_time = time.time()

            try:
                result = await func(*args, **kwargs)
                return result

            finally:
                duration = time.time() - start_time
                from src.monitoring import metrics_collector
                metrics_collector.record_database_query(operation, duration)

        return wrapper
    return decorator


# 全局指标收集器实例
metrics_collector = MetricsCollector()


def get_metrics() -> str:
    """获取Prometheus格式的指标数据"""
    return generate_latest()


def get_system_metrics() -> dict:
    """获取系统指标"""
    import psutil

    return {
        'uptime': metrics_collector.get_uptime(),
        'cpu_percent': psutil.cpu_percent(),
        'memory_percent': psutil.virtual_memory().percent,
        'disk_usage': psutil.disk_usage('/').percent,
        'active_connections': ACTIVE_CONNECTIONS._value.get(),
        'timestamp': datetime.now().isoformat()
    }


class HealthChecker:
    """健康检查器"""

    def __init__(self):
        self.checks = {}

    def add_check(self, name: str, check_func: Callable):
        """添加健康检查"""
        self.checks[name] = check_func

    async def check_all(self) -> dict:
        """执行所有健康检查"""
        results = {}
        overall_healthy = True

        for name, check_func in self.checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()

                results[name] = {
                    'status': 'healthy' if result else 'unhealthy',
                    'timestamp': datetime.now().isoformat()
                }

                if not result:
                    overall_healthy = False

            except Exception as e:
                results[name] = {
                    'status': 'error',
                    'error': str(e),
                    'timestamp': datetime.now().isoformat()
                }
                overall_healthy = False

        return {
            'status': 'healthy' if overall_healthy else 'unhealthy',
            'checks': results,
            'timestamp': datetime.now().isoformat()
        }


# 全局健康检查器实例
health_checker = HealthChecker()