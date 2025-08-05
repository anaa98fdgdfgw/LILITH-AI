"""
Complete computer control module for LILITH-AI
Integrates full computer-control-mcp capabilities with vision, OCR, and automation.
"""
from __future__ import annotations

import base64
import json
import logging
import os
import time
from pathlib import Path
from typing import Dict, List, Optional, Tuple, Any, Union
import threading
import hashlib

import cv2
import numpy as np
from PIL import Image, ImageGrab
import mss
import pyautogui
import pygetwindow as gw
import psutil

# OCR imports
try:
    import pytesseract
    TESSERACT_AVAILABLE = True
except ImportError:
    TESSERACT_AVAILABLE = False

try:
    import easyocr
    EASYOCR_AVAILABLE = True
except ImportError:
    EASYOCR_AVAILABLE = False

# Keyboard and mouse control
try:
    import keyboard
    import mouse as mouse_lib
    import pyperclip
    ADVANCED_INPUT_AVAILABLE = True
except ImportError:
    ADVANCED_INPUT_AVAILABLE = False

# Windows-specific imports
try:
    import win32gui
    import win32con
    import win32api
    import win32clipboard
    WINDOWS_API_AVAILABLE = True
except ImportError:
    WINDOWS_API_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Security and configuration
class ComputerControlConfig:
    """Configuration and security settings for computer control."""
    
    def __init__(self):
        self.permissions = {
            'screen_capture': True,
            'mouse_control': True,
            'keyboard_control': True,
            'window_management': True,
            'file_operations': True,
            'system_commands': False,  # More restrictive by default
        }
        self.safety_bounds = {
            'max_clicks_per_minute': 60,
            'max_keystrokes_per_minute': 300,
            'screenshot_interval_ms': 100,
            'ocr_cache_duration': 5,  # seconds
        }
        self.audit_log_enabled = True
        self.log_file = Path("computer_control_audit.log")
        
    def check_permission(self, action: str) -> bool:
        """Check if an action is permitted."""
        return self.permissions.get(action, False)
    
    def log_action(self, action: str, details: Dict[str, Any]):
        """Log an action for audit trail."""
        if self.audit_log_enabled:
            timestamp = time.strftime('%Y-%m-%d %H:%M:%S')
            log_entry = {
                'timestamp': timestamp,
                'action': action,
                'details': details
            }
            with open(self.log_file, 'a', encoding='utf-8') as f:
                f.write(json.dumps(log_entry) + '\n')

class ComputerVision:
    """Advanced computer vision and OCR capabilities."""
    
    def __init__(self, config: ComputerControlConfig):
        self.config = config
        self.easyocr_reader = None
        self.screenshot_cache = {}
        self.ocr_cache = {}
        
        # Initialize EasyOCR if available
        if EASYOCR_AVAILABLE:
            try:
                self.easyocr_reader = easyocr.Reader(['en', 'fr'])
                logger.info("EasyOCR initialized successfully")
            except Exception as e:
                logger.warning(f"Failed to initialize EasyOCR: {e}")
    
    def capture_screen(self, monitor: int = 0, region: Optional[Tuple[int, int, int, int]] = None) -> np.ndarray:
        """Capture screen with caching and optimization."""
        try:
            with mss.mss() as sct:
                if monitor == 0:
                    # Capture all monitors
                    screenshot = sct.grab(sct.monitors[0])
                else:
                    # Capture specific monitor
                    if monitor < len(sct.monitors):
                        screenshot = sct.grab(sct.monitors[monitor])
                    else:
                        screenshot = sct.grab(sct.monitors[1])  # Fallback to primary
                
                # Convert to numpy array
                img = np.array(screenshot)
                img = cv2.cvtColor(img, cv2.COLOR_BGRA2RGB)
                
                # Apply region if specified
                if region:
                    x1, y1, x2, y2 = region
                    img = img[y1:y2, x1:x2]
                
                # Cache the screenshot
                cache_key = f"{monitor}_{region}_{int(time.time())}"
                self.screenshot_cache[cache_key] = img
                
                # Clean old cache entries
                current_time = time.time()
                self.screenshot_cache = {
                    k: v for k, v in self.screenshot_cache.items()
                    if current_time - int(k.split('_')[-1]) < 60
                }
                
                self.config.log_action('screen_capture', {
                    'monitor': monitor,
                    'region': region,
                    'resolution': f"{img.shape[1]}x{img.shape[0]}"
                })
                
                return img
                
        except Exception as e:
            logger.error(f"Screen capture failed: {e}")
            raise
    
    def extract_text_tesseract(self, image: np.ndarray, config: str = '--psm 6') -> List[Dict[str, Any]]:
        """Extract text using Tesseract OCR."""
        if not TESSERACT_AVAILABLE:
            raise RuntimeError("Tesseract is not available")
        
        try:
            # Convert to PIL Image
            pil_image = Image.fromarray(image)
            
            # Extract text with bounding boxes
            data = pytesseract.image_to_data(pil_image, config=config, output_type=pytesseract.Output.DICT)
            
            results = []
            for i in range(len(data['text'])):
                if int(data['conf'][i]) > 30:  # Confidence threshold
                    results.append({
                        'text': data['text'][i].strip(),
                        'bbox': (data['left'][i], data['top'][i], 
                                data['width'][i], data['height'][i]),
                        'confidence': int(data['conf'][i])
                    })
            
            return [r for r in results if r['text']]
            
        except Exception as e:
            logger.error(f"Tesseract OCR failed: {e}")
            return []
    
    def extract_text_easyocr(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Extract text using EasyOCR."""
        if not self.easyocr_reader:
            raise RuntimeError("EasyOCR is not available")
        
        try:
            results = self.easyocr_reader.readtext(image)
            
            formatted_results = []
            for (bbox, text, confidence) in results:
                if confidence > 0.3:  # Confidence threshold
                    # Convert bbox to (x, y, w, h) format
                    x_coords = [point[0] for point in bbox]
                    y_coords = [point[1] for point in bbox]
                    x, y = int(min(x_coords)), int(min(y_coords))
                    w, h = int(max(x_coords) - x), int(max(y_coords) - y)
                    
                    formatted_results.append({
                        'text': text.strip(),
                        'bbox': (x, y, w, h),
                        'confidence': int(confidence * 100)
                    })
            
            return formatted_results
            
        except Exception as e:
            logger.error(f"EasyOCR failed: {e}")
            return []
    
    def extract_text(self, image: np.ndarray, method: str = 'auto') -> List[Dict[str, Any]]:
        """Extract text using the best available OCR method."""
        # Check cache first
        image_hash = hashlib.md5(image.tobytes()).hexdigest()
        if image_hash in self.ocr_cache:
            cache_time, results = self.ocr_cache[image_hash]
            if time.time() - cache_time < self.config.safety_bounds['ocr_cache_duration']:
                return results
        
        results = []
        
        if method == 'auto':
            # Try EasyOCR first (more accurate), fallback to Tesseract
            if self.easyocr_reader:
                results = self.extract_text_easyocr(image)
            elif TESSERACT_AVAILABLE:
                results = self.extract_text_tesseract(image)
        elif method == 'tesseract' and TESSERACT_AVAILABLE:
            results = self.extract_text_tesseract(image)
        elif method == 'easyocr' and self.easyocr_reader:
            results = self.extract_text_easyocr(image)
        
        # Cache results
        self.ocr_cache[image_hash] = (time.time(), results)
        
        # Clean old cache entries
        current_time = time.time()
        self.ocr_cache = {
            k: v for k, v in self.ocr_cache.items()
            if current_time - v[0] < self.config.safety_bounds['ocr_cache_duration']
        }
        
        self.config.log_action('ocr_extraction', {
            'method': method,
            'texts_found': len(results),
            'total_confidence': sum(r['confidence'] for r in results)
        })
        
        return results
    
    def find_text_on_screen(self, target_text: str, monitor: int = 0, similarity_threshold: float = 0.8) -> Optional[Tuple[int, int, int, int]]:
        """Find text on screen and return its bounding box."""
        try:
            screenshot = self.capture_screen(monitor)
            text_results = self.extract_text(screenshot)
            
            from difflib import SequenceMatcher
            
            for result in text_results:
                similarity = SequenceMatcher(None, result['text'].lower(), target_text.lower()).ratio()
                if similarity >= similarity_threshold:
                    return result['bbox']
            
            return None
            
        except Exception as e:
            logger.error(f"Find text on screen failed: {e}")
            return None
    
    def find_ui_elements(self, image: np.ndarray) -> List[Dict[str, Any]]:
        """Detect UI elements like buttons, text fields, etc."""
        try:
            # Convert to grayscale for processing
            gray = cv2.cvtColor(image, cv2.COLOR_RGB2GRAY)
            
            # Detect edges
            edges = cv2.Canny(gray, 50, 150)
            
            # Find contours
            contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            
            ui_elements = []
            for contour in contours:
                # Get bounding box
                x, y, w, h = cv2.boundingRect(contour)
                area = w * h
                
                # Filter by size (likely UI elements)
                if 100 < area < 50000 and w > 20 and h > 10:
                    # Determine element type based on aspect ratio
                    aspect_ratio = w / h
                    if aspect_ratio > 3:
                        element_type = 'text_field'
                    elif 0.5 < aspect_ratio < 2:
                        element_type = 'button'
                    else:
                        element_type = 'unknown'
                    
                    ui_elements.append({
                        'type': element_type,
                        'bbox': (x, y, w, h),
                        'area': area,
                        'aspect_ratio': aspect_ratio
                    })
            
            return ui_elements
            
        except Exception as e:
            logger.error(f"UI element detection failed: {e}")
            return []

class WindowManager:
    """Advanced window management capabilities."""
    
    def __init__(self, config: ComputerControlConfig):
        self.config = config
    
    def get_all_windows(self) -> List[Dict[str, Any]]:
        """Get information about all open windows."""
        try:
            windows = gw.getAllWindows()
            window_list = []
            
            for window in windows:
                if window.title and window.visible:
                    window_info = {
                        'title': window.title,
                        'left': window.left,
                        'top': window.top,
                        'width': window.width,
                        'height': window.height,
                        'is_maximized': window.isMaximized,
                        'is_minimized': window.isMinimized,
                        'is_active': window.isActive
                    }
                    window_list.append(window_info)
            
            self.config.log_action('get_windows', {'count': len(window_list)})
            return window_list
            
        except Exception as e:
            logger.error(f"Get windows failed: {e}")
            return []
    
    def find_window(self, title_pattern: str) -> Optional[Dict[str, Any]]:
        """Find a window by title pattern."""
        try:
            windows = self.get_all_windows()
            
            for window in windows:
                if title_pattern.lower() in window['title'].lower():
                    return window
            
            return None
            
        except Exception as e:
            logger.error(f"Find window failed: {e}")
            return None
    
    def activate_window(self, title_pattern: str) -> bool:
        """Activate a window by title pattern."""
        if not self.config.check_permission('window_management'):
            logger.warning("Window management permission denied")
            return False
        
        try:
            windows = gw.getWindowsWithTitle(title_pattern)
            if windows:
                window = windows[0]
                window.activate()
                
                self.config.log_action('activate_window', {
                    'title': window.title,
                    'pattern': title_pattern
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Activate window failed: {e}")
            return False
    
    def resize_window(self, title_pattern: str, width: int, height: int) -> bool:
        """Resize a window."""
        if not self.config.check_permission('window_management'):
            logger.warning("Window management permission denied")
            return False
        
        try:
            windows = gw.getWindowsWithTitle(title_pattern)
            if windows:
                window = windows[0]
                window.resizeTo(width, height)
                
                self.config.log_action('resize_window', {
                    'title': window.title,
                    'width': width,
                    'height': height
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Resize window failed: {e}")
            return False
    
    def move_window(self, title_pattern: str, x: int, y: int) -> bool:
        """Move a window to specified coordinates."""
        if not self.config.check_permission('window_management'):
            logger.warning("Window management permission denied")
            return False
        
        try:
            windows = gw.getWindowsWithTitle(title_pattern)
            if windows:
                window = windows[0]
                window.moveTo(x, y)
                
                self.config.log_action('move_window', {
                    'title': window.title,
                    'x': x,
                    'y': y
                })
                return True
            
            return False
            
        except Exception as e:
            logger.error(f"Move window failed: {e}")
            return False

class InputController:
    """Advanced input control with safety measures."""
    
    def __init__(self, config: ComputerControlConfig):
        self.config = config
        self.click_counter = 0
        self.keystroke_counter = 0
        self.last_minute_reset = time.time()
        
        # Disable pyautogui fail-safe for controlled environment
        pyautogui.FAILSAFE = False
        pyautogui.PAUSE = 0.01  # Small pause between operations
    
    def _check_rate_limits(self, action_type: str) -> bool:
        """Check if action is within rate limits."""
        current_time = time.time()
        
        # Reset counters every minute
        if current_time - self.last_minute_reset >= 60:
            self.click_counter = 0
            self.keystroke_counter = 0
            self.last_minute_reset = current_time
        
        if action_type == 'click':
            if self.click_counter >= self.config.safety_bounds['max_clicks_per_minute']:
                logger.warning("Click rate limit exceeded")
                return False
            self.click_counter += 1
        elif action_type == 'keystroke':
            if self.keystroke_counter >= self.config.safety_bounds['max_keystrokes_per_minute']:
                logger.warning("Keystroke rate limit exceeded")
                return False
            self.keystroke_counter += 1
        
        return True
    
    def click(self, x: int, y: int, button: str = 'left', clicks: int = 1, interval: float = 0.0) -> bool:
        """Perform mouse click with safety checks."""
        if not self.config.check_permission('mouse_control'):
            logger.warning("Mouse control permission denied")
            return False
        
        if not self._check_rate_limits('click'):
            return False
        
        try:
            pyautogui.click(x, y, clicks=clicks, interval=interval, button=button)
            
            self.config.log_action('mouse_click', {
                'x': x,
                'y': y,
                'button': button,
                'clicks': clicks
            })
            return True
            
        except Exception as e:
            logger.error(f"Click failed: {e}")
            return False
    
    def click_relative(self, x_rel: float, y_rel: float, button: str = 'left', clicks: int = 1) -> bool:
        """Click at relative coordinates (0.0-1.0)."""
        screen_width, screen_height = pyautogui.size()
        x = int(x_rel * screen_width)
        y = int(y_rel * screen_height)
        
        return self.click(x, y, button, clicks)
    
    def drag(self, start_x: int, start_y: int, end_x: int, end_y: int, duration: float = 1.0, button: str = 'left') -> bool:
        """Perform drag operation."""
        if not self.config.check_permission('mouse_control'):
            logger.warning("Mouse control permission denied")
            return False
        
        try:
            pyautogui.drag(end_x - start_x, end_y - start_y, duration=duration, button=button)
            
            self.config.log_action('mouse_drag', {
                'start_x': start_x,
                'start_y': start_y,
                'end_x': end_x,
                'end_y': end_y,
                'duration': duration
            })
            return True
            
        except Exception as e:
            logger.error(f"Drag failed: {e}")
            return False
    
    def scroll(self, x: int, y: int, clicks: int = 3, direction: str = 'up') -> bool:
        """Perform scroll operation."""
        if not self.config.check_permission('mouse_control'):
            logger.warning("Mouse control permission denied")
            return False
        
        try:
            scroll_amount = clicks if direction == 'up' else -clicks
            pyautogui.scroll(scroll_amount, x=x, y=y)
            
            self.config.log_action('mouse_scroll', {
                'x': x,
                'y': y,
                'clicks': clicks,
                'direction': direction
            })
            return True
            
        except Exception as e:
            logger.error(f"Scroll failed: {e}")
            return False
    
    def type_text(self, text: str, interval: float = 0.0) -> bool:
        """Type text with safety checks."""
        if not self.config.check_permission('keyboard_control'):
            logger.warning("Keyboard control permission denied")
            return False
        
        if not self._check_rate_limits('keystroke'):
            return False
        
        try:
            pyautogui.write(text, interval=interval)
            
            self.config.log_action('keyboard_type', {
                'length': len(text),
                'interval': interval
            })
            return True
            
        except Exception as e:
            logger.error(f"Type text failed: {e}")
            return False
    
    def press_key(self, key: str, presses: int = 1, interval: float = 0.0) -> bool:
        """Press key(s) with safety checks."""
        if not self.config.check_permission('keyboard_control'):
            logger.warning("Keyboard control permission denied")
            return False
        
        try:
            pyautogui.press(key, presses=presses, interval=interval)
            
            self.config.log_action('keyboard_press', {
                'key': key,
                'presses': presses
            })
            return True
            
        except Exception as e:
            logger.error(f"Press key failed: {e}")
            return False
    
    def key_combination(self, keys: List[str]) -> bool:
        """Press key combination (e.g., ['ctrl', 'c'])."""
        if not self.config.check_permission('keyboard_control'):
            logger.warning("Keyboard control permission denied")
            return False
        
        try:
            pyautogui.hotkey(*keys)
            
            self.config.log_action('keyboard_combination', {
                'keys': keys
            })
            return True
            
        except Exception as e:
            logger.error(f"Key combination failed: {e}")
            return False

class ComputerController:
    """Main computer control class integrating all capabilities."""
    
    def __init__(self, config: Optional[ComputerControlConfig] = None):
        self.config = config or ComputerControlConfig()
        self.vision = ComputerVision(self.config)
        self.window_manager = WindowManager(self.config)
        self.input = InputController(self.config)
        self.lock = threading.Lock()
        
        logger.info("Computer controller initialized with all capabilities")
    
    def get_system_info(self) -> Dict[str, Any]:
        """Get comprehensive system information."""
        try:
            screen_size = pyautogui.size()
            mouse_pos = pyautogui.position()
            
            # Get system resources
            cpu_percent = psutil.cpu_percent(interval=1)
            memory = psutil.virtual_memory()
            
            # Get display information
            with mss.mss() as sct:
                monitors = []
                for i, monitor in enumerate(sct.monitors):
                    if i == 0:
                        continue  # Skip "All monitors" entry
                    monitors.append({
                        'index': i,
                        'left': monitor['left'],
                        'top': monitor['top'], 
                        'width': monitor['width'],
                        'height': monitor['height']
                    })
            
            return {
                'screen_size': {'width': screen_size.width, 'height': screen_size.height},
                'mouse_position': {'x': mouse_pos.x, 'y': mouse_pos.y},
                'cpu_percent': cpu_percent,
                'memory_percent': memory.percent,
                'memory_available': memory.available,
                'monitors': monitors,
                'permissions': self.config.permissions,
                'capabilities': {
                    'tesseract_ocr': TESSERACT_AVAILABLE,
                    'easyocr': EASYOCR_AVAILABLE,
                    'advanced_input': ADVANCED_INPUT_AVAILABLE,
                    'windows_api': WINDOWS_API_AVAILABLE
                }
            }
            
        except Exception as e:
            logger.error(f"Get system info failed: {e}")
            return {}
    
    def analyze_screen(self, monitor: int = 0, include_ocr: bool = True, include_ui_elements: bool = True) -> Dict[str, Any]:
        """Comprehensive screen analysis."""
        try:
            with self.lock:
                # Capture screen
                screenshot = self.vision.capture_screen(monitor)
                
                # Convert to base64 for transmission
                _, buffer = cv2.imencode('.jpg', screenshot)
                screenshot_b64 = base64.b64encode(buffer).decode('utf-8')
                
                analysis = {
                    'screenshot': screenshot_b64,
                    'resolution': {'width': screenshot.shape[1], 'height': screenshot.shape[0]},
                    'monitor': monitor,
                    'timestamp': time.time()
                }
                
                # OCR analysis
                if include_ocr:
                    text_results = self.vision.extract_text(screenshot)
                    analysis['text_elements'] = text_results
                    analysis['text_content'] = ' '.join([r['text'] for r in text_results])
                
                # UI element detection
                if include_ui_elements:
                    ui_elements = self.vision.find_ui_elements(screenshot)
                    analysis['ui_elements'] = ui_elements
                
                # Window information
                windows = self.window_manager.get_all_windows()
                analysis['windows'] = windows
                
                self.config.log_action('analyze_screen', {
                    'monitor': monitor,
                    'text_elements': len(text_results) if include_ocr else 0,
                    'ui_elements': len(ui_elements) if include_ui_elements else 0,
                    'windows': len(windows)
                })
                
                return analysis
                
        except Exception as e:
            logger.error(f"Screen analysis failed: {e}")
            return {}
    
    def find_and_click_text(self, text: str, monitor: int = 0, similarity_threshold: float = 0.8) -> bool:
        """Find text on screen and click on it."""
        try:
            bbox = self.vision.find_text_on_screen(text, monitor, similarity_threshold)
            if bbox:
                x, y, w, h = bbox
                # Click in the center of the text
                center_x = x + w // 2
                center_y = y + h // 2
                
                return self.input.click(center_x, center_y)
            
            return False
            
        except Exception as e:
            logger.error(f"Find and click text failed: {e}")
            return False
    
    def automate_task(self, task_description: str, steps: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Execute a series of automation steps."""
        if not self.config.check_permission('system_commands'):
            logger.warning("System automation permission denied")
            return {'success': False, 'error': 'Permission denied'}
        
        results = []
        
        try:
            for i, step in enumerate(steps):
                step_result = {'step': i + 1, 'action': step.get('action')}
                
                action = step.get('action')
                params = step.get('params', {})
                
                if action == 'click':
                    success = self.input.click(**params)
                    step_result['success'] = success
                elif action == 'type':
                    success = self.input.type_text(**params)
                    step_result['success'] = success
                elif action == 'key':
                    success = self.input.press_key(**params)
                    step_result['success'] = success
                elif action == 'wait':
                    time.sleep(params.get('duration', 1))
                    step_result['success'] = True
                elif action == 'find_and_click_text':
                    success = self.find_and_click_text(**params)
                    step_result['success'] = success
                elif action == 'activate_window':
                    success = self.window_manager.activate_window(**params)
                    step_result['success'] = success
                else:
                    step_result['success'] = False
                    step_result['error'] = f'Unknown action: {action}'
                
                results.append(step_result)
                
                # Stop on failure if specified
                if not step_result['success'] and step.get('stop_on_failure', True):
                    break
                
                # Optional delay between steps
                step_delay = step.get('delay', 0.1)
                if step_delay > 0:
                    time.sleep(step_delay)
            
            self.config.log_action('automate_task', {
                'description': task_description,
                'total_steps': len(steps),
                'completed_steps': len(results),
                'success': all(r.get('success', False) for r in results)
            })
            
            return {
                'success': True,
                'task_description': task_description,
                'results': results
            }
            
        except Exception as e:
            logger.error(f"Task automation failed: {e}")
            return {
                'success': False,
                'error': str(e),
                'results': results
            }

# Global instance for easy access
_global_controller = None

def get_computer_controller() -> ComputerController:
    """Get global computer controller instance."""
    global _global_controller
    if _global_controller is None:
        _global_controller = ComputerController()
    return _global_controller

# Convenience functions for easy integration
def capture_screen(monitor: int = 0) -> str:
    """Capture screen and return as base64."""
    controller = get_computer_controller()
    screenshot = controller.vision.capture_screen(monitor)
    _, buffer = cv2.imencode('.jpg', screenshot)
    return base64.b64encode(buffer).decode('utf-8')

def extract_text_from_screen(monitor: int = 0) -> List[Dict[str, Any]]:
    """Extract all text from screen."""
    controller = get_computer_controller()
    screenshot = controller.vision.capture_screen(monitor)
    return controller.vision.extract_text(screenshot)

def click_at_text(text: str, monitor: int = 0) -> bool:
    """Find and click on text."""
    controller = get_computer_controller()
    return controller.find_and_click_text(text, monitor)

def get_all_windows() -> List[Dict[str, Any]]:
    """Get all window information."""
    controller = get_computer_controller()
    return controller.window_manager.get_all_windows()

def analyze_full_screen(monitor: int = 0) -> Dict[str, Any]:
    """Get complete screen analysis."""
    controller = get_computer_controller()
    return controller.analyze_screen(monitor)