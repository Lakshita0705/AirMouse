# AirMouse — Gesture-Controlled Virtual Mouse
---
##  Overview

**AirMouse** is a computer vision-based virtual mouse that replaces your physical mouse with real-time hand gesture recognition. Using a standard webcam, it tracks your hand landmarks via MediaPipe and translates finger gestures into mouse actions — cursor movement, left click, right click, and scroll — with zero additional hardware.

Built as a portfolio project exploring human-computer interaction through computer vision.

---

##  Features

| Gesture | Action |
|---|---|
| Index finger up | Move cursor |
| Index + Middle finger pinch | Left click |
| Thumb + Index pinch | Right click |
| Two fingers up + scroll motion | Scroll |

-  Real-time hand tracking at 30+ FPS
-  Smooth cursor control with noise filtering
-  Works across Windows, macOS, and Linux
-  Runs on any standard webcam — no special hardware needed
-  Zero external dependencies beyond pip packages

---

##  Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.8+ |
| Computer Vision | OpenCV |
| Hand Tracking | MediaPipe |
| Mouse Control | PyAutoGUI |

---

## Project Structure

```
AirMouse/
│
├── gesture_controller.py  # PyAutoGUI mouse action handler
├── requirements.txt     # Dependencies
└── README.md
```

---

## Installation

### Prerequisites

- Python 3.8 or higher
- A working webcam
- pip

### Steps

**1. Clone the repository**

```bash
git clone https://github.com/Lakshita0705/AirMouse.git
cd AirMouse
```

**2. Create a virtual environment**

```bash
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate           # Windows
```

**3. Install dependencies**

```bash
pip install -r requirements.txt
```

---

## Usage

```bash
python airmouse.py
```

- A webcam window will open showing your hand landmarks in real time.
- Position your hand within the camera frame.
- Use the gestures listed above to control your mouse.
- Press **`q`** to quit.

### Configuration

You can tweak sensitivity and smoothing in `utils.py`:

```python
SMOOTHING_FACTOR = 5      # Higher = smoother, slower response
FRAME_REDUCTION = 100     # Webcam frame boundary (pixels)
```

---

##  How It Works

```
Webcam Frame
     │
     ▼
MediaPipe Hand Detection
     │  (21 hand landmarks per frame)
     ▼
Gesture Classifier
     │  (identifies gesture from landmark positions)
     ▼
Coordinate Mapper
     │  (maps webcam coords → screen coords with smoothing)
     ▼
PyAutoGUI Mouse Controller
     │  (executes move / click / scroll)
     ▼
System Mouse Action
```

1. **Hand Detection** — MediaPipe identifies 21 hand landmarks per frame
2. **Gesture Classification** — Relative positions of fingertip landmarks determine the active gesture
3. **Coordinate Mapping** — Webcam frame coordinates are mapped to screen resolution with a smoothing filter to reduce jitter
4. **Mouse Execution** — PyAutoGUI executes the corresponding system mouse action

---

##  Dependencies

```txt
opencv-python
mediapipe
pyautogui
numpy
```

Install all at once:

```bash
pip install opencv-python mediapipe pyautogui numpy
```

---

## Known Limitations

- Performance may vary under poor lighting conditions — ensure good ambient light
- Background clutter can occasionally interfere with hand detection
- High-resolution screens may require tuning the coordinate mapping parameters
- PyAutoGUI's `FAILSAFE` is enabled by default — moving cursor to top-left corner exits the program

---

## Future Improvements

- [ ] Multi-hand support
- [ ] Gesture customization via config file
- [ ] Double-click and drag gestures
- [ ] GUI for real-time sensitivity tuning
- [ ] Optimized performance for lower-end hardware

---

##  Author

**Lakshita Tuli**

---
