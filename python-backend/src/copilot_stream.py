"""
Copilot 流式响应模块
实现与原始 TypeScript 实现兼容的流式响应
"""
import asyncio
import json
import logging
from typing import Dict, List, Optional, Any, AsyncGenerator
from datetime import datetime
from uuid import uuid4

from langchain_openai import ChatOpenAI
from langchain.schema import BaseMessage, HumanMessage, AIMessage, SystemMessage
from langchain.callbacks.base import AsyncCallbackHandler

from .config import settings

logger = logging.getLogger(__name__)


class StreamCallbackHandler(AsyncCallbackHandler):
    """流式回调处理器"""
    
    def __init__(self):
        self.queue = asyncio.Queue()
        self.tokens = []
    
    async def on_llm_new_token(self, token: str, **kwargs) -> None:
        """接收新的 token"""
        await self.queue.put({
            "type": "text-delta",
            "content": token
        })
        self.tokens.append(token)
    
    async def get_next_event(self):
        """获取下一个事件"""
        try:
            return await asyncio.wait_for(self.queue.get(), timeout=0.1)
        except asyncio.TimeoutError:
            return None


class CopilotStreamManager:
    """Copilot 流式响应管理器"""
    
    def __init__(self):
        self.cache: Dict[str, Dict[str, Any]] = {}
        self._llm = None
        logger.info("CopilotStreamManager initialized")
    
    def _get_llm(self):
        """延迟初始化 LLM - 使用正确的模型配置"""
        if self._llm is None:
            # 注意：streaming 参数应该在调用时传递，而不是在初始化时
            # 使用 model 而不是 model_name（model_name 已弃用）
            logger.info(f"Initializing Copilot LLM with model: {settings.provider_copilot_model}")
            self._llm = ChatOpenAI(
                api_key=settings.provider_api_key,
                base_url=settings.provider_base_url,
                model=settings.provider_copilot_model,  # 使用 model 而不是 model_name
                temperature=0.3,
                max_tokens=16000,  # 增加 max_tokens 避免截断（原始实现使用更大的值）
            )
        return self._llm
    
    @property
    def llm(self):
        """LLM 属性，延迟初始化"""
        return self._get_llm()
    
    def create_stream(self, stream_id: str, request_data: Dict[str, Any]):
        """创建新的流式响应任务"""
        self.cache[stream_id] = {
            "data": request_data,
            "created_at": datetime.utcnow(),
            "status": "pending"
        }
        logger.info(f"Created copilot stream: {stream_id}")
        return stream_id
    
    def get_stream_data(self, stream_id: str) -> Optional[Dict[str, Any]]:
        """获取流式响应数据"""
        return self.cache.get(stream_id)
    
    def delete_stream(self, stream_id: str):
        """删除流式响应"""
        if stream_id in self.cache:
            del self.cache[stream_id]
            logger.info(f"Deleted copilot stream: {stream_id}")
    
    async def generate_stream_response(
        self, 
        stream_id: str,
        messages: List[Dict[str, Any]],
        workflow: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        data_sources: Optional[List[Dict[str, Any]]] = None
    ) -> AsyncGenerator[Dict[str, Any], None]:
        """生成流式响应"""
        try:
            logger.info(f"Starting stream generation for {stream_id}")
            
            # 构建系统提示
            system_prompt = self._build_system_prompt(workflow, context, data_sources)
            
            # 构建消息列表
            langchain_messages = [
                SystemMessage(content=system_prompt)
            ]
            
            # 转换消息格式
            for msg in messages:
                role = msg.get("role", "user")
                content = msg.get("content", "")
                if role == "user":
                    langchain_messages.append(HumanMessage(content=content))
                elif role == "assistant":
                    langchain_messages.append(AIMessage(content=content))
            
            # 创建流式回调
            callback_handler = StreamCallbackHandler()
            
            # 使用流式调用
            logger.info(f"Starting LLM stream for {stream_id}")
            
            # 直接使用 LangChain 的流式调用
            try:
                logger.info(f"Starting LLM stream generation for {stream_id}, messages: {len(langchain_messages)}")
                
                # 直接使用 astream，它会自动处理流式响应
                # 注意：LangChain 的 astream 需要 streaming=True 在调用时设置
                stream_completed = False
                token_count = 0
                
                async for chunk in self.llm.astream(langchain_messages, callbacks=[callback_handler]):
                    # chunk 是 AIMessageChunk 或类似的流式块
                    # 通过 callback_handler 已经处理了 token
                    token_count += 1
                    
                    # 同时从队列中获取事件并立即发送
                    while True:
                        try:
                            event = await asyncio.wait_for(callback_handler.queue.get(), timeout=0.01)
                            if event:
                                yield event
                                # 如果是完成或错误事件，退出
                                if event.get("type") in ["done", "error"]:
                                    stream_completed = True
                                    break
                        except asyncio.TimeoutError:
                            break
                    
                    if stream_completed:
                        break
                
                logger.info(f"LLM stream completed for {stream_id}, tokens: {token_count}, total: {len(callback_handler.tokens)}")
                
                # 流式调用完成，等待所有剩余事件
                await asyncio.sleep(0.2)  # 等待所有回调事件完成
                
                # 发送剩余的事件
                while True:
                    try:
                        event = await asyncio.wait_for(callback_handler.queue.get(), timeout=0.1)
                        if event:
                            yield event
                            if event.get("type") in ["done", "error"]:
                                break
                    except asyncio.TimeoutError:
                        break
                
                # 发送完成事件
                logger.info(f"Sending done event for {stream_id}")
                yield {
                    "type": "done"
                }
                
            except Exception as e:
                logger.error(f"Error in LLM stream: {str(e)}")
                yield {
                    "type": "error",
                    "error": str(e)
                }
            
            logger.info(f"Stream generation completed for {stream_id}")
            
        except Exception as e:
            logger.error(f"Error generating stream response: {str(e)}")
            yield {
                "type": "error",
                "error": str(e)
            }
    
    def _build_system_prompt(
        self,
        workflow: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None,
        data_sources: Optional[List[Dict[str, Any]]] = None
    ) -> str:
        """构建系统提示"""
        prompt_parts = [
            "You are Rowboat Copilot, an expert AI assistant specialized in helping users create, configure, and manage AI agents and workflows.",
            "",
            "## Current Workflow Configuration:",
            json.dumps(workflow, indent=2),
        ]
        
        if context:
            context_type = context.get("type", "")
            context_name = context.get("name", "")
            if context_type == "agent":
                prompt_parts.append(f"\n## Current Context: Working on agent '{context_name}'")
            elif context_type == "tool":
                prompt_parts.append(f"\n## Current Context: Working on tool '{context_name}'")
        
        if data_sources:
            prompt_parts.append("\n## Available Data Sources:")
            for ds in data_sources:
                prompt_parts.append(f"- {ds.get('name', 'Unknown')}: {ds.get('description', '')}")
        
        prompt_parts.append("\nProvide helpful guidance on building agents, workflows, or solving problems.")
        
        return "\n".join(prompt_parts)


# 全局实例
copilot_stream_manager = CopilotStreamManager()

