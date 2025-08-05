# LILITH AI - Enhanced Vision and Control System

LILITH AI est un système d'intelligence artificielle avancé avec des capacités de vision complète et de contrôle du PC. Cette version Ultimate offre une capture d'écran multi-moniteur, un contrôle clavier/souris robuste, et une vérification automatique des fonctionnalités.

## Fonctionnalités Principales

### 🖥️ Vision Avancée
- **Capture multi-moniteur** : Support complet de tous les écrans connectés
- **Résolution native** : Capture à la résolution originale sans troncature
- **Méthodes multiples** : MSS (recommandé) + PyAutoGUI (fallback)
- **Formats flexibles** : Base64, NumPy, PIL, fichier

### 🎮 Contrôle Robuste  
- **Contrôle clavier/souris** : pynput (recommandé) + PyAutoGUI (fallback)
- **Coordonnées relatives** : Support 0-1 et pixels absolus
- **Gestion d'erreurs** : Récupération automatique en cas d'échec
- **Combinaisons de touches** : Support complet (Ctrl+C, Alt+Tab, etc.)

### 🔍 Diagnostics Automatiques
- **Vérification au démarrage** : Test automatique des capacités vision/contrôle
- **Messages d'erreur détaillés** : Guidance pour résoudre les problèmes
- **Configuration OS** : Instructions spécifiques par système d'exploitation

## Installation et Configuration

### Dépendances Requises

```bash
pip install mss pynput opencv-python pyautogui pillow numpy
```

### Configuration par OS

#### 🪟 Windows

**Permissions requises :**
- Exécuter en tant qu'administrateur si nécessaire
- Désactiver UAC pour les applications d'automatisation
- Ajouter Python aux exclusions Windows Defender

**Configuration recommandée :**
```bash
# Installer toutes les dépendances
pip install mss pynput opencv-python pyautogui pillow numpy pywin32

# Pour TTS avancé
pip install pyttsx3
```

**Résolution des problèmes courants :**
- Si l'antivirus bloque l'automatisation → Ajouter des exceptions
- Si UAC interfère → Désactiver ou exécuter en admin
- Pour les environnements d'entreprise → Vérifier les stratégies de groupe

#### 🍎 macOS

**Permissions obligatoires :**
1. **Préférences Système** → **Sécurité et confidentialité** → **Confidentialité**
2. Activer **"Accessibilité"** pour votre app Python/Terminal
3. Activer **"Enregistrement d'écran"** pour votre app Python/Terminal  
4. Activer **"Automatisation"** si utilisation d'AppleScript

**Étapes détaillées :**
```bash
# 1. Installer les dépendances
pip install mss pynput opencv-python pyautogui pillow numpy

# 2. Première exécution (déclenchera les demandes de permission)
python launch_ultimate_rtx3060.py

# 3. Accorder les permissions dans Préférences Système
# 4. Redémarrer l'application
```

**⚠️ Important :** Vous devez redémarrer l'application après avoir accordé les permissions.

#### 🐧 Linux

**Prérequis système :**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install python3-dev python3-pip
sudo apt-get install xdotool scrot python3-tk
sudo apt-get install python3-xlib

# Ajouter l'utilisateur au groupe input
sudo usermod -a -G input $USER
```

**Configuration X11 :**
```bash
# Vérifier DISPLAY
echo $DISPLAY

# Si vide, configurer X11 forwarding
export DISPLAY=:0.0

# Pour SSH avec X11
ssh -X user@host
```

**Installation Python :**
```bash
pip install mss pynput opencv-python pyautogui pillow numpy python-xlib evdev
```

**Wayland vs X11 :**
- **X11** : Support complet (recommandé)
- **Wayland** : Support limité, privilégier X11 pour l'automatisation

### Configuration Avancée

#### Variables d'Environnement

```bash
# Désactiver le failsafe PyAutoGUI (automatisation continue)
export PYAUTOGUI_FAILSAFE=0

# Configuration MSS (multi-moniteur)
export MSS_MAX_DISPLAYS=10

# Configuration logging
export LILITH_LOG_LEVEL=INFO
```

#### Configuration Multi-Moniteur

```python
# Obtenir info sur les moniteurs
from lilith.tools import LilithTools
tools = LilithTools()
capabilities = tools.get_vision_capabilities()
print(capabilities["monitors"])

# Capture d'un moniteur spécifique
screenshot = tools.enhanced_screenshot(monitor=1)  # Moniteur principal
screenshot = tools.enhanced_screenshot(monitor=0)  # Tous les moniteurs
```

## Utilisation

### Lancement Standard
```bash
python launch_ultimate_rtx3060.py
```

### Diagnostics Manuels
```bash
# Diagnostic complet
python -m lilith.diagnostics

# Test Python
python -c "from lilith.diagnostics import LilithDiagnostics; LilithDiagnostics().print_detailed_report()"
```

### API de Contrôle

```python
from lilith.tools import LilithTools

tools = LilithTools()

# Capture d'écran multi-moniteur
screenshot = tools.enhanced_screenshot(monitor=0)  # Tous les moniteurs
screenshot = tools.enhanced_screenshot(monitor=1)  # Premier moniteur

# Contrôle souris avancé
tools.enhanced_mouse_control("click", x_rel=0.5, y_rel=0.5)  # Centre de l'écran
tools.enhanced_mouse_control("move", x=100, y=200, duration=0.5)

# Contrôle clavier avancé  
tools.enhanced_keyboard_control("type", text="Hello World!")
tools.enhanced_keyboard_control("press", key="ctrl+c")
```

## Résolution des Problèmes

### Vision Tronquée
1. Vérifier les permissions d'enregistrement d'écran
2. Tester avec différentes méthodes : MSS → PyAutoGUI
3. Vérifier la configuration multi-moniteur

### Contrôles Non-Fonctionnels
1. Vérifier les permissions d'accessibilité
2. Tester pynput → PyAutoGUI (fallback)
3. Redémarrer après changement de permissions

### Messages d'Erreur Communs

**"No screenshot method available"**
```bash
pip install mss pyautogui pillow
```

**"No working mouse control method"**  
```bash
pip install pynput pyautogui
```

**"Permission denied" (macOS)**
```
Préférences Système → Sécurité → Confidentialité → Accessibilité/Enregistrement
```

**"DISPLAY not found" (Linux)**
```bash
export DISPLAY=:0.0
# ou utiliser SSH avec -X
```

### Mode Debug

```python
# Activer le logging détaillé
import logging
logging.basicConfig(level=logging.DEBUG)

# Test diagnostic détaillé
from lilith.diagnostics import LilithDiagnostics
diag = LilithDiagnostics()
diag.print_detailed_report()
```

## Architecture Technique

### Hiérarchie des Méthodes
1. **MSS + pynput** (recommandé) : Performance optimale, multi-moniteur
2. **PyAutoGUI** (fallback) : Compatibilité maximale
3. **AB498 RPC** (legacy) : Serveur distant

### Formats de Coordonnées
- **Absolues** : Pixels exacts (x=100, y=200)
- **Relatives** : Ratios 0-1 (x_rel=0.5, y_rel=0.5)
- **Multi-moniteur** : Support natif avec MSS

### Gestion d'Erreurs
- Fallback automatique entre méthodes
- Messages d'erreur détaillés avec conseils
- Diagnostic automatique au démarrage

## Contribution et Support

Pour rapporter des bugs ou contribuer :
1. Exécuter le diagnostic complet
2. Inclure les logs et informations système
3. Préciser l'OS et la configuration matérielle

---

**Note :** Ce système nécessite des permissions système pour fonctionner. Suivez attentivement les instructions de configuration pour votre OS.