#!/usr/bin/env python3
"""
Example script demonstrating LILITH-AI enhanced computer control capabilities
Run this script to see the new features in action (requires dependencies installed)
"""

import sys
import time
from pathlib import Path

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def demo_screen_analysis():
    """Demonstrate screen analysis capabilities."""
    print("🔍 Demo: Screen Analysis")
    print("-" * 40)
    
    try:
        from lilith.computer_control import analyze_full_screen
        
        print("Analyzing current screen...")
        analysis = analyze_full_screen(monitor=0)
        
        if analysis:
            print(f"✅ Resolution: {analysis['resolution']['width']}x{analysis['resolution']['height']}")
            print(f"✅ Text elements found: {len(analysis.get('text_elements', []))}")
            print(f"✅ UI elements found: {len(analysis.get('ui_elements', []))}")
            print(f"✅ Open windows: {len(analysis.get('windows', []))}")
            
            # Show some detected text
            text_elements = analysis.get('text_elements', [])[:5]
            if text_elements:
                print("\n📝 Sample detected text:")
                for i, element in enumerate(text_elements):
                    print(f"  {i+1}. '{element['text']}' (confidence: {element['confidence']}%)")
            
            # Show open windows
            windows = analysis.get('windows', [])[:3]
            if windows:
                print("\n🖼️ Open windows:")
                for i, window in enumerate(windows):
                    active = "🟢" if window.get('is_active') else "⚪"
                    print(f"  {active} {window['title']}")
        else:
            print("❌ Screen analysis failed")
            
    except Exception as e:
        print(f"❌ Error: {e}")
        print("💡 Make sure dependencies are installed: pip install -r requirements.txt")

def demo_system_info():
    """Demonstrate system information gathering."""
    print("\n💻 Demo: System Information")
    print("-" * 40)
    
    try:
        from lilith.computer_control import get_computer_controller
        
        controller = get_computer_controller()
        system_info = controller.get_system_info()
        
        print(f"✅ Screen size: {system_info['screen_size']['width']}x{system_info['screen_size']['height']}")
        print(f"✅ Mouse position: ({system_info['mouse_position']['x']}, {system_info['mouse_position']['y']})")
        print(f"✅ CPU usage: {system_info['cpu_percent']:.1f}%")
        print(f"✅ Memory usage: {system_info['memory_percent']:.1f}%")
        print(f"✅ Monitors detected: {len(system_info['monitors'])}")
        
        print("\n🔧 Capabilities:")
        capabilities = system_info['capabilities']
        for cap, available in capabilities.items():
            status = "✅" if available else "❌"
            print(f"  {status} {cap.replace('_', ' ').title()}")
        
        print("\n🔐 Permissions:")
        permissions = system_info['permissions']
        for perm, enabled in permissions.items():
            status = "✅" if enabled else "❌"
            print(f"  {status} {perm.replace('_', ' ').title()}")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_text_detection():
    """Demonstrate text detection on screen."""
    print("\n📝 Demo: Text Detection")
    print("-" * 40)
    
    try:
        from lilith.computer_control import extract_text_from_screen
        
        print("Extracting text from current screen...")
        text_results = extract_text_from_screen(monitor=0)
        
        if text_results:
            print(f"✅ Found {len(text_results)} text elements")
            
            # Show top 10 text elements
            top_texts = text_results[:10]
            print("\n📋 Detected text (top 10):")
            for i, element in enumerate(top_texts):
                bbox = element['bbox']
                print(f"  {i+1:2d}. '{element['text'][:30]}...' at ({bbox[0]}, {bbox[1]}) confidence: {element['confidence']}%")
        else:
            print("❌ No text detected")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_window_management():
    """Demonstrate window management capabilities."""
    print("\n🖼️ Demo: Window Management")
    print("-" * 40)
    
    try:
        from lilith.computer_control import get_all_windows
        
        print("Getting list of all open windows...")
        windows = get_all_windows()
        
        if windows:
            print(f"✅ Found {len(windows)} open windows")
            
            print("\n📋 Window list:")
            for i, window in enumerate(windows[:10]):  # Show top 10
                active = "🟢" if window.get('is_active') else "⚪"
                maximized = "📏" if window.get('is_maximized') else ""
                minimized = "📉" if window.get('is_minimized') else ""
                
                title = window['title'][:40] + "..." if len(window['title']) > 40 else window['title']
                size = f"{window['width']}x{window['height']}"
                pos = f"({window['left']}, {window['top']})"
                
                print(f"  {i+1:2d}. {active}{maximized}{minimized} {title}")
                print(f"      Size: {size}, Position: {pos}")
        else:
            print("❌ No windows detected")
            
    except Exception as e:
        print(f"❌ Error: {e}")

def demo_safe_automation():
    """Demonstrate safe automation capabilities."""
    print("\n🤖 Demo: Safe Automation")
    print("-" * 40)
    
    print("This demo shows automation capabilities without actually executing them.")
    print("In a real scenario, these would perform actual actions.")
    
    example_tasks = [
        {
            "description": "Open calculator and perform calculation",
            "steps": [
                {"action": "key", "params": {"key": "cmd"}},
                {"action": "type", "params": {"text": "calculator"}},
                {"action": "key", "params": {"key": "enter"}},
                {"action": "wait", "params": {"duration": 2}},
                {"action": "type", "params": {"text": "2+2="}},
            ]
        },
        {
            "description": "Take screenshot and analyze",
            "steps": [
                {"action": "take_screenshot", "params": {}},
                {"action": "analyze_screen", "params": {"include_ocr": True}},
            ]
        },
        {
            "description": "Find and click specific text",
            "steps": [
                {"action": "find_and_click_text", "params": {"text": "Submit"}},
                {"action": "wait", "params": {"duration": 1}},
            ]
        }
    ]
    
    for i, task in enumerate(example_tasks):
        print(f"\n📋 Example Task {i+1}: {task['description']}")
        print(f"   Steps: {len(task['steps'])}")
        for j, step in enumerate(task['steps']):
            print(f"     {j+1}. {step['action']} - {step['params']}")

def main():
    """Run all demonstrations."""
    print("🎉 LILITH-AI Enhanced Computer Control Demonstration")
    print("=" * 60)
    print("This script demonstrates the new computer control capabilities.")
    print("Some features require dependencies to be installed.")
    print("=" * 60)
    
    demos = [
        demo_system_info,
        demo_screen_analysis,
        demo_text_detection,
        demo_window_management,
        demo_safe_automation,
    ]
    
    for demo in demos:
        try:
            demo()
            time.sleep(1)  # Brief pause between demos
        except KeyboardInterrupt:
            print("\n⚠️ Demo interrupted by user")
            break
        except Exception as e:
            print(f"\n❌ Demo failed: {e}")
    
    print("\n" + "=" * 60)
    print("🎯 Demo Complete!")
    print("\n💡 Next Steps:")
    print("  1. Install dependencies: pip install -r requirements.txt")
    print("  2. Start LILITH-AI: python launch_ultimate_rtx3060.py")
    print("  3. Try asking the AI to analyze your screen or control applications")
    print("  4. Check COMPUTER_CONTROL_GUIDE.md for detailed usage information")
    print("\n🔒 Security Note:")
    print("  The AI has safety limits and permissions to prevent misuse.")
    print("  All actions are logged for audit purposes.")

if __name__ == "__main__":
    main()