import asyncio
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime
from uuid import uuid4

# Try to import crewai, but provide fallback if not available
try:
    from crewai import Agent, Task, Crew
    CREWAI_AVAILABLE = True
except ImportError:
    CREWAI_AVAILABLE = False
    # Create mock classes for testing
    class Agent:
        def __init__(self, **kwargs):
            self.role = kwargs.get('role', 'Assistant')
            self.goal = kwargs.get('goal', 'Help users')
            self.backstory = kwargs.get('backstory', 'An AI assistant')

    class Task:
        def __init__(self, **kwargs):
            self.description = kwargs.get('description', 'Complete task')
            self.expected_output = kwargs.get('expected_output', 'Task result')
            self.agent = kwargs.get('agent')

    class Crew:
        def __init__(self, **kwargs):
            self.agents = kwargs.get('agents', [])
            self.tasks = kwargs.get('tasks', [])

        def kickoff(self):
            # Mock implementation
            return "Task completed successfully by crew"

from langchain_openai import ChatOpenAI
from .models import Agent as AgentModel, Message, Conversation
from .config import settings

logger = logging.getLogger(__name__)


class SimpleCrewAIAgentManager:
    """
    Simplified CrewAI agent manager that works without embedchain dependency
    """

    def __init__(self):
        self.agents: Dict[str, Agent] = {}
        self.crews: Dict[str, Crew] = {}
        self.llm = ChatOpenAI(
            base_url=settings.provider_base_url,
            api_key=settings.provider_api_key,
            model=settings.provider_default_model,
            temperature=0.7
        )
        self.copilot_llm = ChatOpenAI(
            base_url=settings.provider_base_url,
            api_key=settings.provider_api_key,
            model=settings.provider_copilot_model,
            temperature=0.3,
            max_tokens=8000  # 增加 max_tokens 避免输出截断
        )

    async def create_agent(self, agent_config: AgentModel) -> Agent:
        """Create a new CrewAI agent from configuration"""
        try:
            if not CREWAI_AVAILABLE:
                logger.warning("CrewAI not available, using mock agent")
                agent = Agent(
                    role=agent_config.name,
                    goal=agent_config.description or f"Execute tasks for {agent_config.name}",
                    backstory=self._generate_backstory(agent_config)
                )
            else:
                # Create the CrewAI agent
                agent = Agent(
                    role=agent_config.name,
                    goal=agent_config.description or f"Execute tasks for {agent_config.name}",
                    backstory=self._generate_backstory(agent_config),
                    llm=self.llm,
                    tools=[],  # Will be added separately
                    verbose=True,
                    allow_delegation=True
                )

            self.agents[agent_config.id] = agent
            logger.info(f"Created agent: {agent_config.name} (ID: {agent_config.id})")
            return agent

        except Exception as e:
            logger.error(f"Failed to create agent {agent_config.name}: {str(e)}")
            raise

    def _generate_backstory(self, agent_config: AgentModel) -> str:
        """Generate agent backstory from configuration"""
        base_backstory = f"You are {agent_config.name}, an AI assistant designed to help with various tasks."

        if agent_config.description:
            base_backstory += f" {agent_config.description}"

        if agent_config.config.get("personality"):
            base_backstory += f" Your personality is: {agent_config.config['personality']}"

        if agent_config.config.get("expertise"):
            base_backstory += f" Your expertise includes: {agent_config.config['expertise']}"

        return base_backstory

    async def create_crew(self, agent_ids: List[str], task_description: str) -> Crew:
        """Create a crew with multiple agents for collaborative tasks"""
        try:
            agents = [self.agents[agent_id] for agent_id in agent_ids if agent_id in self.agents]

            if not agents:
                raise ValueError("No valid agents found for crew creation")

            if not CREWAI_AVAILABLE:
                logger.warning("CrewAI not available, using mock crew")
                crew = Crew(agents=agents, tasks=[])
            else:
                task = Task(
                    description=task_description,
                    expected_output="Complete the assigned task successfully",
                    agents=agents
                )

                crew = Crew(
                    agents=agents,
                    tasks=[task],
                    verbose=True
                )

            crew_id = str(uuid4())
            self.crews[crew_id] = crew

            logger.info(f"Created crew with {len(agents)} agents")
            return crew

        except Exception as e:
            logger.error(f"Failed to create crew: {str(e)}")
            raise

    async def execute_task(self, agent_id: str, task_description: str, context: Dict[str, Any] = None) -> str:
        """Execute a task with a specific agent"""
        try:
            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")

            agent = self.agents[agent_id]

            # Create task with context
            task_context = json.dumps(context or {})
            full_task_description = f"{task_description}\n\nContext: {task_context}"

            if not CREWAI_AVAILABLE:
                logger.warning("CrewAI not available, using mock task execution")
                # Simulate task execution with LLM
                response = self.llm.invoke(full_task_description)
                return str(response.content)

            task = Task(
                description=full_task_description,
                expected_output="Provide a helpful and accurate response",
                agent=agent
            )

            # Execute task
            crew = Crew(
                agents=[agent],
                tasks=[task],
                verbose=True
            )

            result = crew.kickoff()

            logger.info(f"Task executed by agent {agent_id}")
            return str(result)

        except Exception as e:
            logger.error(f"Failed to execute task with agent {agent_id}: {str(e)}")
            raise

    async def execute_crew_task(self, crew_id: str, task_description: str) -> str:
        """Execute a task with a crew of agents"""
        try:
            if crew_id not in self.crews:
                raise ValueError(f"Crew {crew_id} not found")

            crew = self.crews[crew_id]

            if not CREWAI_AVAILABLE:
                logger.warning("CrewAI not available, using mock crew execution")
                return "Crew task completed successfully (mock)"

            # Update task description
            crew.tasks[0].description = task_description

            result = crew.kickoff()

            logger.info(f"Task executed by crew {crew_id}")
            return str(result)

        except Exception as e:
            logger.error(f"Failed to execute task with crew {crew_id}: {str(e)}")
            raise

    async def process_conversation_message(self, conversation: Conversation, message: Message) -> str:
        """Process a message in a conversation context"""
        try:
            agent_id = conversation.agent_id

            if agent_id not in self.agents:
                raise ValueError(f"Agent {agent_id} not found")

            # Build conversation context
            context = {
                "conversation_id": conversation.id,
                "user_id": conversation.user_id,
                "context": conversation.context,
                "message_metadata": message.metadata
            }

            return await self.execute_task(agent_id, message.content, context)

        except Exception as e:
            logger.error(f"Failed to process conversation message: {str(e)}")
            raise

    async def copilot_assist(self, user_input: str, context: Dict[str, Any] = None) -> str:
        """Get assistance from the copilot agent - 修复输出截断和卡死问题"""
        try:
            if not CREWAI_AVAILABLE:
                logger.warning("CrewAI not available, using direct LLM for copilot")
                # Use direct LLM call for copilot assistance
                copilot_prompt = f"""
                You are Rowboat Copilot, an expert AI assistant specialized in helping users create, configure, and manage AI agents and workflows.

                User Request: {user_input}
                Context: {json.dumps(context or {})}

                Provide helpful guidance on building agents, workflows, or solving problems.
                """
                # 添加超时保护
                try:
                    response = await asyncio.wait_for(
                        asyncio.to_thread(self.copilot_llm.invoke, copilot_prompt),
                        timeout=120.0
                    )
                    return str(response.content)
                except asyncio.TimeoutError:
                    logger.error("Direct LLM copilot assistance timed out")
                    return "生成配置超时，请稍后重试或简化您的需求。"

            # Create a temporary copilot agent
            copilot_agent = Agent(
                role="Rowboat Copilot",
                goal="Help users build and manage AI agents",
                backstory="You are an expert AI assistant specialized in helping users create, configure, and manage AI agents and workflows.",
                llm=self.copilot_llm,
                tools=[],
                verbose=True
            )

            task_context = json.dumps(context or {})
            full_input = f"User Request: {user_input}\n\nContext: {task_context}"

            task = Task(
                description=full_input,
                expected_output="Provide helpful guidance on building agents, workflows, or solving problems",
                agent=copilot_agent
            )

            crew = Crew(
                agents=[copilot_agent],
                tasks=[task],
                verbose=True
            )

            # 修复卡死问题：使用异步执行 + 超时保护
            logger.info(f"Starting copilot assistance with timeout protection (120s)")
            try:
                result = await asyncio.wait_for(
                    asyncio.to_thread(crew.kickoff),
                    timeout=120.0  # 120 秒超时
                )
                
                # 确保完整提取结果
                if hasattr(result, 'raw'):
                    result_str = str(result.raw) if hasattr(result, 'raw') else str(result)
                elif hasattr(result, 'content'):
                    result_str = str(result.content)
                else:
                    result_str = str(result)
                
                logger.info(f"Copilot assistance completed successfully, response length: {len(result_str)}")
                return result_str
                
            except asyncio.TimeoutError:
                logger.error("Copilot assistance timed out after 120 seconds")
                return "生成配置超时，请稍后重试或简化您的需求。"
            except Exception as e:
                logger.error(f"Error during crew.kickoff(): {str(e)}")
                raise

        except Exception as e:
            logger.error(f"Copilot assistance failed: {str(e)}")
            raise

    def get_agent(self, agent_id: str) -> Optional[Agent]:
        """Get an agent by ID"""
        return self.agents.get(agent_id)

    def list_agents(self) -> List[str]:
        """List all agent IDs"""
        return list(self.agents.keys())

    async def remove_agent(self, agent_id: str) -> bool:
        """Remove an agent"""
        if agent_id in self.agents:
            del self.agents[agent_id]

            # Remove any crews that contain this agent
            crews_to_remove = [
                crew_id for crew_id, crew in self.crews.items()
                if any(agent.role == self.agents[agent_id].role for agent in crew.agents)
            ]

            for crew_id in crews_to_remove:
                del self.crews[crew_id]

            logger.info(f"Removed agent: {agent_id}")
            return True

        return False

    async def update_agent_config(self, agent_id: str, config_updates: Dict[str, Any]) -> bool:
        """Update agent configuration"""
        try:
            if agent_id not in self.agents:
                return False

            # For now, we'll need to recreate the agent with updated config
            # In a real implementation, you might want more sophisticated update logic
            logger.info(f"Configuration update requested for agent {agent_id}")
            return True

        except Exception as e:
            logger.error(f"Failed to update agent {agent_id} config: {str(e)}")
            return False


# Global agent manager instance
agent_manager = SimpleCrewAIAgentManager()