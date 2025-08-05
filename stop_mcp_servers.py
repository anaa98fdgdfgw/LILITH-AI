"""Stop all MCP servers and clean up ports."""

import subprocess
import psutil
import time
import sys

# MCP ports to clean
MCP_PORTS = [3001, 3002, 3005, 3006, 3009, 3010, 3011, 3012]

def kill_process_on_port(port):
    """Kill process using a specific port."""
    try:
        # Find process using the port
        for conn in psutil.net_connections():
            if conn.laddr.port == port and conn.status == 'LISTEN':
                try:
                    process = psutil.Process(conn.pid)
                    print(f"Killing process {process.name()} (PID: {conn.pid}) on port {port}")
                    process.terminate()
                    time.sleep(0.5)
                    if process.is_running():
                        process.kill()
                    return True
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    pass
    except Exception as e:
        print(f"Error checking port {port}: {e}")
    return False

def main():
    print("🛑 Stopping all MCP servers...")
    print("=" * 60)
    
    # Kill all Python processes (be careful with this!)
    killed_any = False
    
    # First, try to kill processes on specific ports
    for port in MCP_PORTS:
        if kill_process_on_port(port):
            killed_any = True
    
    # Also kill any remaining Python processes that might be MCP servers
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            if proc.info['name'] == 'python.exe' or proc.info['name'] == 'python':
                cmdline = proc.info.get('cmdline', [])
                if cmdline and any('mcp_server' in arg for arg in cmdline):
                    print(f"Killing MCP server process (PID: {proc.info['pid']})")
                    proc.terminate()
                    killed_any = True
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass
    
    if killed_any:
        print("\n✅ MCP servers stopped")
        time.sleep(2)  # Give time for ports to be released
    else:
        print("\n⚠️ No MCP servers found running")
    
    # Verify ports are free
    print("\nVerifying ports are free...")
    all_free = True
    for port in MCP_PORTS:
        try:
            for conn in psutil.net_connections():
                if conn.laddr.port == port and conn.status == 'LISTEN':
                    print(f"❌ Port {port} is still in use")
                    all_free = False
                    break
            else:
                print(f"✅ Port {port} is free")
        except:
            pass
    
    if all_free:
        print("\n✅ All MCP ports are now free!")
    else:
        print("\n⚠️ Some ports are still in use. You may need to restart your system.")
    
    print("\nPress Enter to exit...")
    input()

if __name__ == "__main__":
    main()