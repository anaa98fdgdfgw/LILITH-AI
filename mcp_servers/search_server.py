"""MCP Search Server for web search operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from typing import Dict, Any, List, Optional
import aiohttp
import json
from datetime import datetime
import urllib.parse


class SearchServer(BaseMCPServer):
    """Web search server using various search APIs."""
    
    def __init__(self, port: int = 3006):
        super().__init__("search", port)
        
        # API configuration
        self.brave_api_key = os.environ.get("BRAVE_API_KEY", "")
        self.searx_url = os.environ.get("SEARX_URL", "https://searx.me")
        
        # Register methods
        self.register_method("search", self.search)
        self.register_method("search_brave", self.search_brave)
        self.register_method("search_duckduckgo", self.search_duckduckgo)
        self.register_method("search_images", self.search_images)
        self.register_method("search_news", self.search_news)
        self.register_method("search_videos", self.search_videos)
        self.register_method("get_instant_answer", self.get_instant_answer)
        
    async def search(self, query: str, engine: str = "duckduckgo", limit: int = 10) -> Dict[str, Any]:
        """Search using specified engine."""
        engines = {
            "brave": self.search_brave,
            "duckduckgo": self.search_duckduckgo,
        }
        
        if engine not in engines:
            return {"error": f"Unknown search engine: {engine}"}
            
        return await engines[engine](query, limit)
        
    async def search_brave(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search using Brave Search API."""
        if not self.brave_api_key:
            return {"error": "BRAVE_API_KEY not configured"}
            
        try:
            url = "https://api.search.brave.com/res/v1/web/search"
            headers = {
                "Accept": "application/json",
                "X-Subscription-Token": self.brave_api_key
            }
            params = {
                "q": query,
                "count": limit
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status != 200:
                        return {"error": f"Brave API error: {response.status}"}
                        
                    data = await response.json()
                    
                    results = []
                    for item in data.get("web", {}).get("results", []):
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("description", ""),
                            "age": item.get("age", "")
                        })
                        
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "engine": "brave"
                    }
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def search_duckduckgo(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search using DuckDuckGo (HTML parsing method)."""
        try:
            # Use DuckDuckGo HTML interface
            url = "https://html.duckduckgo.com/html/"
            params = {"q": query}
            
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, data=params, headers=headers) as response:
                    if response.status != 200:
                        return {"error": f"DuckDuckGo error: {response.status}"}
                        
                    html = await response.text()
                    
                    # Basic HTML parsing (would need BeautifulSoup for better parsing)
                    results = []
                    
                    # Simple regex-based extraction (not ideal but works)
                    import re
                    
                    # Find result blocks
                    result_pattern = r'<a rel="nofollow" class="result__a" href="([^"]+)">([^<]+)</a>'
                    snippet_pattern = r'<a class="result__snippet" href="[^"]+">([^<]+)</a>'
                    
                    urls_titles = re.findall(result_pattern, html)
                    snippets = re.findall(snippet_pattern, html)
                    
                    for i, (url, title) in enumerate(urls_titles[:limit]):
                        result = {
                            "title": title.strip(),
                            "url": url,
                            "description": snippets[i].strip() if i < len(snippets) else ""
                        }
                        results.append(result)
                        
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "engine": "duckduckgo"
                    }
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def search_images(self, query: str, limit: int = 10, safe_search: bool = True) -> Dict[str, Any]:
        """Search for images."""
        try:
            # Use Searx for image search
            url = f"{self.searx_url}/search"
            params = {
                "q": query,
                "categories": "images",
                "format": "json",
                "safesearch": 1 if safe_search else 0
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return {"error": f"Search error: {response.status}"}
                        
                    data = await response.json()
                    
                    results = []
                    for item in data.get("results", [])[:limit]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "thumbnail": item.get("thumbnail", ""),
                            "source": item.get("source", ""),
                            "img_src": item.get("img_src", "")
                        })
                        
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "type": "images"
                    }
                    
        except Exception as e:
            # Fallback response
            return {
                "query": query,
                "results": [],
                "count": 0,
                "type": "images",
                "error": "Image search temporarily unavailable"
            }
            
    async def search_news(self, query: str, limit: int = 10, time_range: str = "week") -> Dict[str, Any]:
        """Search for news articles."""
        try:
            # Use Searx for news search
            url = f"{self.searx_url}/search"
            params = {
                "q": query,
                "categories": "news",
                "format": "json",
                "time_range": time_range
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return {"error": f"Search error: {response.status}"}
                        
                    data = await response.json()
                    
                    results = []
                    for item in data.get("results", [])[:limit]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "description": item.get("content", ""),
                            "source": item.get("source", ""),
                            "published": item.get("publishedDate", "")
                        })
                        
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "type": "news",
                        "time_range": time_range
                    }
                    
        except Exception as e:
            # Fallback response
            return {
                "query": query,
                "results": [],
                "count": 0,
                "type": "news",
                "error": "News search temporarily unavailable"
            }
            
    async def search_videos(self, query: str, limit: int = 10) -> Dict[str, Any]:
        """Search for videos."""
        try:
            # Use Searx for video search
            url = f"{self.searx_url}/search"
            params = {
                "q": query,
                "categories": "videos",
                "format": "json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return {"error": f"Search error: {response.status}"}
                        
                    data = await response.json()
                    
                    results = []
                    for item in data.get("results", [])[:limit]:
                        results.append({
                            "title": item.get("title", ""),
                            "url": item.get("url", ""),
                            "thumbnail": item.get("thumbnail", ""),
                            "duration": item.get("duration", ""),
                            "source": item.get("source", ""),
                            "views": item.get("views", "")
                        })
                        
                    return {
                        "query": query,
                        "results": results,
                        "count": len(results),
                        "type": "videos"
                    }
                    
        except Exception as e:
            # Fallback response
            return {
                "query": query,
                "results": [],
                "count": 0,
                "type": "videos",
                "error": "Video search temporarily unavailable"
            }
            
    async def get_instant_answer(self, query: str) -> Dict[str, Any]:
        """Get instant answer for query (calculations, facts, etc)."""
        try:
            # Use DuckDuckGo Instant Answer API
            url = "https://api.duckduckgo.com/"
            params = {
                "q": query,
                "format": "json",
                "no_html": 1,
                "skip_disambig": 1
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, params=params) as response:
                    if response.status != 200:
                        return {"error": f"API error: {response.status}"}
                        
                    data = await response.json()
                    
                    result = {
                        "query": query,
                        "answer": None,
                        "type": None
                    }
                    
                    # Check for different types of answers
                    if data.get("Answer"):
                        result["answer"] = data["Answer"]
                        result["type"] = data.get("AnswerType", "direct")
                    elif data.get("Definition"):
                        result["answer"] = data["Definition"]
                        result["type"] = "definition"
                        result["source"] = data.get("DefinitionSource", "")
                    elif data.get("AbstractText"):
                        result["answer"] = data["AbstractText"]
                        result["type"] = "abstract"
                        result["source"] = data.get("AbstractSource", "")
                    elif data.get("RelatedTopics"):
                        topics = []
                        for topic in data["RelatedTopics"][:3]:
                            if isinstance(topic, dict) and "Text" in topic:
                                topics.append(topic["Text"])
                        if topics:
                            result["answer"] = " | ".join(topics)
                            result["type"] = "related"
                            
                    # Add additional info if available
                    if data.get("Image"):
                        result["image"] = data["Image"]
                    if data.get("Infobox"):
                        result["infobox"] = data["Infobox"]
                        
                    return result
                    
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Search Server")
    args = parser.parse_args()
    
    server = SearchServer(port=args.port)
    server.run()