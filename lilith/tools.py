"""Tools for Lilith to interact with the system."""
from __future__ import annotations

import subprocess
import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Optional, Any
import tempfile
import textwrap
import ast
import traceback


class LilithTools:
    """Collection of tools that Lilith can use to interact with the system."""
    
    def __init__(self, workspace_dir: Optional[Path] = None):
        """Initialize tools with an optional workspace directory."""
        self.workspace = workspace_dir or Path.cwd() / "lilith_workspace"
        self.workspace.mkdir(exist_ok=True)
        
    def execute_python(self, code: str, timeout: int = 10) -> Dict[str, str]:
        """Execute Python code in a sandboxed environment."""
        with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as fp:
            fp.write(textwrap.dedent(code))
            tmp_path = Path(fp.name)
        
        try:
            proc = subprocess.run(
                [sys.executable, str(tmp_path)],
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
            )
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Code execution timed out after {timeout} seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing code: {str(e)}",
                "returncode": -1
            }
        finally:
            tmp_path.unlink(missing_ok=True)
    
    def execute_command(self, command: str, timeout: int = 30) -> Dict[str, Any]:
        """Execute a shell command."""
        try:
            # Use shell=True on Windows, shell=False on Unix
            shell = sys.platform.startswith('win')
            
            proc = subprocess.run(
                command if not shell else command,
                shell=shell,
                capture_output=True,
                text=True,
                timeout=timeout,
                cwd=str(self.workspace)
            )
            
            return {
                "success": proc.returncode == 0,
                "stdout": proc.stdout,
                "stderr": proc.stderr,
                "returncode": proc.returncode
            }
        except subprocess.TimeoutExpired:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Command timed out after {timeout} seconds",
                "returncode": -1
            }
        except Exception as e:
            return {
                "success": False,
                "stdout": "",
                "stderr": f"Error executing command: {str(e)}",
                "returncode": -1
            }
    
    def read_file(self, filepath: str) -> Dict[str, Any]:
        """Read a file from the workspace or absolute path."""
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.workspace / path
                
            if not path.exists():
                return {
                    "success": False,
                    "content": "",
                    "error": f"File not found: {filepath}"
                }
                
            content = path.read_text(encoding='utf-8')
            return {
                "success": True,
                "content": content,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "content": "",
                "error": f"Error reading file: {str(e)}"
            }
    
    def write_file(self, filepath: str, content: str) -> Dict[str, Any]:
        """Write content to a file in the workspace."""
        try:
            path = Path(filepath)
            if not path.is_absolute():
                path = self.workspace / path
                
            # Create parent directories if they don't exist
            path.parent.mkdir(parents=True, exist_ok=True)
            
            path.write_text(content, encoding='utf-8')
            return {
                "success": True,
                "path": str(path),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "path": "",
                "error": f"Error writing file: {str(e)}"
            }
    
    def list_files(self, directory: str = ".") -> Dict[str, Any]:
        """List files in a directory."""
        try:
            path = Path(directory)
            if not path.is_absolute():
                path = self.workspace / path
                
            if not path.exists():
                return {
                    "success": False,
                    "files": [],
                    "error": f"Directory not found: {directory}"
                }
                
            files = []
            for item in path.iterdir():
                files.append({
                    "name": item.name,
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None
                })
                
            return {
                "success": True,
                "files": files,
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "files": [],
                "error": f"Error listing files: {str(e)}"
            }
    
    def analyze_code(self, code: str, language: str = "python") -> Dict[str, Any]:
        """Analyze code structure and provide insights."""
        if language.lower() != "python":
            return {
                "success": False,
                "analysis": {},
                "error": "Currently only Python analysis is supported"
            }
            
        try:
            tree = ast.parse(code)
            
            analysis = {
                "functions": [],
                "classes": [],
                "imports": [],
                "variables": [],
                "line_count": len(code.splitlines()),
                "has_main": False
            }
            
            for node in ast.walk(tree):
                if isinstance(node, ast.FunctionDef):
                    analysis["functions"].append({
                        "name": node.name,
                        "args": [arg.arg for arg in node.args.args],
                        "lineno": node.lineno
                    })
                    if node.name == "main":
                        analysis["has_main"] = True
                elif isinstance(node, ast.ClassDef):
                    analysis["classes"].append({
                        "name": node.name,
                        "lineno": node.lineno,
                        "methods": [n.name for n in node.body if isinstance(n, ast.FunctionDef)]
                    })
                elif isinstance(node, ast.Import):
                    for alias in node.names:
                        analysis["imports"].append(alias.name)
                elif isinstance(node, ast.ImportFrom):
                    analysis["imports"].append(f"{node.module}.{node.names[0].name}")
                elif isinstance(node, ast.Assign) and isinstance(node.targets[0], ast.Name):
                    analysis["variables"].append(node.targets[0].id)
                    
            return {
                "success": True,
                "analysis": analysis,
                "error": None
            }
        except SyntaxError as e:
            return {
                "success": False,
                "analysis": {},
                "error": f"Syntax error in code: {e.msg} at line {e.lineno}"
            }
        except Exception as e:
            return {
                "success": False,
                "analysis": {},
                "error": f"Error analyzing code: {str(e)}"
            }
    
    def create_project(self, name: str, project_type: str = "python") -> Dict[str, Any]:
        """Create a new project structure."""
        try:
            project_path = self.workspace / name
            if project_path.exists():
                return {
                    "success": False,
                    "path": "",
                    "error": f"Project '{name}' already exists"
                }
                
            project_path.mkdir(parents=True)
            
            if project_type == "python":
                # Create Python project structure
                (project_path / "src").mkdir()
                (project_path / "tests").mkdir()
                (project_path / "docs").mkdir()
                
                # Create initial files
                (project_path / "README.md").write_text(f"# {name}\n\nA Python project created by Lilith.")
                (project_path / "requirements.txt").write_text("")
                (project_path / ".gitignore").write_text("__pycache__/\n*.pyc\n.env\nvenv/\n")
                (project_path / "src" / "__init__.py").write_text("")
                (project_path / "src" / "main.py").write_text(
                    'def main():\n    print("Hello from Lilith!")\n\nif __name__ == "__main__":\n    main()\n'
                )
                
            elif project_type == "web":
                # Create web project structure
                (project_path / "css").mkdir()
                (project_path / "js").mkdir()
                (project_path / "images").mkdir()
                
                # Create initial files
                (project_path / "index.html").write_text(
                    '<!DOCTYPE html>\n<html>\n<head>\n    <title>' + name + 
                    '</title>\n    <link rel="stylesheet" href="css/style.css">\n</head>\n<body>\n    ' +
                    '<h1>Welcome to ' + name + '</h1>\n    <p>Created by Lilith</p>\n    ' +
                    '<script src="js/script.js"></script>\n</body>\n</html>'
                )
                (project_path / "css" / "style.css").write_text(
                    'body {\n    font-family: Arial, sans-serif;\n    margin: 0;\n    padding: 20px;\n}'
                )
                (project_path / "js" / "script.js").write_text(
                    'console.log("Hello from Lilith!");'
                )
                
            return {
                "success": True,
                "path": str(project_path),
                "error": None
            }
        except Exception as e:
            return {
                "success": False,
                "path": "",
                "error": f"Error creating project: {str(e)}"
            }
    
    def get_workspace_info(self) -> Dict[str, Any]:
        """Get information about the current workspace."""
        try:
            projects = []
            total_size = 0
            
            for item in self.workspace.iterdir():
                if item.is_dir():
                    size = sum(f.stat().st_size for f in item.rglob('*') if f.is_file())
                    projects.append({
                        "name": item.name,
                        "size": size,
                        "files": len(list(item.rglob('*')))
                    })
                    total_size += size
                    
            return {
                "workspace_path": str(self.workspace),
                "projects": projects,
                "total_size": total_size,
                "project_count": len(projects)
            }
        except Exception as e:
            return {
                "workspace_path": str(self.workspace),
                "projects": [],
                "total_size": 0,
                "project_count": 0,
                "error": str(e)
            }