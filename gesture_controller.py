import cv2
import numpy as np
import pyautogui
import time
from collections import deque
from enum import Enum, auto
try:
    from ctypes import cast, POINTER
    from comtypes import CLSCTX_ALL
    from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume
    _devices = AudioUtilities.GetSpeakers()
    _interface = _devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
    VOLUME_CTRL = cast(_interface, POINTER(IAudioEndpointVolume))
    VOL_RANGE   = VOLUME_CTRL.GetVolumeRange()   
    USE_PYCAW   = True
    print(" pycaw volume control enabled")
except Exception:
    VOLUME_CTRL = None
    USE_PYCAW   = False
    print(" pycaw not found — using keyboard volume keys as fallback")
    print("   Install for precise control: pip install pycaw")
pyautogui.FAILSAFE = True
pyautogui.PAUSE = 0
class Gesture(Enum):
    NONE        = auto()
    HOVER       = auto()
    MOVE        = auto()
    LEFT_CLICK  = auto()
    RIGHT_CLICK = auto()
    DRAG        = auto()
    STOP        = auto()
    VOLUME      = auto()
TIP = [4, 8, 12, 16, 20]
PIP = [3, 6, 10, 14, 18]
HAND_CONNECTIONS = [
    (0,1),(1,2),(2,3),(3,4),
    (0,5),(5,6),(6,7),(7,8),
    (5,9),(9,10),(10,11),(11,12),
    (9,13),(13,14),(14,15),(15,16),
    (13,17),(17,18),(18,19),(19,20),(0,17),
]
def _load_mediapipe():
    import mediapipe as mp
    try:
        from mediapipe.tasks import python as mp_python
        from mediapipe.tasks.python.vision import (
            HandLandmarker,
            HandLandmarkerOptions,
            RunningMode,
        )
        import urllib.request, os, tempfile
        MODEL_URL  = (
            "https://storage.googleapis.com/mediapipe-models/"
            "hand_landmarker/hand_landmarker/float16/latest/hand_landmarker.task"
        )
        MODEL_PATH = os.path.join(tempfile.gettempdir(), "hand_landmarker.task")
        if not os.path.exists(MODEL_PATH):
            print("Downloading MediaPipe hand model (~9 MB) — one-time only…")
            urllib.request.urlretrieve(MODEL_URL, MODEL_PATH)
            print(" Model ready.")
        options = HandLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_path=MODEL_PATH),
            running_mode=RunningMode.IMAGE,
            num_hands=1,
            min_hand_detection_confidence=0.70,
            min_hand_presence_confidence=0.70,
            min_tracking_confidence=0.70,
        )
        landmarker = HandLandmarker.create_from_options(options)
        def _run(rgb_frame):
            img = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb_frame)
            res = landmarker.detect(img)
            return res.hand_landmarks if res.hand_landmarks else []
        def _draw(frame, lm_lists):
            h, w = frame.shape[:2]
            for lm in lm_lists:
                pts = [(int(l.x * w), int(l.y * h)) for l in lm]
                for a, b in HAND_CONNECTIONS:
                    cv2.line(frame, pts[a], pts[b], (0, 220, 150), 2)
                for pt in pts:
                    cv2.circle(frame, pt, 5, (255, 255, 255), -1)
                    cv2.circle(frame, pt, 5, (0, 180, 120),   1)

        print(" MediaPipe Tasks API detected (v0.10+)")
        return {"run": _run, "draw": _draw, "sol": None}

    except Exception:
        pass 
    try:
        import mediapipe as mp
        hands = mp.solutions.hands.Hands(
            static_image_mode=False,
            max_num_hands=1,
            min_detection_confidence=0.75,
            min_tracking_confidence=0.75,
        )
        draw_utils  = mp.solutions.drawing_utils
        draw_styles = mp.solutions.drawing_styles
        mp_hands_mod = mp.solutions.hands

        def _run(rgb_frame):
            res = hands.process(rgb_frame)
            if res.multi_hand_landmarks:
                return [h.landmark for h in res.multi_hand_landmarks]
            return []
        hands._last_result = None
        def _run_sol_full(rgb_frame):
            res = hands.process(rgb_frame)
            hands._last_result = res
            if res.multi_hand_landmarks:
                return [h.landmark for h in res.multi_hand_landmarks]
            return []
        def _draw(frame, lm_lists):
            res = hands._last_result
            if res and res.multi_hand_landmarks:
                for raw in res.multi_hand_landmarks:
                    draw_utils.draw_landmarks(
                        frame, raw,
                        mp_hands_mod.HAND_CONNECTIONS,
                        draw_styles.get_default_hand_landmarks_style(),
                        draw_styles.get_default_hand_connections_style(),
                    )

        print("MediaPipe solutions API detected (legacy)")
        return {"run": _run_sol_full, "draw": _draw, "sol": hands}

    except Exception as e:
        raise RuntimeError(
            " Could not initialise MediaPipe Hands.\n"
            "   Run: pip install mediapipe --upgrade\n"
            f"   Detail: {e}"
        )

class GestureController:
    COLORS = {
        Gesture.NONE:        (180, 180, 180),
        Gesture.HOVER:       (100, 220, 255),
        Gesture.MOVE:        ( 80, 200, 120),
        Gesture.LEFT_CLICK:  ( 50, 180, 255),
        Gesture.RIGHT_CLICK: (200, 100, 255),
        Gesture.DRAG:        (255, 140,  50),
        Gesture.STOP:        ( 80,  80,  80),
        Gesture.VOLUME:      ( 50, 220, 200),
    }
    LABELS = {
        Gesture.NONE:        "No gesture",
        Gesture.HOVER:       "Hover",
        Gesture.MOVE:        "Move / Scroll",
        Gesture.LEFT_CLICK:  "Left Click",
        Gesture.RIGHT_CLICK: "Right Click",
        Gesture.DRAG:        "Drag",
        Gesture.STOP:        "STOP",
        Gesture.VOLUME:      "Volume Control",
    }

    def __init__(self, cam_index=0, smoothing=7, sensitivity=1.2):
        self.screen_w, self.screen_h = pyautogui.size()
        self.smoothing   = smoothing
        self.sensitivity = sensitivity
        self.cam_index   = cam_index

        self.pos_buffer     = deque(maxlen=smoothing)
        self.prev_gesture   = Gesture.NONE
        self.drag_active    = False
        self.click_cooldown = 0
        self.prev_y         = None
        self.scroll_accum   = 0.0   
        self.vol_dist_prev  = None     
        self.fps_buffer     = deque(maxlen=30)

        mp_api          = _load_mediapipe()
        self._hands_run = mp_api["run"]
        self._draw_fn   = mp_api["draw"]
    def _fingers_up(self, lm):
        up = [False] * 5
        up[0] = lm[4].x < lm[2].x
        for i in range(1, 5):
            up[i] = lm[TIP[i]].y < lm[PIP[i]].y
        return up
    def _pinch_dist(self, lm):
        dx = lm[4].x - lm[8].x
        dy = lm[4].y - lm[8].y
        return np.sqrt(dx*dx + dy*dy)
    def _to_screen(self, lm_pt):
        m  = 0.20
        cx = np.clip((lm_pt.x - m) / (1 - 2*m), 0, 1)
        cy = np.clip((lm_pt.y - m) / (1 - 2*m), 0, 1)
        cx = np.clip(cx * self.sensitivity - (self.sensitivity - 1) / 2, 0, 1)
        cy = np.clip(cy * self.sensitivity - (self.sensitivity - 1) / 2, 0, 1)
        EDGE = 10
        sx = int(cx * (self.screen_w  - 2*EDGE)) + EDGE
        sy = int(cy * (self.screen_h - 2*EDGE)) + EDGE
        return sx, sy

    def classify(self, lm) -> Gesture:
        up    = self._fingers_up(lm)
        pinch = self._pinch_dist(lm)
        count = sum(up[1:])
        if all(up[1:]):                                      return Gesture.STOP
        if up[0] and up[4] and not up[1] and not up[2] and not up[3]: return Gesture.VOLUME
        if up[1] and up[2] and not up[3] and not up[4]:     return Gesture.MOVE
        if up[1] and up[2] and up[3] and not up[4]:         return Gesture.RIGHT_CLICK
        if pinch < 0.06 and not up[2] and not up[3]:        return Gesture.LEFT_CLICK
        if count == 0:                                       return Gesture.DRAG
        if up[1] and not up[2] and not up[3] and not up[4]: return Gesture.HOVER
        return Gesture.NONE

    def _smooth_move(self, sx, sy):
        self.pos_buffer.append((sx, sy))
        ax = int(np.mean([p[0] for p in self.pos_buffer]))
        ay = int(np.mean([p[1] for p in self.pos_buffer]))
        try:
            pyautogui.moveTo(ax, ay)
        except pyautogui.FailSafeException:
            pass
        return ax, ay

    def dispatch(self, gesture: Gesture, lm):
        sx, sy = self._to_screen(lm[8])

        if self.drag_active and gesture != Gesture.DRAG:
            pyautogui.mouseUp()
            self.drag_active = False
        if gesture != Gesture.VOLUME:
            self.vol_dist_prev = None

        if gesture == Gesture.STOP:
            self.prev_y       = None
            self.scroll_accum = 0.0

        elif gesture == Gesture.HOVER:
            self._smooth_move(sx, sy)
            self.prev_y       = None
            self.scroll_accum = 0.0

        elif gesture == Gesture.MOVE:
            cur_y = lm[0].y
            if self.prev_y is not None:
                delta = cur_y - self.prev_y   
                if abs(delta) > 0.005:        
                    clicks = int(delta * 30)  
                    if clicks != 0:
                        pyautogui.scroll(-clicks)
            self.prev_y = cur_y
        elif gesture == Gesture.VOLUME:
            dx = lm[4].x - lm[20].x
            dy = lm[4].y - lm[20].y
            dist = np.sqrt(dx*dx + dy*dy)   
            if self.vol_dist_prev is not None:
                delta = dist - self.vol_dist_prev
                if abs(delta) > 0.01:       
                    if USE_PYCAW:
                        vol = np.clip((dist - 0.1) / 0.5, 0.0, 1.0)
                        VOLUME_CTRL.SetMasterVolumeLevelScalar(float(vol), None)
                    else:
                        if delta > 0:
                            pyautogui.press('volumeup')
                        else:
                            pyautogui.press('volumedown')
            self.vol_dist_prev = dist
            self.prev_y = None

        elif gesture == Gesture.LEFT_CLICK:
            self._smooth_move(sx, sy)
            if self.click_cooldown <= 0 and self.prev_gesture != Gesture.LEFT_CLICK:
                pyautogui.click()
                self.click_cooldown = 20

        elif gesture == Gesture.RIGHT_CLICK:
            self._smooth_move(sx, sy)
            if self.click_cooldown <= 0 and self.prev_gesture != Gesture.RIGHT_CLICK:
                pyautogui.rightClick()
                self.click_cooldown = 20

        elif gesture == Gesture.DRAG:
            if not self.drag_active:
                pyautogui.mouseDown()
                self.drag_active = True
            self._smooth_move(sx, sy)

        else:
            self.prev_y = None

        if self.click_cooldown > 0:
            self.click_cooldown -= 1

        self.prev_gesture = gesture

    def draw_hud(self, frame, gesture, fps):
        h, w  = frame.shape[:2]
        color = self.COLORS[gesture]
        label = self.LABELS[gesture]

        overlay = frame.copy()
        cv2.rectangle(overlay, (0, 0), (230, h), (15, 15, 25), -1)
        cv2.addWeighted(overlay, 0.55, frame, 0.45, 0, frame)

        cv2.putText(frame, "GESTURE",         (10, 30),  cv2.FONT_HERSHEY_SIMPLEX, 0.48, (100,100,120), 1)
        cv2.putText(frame, label,             (10, 58),  cv2.FONT_HERSHEY_DUPLEX,  0.65, color, 2)
        cv2.putText(frame, f"FPS: {fps:.0f}", (10, 88),  cv2.FONT_HERSHEY_SIMPLEX, 0.48, (140,200,140), 1)

        if self.drag_active:
            cv2.putText(frame, "DRAGGING", (10, 112), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255,140,50), 2)

        legend = [
            "Index      -> Hover",
            "2 fingers  -> Move/Scroll",
            "Pinch      -> Left Click",
            "3 fingers  -> Right Click",
            "Fist       -> Drag",
            "Open palm  -> Stop",
            "Thumb+Pinky-> Volume",
        ]
        y0 = h - len(legend) * 22 - 16
        cv2.putText(frame, "-- LEGEND --", (10, y0-6), cv2.FONT_HERSHEY_SIMPLEX, 0.38, (70,70,100), 1)
        for i, line in enumerate(legend):
            cv2.putText(frame, line, (10, y0+i*21), cv2.FONT_HERSHEY_SIMPLEX, 0.36, (155,155,175), 1)

        cv2.rectangle(frame, (0,0), (w-1,h-1), tuple(int(c*0.6) for c in color), 3)
        return frame

    def run(self):
        cap = cv2.VideoCapture(self.cam_index)
        cap.set(cv2.CAP_PROP_FRAME_WIDTH,  640)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        cap.set(cv2.CAP_PROP_FPS, 30)

        if not cap.isOpened():
            raise RuntimeError(
                f"Could not open camera {self.cam_index}. "
                "Try --cam 1 if you have multiple cameras."
            )

        print("\n GestureControl is running — press Q in the window to quit\n")

        prev_time = time.time()

        while cap.isOpened():
            ret, frame = cap.read()
            if not ret:
                print("⚠ Frame read failed.")
                break

            frame = cv2.flip(frame, 1)
            rgb   = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            rgb.flags.writeable = False

            lm_lists = self._hands_run(rgb)

            rgb.flags.writeable = True

            gesture = Gesture.NONE
            if lm_lists:
                self._draw_fn(frame, lm_lists)
                lm = lm_lists[0]
                gesture = self.classify(lm)
                self.dispatch(gesture, lm)

            now = time.time()
            self.fps_buffer.append(1.0 / max(now - prev_time, 1e-9))
            prev_time = now

            frame = self.draw_hud(frame, gesture, float(np.mean(self.fps_buffer)))
            cv2.imshow("GestureControl  [C to quit]", frame)

            if cv2.waitKey(1) & 0xFF == ord('c'):
                break

        if self.drag_active:
            pyautogui.mouseUp()
        cap.release()
        cv2.destroyAllWindows()
        print(" Stopped cleanly.")

if __name__ == "__main__":
    import argparse

    p = argparse.ArgumentParser(description="GestureControl — hand gesture mouse controller")
    p.add_argument("--cam",         type=int,   default=0,   help="Camera index (default 0)")
    p.add_argument("--smoothing",   type=int,   default=7,   help="Smoothing frames (default 7)")
    p.add_argument("--sensitivity", type=float, default=1.5, help="Cursor speed (default 1.5)")
    args = p.parse_args()

    GestureController(
        cam_index   = args.cam,
        smoothing   = args.smoothing,
        sensitivity = args.sensitivity,
    ).run()