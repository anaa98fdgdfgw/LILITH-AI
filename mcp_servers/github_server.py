"""MCP GitHub Server for repository operations."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from typing import Dict, Any, List, Optional
import aiohttp
import json
import base64
from datetime import datetime


class GitHubServer(BaseMCPServer):
    """GitHub operations server."""
    
    def __init__(self, port: int = 3002):
        super().__init__("github", port)
        
        # GitHub configuration
        self.token = os.environ.get("GITHUB_TOKEN", "")
        self.api_base = "https://api.github.com"
        
        # Register methods
        self.register_method("get_user", self.get_user)
        self.register_method("list_repos", self.list_repos)
        self.register_method("get_repo", self.get_repo)
        self.register_method("create_repo", self.create_repo)
        self.register_method("delete_repo", self.delete_repo)
        self.register_method("list_issues", self.list_issues)
        self.register_method("get_issue", self.get_issue)
        self.register_method("create_issue", self.create_issue)
        self.register_method("update_issue", self.update_issue)
        self.register_method("close_issue", self.close_issue)
        self.register_method("list_pull_requests", self.list_pull_requests)
        self.register_method("create_pull_request", self.create_pull_request)
        self.register_method("get_file", self.get_file)
        self.register_method("create_or_update_file", self.create_or_update_file)
        self.register_method("delete_file", self.delete_file)
        self.register_method("list_branches", self.list_branches)
        self.register_method("create_branch", self.create_branch)
        self.register_method("search_code", self.search_code)
        self.register_method("search_repos", self.search_repos)
        
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers."""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "MCP-GitHub-Server"
        }
        if self.token:
            headers["Authorization"] = f"token {self.token}"
        return headers
        
    async def _make_request(self, method: str, endpoint: str, data: Any = None) -> Dict[str, Any]:
        """Make GitHub API request."""
        url = f"{self.api_base}{endpoint}"
        headers = self._get_headers()
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.request(method, url, headers=headers, json=data) as response:
                    result = await response.json()
                    
                    if response.status >= 400:
                        return {"error": result.get("message", f"API error: {response.status}")}
                        
                    return result
                    
        except Exception as e:
            return {"error": str(e)}
            
    async def get_user(self, username: str = None) -> Dict[str, Any]:
        """Get user information."""
        endpoint = f"/users/{username}" if username else "/user"
        return await self._make_request("GET", endpoint)
        
    async def list_repos(self, username: str = None, type: str = "all", sort: str = "updated") -> Dict[str, Any]:
        """List repositories."""
        if username:
            endpoint = f"/users/{username}/repos"
        else:
            endpoint = "/user/repos"
            
        params = f"?type={type}&sort={sort}"
        result = await self._make_request("GET", endpoint + params)
        
        if isinstance(result, list):
            repos = []
            for repo in result:
                repos.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo["description"],
                    "private": repo["private"],
                    "url": repo["html_url"],
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo["language"],
                    "updated_at": repo["updated_at"]
                })
            return {"repos": repos, "count": len(repos)}
        else:
            return result
            
    async def get_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information."""
        endpoint = f"/repos/{owner}/{repo}"
        return await self._make_request("GET", endpoint)
        
    async def create_repo(self, name: str, description: str = "", private: bool = False,
                         auto_init: bool = True) -> Dict[str, Any]:
        """Create a new repository."""
        data = {
            "name": name,
            "description": description,
            "private": private,
            "auto_init": auto_init
        }
        return await self._make_request("POST", "/user/repos", data)
        
    async def delete_repo(self, owner: str, repo: str) -> Dict[str, Any]:
        """Delete a repository."""
        endpoint = f"/repos/{owner}/{repo}"
        result = await self._make_request("DELETE", endpoint)
        if result == {}:  # Successful deletion returns empty response
            return {"success": True}
        return result
        
    async def list_issues(self, owner: str, repo: str, state: str = "open",
                         labels: str = None) -> Dict[str, Any]:
        """List repository issues."""
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = f"?state={state}"
        if labels:
            params += f"&labels={labels}"
            
        result = await self._make_request("GET", endpoint + params)
        
        if isinstance(result, list):
            issues = []
            for issue in result:
                issues.append({
                    "number": issue["number"],
                    "title": issue["title"],
                    "state": issue["state"],
                    "user": issue["user"]["login"],
                    "labels": [l["name"] for l in issue["labels"]],
                    "created_at": issue["created_at"],
                    "updated_at": issue["updated_at"],
                    "comments": issue["comments"]
                })
            return {"issues": issues, "count": len(issues)}
        else:
            return result
            
    async def get_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Get issue details."""
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        return await self._make_request("GET", endpoint)
        
    async def create_issue(self, owner: str, repo: str, title: str, body: str = "",
                          labels: List[str] = None, assignees: List[str] = None) -> Dict[str, Any]:
        """Create a new issue."""
        data = {
            "title": title,
            "body": body
        }
        if labels:
            data["labels"] = labels
        if assignees:
            data["assignees"] = assignees
            
        endpoint = f"/repos/{owner}/{repo}/issues"
        return await self._make_request("POST", endpoint, data)
        
    async def update_issue(self, owner: str, repo: str, issue_number: int,
                          title: str = None, body: str = None, state: str = None,
                          labels: List[str] = None) -> Dict[str, Any]:
        """Update an issue."""
        data = {}
        if title:
            data["title"] = title
        if body:
            data["body"] = body
        if state:
            data["state"] = state
        if labels is not None:
            data["labels"] = labels
            
        endpoint = f"/repos/{owner}/{repo}/issues/{issue_number}"
        return await self._make_request("PATCH", endpoint, data)
        
    async def close_issue(self, owner: str, repo: str, issue_number: int) -> Dict[str, Any]:
        """Close an issue."""
        return await self.update_issue(owner, repo, issue_number, state="closed")
        
    async def list_pull_requests(self, owner: str, repo: str, state: str = "open") -> Dict[str, Any]:
        """List pull requests."""
        endpoint = f"/repos/{owner}/{repo}/pulls?state={state}"
        result = await self._make_request("GET", endpoint)
        
        if isinstance(result, list):
            prs = []
            for pr in result:
                prs.append({
                    "number": pr["number"],
                    "title": pr["title"],
                    "state": pr["state"],
                    "user": pr["user"]["login"],
                    "created_at": pr["created_at"],
                    "updated_at": pr["updated_at"],
                    "head": pr["head"]["ref"],
                    "base": pr["base"]["ref"]
                })
            return {"pull_requests": prs, "count": len(prs)}
        else:
            return result
            
    async def create_pull_request(self, owner: str, repo: str, title: str,
                                 head: str, base: str, body: str = "") -> Dict[str, Any]:
        """Create a pull request."""
        data = {
            "title": title,
            "head": head,
            "base": base,
            "body": body
        }
        endpoint = f"/repos/{owner}/{repo}/pulls"
        return await self._make_request("POST", endpoint, data)
        
    async def get_file(self, owner: str, repo: str, path: str, ref: str = None) -> Dict[str, Any]:
        """Get file contents."""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        if ref:
            endpoint += f"?ref={ref}"
            
        result = await self._make_request("GET", endpoint)
        
        if "content" in result:
            # Decode base64 content
            content = base64.b64decode(result["content"]).decode("utf-8")
            result["decoded_content"] = content
            
        return result
        
    async def create_or_update_file(self, owner: str, repo: str, path: str,
                                   message: str, content: str, branch: str = None,
                                   sha: str = None) -> Dict[str, Any]:
        """Create or update a file."""
        # Encode content to base64
        encoded_content = base64.b64encode(content.encode("utf-8")).decode("utf-8")
        
        data = {
            "message": message,
            "content": encoded_content
        }
        if branch:
            data["branch"] = branch
        if sha:  # Required for updates
            data["sha"] = sha
            
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        return await self._make_request("PUT", endpoint, data)
        
    async def delete_file(self, owner: str, repo: str, path: str,
                         message: str, sha: str, branch: str = None) -> Dict[str, Any]:
        """Delete a file."""
        data = {
            "message": message,
            "sha": sha
        }
        if branch:
            data["branch"] = branch
            
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        return await self._make_request("DELETE", endpoint, data)
        
    async def list_branches(self, owner: str, repo: str) -> Dict[str, Any]:
        """List repository branches."""
        endpoint = f"/repos/{owner}/{repo}/branches"
        result = await self._make_request("GET", endpoint)
        
        if isinstance(result, list):
            branches = []
            for branch in result:
                branches.append({
                    "name": branch["name"],
                    "protected": branch["protected"],
                    "commit_sha": branch["commit"]["sha"]
                })
            return {"branches": branches, "count": len(branches)}
        else:
            return result
            
    async def create_branch(self, owner: str, repo: str, branch_name: str,
                           from_branch: str = "main") -> Dict[str, Any]:
        """Create a new branch."""
        # First get the SHA of the source branch
        ref_endpoint = f"/repos/{owner}/{repo}/git/refs/heads/{from_branch}"
        ref_result = await self._make_request("GET", ref_endpoint)
        
        if "error" in ref_result:
            return ref_result
            
        sha = ref_result["object"]["sha"]
        
        # Create new branch
        data = {
            "ref": f"refs/heads/{branch_name}",
            "sha": sha
        }
        endpoint = f"/repos/{owner}/{repo}/git/refs"
        return await self._make_request("POST", endpoint, data)
        
    async def search_code(self, query: str, repo: str = None, language: str = None,
                         limit: int = 10) -> Dict[str, Any]:
        """Search code on GitHub."""
        search_query = query
        if repo:
            search_query += f" repo:{repo}"
        if language:
            search_query += f" language:{language}"
            
        endpoint = f"/search/code?q={search_query}&per_page={limit}"
        result = await self._make_request("GET", endpoint)
        
        if "items" in result:
            items = []
            for item in result["items"]:
                items.append({
                    "name": item["name"],
                    "path": item["path"],
                    "repository": item["repository"]["full_name"],
                    "url": item["html_url"],
                    "score": item["score"]
                })
            return {
                "results": items,
                "count": len(items),
                "total_count": result["total_count"]
            }
        else:
            return result
            
    async def search_repos(self, query: str, language: str = None, sort: str = "stars",
                          limit: int = 10) -> Dict[str, Any]:
        """Search repositories."""
        search_query = query
        if language:
            search_query += f" language:{language}"
            
        endpoint = f"/search/repositories?q={search_query}&sort={sort}&per_page={limit}"
        result = await self._make_request("GET", endpoint)
        
        if "items" in result:
            repos = []
            for repo in result["items"]:
                repos.append({
                    "name": repo["name"],
                    "full_name": repo["full_name"],
                    "description": repo["description"],
                    "stars": repo["stargazers_count"],
                    "forks": repo["forks_count"],
                    "language": repo["language"],
                    "url": repo["html_url"],
                    "owner": repo["owner"]["login"]
                })
            return {
                "results": repos,
                "count": len(repos),
                "total_count": result["total_count"]
            }
        else:
            return result


if __name__ == "__main__":
    parser = create_argument_parser("MCP GitHub Server")
    args = parser.parse_args()
    
    if not os.environ.get("GITHUB_TOKEN"):
        print("Warning: GITHUB_TOKEN not set. Some operations may be limited.")
    
    server = GitHubServer(port=args.port)
    server.run()