"""Real-time streaming server with WebRTC support for Lilith AI."""
from flask import Flask, render_template, request, jsonify
from flask_socketio import SocketIO, emit, join_room, leave_room
from flask_cors import CORS
import base64
import cv2
import numpy as np
import threading
import time
import mss
from pathlib import Path
import os
import json
import pyttsx3
import asyncio
from datetime import datetime
import langdetect  # Pour détection de langue

# Import Lilith controller
from .controller_ultimate import LilithControllerUltimate

# Import enhanced computer control
try:
    from .computer_control import (
        get_computer_controller, 
        capture_screen as capture_full_screen,
        analyze_full_screen
    )
    ENHANCED_CONTROL_AVAILABLE = True
except ImportError:
    ENHANCED_CONTROL_AVAILABLE = False

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lilith-ai-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize components
controller = None
computer_controller = None  # Enhanced computer controller for streaming

def initialize_controller():
    """Initialize controller with proper error handling."""
    global controller
    try:
        print("🔧 Initializing Lilith Controller...")
        controller = LilithControllerUltimate()
        print("✅ Controller initialized successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to initialize controller: {e}")
        import traceback
        traceback.print_exc()
        return False

# Try to initialize controller
if not initialize_controller():
    print("⚠️ Controller initialization failed, will retry on first message")

# Try to initialize TTS
TTS_AVAILABLE = False
tts_engine = None
tts_lock = threading.Lock()

def init_tts():
    """Initialize TTS engine with multi-language support and CABLE Output routing."""
    global tts_engine, TTS_AVAILABLE
    try:
        # Try different TTS engines
        try:
            # Try SAPI5 on Windows (best quality)
            tts_engine = pyttsx3.init('sapi5')
        except:
            try:
                # Try espeak (good multi-language support)
                tts_engine = pyttsx3.init('espeak')
            except:
                # Fallback to default
                tts_engine = pyttsx3.init()
        
        # Try to set audio output to CABLE Output
        try:
            import win32com.client
            speaker = win32com.client.Dispatch("SAPI.SpVoice")
            
            # Get available audio outputs
            audio_outputs = speaker.GetAudioOutputs()
            cable_output = None
            
            # Find CABLE Output device
            for i in range(audio_outputs.Count):
                output = audio_outputs.Item(i)
                desc = output.GetDescription()
                if "CABLE" in desc.upper() and "OUTPUT" in desc.upper():
                    cable_output = output
                    print(f"✅ Found CABLE Output: {desc}")
                    break
            
            # Set CABLE Output as the audio output
            if cable_output:
                speaker.AudioOutput = cable_output
                # Use the configured speaker for TTS
                # Note: pyttsx3 doesn't directly support output device selection,
                # so we'll use win32com.client directly for TTS
                state.sapi_speaker = speaker
                print("✅ TTS will output to CABLE Output (VB-Virtual Cable)")
            else:
                print("⚠️ CABLE Output not found, using default audio output")
                state.sapi_speaker = None
                
        except Exception as e:
            print(f"⚠️ Could not configure CABLE Output: {e}")
            state.sapi_speaker = None
        
        # Configure TTS
        tts_engine.setProperty('rate', 150)  # Balanced speed
        tts_engine.setProperty('volume', 0.9)  # Clear volume
        
        # Get available voices
        voices = tts_engine.getProperty('voices')
        print(f"Found {len(voices)} TTS voices")
        
        # Voice selection preferences
        voice_preferences = {
            'fr': {
                'keywords': ['french', 'français', 'france', 'hortense', 'julie', 'paul', 'fr-fr', 'fr_fr'],
                'female_keywords': ['hortense', 'julie', 'female', 'femme'],
                'selected': None
            },
            'en': {
                'keywords': ['english', 'en-us', 'en_us', 'david', 'zira', 'hazel'],
                'female_keywords': ['zira', 'hazel', 'female'],
                'selected': None
            }
        }
        
        # Find best voices for each language
        for lang, prefs in voice_preferences.items():
            # First try to find a female voice
            for i, voice in enumerate(voices):
                voice_name = voice.name.lower()
                voice_id = voice.id.lower()
                
                if any(keyword in voice_name or keyword in voice_id for keyword in prefs['keywords']):
                    if any(keyword in voice_name or keyword in voice_id for keyword in prefs['female_keywords']):
                        prefs['selected'] = voice.id
                        print(f"✅ Selected {lang} female voice: {voice.name}")
                        break
            
            # If no female voice, try any voice for that language
            if not prefs['selected']:
                for i, voice in enumerate(voices):
                    voice_name = voice.name.lower()
                    voice_id = voice.id.lower()
                    if any(keyword in voice_name or keyword in voice_id for keyword in prefs['keywords']):
                        prefs['selected'] = voice.id
                        print(f"✅ Selected {lang} voice: {voice.name}")
                        break
        
        # Set default voice (prefer French if available)
        if voice_preferences['fr']['selected']:
            tts_engine.setProperty('voice', voice_preferences['fr']['selected'])
        elif voice_preferences['en']['selected']:
            tts_engine.setProperty('voice', voice_preferences['en']['selected'])
        elif len(voices) > 0:
            tts_engine.setProperty('voice', voices[0].id)
            print("⚠️ Using default voice")
        
        # Store voice preferences globally
        state.voice_preferences = voice_preferences
        
        # Test TTS
        try:
            tts_engine.say("Test")
            tts_engine.runAndWait()
            tts_engine.stop()
        except:
            pass
        
        TTS_AVAILABLE = True
        print("✅ TTS initialized successfully")
        return True
        
    except Exception as e:
        print(f"⚠️ TTS initialization error: {e}")
        print("   TTS will be disabled for this session")
        TTS_AVAILABLE = False
        return False

# Global state
class StreamingState:
    def __init__(self):
        self.active_users = {}
        self.ai_screen_enabled = False
        self.ai_screen_thread = None
        self.vtube_stream_enabled = False
        self.vtube_thread = None
        self.chat_history = []
        self.current_ai_frame = None
        self.current_vtube_frame = None
        self.tts_queue = []
        self.tts_thread = None
        self.lock = threading.Lock()
        # Dynamic reaction system
        self.dynamic_monitoring = False
        self.monitor_thread = None
        self.last_analysis_time = 0
        self.last_screen_hash = None
        self.reaction_cooldown = 20  # seconds between reactions (reduced for more interactivity)
        self.significant_changes = []
        self.context_memory = []  # Remember recent context
        self.last_activity_type = None
        
state = StreamingState()

# Initialize TTS after state is created
init_tts()

# TTS worker
def tts_worker():
    """Background worker for TTS with robust error handling."""
    global TTS_AVAILABLE, tts_engine
    
    if not TTS_AVAILABLE:
        return
    
    consecutive_errors = 0
    max_consecutive_errors = 3
    
    # Dictionnaire des voix par langue
    voice_by_lang = {
        'fr': None,  # Sera défini dans init_tts
        'en': None
    }
    
    while True:
        try:
            if state.tts_queue and TTS_AVAILABLE:
                text = state.tts_queue.pop(0)
                
                # Skip empty texts
                if not text or not text.strip():
                    continue
                
                try:
                    with tts_lock:
                        # Clean text for TTS
                        clean_text = clean_text_for_tts(text)
                        if clean_text:
                            # Use SAPI speaker with CABLE Output if available
                            if hasattr(state, 'sapi_speaker') and state.sapi_speaker:
                                try:
                                    # Detect language
                                    lang = detect_language(clean_text)
                                    
                                    # Get available voices from SAPI
                                    voices = state.sapi_speaker.GetVoices()
                                    
                                    # Select voice based on language
                                    for i in range(voices.Count):
                                        voice = voices.Item(i)
                                        desc = voice.GetDescription().lower()
                                        if lang == 'fr' and ('french' in desc or 'français' in desc or 'hortense' in desc):
                                            state.sapi_speaker.Voice = voice
                                            break
                                        elif lang == 'en' and ('english' in desc or 'zira' in desc):
                                            state.sapi_speaker.Voice = voice
                                            break
                                    
                                    # Set rate and volume
                                    state.sapi_speaker.Rate = 0  # Normal speed
                                    state.sapi_speaker.Volume = 90  # 90% volume
                                    
                                    # Speak using SAPI (outputs to CABLE)
                                    state.sapi_speaker.Speak(clean_text)
                                    
                                    # Reset error counter on success
                                    consecutive_errors = 0
                                    
                                except Exception as sapi_error:
                                    print(f"SAPI TTS error: {sapi_error}")
                                    # Fall back to pyttsx3
                                    if tts_engine:
                                        tts_engine.say(clean_text)
                                        tts_engine.runAndWait()
                            else:
                                # Use pyttsx3 as fallback
                                if tts_engine:
                                    # Detect language
                                    lang = detect_language(clean_text)
                                    
                                    # Change voice if necessary
                                    if hasattr(state, 'voice_preferences') and state.voice_preferences.get(lang, {}).get('selected'):
                                        tts_engine.setProperty('voice', state.voice_preferences[lang]['selected'])
                                    
                                    # Adjust speed
                                    tts_engine.setProperty('rate', 150)
                                    
                                    # Stop any ongoing speech
                                    try:
                                        tts_engine.stop()
                                    except:
                                        pass
                                    
                                    # Speak the text
                                    tts_engine.say(clean_text)
                                    tts_engine.runAndWait()
                                    
                                    # Reset error counter on success
                                    consecutive_errors = 0
                            
                except RuntimeError as e:
                    # Common error when TTS is busy
                    print(f"TTS busy: {e}")
                    # Put text back in queue
                    state.tts_queue.insert(0, text)
                    time.sleep(0.5)
                    
                except Exception as e:
                    print(f"TTS error: {e}")
                    consecutive_errors += 1
                    
                    # If too many errors, try to reinitialize
                    if consecutive_errors >= max_consecutive_errors:
                        print("Too many TTS errors, attempting to reinitialize...")
                        TTS_AVAILABLE = False
                        try:
                            # Clean up old engine
                            if tts_engine:
                                try:
                                    tts_engine.stop()
                                except:
                                    pass
                            
                            # Reinitialize
                            time.sleep(1)
                            if init_tts():
                                consecutive_errors = 0
                                print("TTS reinitialized successfully")
                            else:
                                print("Failed to reinitialize TTS")
                                time.sleep(5)  # Wait longer before retrying
                        except Exception as reinit_error:
                            print(f"Error during TTS reinitialization: {reinit_error}")
                            time.sleep(5)
            
            time.sleep(0.1)
            
        except Exception as e:
            print(f"Critical error in TTS worker: {e}")
            time.sleep(1)

def detect_language(text):
    """Detect language of text for TTS voice selection."""
    try:
        lang = langdetect.detect(text)
        # Map to our supported languages
        if lang.startswith('fr'):
            return 'fr'
        else:
            return 'en'  # Default to English
    except:
        return 'en'  # Default to English on error

def clean_text_for_tts(text):
    """Clean text for TTS output."""
    # Remove markdown formatting
    import re
    
    # Remove code blocks
    text = re.sub(r'```[\s\S]*?```', '', text)
    text = re.sub(r'`[^`]+`', '', text)
    
    # Remove markdown headers
    text = re.sub(r'^#+\s+', '', text, flags=re.MULTILINE)
    
    # Remove bold/italic
    text = re.sub(r'\*\*([^*]+)\*\*', r'\1', text)
    text = re.sub(r'\*([^*]+)\*', r'\1', text)
    
    # Remove links
    text = re.sub(r'\[([^\]]+)\]\([^)]+\)', r'\1', text)
    
    # Remove emojis (optional, some TTS engines handle them)
    text = re.sub(r'[^\x00-\x7F]+', ' ', text)
    
    # Remove execution results section
    text = re.sub(r'---\s*\n.*?Execution Results:.*', '', text, flags=re.DOTALL)
    
    # Limit length for TTS
    max_length = 500
    if len(text) > max_length:
        text = text[:max_length] + "..."
    
    return text.strip()

# Start TTS worker only if TTS is available
if TTS_AVAILABLE:
    state.tts_thread = threading.Thread(target=tts_worker, daemon=True)
    state.tts_thread.start()

def capture_ai_screen():
    """Capture AI's screen (server-side) with enhanced capabilities."""
    global computer_controller
    
    # Initialize enhanced controller if available
    if ENHANCED_CONTROL_AVAILABLE and computer_controller is None:
        try:
            computer_controller = get_computer_controller()
            print("✅ Enhanced computer control initialized for streaming")
        except Exception as e:
            print(f"⚠️ Enhanced control failed, using basic mode: {e}")
    
    with mss.mss() as sct:
        # Use monitor 2 if available, otherwise monitor 1
        monitor_idx = 2 if len(sct.monitors) > 2 else 1
        
        while state.ai_screen_enabled:
            try:
                if ENHANCED_CONTROL_AVAILABLE and computer_controller:
                    # Use enhanced screen capture
                    screenshot = computer_controller.vision.capture_screen(monitor_idx)
                    frame = screenshot  # Already in RGB format
                else:
                    # Use basic MSS capture
                    monitor = sct.monitors[monitor_idx]
                    screenshot = sct.grab(monitor)
                    frame = np.array(screenshot)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                
                # Resize for performance
                height, width = frame.shape[:2]
                if width > 1280:
                    scale = 1280 / width
                    new_width = int(width * scale)
                    new_height = int(height * scale)
                    frame = cv2.resize(frame, (new_width, new_height))
                
                # Add enhanced info overlay
                if ENHANCED_CONTROL_AVAILABLE:
                    cv2.putText(frame, f"AI Screen - Enhanced Mode - Monitor {monitor_idx}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
                else:
                    cv2.putText(frame, f"AI Screen - Basic Mode - Monitor {monitor_idx}", 
                               (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2)
                
                # Convert to base64
                _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 80])
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                with state.lock:
                    state.current_ai_frame = jpg_as_text
                
                # Emit to all clients
                socketio.emit('ai_screen_frame', {'frame': jpg_as_text})
                
                time.sleep(0.1)  # 10 FPS
                
            except Exception as e:
                print(f"AI screen capture error: {e}")
                time.sleep(1)

def capture_vtube_studio():
    """Capture VTube Studio window even when not in foreground."""
    import ctypes
    from ctypes import wintypes
    
    # Windows API functions
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    while state.vtube_stream_enabled:
        try:
            # Find VTube Studio window using Windows API
            def enum_windows_callback(hwnd, windows):
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if "VTube Studio" in buff.value:
                            windows.append(hwnd)
                return True
            
            # Find VTube Studio window
            windows = []
            WNDENUMPROC = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            user32.EnumWindows(WNDENUMPROC(enum_windows_callback), ctypes.py_object(windows))
            
            if windows:
                hwnd = windows[0]
                
                # Get window dimensions
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.pointer(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                
                # Create device contexts
                hwndDC = user32.GetWindowDC(hwnd)
                mfcDC = gdi32.CreateCompatibleDC(hwndDC)
                saveBitMap = gdi32.CreateCompatibleBitmap(hwndDC, width, height)
                
                # Select bitmap into DC
                gdi32.SelectObject(mfcDC, saveBitMap)
                
                # Copy window content
                result = user32.PrintWindow(hwnd, mfcDC, 2)  # PW_RENDERFULLCONTENT
                
                if result:
                    # Convert to numpy array
                    bmpinfo = ctypes.create_string_buffer(64)
                    ctypes.memmove(bmpinfo, b'\x28\x00\x00\x00' + width.to_bytes(4, 'little') + height.to_bytes(4, 'little') + b'\x01\x00\x20\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00', 40)
                    
                    # Get bitmap bits
                    bmpstr = ctypes.create_string_buffer(width * height * 4)
                    gdi32.GetDIBits(mfcDC, saveBitMap, 0, height, bmpstr, bmpinfo, 0)
                    
                    # Convert to numpy array
                    frame = np.frombuffer(bmpstr, dtype=np.uint8).reshape(height, width, 4)
                    frame = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                    
                    # Flip vertically (Windows bitmaps are bottom-up)
                    frame = cv2.flip(frame, 0)
                    
                    # Convert to base64
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 85])
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    
                    with state.lock:
                        state.current_vtube_frame = jpg_as_text
                    
                    # Emit to all clients
                    socketio.emit('vtube_frame', {'frame': jpg_as_text})
                
                # Clean up
                gdi32.DeleteObject(saveBitMap)
                gdi32.DeleteDC(mfcDC)
                user32.ReleaseDC(hwnd, hwndDC)
            
            time.sleep(0.033)  # 30 FPS for smooth animation
            
        except Exception as e:
            print(f"VTube capture error: {e}")
            time.sleep(1)

@app.route('/')
def index():
    """Serve the main page."""
    return render_template('streaming_client.html')

@socketio.on('connect')
def handle_connect():
    """Handle client connection."""
    print(f"Client connected: {request.sid}")
    emit('connected', {'sid': request.sid})

@socketio.on('disconnect')
def handle_disconnect():
    """Handle client disconnection."""
    print(f"Client disconnected: {request.sid}")
    if request.sid in state.active_users:
        username = state.active_users[request.sid]['username']
        del state.active_users[request.sid]
        emit('user_left', {'username': username}, broadcast=True)

@socketio.on('join')
def handle_join(data):
    """Handle user joining."""
    username = data.get('username', f'User_{request.sid[:8]}')
    state.active_users[request.sid] = {
        'username': username,
        'joined': datetime.now(),
        'sharing_screen': False
    }
    
    # Send current state
    emit('joined', {
        'username': username,
        'chat_history': state.chat_history,
        'active_users': [u['username'] for u in state.active_users.values()]
    })
    
    # Notify others
    emit('user_joined', {'username': username}, broadcast=True, include_self=False)

@socketio.on('client_screen_frame')
def handle_client_screen(data):
    """Handle screen frame from client."""
    if request.sid in state.active_users:
        username = state.active_users[request.sid]['username']
        frame_data = data.get('frame')
        
        # Store the frame in user state for AI to access
        state.active_users[request.sid]['current_frame'] = frame_data
        state.active_users[request.sid]['sharing_screen'] = True
        
        # Broadcast to all clients including the sender
        emit('user_screen_frame', {
            'username': username,
            'frame': frame_data
        }, broadcast=True, include_self=True)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message."""
    try:
        if request.sid not in state.active_users:
            return
        
        username = state.active_users[request.sid]['username']
        message = data.get('message', '')
        
        if not message.strip():
            return
        
        # Add to history
        state.chat_history.append({
            'role': 'user',
            'username': username,
            'content': message,
            'timestamp': datetime.now().isoformat()
        })
        
        # Broadcast user message
        emit('chat_message', {
            'username': username,
            'message': message,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)
        
        # --- Enhanced Vision System ---
        # Get frames from multiple sources
        client_frame_data = data.get('client_frame')  # Frame sent with message
        ai_frame_data = data.get('ai_frame')  # AI's own screen if available
        
        # Also check for any active user streams
        user_frames = []
        for sid, user in state.active_users.items():
            if user.get('sharing_screen') and user.get('current_frame'):
                user_frames.append({
                    'username': user['username'],
                    'frame': user['current_frame']
                })
        
        # Enhanced analysis if computer control is available
        enhanced_analysis = None
        if ENHANCED_CONTROL_AVAILABLE and computer_controller:
            try:
                # Get comprehensive screen analysis
                analysis = computer_controller.analyze_screen(monitor=0, include_ocr=True, include_ui_elements=True)
                if analysis:
                    enhanced_analysis = analysis
                    print(f"📊 Enhanced analysis: {len(analysis.get('text_elements', []))} text elements found")
            except Exception as e:
                print(f"Enhanced analysis error: {e}")
        
        # Create composite image from all available sources
        composite_image = None
        try:
            # Priority: Use enhanced analysis screenshot if available
            if enhanced_analysis and enhanced_analysis.get('screenshot'):
                # Decode enhanced screenshot
                screenshot_b64 = enhanced_analysis['screenshot']
                img_bytes = base64.b64decode(screenshot_b64)
                img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                composite_image = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
            elif client_frame_data:
                # Client sent a frame with the message
                composite_image = create_composite_image(client_frame_data, ai_frame_data)
            elif user_frames:
                # Use the first available user stream
                composite_image = create_composite_image(user_frames[0]['frame'], ai_frame_data)
            elif ai_frame_data:
                # Only AI screen available
                composite_image = create_composite_image(None, ai_frame_data)
            elif state.current_ai_frame:
                # Use stored AI frame if nothing else
                composite_image = create_composite_image(None, state.current_ai_frame)
                
        except Exception as e:
            print(f"Error creating composite image: {e}")
        
        # Get active streams info for context
        active_streams = []
        if state.ai_screen_enabled:
            active_streams.append("AI Screen")
        if state.vtube_stream_enabled:
            active_streams.append("VTube Studio")
        for sid, user in state.active_users.items():
            if user.get('sharing_screen'):
                active_streams.append(f"{user['username']}'s screen")
        
        # Process with AI
        try:
            # Check if controller is initialized, if not try to initialize it
            global controller
            if controller is None:
                print("⚠️ Controller not initialized, attempting to initialize...")
                if not initialize_controller():
                    response = "❌ Unable to initialize AI controller. Please check LM Studio is running."
                    emit('ai_response', {
                        'message': response,
                        'timestamp': datetime.now().isoformat()
                    }, broadcast=True)
                    return
            
            message_to_send = f"[{username}]: {message}"
            if composite_image is not None:
                message_to_send += " [ANALYSE VISUELLE REQUISE]"
            
            # Add enhanced analysis context
            if enhanced_analysis:
                text_elements = enhanced_analysis.get('text_elements', [])
                ui_elements = enhanced_analysis.get('ui_elements', [])
                windows = enhanced_analysis.get('windows', [])
                
                if text_elements:
                    top_texts = [t['text'] for t in text_elements[:5]]  # Top 5 text elements
                    message_to_send += f"\n[SCREEN TEXT DETECTED: {', '.join(top_texts)}]"
                
                if ui_elements:
                    ui_count = len(ui_elements)
                    message_to_send += f"\n[UI ELEMENTS: {ui_count} interactive elements detected]"
                
                if windows:
                    active_windows = [w['title'] for w in windows if w.get('is_active')]
                    if active_windows:
                        message_to_send += f"\n[ACTIVE WINDOW: {active_windows[0]}]"
                    
                    window_titles = [w['title'] for w in windows[:3]]  # Top 3 windows
                    message_to_send += f"\n[OPEN WINDOWS: {', '.join(window_titles)}]"
            
            # Add stream context
            if active_streams:
                message_to_send += f"\n[ACTIVE STREAMS: {', '.join(active_streams)}]"
            else:
                message_to_send += "\n[NO ACTIVE STREAMS]"
            
            # Add computer control capabilities context
            if ENHANCED_CONTROL_AVAILABLE:
                message_to_send += "\n[ENHANCED COMPUTER CONTROL: Full screen analysis, OCR, window management, and automation available]"
            else:
                message_to_send += "\n[BASIC COMPUTER CONTROL: Limited to basic mouse/keyboard operations]"

            response = controller.chat(
                message_to_send,
                image_frame=composite_image,
                personality='Playful',
                stream_context={"active_streams": active_streams}
            )
        except AttributeError as e:
            # Controller might not be properly initialized
            print(f"AttributeError in controller.chat: {e}")
            print("Attempting to reinitialize controller...")
            if initialize_controller():
                try:
                    response = controller.chat(
                        message_to_send,
                        image_frame=composite_image,
                        personality='Playful',
                        stream_context={"active_streams": active_streams}
                    )
                except Exception as retry_e:
                    print(f"Error after reinitializing: {retry_e}")
                    response = "❌ Unable to process message. Please ensure LM Studio is running with a model loaded."
            else:
                response = "❌ Unable to initialize AI controller. Please check LM Studio."
        except Exception as e:
            print(f"Error calling controller.chat: {e}")
            import traceback
            traceback.print_exc()
            response = "❌ I encountered an error processing your message. Please ensure LM Studio is running and try again."
        
        # Add AI response to history
        state.chat_history.append({
            'role': 'assistant',
            'content': response,
            'timestamp': datetime.now().isoformat()
        })
        
        # Send AI response
        emit('ai_response', {
            'message': response,
            'timestamp': datetime.now().isoformat()
        }, broadcast=True)
        
        # Add to TTS queue only if TTS is available
        if TTS_AVAILABLE and data.get('tts_enabled', True):
            state.tts_queue.append(response)
            
    except Exception as e:
        print(f"Error in handle_chat_message: {e}")
        import traceback
        traceback.print_exc()
        # Send error message to user
        emit('ai_response', {
            'message': "Sorry, I encountered an error. Please try again.",
            'timestamp': datetime.now().isoformat()
        })

@socketio.on('toggle_ai_screen')
def handle_toggle_ai_screen(data):
    """Toggle AI screen sharing."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.ai_screen_enabled = enabled
        
        if enabled and not state.ai_screen_thread:
            state.ai_screen_thread = threading.Thread(target=capture_ai_screen, daemon=True)
            state.ai_screen_thread.start()
        elif not enabled:
            state.ai_screen_thread = None

@socketio.on('toggle_vtube_stream')
def handle_toggle_vtube(data):
    """Toggle VTube Studio stream."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.vtube_stream_enabled = enabled
        
        if enabled and not state.vtube_thread:
            state.vtube_thread = threading.Thread(target=capture_vtube_studio, daemon=True)
            state.vtube_thread.start()
        elif not enabled:
            state.vtube_thread = None

@socketio.on('get_active_streams')
def handle_get_streams():
    """Get list of active streams."""
    streams = []
    
    if state.ai_screen_enabled:
        streams.append({'name': 'AI Screen', 'type': 'ai'})
    
    if state.vtube_stream_enabled:
        streams.append({'name': 'VTube Studio', 'type': 'vtube'})
    
    for sid, user in state.active_users.items():
        if user.get('sharing_screen'):
            streams.append({
                'name': f"{user['username']}'s Screen",
                'type': 'user',
                'username': user['username']
            })
    
    emit('active_streams', {'streams': streams})

@socketio.on('ai_stream_control')
def handle_ai_stream_control(data):
    """Handle AI-initiated stream control commands."""
    action = data.get('action')
    stream_type = data.get('stream_type')
    reason = data.get('reason', '')
    
    print(f"AI Stream Control: {action} {stream_type} - {reason}")
    
    # Emit to all clients that AI wants to control streams
    emit('ai_stream_suggestion', {
        'action': action,
        'stream_type': stream_type,
        'reason': reason,
        'timestamp': datetime.now().isoformat()
    }, broadcast=True)
    
    # Auto-execute if configured (optional)
    auto_execute = data.get('auto_execute', False)
    if auto_execute:
        if stream_type == 'ai' and action in ['enable', 'disable']:
            handle_toggle_ai_screen({'enabled': action == 'enable'})
        elif stream_type == 'vtube' and action in ['enable', 'disable']:
            handle_toggle_vtube({'enabled': action == 'enable'})

def run_streaming_server(host='0.0.0.0', port=7861):
    """Run the streaming server."""
    print(f"🚀 Starting Lilith Streaming Server on {host}:{port}")
    
    # Auto-start dynamic monitoring
    def start_monitoring():
        time.sleep(5)  # Wait for server to be ready
        with state.lock:
            state.dynamic_monitoring = True
            state.monitor_thread = threading.Thread(target=dynamic_screen_monitor, daemon=True)
            state.monitor_thread.start()
            print("🔍 Dynamic monitoring auto-started")
    
    monitor_starter = threading.Thread(target=start_monitoring, daemon=True)
    monitor_starter.start()
    
    socketio.run(app, host=host, port=port, debug=False)

def create_composite_image(client_b64, ai_b64):
    """Create a composite image from two base64 strings."""
    images = []
    labels = []

    # Decode client image
    if client_b64:
        try:
            img_bytes = base64.b64decode(client_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
            images.append(img)
            labels.append("USER SCREEN")
        except Exception as e:
            print(f"Could not decode client image: {e}")

    # Decode AI image
    if ai_b64:
        try:
            img_bytes = base64.b64decode(ai_b64)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
            images.append(img)
            labels.append("AI SCREEN")
        except Exception as e:
            print(f"Could not decode AI image: {e}")

    if not images:
        return None

    # Resize images to a standard width (e.g., 800px)
    std_width = 800
    resized_images = []
    for img in images:
        h, w, _ = img.shape
        scale = std_width / w
        new_h = int(h * scale)
        resized_img = cv2.resize(img, (std_width, new_h), interpolation=cv2.INTER_AREA)
        resized_images.append(resized_img)

    # Add labels to images
    labeled_images = []
    for i, img in enumerate(resized_images):
        cv2.putText(img, labels[i], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 6, cv2.LINE_AA)
        cv2.putText(img, labels[i], (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 1, (255, 255, 0), 2, cv2.LINE_AA)
        labeled_images.append(img)

    # Combine images vertically
    composite = cv2.vconcat(labeled_images)
    return composite

def analyze_screen_changes(current_frame, previous_hash):
    """Analyze screen for significant changes with improved detection."""
    if current_frame is None:
        return None, []
    
    # Decode base64 image
    try:
        img_bytes = base64.b64decode(current_frame)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        img = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate hash for change detection
        resized = cv2.resize(gray, (16, 16))
        current_hash = hash(resized.tobytes())
        
        changes = []
        
        # Detect significant changes
        if previous_hash and current_hash != previous_hash:
            # Analyze what changed
            if previous_hash:
                # Calculate change magnitude
                change_magnitude = abs(current_hash - previous_hash)
                
                # Only process if change is significant
                if change_magnitude > 1000000:  # Threshold for significant change
                    height, width = img.shape[:2]
                    
                    # Enhanced window detection
                    edges = cv2.Canny(gray, 50, 150)
                    contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                    large_contours = [c for c in contours if cv2.contourArea(c) > (width * height * 0.05)]
                    
                    # Detect window changes
                    if len(large_contours) > 3:
                        changes.append("new_window")
                    
                    # Color analysis for better detection
                    mean_color = cv2.mean(img)[:3]
                    
                    # Error detection (red tones)
                    if mean_color[2] > 180 and mean_color[2] > mean_color[1] * 1.5:
                        changes.append("error_detected")
                    
                    # Success detection (green tones)
                    elif mean_color[1] > 180 and mean_color[1] > mean_color[2] * 1.5:
                        changes.append("success_detected")
                    
                    # Blue tones (often links, buttons, selections)
                    elif mean_color[0] > 180 and mean_color[0] > mean_color[1] * 1.2:
                        changes.append("selection_active")
                    
                    # Activity detection based on brightness
                    avg_brightness = np.mean(gray)
                    
                    if avg_brightness < 40:  # Very dark
                        changes.append("terminal_active")
                    elif avg_brightness > 220:  # Very bright
                        changes.append("browser_active")
                    elif 100 < avg_brightness < 150:  # Medium (often IDEs)
                        changes.append("code_editor_active")
                    
                    # Detect loading or progress indicators
                    if change_magnitude > 5000000:
                        changes.append("major_transition")
                    
                    # Remember activity type
                    if changes:
                        state.last_activity_type = changes[0]
        
        return current_hash, changes
        
    except Exception as e:
        print(f"Error analyzing screen: {e}")
        return previous_hash, []

def dynamic_screen_monitor():
    """Monitor screens dynamically and generate AI reactions."""
    while state.dynamic_monitoring:
        try:
            current_time = time.time()
            
            # Check if enough time has passed since last reaction
            if current_time - state.last_analysis_time < state.reaction_cooldown:
                time.sleep(5)
                continue
            
            # Get current frames from all sources
            frames_to_analyze = []
            contexts = []
            
            # Priority 1: AI's own screen
            if state.ai_screen_enabled and state.current_ai_frame:
                frames_to_analyze.append(state.current_ai_frame)
                contexts.append("AI Screen")
            
            # Priority 2: Active user screens
            for sid, user in state.active_users.items():
                if user.get('sharing_screen') and user.get('current_frame'):
                    frames_to_analyze.append(user['current_frame'])
                    contexts.append(f"{user['username']}'s screen")
                    break  # Use first available user screen
            
            # Priority 3: VTube Studio if active
            if not frames_to_analyze and state.vtube_stream_enabled and state.current_vtube_frame:
                frames_to_analyze.append(state.current_vtube_frame)
                contexts.append("VTube Studio")
            
            if not frames_to_analyze:
                time.sleep(5)
                continue
            
            # Analyze the main frame
            new_hash, changes = analyze_screen_changes(
                frames_to_analyze[0], 
                state.last_screen_hash
            )
            
            # If significant changes detected, generate AI reaction
            if changes and new_hash != state.last_screen_hash:
                state.last_screen_hash = new_hash
                state.last_analysis_time = current_time
                
                # Create context for AI
                change_context = f"[DYNAMIC OBSERVATION: Detected {', '.join(changes)} on {contexts[0]}]"
                
                # Generate AI reaction
                try:
                    # Decode the frame for AI analysis
                    img_bytes = base64.b64decode(frames_to_analyze[0])
                    img_array = np.frombuffer(img_bytes, dtype=np.uint8)
                    img = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
                    
                    # Get all active streams for context
                    active_streams = []
                    if state.ai_screen_enabled:
                        active_streams.append("AI Screen")
                    if state.vtube_stream_enabled:
                        active_streams.append("VTube Studio")
                    for sid, user in state.active_users.items():
                        if user.get('sharing_screen'):
                            active_streams.append(f"{user['username']}'s screen")
                    
                    response = controller.chat(
                        change_context,
                        image_frame=img,
                        personality='Playful',
                        stream_context={
                            "observation_mode": True, 
                            "changes": changes,
                            "active_streams": active_streams,
                            "observing": contexts[0]
                        }
                    )
                    
                    # Send spontaneous AI observation
                    socketio.emit('ai_observation', {
                        'message': response,
                        'context': changes,
                        'source': contexts[0],
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Add to TTS queue if enabled
                    if TTS_AVAILABLE:
                        state.tts_queue.append(response)
                        
                except Exception as e:
                    print(f"Error generating dynamic reaction: {e}")
            
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            print(f"Error in dynamic monitoring: {e}")
            time.sleep(5)

@socketio.on('toggle_dynamic_monitoring')
def handle_toggle_monitoring(data):
    """Toggle dynamic screen monitoring."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.dynamic_monitoring = enabled
        
        if enabled and not state.monitor_thread:
            state.monitor_thread = threading.Thread(target=dynamic_screen_monitor, daemon=True)
            state.monitor_thread.start()
            print("🔍 Dynamic monitoring started")
        elif not enabled:
            state.monitor_thread = None
            print("🔍 Dynamic monitoring stopped")

if __name__ == '__main__':
    run_streaming_server()