# LILITH-AI Enhanced Computer Control Integration

## Overview

LILITH-AI has been successfully enhanced with complete computer control capabilities, integrating the full power of computer-control-mcp. The AI can now see the entire screen, extract text with OCR, manage windows, and perform complex automation tasks with advanced safety measures.

## New Capabilities

### 🎯 Enhanced Vision System
- **Full Screen OCR**: Extract all text from screen with confidence scores and bounding boxes
- **UI Element Detection**: Automatically detect buttons, text fields, and interactive elements
- **Multi-Monitor Support**: Capture and analyze content across multiple displays
- **Real-time Analysis**: Continuous screen monitoring with intelligent change detection

### 🖱️ Complete Mouse & Keyboard Control
- **Precise Mouse Control**: Click, drag, scroll with pixel-perfect accuracy
- **Relative Coordinates**: Support for both absolute and relative positioning
- **Advanced Keyboard Input**: Type text, press keys, execute shortcuts
- **Safety Limits**: Rate limiting and bounds checking to prevent abuse

### 🖼️ Window Management
- **Window Discovery**: Find and list all open windows
- **Window Control**: Activate, resize, move, minimize, maximize
- **Smart Targeting**: Find windows by title patterns
- **Multi-Application**: Control any application on the system

### 🤖 Task Automation
- **Sequence Execution**: Run complex automation workflows
- **Error Handling**: Robust error recovery and reporting
- **Step-by-Step Control**: Execute tasks with precise timing
- **Conditional Logic**: Smart decision making based on screen content

### 🔒 Security & Safety
- **Permission System**: Granular control over what actions are allowed
- **Rate Limiting**: Prevent excessive mouse clicks or keystrokes
- **Audit Logging**: Complete log of all actions taken
- **Safe Defaults**: Conservative permissions by default

## Available Tools

### Vision Tools
```python
# Capture full screen with OCR analysis
capture_full_screen(monitor=0)

# Complete screen analysis
analyze_screen(monitor=0, include_ocr=True, include_ui_elements=True)

# Extract text from current screen
extract_text_from_screen(monitor=0)
```

### Input Control Tools
```python
# Click at specific coordinates
click_screen(x=100, y=200, button="left")

# Click using relative coordinates (0.0-1.0)
click_screen(x_rel=0.5, y_rel=0.3, button="left")

# Find and click on specific text
click_at_text(text="Submit", monitor=0)

# Type text with optional delay
type_text(text="Hello World", interval=0.1)

# Press keyboard keys
press_key(key="enter", presses=1)

# Keyboard shortcuts
key_combination(keys=["ctrl", "c"])

# Drag operations
drag_mouse(start_x=100, start_y=100, end_x=200, end_y=200, duration=1.0)

# Mouse scrolling
scroll_at(x=500, y=300, clicks=3, direction="up")
```

### Window Management Tools
```python
# Get all open windows
get_all_windows()

# Activate a window by title
activate_window(title_pattern="Chrome")

# Resize a window
resize_window(title_pattern="Notepad", width=800, height=600)

# Move a window
move_window(title_pattern="Calculator", x=100, y=100)
```

### System Information
```python
# Get comprehensive system info
get_system_info()
```

### Task Automation
```python
# Execute complex automation sequence
automate_task(
    description="Open calculator and perform calculation",
    steps=[
        {"action": "key", "params": {"key": "cmd"}},
        {"action": "type", "params": {"text": "calculator"}},
        {"action": "key", "params": {"key": "enter"}},
        {"action": "wait", "params": {"duration": 2}},
        {"action": "type", "params": {"text": "2+2="}},
    ]
)
```

## Usage Examples

### Example 1: Analyze Current Screen
```python
# Get complete screen analysis
analysis = analyze_screen(monitor=0)
print(f"Found {len(analysis['text_elements'])} text elements")
print(f"Found {len(analysis['ui_elements'])} UI elements")
print(f"Active window: {analysis['windows'][0]['title']}")
```

### Example 2: Find and Click Text
```python
# Find "Submit" button and click it
success = click_at_text("Submit")
if success:
    print("Successfully clicked Submit button")
else:
    print("Submit button not found")
```

### Example 3: Window Management
```python
# Switch to Chrome browser
activate_window("Chrome")

# Resize it to specific dimensions
resize_window("Chrome", 1200, 800)

# Move it to top-left corner
move_window("Chrome", 0, 0)
```

### Example 4: Complex Automation
```python
# Automated web search example
automate_task("Perform web search", [
    {"action": "activate_window", "params": {"title_pattern": "Chrome"}},
    {"action": "key", "params": {"key": "ctrl+l"}},  # Address bar
    {"action": "type", "params": {"text": "github.com"}},
    {"action": "key", "params": {"key": "enter"}},
    {"action": "wait", "params": {"duration": 3}},
    {"action": "find_and_click_text", "params": {"text": "Search"}}
])
```

## Configuration

### Permissions
Control what the AI can do:
```python
from lilith.computer_control import ComputerControlConfig

config = ComputerControlConfig()
config.permissions = {
    'screen_capture': True,      # Allow screen capture
    'mouse_control': True,       # Allow mouse control
    'keyboard_control': True,    # Allow keyboard input
    'window_management': True,   # Allow window operations
    'system_commands': False,    # Restrict system commands
}
```

### Safety Limits
Configure rate limiting:
```python
config.safety_bounds = {
    'max_clicks_per_minute': 60,        # Limit mouse clicks
    'max_keystrokes_per_minute': 300,   # Limit keystrokes
    'screenshot_interval_ms': 100,      # Screenshot frequency
    'ocr_cache_duration': 5,           # OCR cache time
}
```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **OCR Setup** (Optional but recommended):
   - **Tesseract**: Install from https://github.com/tesseract-ocr/tesseract
   - **EasyOCR**: Automatically installed with requirements

3. **Platform-Specific**:
   - **Windows**: PyWin32 for advanced Windows API features
   - **Linux**: X11 development libraries for screen capture
   - **macOS**: May require accessibility permissions

## Integration Points

### Controller Ultimate
The main controller now includes all computer control capabilities:
- Enhanced system prompt with new tool descriptions
- Automatic fallback to legacy tools when enhanced control unavailable
- Comprehensive error handling and user feedback

### Streaming Server  
Real-time streaming enhanced with:
- Full screen analysis during chat interactions
- Enhanced context generation with OCR results
- Multi-monitor support for streaming
- Dynamic screen change detection

### UI Ultimate
Gradio interface includes:
- Computer control status display
- Capability detection and reporting
- Real-time system monitoring
- Permission management interface

### AB498 MCP Server
Enhanced server provides:
- All computer-control-mcp capabilities via JSON-RPC
- Backward compatibility with existing clients
- Health check endpoints
- Enhanced error reporting

## Security Considerations

### Safe Defaults
- Most restrictive permissions enabled by default
- Rate limiting active to prevent abuse
- Comprehensive audit logging
- Error handling prevents system crashes

### Best Practices
- Review audit logs regularly
- Use minimum required permissions
- Test automation scripts in safe environments
- Monitor system resource usage

### Audit Trail
All actions are logged with:
- Timestamp and action type
- Parameters and results
- User context and permissions
- System state information

## Troubleshooting

### Common Issues

1. **"Computer control not available"**
   - Check if dependencies are installed
   - Verify permissions are enabled
   - Check audit logs for errors

2. **OCR not working**
   - Install Tesseract or EasyOCR
   - Check image quality and contrast
   - Verify text language settings

3. **Window operations failing**
   - Check if target application is running
   - Verify window titles match patterns
   - Ensure sufficient system permissions

4. **Rate limiting errors**
   - Reduce automation speed
   - Increase rate limit thresholds
   - Add delays between operations

### Debugging
- Enable detailed logging in config
- Use test_computer_control.py for verification
- Check system resource usage
- Monitor network connectivity for MCP servers

## Future Enhancements

Potential future improvements:
- Machine learning-based UI element recognition
- Cross-platform window management improvements
- Enhanced OCR with multiple language support
- Integration with browser automation tools
- Advanced computer vision capabilities

## Support

For issues or questions:
1. Check the audit logs for error details
2. Run the test script to verify installation
3. Review the troubleshooting section
4. Check system permissions and dependencies