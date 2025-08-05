"""Diagnostic system for LILITH AI vision and control capabilities."""
from __future__ import annotations

import sys
import platform
import traceback
from typing import Dict, List, Tuple, Any
from pathlib import Path

# Import checking function
def _safe_import(module_name: str) -> Tuple[bool, str, Any]:
    """Safely import a module and return status."""
    try:
        if module_name == "mss":
            import mss
            return True, "Available", mss
        elif module_name == "pyautogui":
            import pyautogui
            return True, "Available", pyautogui
        elif module_name == "pynput":
            import pynput
            return True, "Available", pynput
        elif module_name == "cv2":
            import cv2
            return True, "Available", cv2
        elif module_name == "PIL":
            from PIL import Image
            return True, "Available", Image
        else:
            exec(f"import {module_name}")
            return True, "Available", None
    except ImportError as e:
        return False, f"Missing: {str(e)}", None
    except Exception as e:
        return False, f"Error: {str(e)}", None


class LilithDiagnostics:
    """Comprehensive diagnostic system for LILITH AI."""
    
    def __init__(self):
        self.os_info = self._get_os_info()
        self.dependency_status = {}
        self.vision_status = {}
        self.control_status = {}
        self.permissions_status = {}
        
    def _get_os_info(self) -> Dict[str, str]:
        """Get operating system information."""
        return {
            "system": platform.system(),
            "release": platform.release(),
            "version": platform.version(),
            "machine": platform.machine(),
            "python_version": sys.version,
        }
    
    def check_dependencies(self) -> Dict[str, Dict[str, Any]]:
        """Check all required dependencies."""
        required_deps = {
            "mss": "Multi-monitor screen capture",
            "pyautogui": "Basic screen capture and control (fallback)",
            "pynput": "Cross-platform input control",
            "cv2": "OpenCV for image processing and video",
            "PIL": "Python Imaging Library",
            "numpy": "Numerical processing",
        }
        
        results = {}
        for dep, description in required_deps.items():
            available, status, module = _safe_import(dep)
            results[dep] = {
                "available": available,
                "status": status,
                "description": description,
                "module": module
            }
            
        self.dependency_status = results
        return results
    
    def check_vision_capabilities(self) -> Dict[str, Any]:
        """Test vision and screen capture capabilities."""
        results = {
            "multi_monitor_support": False,
            "full_screen_capture": False,
            "monitor_info": [],
            "capture_methods": [],
            "errors": []
        }
        
        # Test MSS (Multi-Screen Shot)
        mss_available, _, mss_module = _safe_import("mss")
        if mss_available and mss_module:
            try:
                with mss_module.mss() as sct:
                    # Get monitor information
                    monitors = sct.monitors
                    results["monitor_info"] = [
                        {
                            "index": i,
                            "left": mon["left"],
                            "top": mon["top"], 
                            "width": mon["width"],
                            "height": mon["height"]
                        }
                        for i, mon in enumerate(monitors)
                    ]
                    
                    # Test capture
                    if len(monitors) > 1:  # Monitor 0 is all monitors combined
                        screenshot = sct.grab(monitors[0])  # All monitors
                        if screenshot:
                            results["multi_monitor_support"] = True
                            results["full_screen_capture"] = True
                            results["capture_methods"].append("mss (recommended)")
                            
                    # Test individual monitor capture
                    for i, monitor in enumerate(monitors[1:], 1):
                        try:
                            screenshot = sct.grab(monitor)
                            if screenshot:
                                results["capture_methods"].append(f"mss_monitor_{i}")
                        except Exception as e:
                            results["errors"].append(f"MSS monitor {i} error: {str(e)}")
                            
            except Exception as e:
                results["errors"].append(f"MSS error: {str(e)}")
        
        # Test PyAutoGUI (fallback)
        pyautogui_available, _, pyautogui_module = _safe_import("pyautogui")
        if pyautogui_available and pyautogui_module:
            try:
                # Test basic screenshot
                screenshot = pyautogui_module.screenshot()
                if screenshot:
                    results["capture_methods"].append("pyautogui (fallback)")
                    if not results["full_screen_capture"]:
                        results["full_screen_capture"] = True
                        
                # Get screen size
                size = pyautogui_module.size()
                if not results["monitor_info"]:
                    results["monitor_info"] = [{
                        "index": 1,
                        "left": 0,
                        "top": 0,
                        "width": size[0],
                        "height": size[1]
                    }]
                    
            except Exception as e:
                results["errors"].append(f"PyAutoGUI error: {str(e)}")
        
        self.vision_status = results
        return results
    
    def check_control_capabilities(self) -> Dict[str, Any]:
        """Test keyboard and mouse control capabilities."""
        results = {
            "mouse_control": False,
            "keyboard_control": False,
            "control_methods": [],
            "coordinate_systems": [],
            "errors": []
        }
        
        # Test pynput
        pynput_available, _, pynput_module = _safe_import("pynput")
        if pynput_available and pynput_module:
            try:
                from pynput import mouse, keyboard
                
                # Test mouse control
                try:
                    current_pos = mouse.Controller().position
                    results["mouse_control"] = True
                    results["control_methods"].append("pynput_mouse (recommended)")
                    results["coordinate_systems"].append("absolute_pixels")
                except Exception as e:
                    results["errors"].append(f"Pynput mouse error: {str(e)}")
                
                # Test keyboard control
                try:
                    kb = keyboard.Controller()
                    results["keyboard_control"] = True
                    results["control_methods"].append("pynput_keyboard (recommended)")
                except Exception as e:
                    results["errors"].append(f"Pynput keyboard error: {str(e)}")
                    
            except Exception as e:
                results["errors"].append(f"Pynput import error: {str(e)}")
        
        # Test PyAutoGUI (fallback)
        pyautogui_available, _, pyautogui_module = _safe_import("pyautogui")
        if pyautogui_available and pyautogui_module:
            try:
                # Test mouse control
                pos = pyautogui_module.position()
                if not results["mouse_control"]:
                    results["mouse_control"] = True
                results["control_methods"].append("pyautogui_mouse (fallback)")
                if "absolute_pixels" not in results["coordinate_systems"]:
                    results["coordinate_systems"].append("absolute_pixels")
                
                # Test keyboard control
                if not results["keyboard_control"]:
                    results["keyboard_control"] = True
                results["control_methods"].append("pyautogui_keyboard (fallback)")
                    
            except Exception as e:
                results["errors"].append(f"PyAutoGUI control error: {str(e)}")
        
        self.control_status = results
        return results
    
    def check_permissions(self) -> Dict[str, Any]:
        """Check OS-specific permissions for vision and control."""
        results = {
            "accessibility_enabled": False,
            "screen_recording_enabled": False,
            "automation_permissions": False,
            "permission_issues": [],
            "configuration_advice": []
        }
        
        os_type = self.os_info["system"]
        
        if os_type == "Darwin":  # macOS
            results["configuration_advice"] = [
                "macOS requires specific permissions for automation:",
                "1. System Preferences > Security & Privacy > Privacy",
                "2. Enable 'Accessibility' for your Python/Terminal app",
                "3. Enable 'Screen Recording' for your Python/Terminal app",
                "4. Enable 'Automation' if using AppleScript integration",
                "5. You may need to restart the application after granting permissions"
            ]
            
            # Check for common permission errors
            try:
                import pyautogui
                pyautogui.screenshot()
                results["screen_recording_enabled"] = True
            except Exception as e:
                if "accessibility" in str(e).lower() or "permission" in str(e).lower():
                    results["permission_issues"].append("Screen recording permission denied")
                    
            try:
                import pyautogui
                pyautogui.position()
                results["accessibility_enabled"] = True
            except Exception as e:
                if "accessibility" in str(e).lower() or "permission" in str(e).lower():
                    results["permission_issues"].append("Accessibility permission denied")
                    
        elif os_type == "Windows":  # Windows
            results["configuration_advice"] = [
                "Windows may require administrator privileges for some automation:",
                "1. Run as Administrator if experiencing permission issues",
                "2. Disable UAC (User Account Control) for automation apps if needed",
                "3. Add Python to Windows Defender exclusions if antivirus blocks automation",
                "4. For corporate environments, check Group Policy restrictions",
                "5. Some antivirus software may block automation - add exceptions"
            ]
            
            # Windows generally has fewer permission restrictions
            results["accessibility_enabled"] = True
            results["screen_recording_enabled"] = True
            results["automation_permissions"] = True
            
        else:  # Linux/Unix
            results["configuration_advice"] = [
                "Linux requires X11 or Wayland permissions for automation:",
                "1. Ensure X11 forwarding is enabled for remote sessions",
                "2. Add user to 'input' group for low-level input access:",
                "   sudo usermod -a -G input $USER",
                "3. For Wayland, some automation may not work - consider X11",
                "4. Install xdotool for additional automation capabilities:",
                "   sudo apt-get install xdotool",
                "5. Check if running in a sandbox that restricts automation"
            ]
            
            # Check X11 availability
            try:
                import os
                if os.environ.get("DISPLAY"):
                    results["accessibility_enabled"] = True
                    results["screen_recording_enabled"] = True
                else:
                    results["permission_issues"].append("No DISPLAY environment variable (X11 not available)")
            except Exception as e:
                results["permission_issues"].append(f"X11 check failed: {str(e)}")
        
        self.permissions_status = results
        return results
    
    def run_full_diagnostic(self) -> Dict[str, Any]:
        """Run comprehensive diagnostic check."""
        print("🔍 Running LILITH AI diagnostic check...")
        
        results = {
            "system_info": self.os_info,
            "dependencies": self.check_dependencies(),
            "vision": self.check_vision_capabilities(),
            "control": self.check_control_capabilities(),
            "permissions": self.check_permissions(),
            "overall_status": "unknown"
        }
        
        # Determine overall status
        critical_issues = []
        warnings = []
        
        # Check dependencies
        for dep, info in results["dependencies"].items():
            if not info["available"]:
                if dep in ["mss", "pyautogui"]:  # At least one vision method needed
                    critical_issues.append(f"No screen capture method available: {dep} missing")
                elif dep in ["pynput"]:  # Control methods
                    warnings.append(f"Recommended control library missing: {dep}")
        
        # Check vision capabilities
        if not results["vision"]["full_screen_capture"]:
            critical_issues.append("Screen capture not working")
        
        if not results["vision"]["capture_methods"]:
            critical_issues.append("No working screen capture methods found")
            
        # Check control capabilities  
        if not results["control"]["mouse_control"]:
            critical_issues.append("Mouse control not working")
            
        if not results["control"]["keyboard_control"]:
            critical_issues.append("Keyboard control not working")
        
        # Determine status
        if critical_issues:
            results["overall_status"] = "critical"
            results["critical_issues"] = critical_issues
        elif warnings:
            results["overall_status"] = "warning"
            results["warnings"] = warnings
        else:
            results["overall_status"] = "healthy"
            
        results["summary"] = self._generate_summary(results)
        return results
    
    def _generate_summary(self, results: Dict[str, Any]) -> str:
        """Generate human-readable summary of diagnostic results."""
        status = results["overall_status"]
        
        if status == "healthy":
            return "✅ LILITH AI vision and control systems are fully operational!"
        
        summary_lines = []
        
        if status == "critical":
            summary_lines.append("❌ CRITICAL ISSUES DETECTED:")
            for issue in results.get("critical_issues", []):
                summary_lines.append(f"   • {issue}")
        
        if results.get("warnings"):
            summary_lines.append("⚠️ WARNINGS:")
            for warning in results["warnings"]:
                summary_lines.append(f"   • {warning}")
        
        # Add configuration advice if there are permission issues
        if results["permissions"]["permission_issues"]:
            summary_lines.append("\n🔧 CONFIGURATION REQUIRED:")
            for advice in results["permissions"]["configuration_advice"]:
                summary_lines.append(f"   {advice}")
        
        return "\n".join(summary_lines)
    
    def print_detailed_report(self, results: Dict[str, Any] = None):
        """Print detailed diagnostic report."""
        if results is None:
            results = self.run_full_diagnostic()
            
        print("\n" + "="*60)
        print("           LILITH AI DIAGNOSTIC REPORT")
        print("="*60)
        
        # System Info
        print(f"\n🖥️ SYSTEM INFORMATION:")
        print(f"   OS: {results['system_info']['system']} {results['system_info']['release']}")
        print(f"   Machine: {results['system_info']['machine']}")
        print(f"   Python: {results['system_info']['python_version'].split()[0]}")
        
        # Dependencies
        print(f"\n📦 DEPENDENCIES:")
        for dep, info in results["dependencies"].items():
            status_icon = "✅" if info["available"] else "❌"
            print(f"   {status_icon} {dep}: {info['status']}")
            
        # Vision
        print(f"\n👁️ VISION CAPABILITIES:")
        vision = results["vision"]
        print(f"   Multi-monitor support: {'✅' if vision['multi_monitor_support'] else '❌'}")
        print(f"   Full screen capture: {'✅' if vision['full_screen_capture'] else '❌'}")
        print(f"   Available methods: {', '.join(vision['capture_methods'])}")
        print(f"   Detected monitors: {len(vision['monitor_info'])}")
        
        # Control
        print(f"\n🎮 CONTROL CAPABILITIES:")
        control = results["control"]
        print(f"   Mouse control: {'✅' if control['mouse_control'] else '❌'}")
        print(f"   Keyboard control: {'✅' if control['keyboard_control'] else '❌'}")
        print(f"   Available methods: {', '.join(control['control_methods'])}")
        
        # Permissions
        print(f"\n🔐 PERMISSIONS:")
        perms = results["permissions"]
        print(f"   Accessibility: {'✅' if perms['accessibility_enabled'] else '⚠️'}")
        print(f"   Screen recording: {'✅' if perms['screen_recording_enabled'] else '⚠️'}")
        
        # Summary
        print(f"\n📋 SUMMARY:")
        print(results["summary"])
        
        print("\n" + "="*60)


def run_startup_diagnostic() -> bool:
    """Run diagnostic check and return True if systems are operational."""
    diagnostics = LilithDiagnostics()
    results = diagnostics.run_full_diagnostic()
    
    print(results["summary"])
    
    if results["overall_status"] == "critical":
        print("\n💡 To see detailed diagnostic information, run:")
        print("   from lilith.diagnostics import LilithDiagnostics")
        print("   LilithDiagnostics().print_detailed_report()")
        return False
    
    return True


if __name__ == "__main__":
    # Run diagnostic when called directly
    diagnostics = LilithDiagnostics()
    diagnostics.print_detailed_report()