"""VTube Studio MCP Server - Control VTube Studio via API on port 8001."""

import asyncio
import aiohttp
import json
import base64
import time
from typing import Dict, Any, List, Optional
from pathlib import Path
import sys

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from mcp_servers.base_server import BaseMCPServer


class VTubeStudioServer(BaseMCPServer):
    """MCP Server for VTube Studio control via API."""
    
    def __init__(self, port: int = 3013):
        super().__init__("vtube_studio", port)
        self.api_base = "http://localhost:8001/api"
        self.auth_token = None
        self.session_token = None
        self.plugin_name = "LILITH-AI"
        self.plugin_developer = "LILITH"
        self.plugin_icon = None  # Base64 encoded icon
        
    async def initialize(self):
        """Initialize VTube Studio connection."""
        await super().initialize()
        
        # Try to authenticate with VTube Studio
        await self.authenticate()
        
    async def authenticate(self):
        """Authenticate with VTube Studio API."""
        try:
            # Request authentication token
            auth_request = {
                "apiName": "VTubeStudioPublicAPI",
                "apiVersion": "1.0",
                "requestID": str(int(time.time() * 1000)),
                "messageType": "AuthenticationTokenRequest",
                "data": {
                    "pluginName": self.plugin_name,
                    "pluginDeveloper": self.plugin_developer,
                    "pluginIcon": self.plugin_icon
                }
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_base, json=auth_request) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        if result.get("data", {}).get("authenticationToken"):
                            self.auth_token = result["data"]["authenticationToken"]
                            self.logger.info("✅ VTube Studio authentication token received")
                            
                            # Now authenticate with the token
                            await self.authenticate_with_token()
                        else:
                            self.logger.error("Failed to get authentication token")
                    else:
                        self.logger.error(f"VTube Studio API error: {resp.status}")
                        
        except Exception as e:
            self.logger.error(f"Failed to authenticate with VTube Studio: {e}")
            
    async def authenticate_with_token(self):
        """Authenticate using the received token."""
        if not self.auth_token:
            return
            
        auth_request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(int(time.time() * 1000)),
            "messageType": "AuthenticationRequest",
            "data": {
                "pluginName": self.plugin_name,
                "pluginDeveloper": self.plugin_developer,
                "authenticationToken": self.auth_token
            }
        }
        
        async with aiohttp.ClientSession() as session:
            async with session.post(self.api_base, json=auth_request) as resp:
                if resp.status == 200:
                    result = await resp.json()
                    if result.get("data", {}).get("authenticated"):
                        self.session_token = result["data"].get("sessionToken")
                        self.logger.info("✅ VTube Studio authenticated successfully")
                    else:
                        self.logger.error("Authentication failed")
                        
    async def make_api_request(self, message_type: str, data: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Make an authenticated API request to VTube Studio."""
        if not self.auth_token:
            await self.authenticate()
            
        request = {
            "apiName": "VTubeStudioPublicAPI",
            "apiVersion": "1.0",
            "requestID": str(int(time.time() * 1000)),
            "messageType": message_type,
            "data": data
        }
        
        # Add authentication if needed
        if self.session_token and message_type != "AuthenticationRequest":
            request["data"]["authenticationToken"] = self.auth_token
            
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(self.api_base, json=request) as resp:
                    if resp.status == 200:
                        return await resp.json()
                    else:
                        self.logger.error(f"API request failed: {resp.status}")
                        return None
        except Exception as e:
            self.logger.error(f"API request error: {e}")
            return None
            
    async def handle_request(self, request_type: str, params: Dict[str, Any]) -> Dict[str, Any]:
        """Handle incoming MCP requests."""
        
        # Map request types to handlers
        handlers = {
            "get_current_model": self.get_current_model,
            "list_available_models": self.list_available_models,
            "load_model": self.load_model,
            "move_model": self.move_model,
            "get_hotkeys": self.get_hotkeys,
            "trigger_hotkey": self.trigger_hotkey,
            "get_expressions": self.get_expressions,
            "set_expression": self.set_expression,
            "get_parameters": self.get_parameters,
            "set_parameter": self.set_parameter,
            "get_physics": self.get_physics,
            "set_physics": self.set_physics,
            "take_screenshot": self.take_screenshot,
            "get_face_found": self.get_face_found,
            "calibrate_camera": self.calibrate_camera,
            "set_background": self.set_background,
            "reload_textures": self.reload_textures
        }
        
        handler = handlers.get(request_type)
        if handler:
            try:
                result = await handler(params)
                return {"success": True, "result": result}
            except Exception as e:
                return {"success": False, "error": str(e)}
        else:
            return {"success": False, "error": f"Unknown request type: {request_type}"}
            
    async def get_current_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get information about the currently loaded model."""
        response = await self.make_api_request("CurrentModelRequest", {})
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to get current model"}
        
    async def list_available_models(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """List all available VTube Studio models."""
        response = await self.make_api_request("AvailableModelsRequest", {})
        if response and response.get("data"):
            return response["data"].get("availableModels", [])
        return []
        
    async def load_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Load a specific model."""
        model_id = params.get("model_id")
        if not model_id:
            return {"error": "model_id is required"}
            
        response = await self.make_api_request("ModelLoadRequest", {
            "modelID": model_id
        })
        
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to load model"}
        
    async def move_model(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Move the model position."""
        data = {
            "timeInSeconds": params.get("time", 0.2),
            "valuesAreRelativeToModel": params.get("relative", False),
            "positionX": params.get("x", 0),
            "positionY": params.get("y", 0),
            "rotation": params.get("rotation", 0),
            "size": params.get("size", 0)
        }
        
        response = await self.make_api_request("MoveModelRequest", data)
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to move model"}
        
    async def get_hotkeys(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get list of available hotkeys."""
        response = await self.make_api_request("HotkeysInCurrentModelRequest", {})
        if response and response.get("data"):
            return response["data"].get("availableHotkeys", [])
        return []
        
    async def trigger_hotkey(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger a hotkey by ID or name."""
        hotkey_id = params.get("hotkey_id")
        hotkey_name = params.get("hotkey_name")
        
        if not hotkey_id and not hotkey_name:
            return {"error": "Either hotkey_id or hotkey_name is required"}
            
        data = {}
        if hotkey_id:
            data["hotkeyID"] = hotkey_id
        else:
            # First, find the hotkey ID by name
            hotkeys = await self.get_hotkeys({})
            for hk in hotkeys:
                if hk.get("name") == hotkey_name:
                    data["hotkeyID"] = hk.get("hotkeyID")
                    break
                    
            if "hotkeyID" not in data:
                return {"error": f"Hotkey '{hotkey_name}' not found"}
                
        response = await self.make_api_request("HotkeyTriggerRequest", data)
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to trigger hotkey"}
        
    async def get_expressions(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get available expression states."""
        response = await self.make_api_request("ExpressionStateRequest", {})
        if response and response.get("data"):
            return response["data"].get("expressions", [])
        return []
        
    async def set_expression(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set expression state."""
        expression_file = params.get("expression_file")
        active = params.get("active", True)
        
        if not expression_file:
            return {"error": "expression_file is required"}
            
        response = await self.make_api_request("ExpressionActivationRequest", {
            "expressionFile": expression_file,
            "active": active
        })
        
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to set expression"}
        
    async def get_parameters(self, params: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Get model parameters."""
        response = await self.make_api_request("InputParameterListRequest", {})
        if response and response.get("data"):
            return response["data"].get("parameters", [])
        return []
        
    async def set_parameter(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set a model parameter value."""
        param_name = params.get("name")
        value = params.get("value")
        
        if not param_name or value is None:
            return {"error": "name and value are required"}
            
        response = await self.make_api_request("InjectParameterDataRequest", {
            "parameterValues": [
                {
                    "id": param_name,
                    "value": value
                }
            ]
        })
        
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to set parameter"}
        
    async def get_physics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Get physics settings."""
        response = await self.make_api_request("GetCurrentModelPhysicsRequest", {})
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to get physics settings"}
        
    async def set_physics(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set physics strength."""
        strength = params.get("strength")
        wind = params.get("wind")
        
        data = {}
        if strength is not None:
            data["strengthOverrides"] = [
                {
                    "id": "PhysicsStrength",
                    "value": strength
                }
            ]
        if wind is not None:
            data["windOverrides"] = [
                {
                    "id": "PhysicsWind", 
                    "value": wind
                }
            ]
            
        response = await self.make_api_request("SetCurrentModelPhysicsRequest", data)
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to set physics"}
        
    async def take_screenshot(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Take a screenshot of the current view."""
        response = await self.make_api_request("ScreenshotRequest", {
            "includeBackground": params.get("include_background", True),
            "outputFormat": params.get("format", "png"),
            "outputWidth": params.get("width", 1920),
            "outputHeight": params.get("height", 1080)
        })
        
        if response and response.get("data"):
            return {
                "image_base64": response["data"].get("imageBase64"),
                "success": True
            }
        return {"error": "Failed to take screenshot"}
        
    async def get_face_found(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Check if face tracking is detecting a face."""
        response = await self.make_api_request("FaceFoundRequest", {})
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to get face tracking status"}
        
    async def calibrate_camera(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Trigger camera calibration."""
        response = await self.make_api_request("CalibrateCameraRequest", {})
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to calibrate camera"}
        
    async def set_background(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Set background color."""
        color = params.get("color", {"r": 0, "g": 255, "b": 0})
        
        response = await self.make_api_request("BackgroundColorRequest", {
            "red": color.get("r", 0),
            "green": color.get("g", 255),
            "blue": color.get("b", 0),
            "alpha": color.get("a", 255)
        })
        
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to set background"}
        
    async def reload_textures(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """Reload model textures."""
        response = await self.make_api_request("ReloadTexturesRequest", {})
        if response and response.get("data"):
            return response["data"]
        return {"error": "Failed to reload textures"}


# Run the server
if __name__ == "__main__":
    server = VTubeStudioServer(port=3013)
    server.run()