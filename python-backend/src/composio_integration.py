# -*- coding: utf-8 -*-
"""
Composio integration module for Rowboat Python Backend
Provides AI tools and toolkit management through Composio
"""

import os
import logging
from typing import List, Dict, Optional, Any
from functools import lru_cache

# Composio imports
try:
    from composio import Composio
    from composio_langchain import LangchainProvider
    COMPOSIO_AVAILABLE = True
except ImportError as e:
    COMPOSIO_AVAILABLE = False
    logging.warning(f"Composio not available - tools will be limited: {e}")

try:
    from .config import settings
except ImportError:
    # Handle import when running as standalone script
    try:
        from config import settings
    except ImportError:
        # Fallback with basic settings
        settings = type('Settings', (), {'composio_api_key': os.getenv('COMPOSIO_API_KEY', '')})

logger = logging.getLogger(__name__)


class ComposioManager:
    """Composio tools manager for AI agent capabilities"""

    def __init__(self):
        self.composio = None
        self.provider = None
        self.available_toolkits = []
        self.initialized = False

        if not COMPOSIO_AVAILABLE:
            logger.warning("Composio packages not available")
            return

        self._initialize_composio()

    def _initialize_composio(self):
        """Initialize Composio client with LangChain provider"""
        try:
            # Check API key availability
            api_key = settings.composio_api_key or os.getenv('COMPOSIO_API_KEY')
            
            if not api_key:
                logger.warning("Composio API key not configured. Set COMPOSIO_API_KEY environment variable.")
                self.initialized = False
                return

            # Set API key in environment
            os.environ['COMPOSIO_API_KEY'] = api_key

            # Initialize provider
            self.provider = LangchainProvider()
            
            # Initialize Composio client with LangChain provider
            self.composio = Composio(provider=self.provider)

            # Load available toolkits
            self._load_available_toolkits()

            self.initialized = True
            logger.info("Composio initialized successfully with LangChain provider")

        except Exception as e:
            logger.error(f"Failed to initialize Composio: {e}")
            self.initialized = False

    def _load_available_toolkits(self):
        """Load available Composio toolkits"""
        try:
            if self.composio:
                # Get list of available toolkits
                toolkits = self.composio.toolkits.get()
                self.available_toolkits = [toolkit.name for toolkit in toolkits]
                logger.info(f"Loaded {len(self.available_toolkits)} Composio toolkits")
        except Exception as e:
            logger.warning(f"Failed to load Composio toolkits: {e}")
            self.available_toolkits = []

    def get_available_tools(self) -> List[str]:
        """Get list of available tool names"""
        if not self.initialized:
            return []

        try:
            # Get all tools
            tools = self.composio.tools.get()
            return [tool.slug for tool in tools]
        except Exception as e:
            logger.error(f"Failed to get available tools: {e}")
            return []

    def get_tools_for_app(self, app_name: str) -> List[Any]:
        """Get tools for a specific app"""
        if not self.initialized:
            return []

        try:
            # Get tools for specific app using the new API
            tools = self.composio.tools.get(apps=[app_name.upper()])
            logger.info(f"Retrieved {len(tools)} tools for app: {app_name}")
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools for app {app_name}: {e}")
            return []

    def get_all_tools(self, app_names: Optional[List[str]] = None) -> List[Any]:
        """Get all available tools or tools for specific apps"""
        if not self.initialized:
            return []

        try:
            if app_names:
                # Get tools for specific apps
                tools = self.composio.tools.get(apps=[app.upper() for app in app_names])
            else:
                # Get all tools
                tools = self.composio.tools.get()
            
            logger.info(f"Total tools retrieved: {len(tools)}")
            return tools
        except Exception as e:
            logger.error(f"Failed to get tools: {e}")
            return []

    def get_tools_by_category(self, category: str) -> List[Any]:
        """Get tools by category (e.g., 'coding', 'social', 'productivity')"""
        if not self.initialized:
            return []

        # Map categories to Composio app names
        category_mapping = {
            'coding': ['GITHUB', 'GITLAB', 'BITBUCKET'],
            'social': ['TWITTER', 'LINKEDIN'],
            'productivity': ['SLACK', 'DISCORD', 'NOTION', 'TRELLO'],
            'communication': ['GMAIL', 'OUTLOOK'],
            'development': ['GITHUB', 'GITLAB'],
        }

        app_names = category_mapping.get(category.lower(), [])
        if not app_names:
            return []
            
        return self.get_all_tools(app_names)

    def is_available(self) -> bool:
        """Check if Composio is available and initialized"""
        return COMPOSIO_AVAILABLE and self.initialized

    def get_status(self) -> Dict[str, Any]:
        """Get Composio integration status"""
        return {
            "available": self.is_available(),
            "initialized": self.initialized,
            "api_key_configured": bool(settings.composio_api_key or os.getenv('COMPOSIO_API_KEY')),
            "available_toolkits": self.available_toolkits[:10],  # First 10 toolkits
            "total_toolkits": len(self.available_toolkits)
        }


# Global Composio manager instance
composio_manager = ComposioManager()


def get_composio_tools(app_names: Optional[List[str]] = None) -> List[Any]:
    """Get Composio tools for AI agents"""
    return composio_manager.get_all_tools(app_names)


def get_composio_tools_by_category(category: str) -> List[Any]:
    """Get Composio tools by category"""
    return composio_manager.get_tools_by_category(category)


def get_composio_status() -> Dict[str, Any]:
    """Get Composio integration status"""
    return composio_manager.get_status()


# Legacy compatibility
class ComposioToolProvider:
    """Legacy compatibility class for Composio tools"""

    def __init__(self):
        self.manager = composio_manager

    def get_tools(self, app_names: Optional[List[str]] = None) -> List[Any]:
        return self.manager.get_all_tools(app_names)

    def is_available(self) -> bool:
        return self.manager.is_available()