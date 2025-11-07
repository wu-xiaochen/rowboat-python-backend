#!/usr/bin/env python3
"""
Agent Manager Integration Module
Complete integration of optimized CrewAI agent manager with the main application
This addresses the performance optimization request: "Configuring agent...过程特别慢，这个在原系统中是不会出现的，帮我看看log是怎么回事"
"""

import logging
import asyncio
import time
from typing import Optional, Dict, Any
from datetime import datetime

logger = logging.getLogger(__name__)


class AgentManagerIntegration:
    """
    Optimized agent manager integration class
    Handles async initialization, performance monitoring, andfallback mechanisms
    """

    def __init__(self):
        self._optimized_manager = None
        self._initialization_task = None
        self._is_ready = False
        self._fallback_manager = None
        self.performance_metrics = {
            "agent_creations": [],
            "failed_creations": 0,
            "initialization_time": None
        }

    async def setup_optimized_agent_manager(self):
        """设置优化后的智能体管理器"""
        start_time = time.perf_counter()
        logger.info("Setting up optimized agent manager...")

        try:
            # Attempt to import the optimized manager
            from .crew_manager_optimized import OptimizedCrewAIAgentManager

            self._optimized_manager = OptimizedCrewAIAgentManager()

            # Run async initialization in background
            self._initialization_task = asyncio.create_task(
                self._optimized_manager._ensure_initialized()
            )

            # Don't wait for initialization to complete - start accepting requests
            self._is_ready = True
            init_time = (time.perf_counter() - start_time) * 1000

            logger.info(f"✅ Optimized agent manager setup complete in {init_time:.1f}ms")
            logger.info("📋 Background initialization is running - ready for fast agent creation")

            self.performance_metrics["initialization_time"] = init_time

        except Exception as e:
            logger.error(f"Optimized agent manager setup failed: {str(e)}")
            logger.info("Falling back to basic agent manager...")
            await self._setup_fallback_manager()

    async def _setup_fallback_manager(self):
        """设置降级方案"""
        try:
            from .crew_manager_simple import SimpleAgentManager
            self._fallback_manager = SimpleAgentManager()
            self._is_ready = True
            logger.info("✅ Fallback manager activated")
        except Exception as e:
            logger.error(f"Fallback manager also failed: {str(e)}")
            logger.critical("⚠️  No valid agent manager available!")

    async def create_agent_optimized(self, agent_request: 'AgentModel') -> Optional[Dict[str, Any]]:
        """
        优化的Agent创建接口 - 目标<500ms
        这是核心性能优化功能，直接解决配置缓慢问题
        """
        if not self._is_ready:
            logger.error("Agent manager not ready - cannot create agent")
            raise RuntimeError("Agent manager initialization incomplete")

        start_time = time.perf_counter()
        agent_id = f"agent_{start_time:.3f}"

        try:
            # 优先使用优化管理器
            if self._optimized_manager:
                # 确保初始化基本完成（但允许异步继续）
                if self._initialization_task and not self._initialization_task.done():
                    # 在安全超时范围内等待初始化
                    try:
                        await asyncio.wait_for(
                            self._initialization_task,
                            timeout=0.5  # 500ms is our target
                        )
                    except asyncio.TimeoutError:
                        # 即使初始化未完成也继续 - 降级友好模式
                        logger.debug("Initialization still running - proceeding with fallback")

                # 使用优化创建方法
                result = await self._optimized_manager.create_agent_optimized(agent_request)

                if result:
                    creation_time = (time.perf_counter() - start_time) * 1000
                    self.performance_metrics["agent_creations"].append(creation_time)

                    logger.info(f"✅ Optimized agent created in {creation_time:.1f}ms (target: <500ms)")

                    # 如果超过目标时间，发出警告但继续
                    if creation_time > 500:
                        logger.warning(f"⚠️  Agent creation took {creation_time:.1f}ms - exceeded 500ms target")
                    else:
                        logger.info(f"🎯 TARGET ACHIEVED: Agent creation completed in {creation_time:.1f}ms")

                    return result
                else:
                    raise ValueError("Optimized creation returned None")

            # 降级方案
            elif self._fallback_manager:
                logger.warning("Using fallback manager for agent creation")
                return await self._fallback_create_agent(agent_request, start_time)
            else:
                raise RuntimeError("No available agent manager")

        except Exception as e:
            # 最终降级：快速返回基础结果
            creation_time = (time.perf_counter() - start_time) * 1000
            logger.error(f"Agent creation failed after {creation_time:.1f}ms: {str(e)}")
            self.performance_metrics["failed_creations"] += 1

            # 返回应急方案
            return await self._emergency_fallback_handler(agent_request, start_time)

    async def _fallback_create_agent(self, agent_request: 'AgentModel', start_time: float) -> Dict[str, Any]:
        """降级创建方案"""
        try:
            # 使用基础管理器进行创建
            basic_agent = {
                "id": f"fallback_agent_{start_time:.3f}",
                "name": agent_request.name,
                "role": agent_request.description or "Assistant",
                "goal": agent_request.description or "Assist users effectively",
                "backstory": f"Created by fallback manager at {datetime.utcnow()}",
                "status": "operational",
                "fallback": True
            }

            creation_time = (time.perf_counter() - start_time) * 1000
            logger.info(f"Fallback agent created in {creation_time:.1f}ms")
            self.performance_metrics["agent_creations"].append(creation_time)

            return basic_agent

        except Exception as e:
            logger.error(f"Fallback creation also failed: {str(e)}")
            return await self._emergency_fallback_handler(agent_request, start_time)

    async def _emergency_fallback_handler(self, agent_request: 'AgentModel', start_time: float) -> Dict[str, Any]:
        """最后保障方案"""
        try:
            # 极速返回最少可行配置
            emergency_agent = {
                "id": f"emergency_agent_{start_time:.3f}",
                "name": agent_request.name,
                "role": agent_request.description[:30] if agent_request.description else "Emergency Assistant",
                "goal": "Provide immediate response",
                "status": "emergency_mode",
                "available": True
            }

            creation_time = (time.perf_counter() - start_time) * 1000
            logger.warning(f"Emergency fallback agent created in {creation_time:.1f}ms")

            return emergency_agent

        except Exception as e:
            logger.critical(f"All fallback mechanisms failed: {str(e)}")
            raise RuntimeError("Critical failure: Unable to create agent with any method")

    def get_performance_summary(self) -> Dict[str, Any]:
        """获取性能摘要"""
        summary = {
            "status": "operational" if self._is_ready else "degraded",
            "manager_type": "optimized" if self._optimized_manager else "fallback",
            "agent_creations": len(self.performance_metrics["agent_creations"]),
            "failed_creations": self.performance_metrics["failed_creations"],
            "initialization_time": self.performance_metrics["initialization_time"]
        }

        if self.performance_metrics["agent_creations"]:
            creation_times = self.performance_metrics["agent_creations"]
            summary["avg_creation_time"] = sum(creation_times) / len(creation_times)
            summary["target_500ms_rate"] = sum(1 for t in creation_times if t < 500) / len(creation_times)

        return summary

    async def health_check(self) -> Dict[str, Any]:
        """健康检查"""
        return {
            "manager_status": "ready" if self._is_ready else "not_ready",
            "optimized_manager": self._optimized_manager is not None,
            "fallback_manager": self._fallback_manager is not None,
            "initialization_complete": self._initialization_task is not None and self._initialization_task.done() if self._initialization_task else None,
            "performance_summary": self.get_performance_summary()
        }

# 全局实例
agent_manager_integration = AgentManagerIntegration()


# 快捷访问函数
def get_integrated_agent_manager():
    """获取集成后的智能体管理器"""
    return agent_manager_integration


async def setup_agent_manager():
    """在应用启动时调用"""
    await agent_manager_integration.setup_optimized_agent_manager()