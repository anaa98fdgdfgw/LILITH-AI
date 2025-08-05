"""MCP Fetch Server for HTTP requests and web content."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from typing import Dict, Any, List, Optional
import aiohttp
import asyncio
import json
import base64
from urllib.parse import urljoin, urlparse
import mimetypes


class FetchServer(BaseMCPServer):
    """HTTP fetch and web content server."""
    
    def __init__(self, port: int = 3010):
        super().__init__("fetch", port)
        
        # Default headers
        self.default_headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
        }
        
        # Register methods
        self.register_method("get", self.get)
        self.register_method("post", self.post)
        self.register_method("put", self.put)
        self.register_method("delete", self.delete)
        self.register_method("head", self.head)
        self.register_method("options", self.options)
        self.register_method("download", self.download)
        self.register_method("fetch_json", self.fetch_json)
        self.register_method("fetch_text", self.fetch_text)
        self.register_method("fetch_headers", self.fetch_headers)
        self.register_method("check_status", self.check_status)
        self.register_method("follow_redirects", self.follow_redirects)
        
    async def _make_request(self, method: str, url: str, headers: Dict[str, str] = None,
                          data: Any = None, json_data: Any = None, params: Dict[str, str] = None,
                          timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make HTTP request."""
        try:
            # Merge headers
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
                
            # Create timeout
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.request(
                    method=method,
                    url=url,
                    headers=request_headers,
                    data=data,
                    json=json_data,
                    params=params,
                    allow_redirects=follow_redirects
                ) as response:
                    # Get response info
                    result = {
                        "status": response.status,
                        "status_text": response.reason,
                        "headers": dict(response.headers),
                        "url": str(response.url),
                        "method": method,
                        "content_type": response.content_type,
                        "encoding": response.charset
                    }
                    
                    # Handle different content types
                    content_type = response.content_type or ""
                    
                    if "application/json" in content_type:
                        try:
                            result["json"] = await response.json()
                            result["text"] = await response.text()
                        except:
                            result["text"] = await response.text()
                    elif "text" in content_type or "html" in content_type or "xml" in content_type:
                        result["text"] = await response.text()
                    else:
                        # Binary content
                        content = await response.read()
                        result["base64"] = base64.b64encode(content).decode()
                        result["size"] = len(content)
                        
                    # Add redirect history if any
                    if response.history:
                        result["redirects"] = [
                            {"url": str(r.url), "status": r.status} 
                            for r in response.history
                        ]
                        
                    return result
                    
        except asyncio.TimeoutError:
            return {"error": f"Request timeout after {timeout} seconds"}
        except aiohttp.ClientError as e:
            return {"error": f"Client error: {str(e)}"}
        except Exception as e:
            return {"error": str(e)}
            
    async def get(self, url: str, headers: Dict[str, str] = None, params: Dict[str, str] = None,
                  timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make GET request."""
        return await self._make_request("GET", url, headers=headers, params=params,
                                      timeout=timeout, follow_redirects=follow_redirects)
                                      
    async def post(self, url: str, headers: Dict[str, str] = None, data: Any = None,
                   json_data: Any = None, params: Dict[str, str] = None,
                   timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make POST request."""
        return await self._make_request("POST", url, headers=headers, data=data,
                                      json_data=json_data, params=params,
                                      timeout=timeout, follow_redirects=follow_redirects)
                                      
    async def put(self, url: str, headers: Dict[str, str] = None, data: Any = None,
                  json_data: Any = None, params: Dict[str, str] = None,
                  timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make PUT request."""
        return await self._make_request("PUT", url, headers=headers, data=data,
                                      json_data=json_data, params=params,
                                      timeout=timeout, follow_redirects=follow_redirects)
                                      
    async def delete(self, url: str, headers: Dict[str, str] = None, params: Dict[str, str] = None,
                     timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make DELETE request."""
        return await self._make_request("DELETE", url, headers=headers, params=params,
                                      timeout=timeout, follow_redirects=follow_redirects)
                                      
    async def head(self, url: str, headers: Dict[str, str] = None, params: Dict[str, str] = None,
                   timeout: int = 30, follow_redirects: bool = True) -> Dict[str, Any]:
        """Make HEAD request."""
        return await self._make_request("HEAD", url, headers=headers, params=params,
                                      timeout=timeout, follow_redirects=follow_redirects)
                                      
    async def options(self, url: str, headers: Dict[str, str] = None,
                      timeout: int = 30) -> Dict[str, Any]:
        """Make OPTIONS request."""
        return await self._make_request("OPTIONS", url, headers=headers, timeout=timeout)
        
    async def download(self, url: str, save_path: str = None, headers: Dict[str, str] = None,
                      timeout: int = 60) -> Dict[str, Any]:
        """Download file from URL."""
        try:
            request_headers = self.default_headers.copy()
            if headers:
                request_headers.update(headers)
                
            timeout_obj = aiohttp.ClientTimeout(total=timeout)
            
            async with aiohttp.ClientSession(timeout=timeout_obj) as session:
                async with session.get(url, headers=request_headers) as response:
                    response.raise_for_status()
                    
                    # Get filename
                    if save_path:
                        filename = save_path
                    else:
                        # Try to get filename from Content-Disposition
                        cd = response.headers.get("Content-Disposition")
                        if cd and "filename=" in cd:
                            filename = cd.split("filename=")[1].strip('"')
                        else:
                            # Get from URL
                            parsed = urlparse(url)
                            filename = os.path.basename(parsed.path) or "download"
                            
                    # Download content
                    content = await response.read()
                    
                    # Save if path provided
                    if save_path:
                        with open(save_path, "wb") as f:
                            f.write(content)
                            
                    return {
                        "success": True,
                        "filename": filename,
                        "size": len(content),
                        "content_type": response.content_type,
                        "saved": bool(save_path),
                        "save_path": save_path,
                        "base64": base64.b64encode(content).decode() if not save_path else None
                    }
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def fetch_json(self, url: str, headers: Dict[str, str] = None,
                        timeout: int = 30) -> Dict[str, Any]:
        """Fetch JSON from URL."""
        result = await self.get(url, headers=headers, timeout=timeout)
        
        if "error" in result:
            return result
            
        if "json" in result:
            return {"data": result["json"], "status": result["status"]}
        else:
            return {"error": "Response is not JSON", "text": result.get("text", "")}
            
    async def fetch_text(self, url: str, headers: Dict[str, str] = None,
                        timeout: int = 30) -> Dict[str, Any]:
        """Fetch text content from URL."""
        result = await self.get(url, headers=headers, timeout=timeout)
        
        if "error" in result:
            return result
            
        if "text" in result:
            return {"text": result["text"], "status": result["status"]}
        else:
            return {"error": "Response is not text", "content_type": result.get("content_type", "")}
            
    async def fetch_headers(self, url: str, timeout: int = 30) -> Dict[str, Any]:
        """Fetch only headers from URL."""
        result = await self.head(url, timeout=timeout)
        
        if "error" in result:
            return result
            
        return {
            "headers": result["headers"],
            "status": result["status"],
            "url": result["url"]
        }
        
    async def check_status(self, url: str, timeout: int = 10) -> Dict[str, Any]:
        """Check if URL is accessible."""
        try:
            result = await self.head(url, timeout=timeout)
            
            if "error" in result:
                return {"accessible": False, "error": result["error"]}
                
            return {
                "accessible": result["status"] < 400,
                "status": result["status"],
                "status_text": result["status_text"],
                "content_type": result.get("content_type", ""),
                "content_length": result["headers"].get("Content-Length", "unknown")
            }
            
        except Exception as e:
            return {"accessible": False, "error": str(e)}
            
    async def follow_redirects(self, url: str, max_redirects: int = 10,
                             timeout: int = 30) -> Dict[str, Any]:
        """Follow redirect chain."""
        try:
            redirects = []
            current_url = url
            
            for i in range(max_redirects):
                result = await self.get(current_url, follow_redirects=False, timeout=timeout)
                
                if "error" in result:
                    return {"error": result["error"], "redirects": redirects}
                    
                redirects.append({
                    "url": current_url,
                    "status": result["status"],
                    "location": result["headers"].get("Location", "")
                })
                
                # Check if redirect
                if result["status"] in [301, 302, 303, 307, 308]:
                    location = result["headers"].get("Location")
                    if location:
                        # Handle relative URLs
                        current_url = urljoin(current_url, location)
                    else:
                        break
                else:
                    # Final destination reached
                    break
                    
            return {
                "final_url": current_url,
                "redirects": redirects,
                "redirect_count": len(redirects) - 1,
                "final_status": redirects[-1]["status"] if redirects else None
            }
            
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Fetch Server")
    args = parser.parse_args()
    
    server = FetchServer(port=args.port)
    server.run()