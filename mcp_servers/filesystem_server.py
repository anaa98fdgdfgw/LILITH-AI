"""MCP Filesystem Server."""
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from base_server import BaseMCPServer, create_argument_parser
from pathlib import Path
import json
import shutil
from typing import List, Dict, Any
import mimetypes


class FilesystemServer(BaseMCPServer):
    """Filesystem operations MCP server."""
    
    def __init__(self, port: int = 3001, allowed_dirs: List[str] = None):
        super().__init__("filesystem", port)
        self.allowed_dirs = [Path(d).resolve() for d in (allowed_dirs or [Path.cwd()])]
        
        # Register methods
        self.register_method("read_file", self.read_file)
        self.register_method("write_file", self.write_file)
        self.register_method("list_directory", self.list_directory)
        self.register_method("create_directory", self.create_directory)
        self.register_method("delete_file", self.delete_file)
        self.register_method("move_file", self.move_file)
        self.register_method("copy_file", self.copy_file)
        self.register_method("get_file_info", self.get_file_info)
        self.register_method("search_files", self.search_files)
        
    def _is_allowed_path(self, path: Path) -> bool:
        """Check if path is within allowed directories."""
        path = path.resolve()
        return any(str(path).startswith(str(allowed_dir)) for allowed_dir in self.allowed_dirs)
        
    async def read_file(self, path: str, encoding: str = "utf-8") -> Dict[str, Any]:
        """Read a file."""
        try:
            file_path = Path(path).resolve()
            if not self._is_allowed_path(file_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not file_path.exists():
                return {"error": "File not found"}
                
            if file_path.is_dir():
                return {"error": "Path is a directory"}
                
            # Try to read as text first
            try:
                content = file_path.read_text(encoding=encoding)
                return {"content": content, "encoding": encoding}
            except UnicodeDecodeError:
                # Read as binary
                content = file_path.read_bytes()
                import base64
                return {"content": base64.b64encode(content).decode(), "encoding": "base64"}
                
        except Exception as e:
            return {"error": str(e)}
            
    async def write_file(self, path: str, content: str, encoding: str = "utf-8", create_dirs: bool = True) -> Dict[str, Any]:
        """Write a file."""
        try:
            file_path = Path(path).resolve()
            if not self._is_allowed_path(file_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if create_dirs:
                file_path.parent.mkdir(parents=True, exist_ok=True)
                
            # Check if content is base64 encoded
            if encoding == "base64":
                import base64
                content_bytes = base64.b64decode(content)
                file_path.write_bytes(content_bytes)
            else:
                file_path.write_text(content, encoding=encoding)
                
            return {"success": True, "path": str(file_path)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def list_directory(self, path: str = ".", pattern: str = "*") -> Dict[str, Any]:
        """List directory contents."""
        try:
            dir_path = Path(path).resolve()
            if not self._is_allowed_path(dir_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not dir_path.exists():
                return {"error": "Directory not found"}
                
            if not dir_path.is_dir():
                return {"error": "Path is not a directory"}
                
            items = []
            for item in dir_path.glob(pattern):
                items.append({
                    "name": item.name,
                    "path": str(item),
                    "type": "directory" if item.is_dir() else "file",
                    "size": item.stat().st_size if item.is_file() else None,
                    "modified": item.stat().st_mtime
                })
                
            return {"items": items, "count": len(items)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def create_directory(self, path: str, parents: bool = True) -> Dict[str, Any]:
        """Create a directory."""
        try:
            dir_path = Path(path).resolve()
            if not self._is_allowed_path(dir_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            dir_path.mkdir(parents=parents, exist_ok=True)
            return {"success": True, "path": str(dir_path)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def delete_file(self, path: str, recursive: bool = False) -> Dict[str, Any]:
        """Delete a file or directory."""
        try:
            file_path = Path(path).resolve()
            if not self._is_allowed_path(file_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not file_path.exists():
                return {"error": "Path not found"}
                
            if file_path.is_dir():
                if recursive:
                    shutil.rmtree(file_path)
                else:
                    file_path.rmdir()
            else:
                file_path.unlink()
                
            return {"success": True}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def move_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Move a file or directory."""
        try:
            src_path = Path(source).resolve()
            dst_path = Path(destination).resolve()
            
            if not self._is_allowed_path(src_path) or not self._is_allowed_path(dst_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not src_path.exists():
                return {"error": "Source not found"}
                
            shutil.move(str(src_path), str(dst_path))
            return {"success": True, "new_path": str(dst_path)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def copy_file(self, source: str, destination: str) -> Dict[str, Any]:
        """Copy a file or directory."""
        try:
            src_path = Path(source).resolve()
            dst_path = Path(destination).resolve()
            
            if not self._is_allowed_path(src_path) or not self._is_allowed_path(dst_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not src_path.exists():
                return {"error": "Source not found"}
                
            if src_path.is_dir():
                shutil.copytree(str(src_path), str(dst_path))
            else:
                shutil.copy2(str(src_path), str(dst_path))
                
            return {"success": True, "new_path": str(dst_path)}
            
        except Exception as e:
            return {"error": str(e)}
            
    async def get_file_info(self, path: str) -> Dict[str, Any]:
        """Get detailed file information."""
        try:
            file_path = Path(path).resolve()
            if not self._is_allowed_path(file_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not file_path.exists():
                return {"error": "Path not found"}
                
            stat = file_path.stat()
            info = {
                "name": file_path.name,
                "path": str(file_path),
                "type": "directory" if file_path.is_dir() else "file",
                "size": stat.st_size,
                "created": stat.st_ctime,
                "modified": stat.st_mtime,
                "accessed": stat.st_atime,
                "permissions": oct(stat.st_mode)[-3:],
                "mime_type": mimetypes.guess_type(str(file_path))[0] if file_path.is_file() else None
            }
            
            if file_path.is_dir():
                info["item_count"] = len(list(file_path.iterdir()))
                
            return info
            
        except Exception as e:
            return {"error": str(e)}
            
    async def search_files(self, pattern: str, path: str = ".", recursive: bool = True) -> Dict[str, Any]:
        """Search for files matching a pattern."""
        try:
            search_path = Path(path).resolve()
            if not self._is_allowed_path(search_path):
                return {"error": "Access denied: Path not in allowed directories"}
                
            if not search_path.exists():
                return {"error": "Search path not found"}
                
            matches = []
            if recursive:
                for match in search_path.rglob(pattern):
                    if self._is_allowed_path(match):
                        matches.append({
                            "name": match.name,
                            "path": str(match),
                            "type": "directory" if match.is_dir() else "file",
                            "size": match.stat().st_size if match.is_file() else None
                        })
            else:
                for match in search_path.glob(pattern):
                    if self._is_allowed_path(match):
                        matches.append({
                            "name": match.name,
                            "path": str(match),
                            "type": "directory" if match.is_dir() else "file",
                            "size": match.stat().st_size if match.is_file() else None
                        })
                        
            return {"matches": matches, "count": len(matches)}
            
        except Exception as e:
            return {"error": str(e)}


if __name__ == "__main__":
    parser = create_argument_parser("MCP Filesystem Server")
    parser.add_argument('--allowed-directories', nargs='+', 
                       help='Directories to allow access to')
    args = parser.parse_args()
    
    allowed_dirs = args.allowed_directories or [str(Path.cwd())]
    server = FilesystemServer(port=args.port, allowed_dirs=allowed_dirs)
    server.run()
