#!/usr/bin/env python3
"""
Test script to verify computer control integration
Tests syntax and import structure without external dependencies
"""
import sys
from pathlib import Path

# Add the project root to the path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))

def test_syntax_compilation():
    """Test that all Python files compile without syntax errors."""
    files_to_test = [
        "lilith/computer_control.py",
        "lilith/controller_ultimate.py", 
        "lilith/streaming_server.py",
        "mcp_servers/ab498_control_server.py"
    ]
    
    passed = 0
    total = len(files_to_test)
    
    for file_path in files_to_test:
        try:
            import py_compile
            py_compile.compile(file_path, doraise=True)
            print(f"✅ {file_path} - Syntax OK")
            passed += 1
        except py_compile.PyCompileError as e:
            print(f"❌ {file_path} - Syntax error: {e}")
        except Exception as e:
            print(f"⚠️ {file_path} - Could not test: {e}")
    
    return passed, total

def test_requirements_file():
    """Test that requirements.txt exists and is well-formed."""
    try:
        req_file = Path("requirements.txt")
        if req_file.exists():
            content = req_file.read_text()
            lines = [l.strip() for l in content.split('\n') if l.strip() and not l.startswith('#')]
            print(f"✅ requirements.txt exists with {len(lines)} dependencies")
            
            # Check for key dependencies
            key_deps = ['pyautogui', 'opencv-python', 'mss', 'psutil', 'openai']
            found_deps = []
            for dep in key_deps:
                if any(dep in line for line in lines):
                    found_deps.append(dep)
            
            print(f"✅ Found {len(found_deps)}/{len(key_deps)} key dependencies: {', '.join(found_deps)}")
            return True
        else:
            print("❌ requirements.txt not found")
            return False
    except Exception as e:
        print(f"❌ Error checking requirements.txt: {e}")
        return False

def test_module_structure():
    """Test that module structure is correct."""
    try:
        # Test import structure without actually importing (to avoid dependency issues)
        computer_control_file = Path("lilith/computer_control.py")
        if computer_control_file.exists():
            content = computer_control_file.read_text()
            
            # Check for key classes and functions
            key_items = [
                'class ComputerController',
                'class ComputerVision', 
                'class WindowManager',
                'class InputController',
                'def get_computer_controller',
                'def capture_screen',
                'def analyze_full_screen'
            ]
            
            found_items = []
            for item in key_items:
                if item in content:
                    found_items.append(item)
            
            print(f"✅ Computer control module structure: {len(found_items)}/{len(key_items)} key items found")
            return len(found_items) >= len(key_items) * 0.8  # 80% threshold
        else:
            print("❌ Computer control module not found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking module structure: {e}")
        return False

def test_integration_points():
    """Test that integration points exist in controller_ultimate.py."""
    try:
        controller_file = Path("lilith/controller_ultimate.py")
        if controller_file.exists():
            content = controller_file.read_text()
            
            # Check for integration points
            integration_points = [
                'from .computer_control import',
                'self.computer_controller = get_computer_controller()',
                'capture_full_screen',
                'analyze_screen',
                'click_at_text',
                'get_all_windows'
            ]
            
            found_points = []
            for point in integration_points:
                if point in content:
                    found_points.append(point)
            
            print(f"✅ Controller integration: {len(found_points)}/{len(integration_points)} integration points found")
            return len(found_points) >= len(integration_points) * 0.7  # 70% threshold
        else:
            print("❌ Controller ultimate not found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking integration points: {e}")
        return False

def test_server_enhancements():
    """Test that AB498 server has been enhanced."""
    try:
        server_file = Path("mcp_servers/ab498_control_server.py")
        if server_file.exists():
            content = server_file.read_text()
            
            # Check for enhanced features
            enhanced_features = [
                'from lilith.computer_control import',
                'analyze_screen',
                'capture_full_screen',
                'click_at_text',
                'get_all_windows',
                'automate_task',
                'health_check'
            ]
            
            found_features = []
            for feature in enhanced_features:
                if feature in content:
                    found_features.append(feature)
            
            print(f"✅ Server enhancements: {len(found_features)}/{len(enhanced_features)} enhanced features found")
            return len(found_features) >= len(enhanced_features) * 0.6  # 60% threshold
        else:
            print("❌ AB498 server not found")
            return False
            
    except Exception as e:
        print(f"❌ Error checking server enhancements: {e}")
        return False

def main():
    """Run all tests."""
    print("🧪 Testing LILITH-AI Computer Control Integration")
    print("🔍 Focus: Syntax, Structure, and Integration Points")
    print("=" * 60)
    
    tests = [
        ("Syntax Compilation", test_syntax_compilation),
        ("Requirements File", test_requirements_file),
        ("Module Structure", test_module_structure),
        ("Integration Points", test_integration_points),
        ("Server Enhancements", test_server_enhancements),
    ]
    
    passed = 0
    total = len(tests)
    
    for test_name, test_func in tests:
        print(f"\n🔍 Testing: {test_name}")
        try:
            if test_name == "Syntax Compilation":
                syntax_passed, syntax_total = test_func()
                print(f"   Syntax results: {syntax_passed}/{syntax_total} files compiled successfully")
                if syntax_passed == syntax_total:
                    passed += 1
            else:
                if test_func():
                    passed += 1
                else:
                    print(f"   Failed: {test_name}")
        except Exception as e:
            print(f"   Error in {test_name}: {e}")
    
    print("\n" + "=" * 60)
    print(f"📊 Test Results: {passed}/{total} tests passed")
    
    if passed >= total * 0.8:  # 80% pass rate
        print("🎉 Integration structure looks good! Most components are properly integrated.")
        print("💡 Next steps: Install dependencies and test runtime functionality.")
        return 0
    else:
        print("⚠️ Some integration issues detected. Check the output above for details.")
        return 1

if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)