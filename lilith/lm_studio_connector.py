"""LM Studio Connector - Enhanced communication with LM Studio server.

This module ensures reliable connection to LM Studio and proper MCP injection.
"""

import requests
import time
import json
from typing import Dict, Any, Optional, List
from openai import OpenAI
import logging
from pathlib import Path
import subprocess
import psutil
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LMStudioConnector:
    """Enhanced connector for LM Studio with automatic server detection and MCP injection."""
    
    def __init__(self, 
                 base_url: str = "http://127.0.0.1:1234",
                 timeout: int = 30,
                 retry_count: int = 3,
                 lm_studio_path: str = "C:\\Program Files\\LM Studio\\LM Studio.exe"):
        """
        Initialize LM Studio connector.
        
        Args:
            base_url: Base URL for LM Studio server (default: http://127.0.0.1:1234)
            timeout: Request timeout in seconds
            retry_count: Number of retries for failed requests
            lm_studio_path: Path to LM Studio executable
        """
        self.base_url = base_url.rstrip('/')
        self.api_url = f"{self.base_url}/v1"
        self.timeout = timeout
        self.retry_count = retry_count
        self.lm_studio_path = Path(lm_studio_path)
        self.client = None
        self._server_info = None
        
    def is_lm_studio_running(self) -> bool:
        """Check if LM Studio process is running."""
        for proc in psutil.process_iter(['name']):
            try:
                if proc.info['name'] and 'LM Studio' in proc.info['name']:
                    return True
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass
        return False
    
    def is_server_available(self) -> bool:
        """Check if LM Studio server is available."""
        try:
            response = requests.get(
                f"{self.api_url}/models",
                timeout=5
            )
            return response.status_code == 200
        except:
            return False
    
    def wait_for_server(self, max_wait: int = 60) -> bool:
        """
        Wait for LM Studio server to become available.
        
        Args:
            max_wait: Maximum time to wait in seconds
            
        Returns:
            True if server is available, False otherwise
        """
        logger.info(f"Waiting for LM Studio server at {self.base_url}...")
        start_time = time.time()
        
        while time.time() - start_time < max_wait:
            if self.is_server_available():
                logger.info("✅ LM Studio server is available!")
                return True
            time.sleep(2)
            
        logger.error(f"❌ LM Studio server not available after {max_wait} seconds")
        return False
    
    def start_lm_studio(self) -> bool:
        """Start LM Studio if not running."""
        if self.is_lm_studio_running():
            logger.info("LM Studio is already running")
            return True
            
        if not self.lm_studio_path.exists():
            logger.error(f"LM Studio not found at {self.lm_studio_path}")
            return False
            
        try:
            logger.info("Starting LM Studio...")
            subprocess.Popen([str(self.lm_studio_path)])
            time.sleep(5)  # Give it time to start
            return True
        except Exception as e:
            logger.error(f"Failed to start LM Studio: {e}")
            return False
    
    def get_server_info(self) -> Optional[Dict[str, Any]]:
        """Get information about the LM Studio server."""
        try:
            response = requests.get(
                f"{self.api_url}/models",
                timeout=self.timeout
            )
            if response.status_code == 200:
                self._server_info = response.json()
                return self._server_info
        except Exception as e:
            logger.error(f"Failed to get server info: {e}")
        return None
    
    def get_loaded_model(self) -> Optional[str]:
        """Get the currently loaded model name."""
        info = self.get_server_info()
        if info and 'data' in info and len(info['data']) > 0:
            return info['data'][0].get('id', 'Unknown')
        return None
    
    def test_connection(self) -> Dict[str, Any]:
        """Test connection to LM Studio server."""
        result = {
            "server_available": False,
            "model_loaded": False,
            "model_name": None,
            "error": None
        }
        
        try:
            # Check if server is available
            if not self.is_server_available():
                result["error"] = "Server not available"
                return result
                
            result["server_available"] = True
            
            # Check loaded model
            model_name = self.get_loaded_model()
            if model_name:
                result["model_loaded"] = True
                result["model_name"] = model_name
            else:
                result["error"] = "No model loaded"
                
        except Exception as e:
            result["error"] = str(e)
            
        return result
    
    def create_client(self) -> Optional[OpenAI]:
        """Create OpenAI client for LM Studio."""
        try:
            self.client = OpenAI(
                base_url=self.api_url,
                api_key="not-needed"  # LM Studio doesn't require API key
            )
            return self.client
        except Exception as e:
            logger.error(f"Failed to create OpenAI client: {e}")
            return None
    
    def ensure_connection(self) -> bool:
        """
        Ensure LM Studio is running and server is available.
        
        Returns:
            True if connection is established, False otherwise
        """
        # Step 1: Check if server is already available
        if self.is_server_available():
            logger.info("✅ LM Studio server is already available")
            # Create client if not already created
            if not self.client:
                self.create_client()
            return self.client is not None
            
        # Step 2: Check if LM Studio is running
        if not self.is_lm_studio_running():
            logger.info("LM Studio is not running, attempting to start...")
            if not self.start_lm_studio():
                return False
                
        # Step 3: Wait for server
        if self.wait_for_server():
            # Step 4: Create client if not already created
            if not self.client:
                self.create_client()
            return self.client is not None
                
        return False
    
    def inject_mcp_context(self, messages: List[Dict[str, Any]], 
                          mcp_servers: Dict[str, Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Inject MCP server context into messages.
        
        Args:
            messages: Original messages
            mcp_servers: Dictionary of MCP server configurations
            
        Returns:
            Messages with MCP context injected
        """
        # Build MCP context
        mcp_context = self._build_mcp_context(mcp_servers)
        
        # Find or create system message
        system_msg_index = None
        for i, msg in enumerate(messages):
            if msg.get("role") == "system":
                system_msg_index = i
                break
                
        if system_msg_index is not None:
            # Append MCP context to existing system message
            messages[system_msg_index]["content"] += f"\n\n{mcp_context}"
        else:
            # Insert new system message with MCP context
            messages.insert(0, {
                "role": "system",
                "content": mcp_context
            })
            
        return messages
    
    def _build_mcp_context(self, mcp_servers: Dict[str, Dict[str, Any]]) -> str:
        """Build MCP context string from server configurations."""
        context_parts = ["**AVAILABLE MCP SERVERS:**"]
        
        for server_name, config in mcp_servers.items():
            if config.get("enabled", False):
                status = "✅ Active" if config.get("running", False) else "⚠️ Starting"
                port = config.get("port", "Unknown")
                
                # Add server info
                context_parts.append(f"\n**{server_name.upper()} SERVER** [{status}] (Port: {port})")
                
                # Add capabilities based on server type
                capabilities = self._get_server_capabilities(server_name)
                if capabilities:
                    context_parts.append(f"Capabilities: {capabilities}")
                    
                # Add usage examples
                examples = self._get_server_examples(server_name)
                if examples:
                    context_parts.append(f"Examples: {examples}")
                    
        return "\n".join(context_parts)
    
    def _get_server_capabilities(self, server_name: str) -> str:
        """Get capabilities description for a server."""
        capabilities = {
            "filesystem": "Read/write files, navigate directories, manage projects",
            "github": "Create issues, manage repos, search code, pull requests",
            "memory": "Store and retrieve persistent information, knowledge graph",
            "search": "Web search, information retrieval, fact checking",
            "time": "Get current time/date, schedule tasks, time calculations",
            "fetch": "HTTP requests, API calls, web scraping",
            "ab498_control": "Mouse/keyboard control, screen interaction, automation",
            "alpaca": "Stock trading, market data, portfolio management",
            "slack": "Send messages, manage channels, read conversations",
            "drive": "Google Drive file management, sharing, collaboration",
            "notion": "Create/update pages, manage databases, workspace control",
            "postgres": "SQL queries, database management, data analysis",
            "sqlite": "Local database operations, data storage",
            "git": "Version control, commits, branches, diffs",
            "puppeteer": "Browser automation, web testing, screenshots",
            "sentry": "Error tracking, performance monitoring, debugging"
        }
        return capabilities.get(server_name, "Various operations")
    
    def _get_server_examples(self, server_name: str) -> str:
        """Get usage examples for a server."""
        examples = {
            "filesystem": "MCP_FS: read 'file.py' | MCP_FS: write 'output.txt' 'content'",
            "github": "MCP_GITHUB: create_issue 'repo' 'title' 'body'",
            "memory": "MCP_MEMORY: store 'key' 'value' | MCP_MEMORY: retrieve 'key'",
            "search": "MCP_SEARCH: 'query terms'",
            "remote_control": "MCP_CONTROL: click 100 200 | MCP_CONTROL: type 'text'",
            "alpaca": "MCP_TRADE: AAPL 10 buy market"
        }
        return examples.get(server_name, "")
    
    def send_completion(self, 
                       messages: List[Dict[str, Any]], 
                       model: str = "local-model",
                       temperature: float = 0.7,
                       max_tokens: int = 1024,
                       stream: bool = False,
                       **kwargs) -> Optional[Any]:
        """
        Send completion request to LM Studio with retry logic.
        
        Args:
            messages: List of message dictionaries
            model: Model name (default: "local-model")
            temperature: Temperature for generation
            max_tokens: Maximum tokens to generate
            stream: Whether to stream the response
            **kwargs: Additional parameters
            
        Returns:
            Completion response or None if failed
        """
        if not self.client:
            if not self.ensure_connection():
                logger.error("Failed to establish connection to LM Studio")
                return None
                
        for attempt in range(self.retry_count):
            try:
                response = self.client.chat.completions.create(
                    model=model,
                    messages=messages,
                    temperature=temperature,
                    max_tokens=max_tokens,
                    stream=stream,
                    **kwargs
                )
                return response
                
            except Exception as e:
                logger.warning(f"Attempt {attempt + 1} failed: {e}")
                if attempt < self.retry_count - 1:
                    time.sleep(2 ** attempt)  # Exponential backoff
                else:
                    logger.error(f"All attempts failed: {e}")
                    
        return None
    
    def health_check(self) -> Dict[str, Any]:
        """Perform comprehensive health check."""
        return {
            "timestamp": time.time(),
            "lm_studio_running": self.is_lm_studio_running(),
            "server_available": self.is_server_available(),
            "server_url": self.base_url,
            "connection_test": self.test_connection(),
            "client_initialized": self.client is not None
        }


# Singleton instance
_connector_instance = None


def get_lm_studio_connector() -> LMStudioConnector:
    """Get or create singleton LM Studio connector instance."""
    global _connector_instance
    if _connector_instance is None:
        _connector_instance = LMStudioConnector()
    return _connector_instance


# Convenience functions
def ensure_lm_studio_connection() -> bool:
    """Ensure LM Studio connection is established."""
    connector = get_lm_studio_connector()
    return connector.ensure_connection()


def test_lm_studio_connection() -> Dict[str, Any]:
    """Test LM Studio connection."""
    connector = get_lm_studio_connector()
    return connector.test_connection()


def get_lm_studio_health() -> Dict[str, Any]:
    """Get LM Studio health status."""
    connector = get_lm_studio_connector()
    return connector.health_check()


if __name__ == "__main__":
    # Test the connector
    print("🔍 Testing LM Studio Connector...")
    
    connector = LMStudioConnector()
    
    # Health check
    health = connector.health_check()
    print(f"\n📊 Health Check:")
    print(json.dumps(health, indent=2))
    
    # Ensure connection
    if connector.ensure_connection():
        print("\n✅ Connection established successfully!")
        
        # Test completion
        test_messages = [
            {"role": "system", "content": "You are a helpful assistant."},
            {"role": "user", "content": "Say hello!"}
        ]
        
        response = connector.send_completion(test_messages, max_tokens=50)
        if response:
            print(f"\n🤖 Response: {response.choices[0].message.content}")
        else:
            print("\n❌ Failed to get response")
    else:
        print("\n❌ Failed to establish connection")