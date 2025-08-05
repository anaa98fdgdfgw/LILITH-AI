"""Base MCP Server implementation."""
import asyncio
import json
import sys
from aiohttp import web
import argparse
import logging
from typing import Dict, Any, Callable
from pathlib import Path

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class BaseMCPServer:
    """Base class for MCP servers."""
    
    def __init__(self, name: str, port: int = 3000):
        self.name = name
        self.port = port
        self.methods: Dict[str, Callable] = {}
        self.app = web.Application()
        self.setup_routes()
        
    def setup_routes(self):
        """Setup HTTP routes."""
        self.app.router.add_post('/rpc', self.handle_rpc)
        self.app.router.add_get('/health', self.handle_health)
        
    def register_method(self, name: str, handler: Callable):
        """Register an RPC method."""
        self.methods[name] = handler
        
    async def handle_health(self, request):
        """Health check endpoint."""
        return web.json_response({
            "status": "ok",
            "server": self.name,
            "port": self.port
        })
        
    async def handle_rpc(self, request):
        """Handle JSON-RPC requests."""
        try:
            data = await request.json()
            method = data.get("method")
            params = data.get("params", {})
            request_id = data.get("id", 1)
            
            if method not in self.methods:
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    },
                    "id": request_id
                })
                
            # Call the method
            try:
                result = await self.methods[method](**params)
                return web.json_response({
                    "jsonrpc": "2.0",
                    "result": result,
                    "id": request_id
                })
            except Exception as e:
                logger.error(f"Error in method {method}: {e}")
                return web.json_response({
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32603,
                        "message": str(e)
                    },
                    "id": request_id
                })
                
        except Exception as e:
            logger.error(f"Error handling RPC: {e}")
            return web.json_response({
                "jsonrpc": "2.0",
                "error": {
                    "code": -32700,
                    "message": "Parse error"
                },
                "id": None
            })
            
    def run(self):
        """Run the server."""
        logger.info(f"Starting {self.name} MCP server on port {self.port}")
        web.run_app(self.app, host='localhost', port=self.port)
        

def create_argument_parser(description: str):
    """Create standard argument parser for MCP servers."""
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument('--port', type=int, default=3000, help='Port to run server on')
    return parser