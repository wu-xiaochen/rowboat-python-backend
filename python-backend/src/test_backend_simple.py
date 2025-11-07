#!/usr/bin/env python3
"""
Simple test to verify the Python backend is working correctly
"""

import asyncio
import sys
import os

# Add the src directory to the path
sys.path.insert(0, os.path.dirname(__file__))

from database import DatabaseManager
from crew_manager_simple import agent_manager
from models import CreateAgentRequest, CreateConversationRequest, SendMessageRequest
from config import settings

async def test_backend():
    """Simple test of the backend functionality"""
    print("🚢 Testing Rowboat Python Backend...")

    try:
        # Test 1: Database initialization
        print("1. Testing database initialization...")
        db_manager = DatabaseManager()
        await db_manager.initialize()
        print("✅ Database initialized successfully")

        # Test 2: Create a test agent
        print("2. Testing agent creation...")
        agent_request = CreateAgentRequest(
            name="Test Agent",
            description="A test agent for verification",
            agent_type="custom",
            config={
                "personality": "helpful and professional",
                "expertise": "testing and verification"
            },
            tools=[],
            triggers=[],
            rag_enabled=False,
            rag_sources=[]
        )

        # Create agent in database
        test_user_id = "test_user_123"
        agent = await db_manager.create_agent(agent_request, test_user_id)
        print(f"✅ Agent created: {agent.name} (ID: {agent.id})")

        # Create CrewAI agent
        await agent_manager.create_agent(agent)
        print("✅ CrewAI agent created successfully")

        # Test 3: Create conversation
        print("3. Testing conversation creation...")
        conversation_request = CreateConversationRequest(
            agent_id=agent.id,
            user_id=test_user_id,
            title="Test Conversation",
            context={"test": "context"}
        )

        conversation = await db_manager.create_conversation(conversation_request, test_user_id)
        print(f"✅ Conversation created: {conversation.id}")

        # Test 4: Process a message
        print("4. Testing message processing...")
        from models import Message

        test_message = Message(
            id="test_msg_123",
            conversation_id=conversation.id,
            role="user",
            content="Hello, can you help me test this system?",
            metadata={},
            created_at=datetime.now()
        )

        response = await agent_manager.process_conversation_message(conversation, test_message)
        print(f"✅ Message processed. Response: {response[:100]}...")

        # Test 5: Copilot assistance
        print("5. Testing copilot assistance...")
        copilot_response = await agent_manager.copilot_assist(
            "How do I create a multi-agent crew?",
            {"current_page": "copilot"}
        )
        print(f"✅ Copilot response: {copilot_response[:100]}...")

        # Cleanup
        print("6. Cleaning up test data...")
        await db_manager.delete_agent(agent.id, test_user_id)
        await db_manager.cleanup()
        print("✅ Cleanup completed")

        print("\n🎉 All tests passed! Backend is working correctly.")
        return True

    except Exception as e:
        print(f"\n❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = asyncio.run(test_backend())
    sys.exit(0 if success else 1)