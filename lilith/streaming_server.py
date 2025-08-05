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

app = Flask(__name__)
app.config['SECRET_KEY'] = 'lilith-ai-secret-key'
CORS(app)
socketio = SocketIO(app, cors_allowed_origins="*", async_mode='threading')

# Initialize components
controller = None

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
        self.reaction_cooldown = 20  # seconds between reactions
        self.significant_changes = []
        self.context_memory = []  # Remember recent context
        self.last_activity_type = None
        # AI vision system
        self.current_view = "AI"  # Default AI view
        self.current_ai_frame_b64 = None  # Current image in base64
        # Autonomous mode
        self.autonomous_mode = False
        
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
                                time.sleep(5)
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
    """Capture l'écran complet SANS AUCUN redimensionnement pour garantir une vision complète."""
    with mss.mss() as sct:
        # Utiliser le moniteur 2 si disponible, sinon le moniteur 1
        monitor_idx = 2 if len(sct.monitors) > 2 else 1
        
        while state.ai_screen_enabled:
            try:
                # Récupérer les infos du moniteur
                monitor = sct.monitors[monitor_idx]
                print(f"📊 Moniteur {monitor_idx}: {monitor}")
                
                # CAPTURE INTÉGRALE sans modification
                screenshot = sct.grab(monitor)
                frame = np.array(screenshot)
                
                # Conserver l'image originale sans aucune transformation
                frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGRA2RGB)
                
                # Log des dimensions précises (important pour le diagnostic)
                h, w = frame_rgb.shape[:2]
                print(f"📏 Image capturée: {w}x{h} pixels")
                
                # ABSOLUMENT AUCUN REDIMENSIONNEMENT
                # Convertir directement en base64 avec qualité maximale
                _, buffer = cv2.imencode('.jpg', frame_rgb, [cv2.IMWRITE_JPEG_QUALITY, 100])
                jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                
                file_size_kb = len(buffer) / 1024
                print(f"📦 Taille de l'image: {file_size_kb:.2f} KB")
                
                with state.lock:
                    # Stocker à la fois l'image numpy originale et sa version base64
                    state.current_ai_frame = frame_rgb
                    state.current_ai_frame_b64 = jpg_as_text
                
                # Envoi de l'image intégrale aux clients
                socketio.emit('ai_screen_frame', {'frame': jpg_as_text})
                
                time.sleep(0.1)  # 10 FPS
                
            except Exception as e:
                print(f"❌ Erreur capture écran: {e}")
                import traceback
                traceback.print_exc()
                time.sleep(1)

def decode_b64_to_image(b64_string):
    """Decode base64 image to numpy array."""
    try:
        img_bytes = base64.b64decode(b64_string)
        img_array = np.frombuffer(img_bytes, dtype=np.uint8)
        return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
    except Exception as e:
        print(f"Error decoding base64 image: {e}")
        return None

def capture_vtube_studio():
    """Capture VTube Studio window even when not in foreground - FIXED VERSION."""
    import ctypes
    from ctypes import wintypes
    
    # Windows API functions
    user32 = ctypes.windll.user32
    gdi32 = ctypes.windll.gdi32
    
    # Correction: Utiliser une classe pour éviter l'erreur d'attribut 'append'
    class WindowFinder:
        def __init__(self):
            self.found_hwnds = []
            
        def callback(self, hwnd, _):
            try:
                if user32.IsWindowVisible(hwnd):
                    length = user32.GetWindowTextLengthW(hwnd)
                    if length > 0:
                        buff = ctypes.create_unicode_buffer(length + 1)
                        user32.GetWindowTextW(hwnd, buff, length + 1)
                        if "VTube Studio" in buff.value:
                            self.found_hwnds.append(hwnd)
                            print(f"✅ Found VTube Studio window: {buff.value}")
            except Exception as e:
                print(f"Error in window callback: {e}")
            return True
    
    while state.vtube_stream_enabled:
        try:
            # Utiliser notre classe WindowFinder pour trouver VTube Studio
            finder = WindowFinder()
            EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int))
            user32.EnumWindows(EnumWindowsProc(finder.callback), 0)
            
            # Si la fenêtre VTube Studio a été trouvée
            if finder.found_hwnds:
                hwnd = finder.found_hwnds[0]
                
                # Get window dimensions
                rect = wintypes.RECT()
                user32.GetWindowRect(hwnd, ctypes.pointer(rect))
                width = rect.right - rect.left
                height = rect.bottom - rect.top
                
                print(f"📐 VTube Studio window: {width}x{height}")
                
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
                    
                    # Convert to base64 with maximum quality
                    _, buffer = cv2.imencode('.jpg', frame, [cv2.IMWRITE_JPEG_QUALITY, 95])
                    jpg_as_text = base64.b64encode(buffer).decode('utf-8')
                    
                    with state.lock:
                        state.current_vtube_frame = jpg_as_text
                    
                    # Emit to all clients
                    socketio.emit('vtube_frame', {'frame': jpg_as_text})
                    
                    print("📸 VTube Studio frame captured successfully")
                else:
                    print("⚠️ Failed to capture VTube Studio window")
                
                # Clean up
                gdi32.DeleteObject(saveBitMap)
                gdi32.DeleteDC(mfcDC)
                user32.ReleaseDC(hwnd, hwndDC)
            else:
                print("🔍 VTube Studio window not found")
            
            time.sleep(0.033)  # 30 FPS for smooth animation
            
        except Exception as e:
            print(f"❌ VTube capture error: {e}")
            import traceback
            traceback.print_exc()
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
    """Handle screen frame from client with optimized image quality."""
    if request.sid in state.active_users:
        username = state.active_users[request.sid]['username']
        frame_data = data.get('frame')
        
        # Store the frame in user state for AI to access
        state.active_users[request.sid]['current_frame_b64'] = frame_data
        
        # Decode the frame and store it as well
        try:
            img_bytes = base64.b64decode(frame_data)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, cv2.IMREAD_COLOR)
            
            # Log dimensions for debugging
            if img is not None:
                h, w = img.shape[:2]
                print(f"📺 Received {username}'s screen frame: {w}x{h}")
                
                # Store the numpy array version for AI processing
                state.active_users[request.sid]['current_frame'] = img
                state.active_users[request.sid]['sharing_screen'] = True
            else:
                print(f"⚠️ Warning: Received invalid image frame from {username}")
        except Exception as e:
            print(f"❌ Error decoding client frame from {username}: {e}")
        
        # Broadcast to all clients including the sender
        emit('user_screen_frame', {
            'username': username,
            'frame': frame_data
        }, broadcast=True, include_self=True)

@socketio.on('chat_message')
def handle_chat_message(data):
    """Handle chat message with intelligent stream selection."""
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
        
        # --- INTELLIGENT STREAM SELECTION ---
        # Get all available streams
        available_streams = []
        if state.ai_screen_enabled:
            available_streams.append("AI")
        if state.vtube_stream_enabled:
            available_streams.append("VTube Studio")
        for sid, user in state.active_users.items():
            if user.get('sharing_screen'):
                available_streams.append(user['username'])
        
        # Auto-select best stream for AI to watch
        best_stream = select_best_stream(available_streams, username)
        composite_image = get_stream_image(best_stream)
        
        if composite_image is not None:
            print(f"👁️ AI watching: {best_stream} - Image shape: {composite_image.shape}")
        else:
            print(f"❌ No image available from stream: {best_stream}")
        
        # Process with AI
        try:
            # Check if controller is initialized
            global controller
            if controller is None:
                if not initialize_controller():
                    response = "❌ Unable to initialize AI controller. Please check LM Studio is running."
                    emit('ai_response', {'message': response, 'timestamp': datetime.now().isoformat()}, broadcast=True)
                    return

            # Call the controller with the selected image
            response = controller.chat(
                user_msg=message,
                image_frame=composite_image,
                personality='Playful',
                stream_context={
                    "active_streams": available_streams,
                    "current_view": best_stream,
                    "observation_mode": state.dynamic_monitoring,
                    "autonomous_mode": state.autonomous_mode
                }
            )
        except Exception as e:
            print(f"❌ Error calling controller.chat: {e}")
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
        print(f"❌ Error in handle_chat_message: {e}")
        import traceback
        traceback.print_exc()
        emit('ai_response', {
            'message': "Sorry, I encountered an error. Please try again.",
            'timestamp': datetime.now().isoformat()
        })

def select_best_stream(available_streams, current_user):
    """Intelligently select which stream the AI should watch."""
    if not available_streams:
        return "AI"
    
    # Priority 1: If a user just shared their screen, watch it
    user_streams = [stream for stream in available_streams 
                   if stream not in ["AI", "VTube Studio"]]
    
    if user_streams:
        # Prioritize the current user if they're sharing
        if current_user in user_streams:
            return current_user
        # Otherwise use the first user sharing
        return user_streams[0]
    
    # Priority 2: AI's own screen if available
    if "AI" in available_streams:
        return "AI"
    
    # Priority 3: VTube Studio
    if "VTube Studio" in available_streams:
        return "VTube Studio"
    
    # Default: first available
    return available_streams[0]

def get_stream_image(stream_name):
    """Get image from the specified stream."""
    if stream_name == "AI" and state.current_ai_frame is not None:
        return state.current_ai_frame
    elif stream_name == "VTube Studio" and state.current_vtube_frame:
        # Decode VTube frame
        try:
            img_bytes = base64.b64decode(state.current_vtube_frame)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            return cv2.imdecode(img_array, cv2.IMREAD_COLOR)
        except:
            return None
    else:
        # Check user streams
        for sid, user in state.active_users.items():
            if user['username'] == stream_name and user.get('current_frame') is not None:
                return user['current_frame']
    
    return None

@socketio.on('toggle_ai_screen')
def handle_toggle_ai_screen(data):
    """Toggle AI screen sharing."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.ai_screen_enabled = enabled
        
        if enabled and not state.ai_screen_thread:
            state.ai_screen_thread = threading.Thread(target=capture_ai_screen, daemon=True)
            state.ai_screen_thread.start()
            print("🖥️ AI screen capture started")
        elif not enabled:
            state.ai_screen_thread = None
            print("🖥️ AI screen capture stopped")

@socketio.on('toggle_vtube_stream')
def handle_toggle_vtube(data):
    """Toggle VTube Studio stream."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.vtube_stream_enabled = enabled
        
        if enabled and not state.vtube_thread:
            state.vtube_thread = threading.Thread(target=capture_vtube_studio, daemon=True)
            state.vtube_thread.start()
            print("🎭 VTube Studio capture started")
        elif not enabled:
            state.vtube_thread = None
            print("🎭 VTube Studio capture stopped")

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

@socketio.on('set_ai_view')
def handle_set_ai_view(data):
    """Set which view the AI should look at."""
    view = data.get('view', 'AI')
    with state.lock:
        state.current_view = view
        emit('ai_view_changed', {'current_view': view}, broadcast=True)
        print(f"👁️ AI view changed to: {view}")

@socketio.on('ai_stream_control')
def handle_ai_stream_control(data):
    """Handle AI-initiated stream control commands."""
    action = data.get('action')
    stream_type = data.get('stream_type')
    reason = data.get('reason', '')
    
    print(f"🤖 AI Stream Control: {action} {stream_type} - {reason}")
    
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

def analyze_screen_changes(current_frame, previous_hash):
    """Analyze screen for significant changes with improved detection."""
    if current_frame is None:
        return None, []
    
    try:
        # Handle both numpy arrays and base64 strings
        if isinstance(current_frame, str):
            # Decode base64 image
            img_bytes = base64.b64decode(current_frame)
            img_array = np.frombuffer(img_bytes, dtype=np.uint8)
            img = cv2.imdecode(img_array, flags=cv2.IMREAD_COLOR)
        else:
            # Already a numpy array
            img = current_frame
        
        if img is None:
            return previous_hash, []
        
        # Convert to grayscale for analysis
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        
        # Calculate hash for change detection
        resized = cv2.resize(gray, (16, 16))
        current_hash = hash(resized.tobytes())
        
        changes = []
        
        # Detect significant changes
        if previous_hash and current_hash != previous_hash:
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
        print(f"❌ Error analyzing screen: {e}")
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
            
            # Get current frame to analyze
            current_frame = None
            context = ""
            
            # Priority order for monitoring
            if state.current_ai_frame is not None:
                current_frame = state.current_ai_frame
                context = "AI Screen"
            elif state.active_users:
                # Find first user sharing screen
                for sid, user in state.active_users.items():
                    if user.get('sharing_screen') and user.get('current_frame') is not None:
                        current_frame = user['current_frame']
                        context = f"{user['username']}'s screen"
                        break
            
            if current_frame is None:
                time.sleep(5)
                continue
            
            # Analyze the frame for changes
            new_hash, changes = analyze_screen_changes(current_frame, state.last_screen_hash)
            
            # If significant changes detected, generate AI reaction
            if changes and new_hash != state.last_screen_hash:
                state.last_screen_hash = new_hash
                state.last_analysis_time = current_time
                
                # Create context for AI
                change_context = f"[DYNAMIC OBSERVATION: Detected {', '.join(changes)} on {context}]"
                
                # Generate AI reaction
                try:
                    # Get all active streams for context
                    active_streams = []
                    if state.ai_screen_enabled:
                        active_streams.append("AI")
                    if state.vtube_stream_enabled:
                        active_streams.append("VTube Studio")
                    for sid, user in state.active_users.items():
                        if user.get('sharing_screen'):
                            active_streams.append(user['username'])
                    
                    response = controller.chat(
                        change_context,
                        image_frame=current_frame,
                        personality='Playful',
                        stream_context={
                            "observation_mode": True, 
                            "changes": changes,
                            "active_streams": active_streams,
                            "observing": context
                        }
                    )
                    
                    # Send spontaneous AI observation
                    socketio.emit('ai_observation', {
                        'message': response,
                        'context': changes,
                        'source': context,
                        'timestamp': datetime.now().isoformat()
                    })
                    
                    # Add to TTS queue if enabled
                    if TTS_AVAILABLE:
                        state.tts_queue.append(response)
                        
                except Exception as e:
                    print(f"❌ Error generating dynamic reaction: {e}")
            
            time.sleep(5)  # Check every 5 seconds
            
        except Exception as e:
            print(f"❌ Error in dynamic monitoring: {e}")
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

@socketio.on('toggle_autonomous_mode')
def handle_toggle_autonomous(data):
    """Toggle autonomous mode."""
    enabled = data.get('enabled', False)
    
    with state.lock:
        state.autonomous_mode = enabled
        
        # Notify all clients of mode change
        socketio.emit('autonomous_mode_status', {'enabled': enabled})
        
        # Log the action
        socketio.emit('task_log', {
            'message': f"Autonomous mode {'activated' if enabled else 'deactivated'}",
            'type': 'status'
        })
        
        if enabled:
            # Add message to chat
            socketio.emit('ai_response', {
                'message': "🤖 **Autonomous mode activated**. I'll now help you more proactively and take initiative when needed.",
                'timestamp': datetime.now().isoformat()
            }, broadcast=True)
        else:
            # Add message to chat
            socketio.emit('ai_response', {
                'message': "🤖 **Autonomous mode deactivated**. I'll wait for your instructions.",
                'timestamp': datetime.now().isoformat()
            }, broadcast=True)

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

if __name__ == '__main__':
    run_streaming_server()