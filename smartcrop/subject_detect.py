import cv2
import os
import numpy as np

# YOLOv8 ONNX configuration
ONNX_MODEL_PATH = "models/yolov8n.onnx"
net = None
if os.path.exists(ONNX_MODEL_PATH):
    try:
        net = cv2.dnn.readNetFromONNX(ONNX_MODEL_PATH)
        # Try to use OpenVINO or CUDA if available, but default to CPU for stability
        net.setPreferableBackend(cv2.dnn.DNN_BACKEND_OPENCV)
        net.setPreferableTarget(cv2.dnn.DNN_TARGET_CPU)
    except Exception as e:
        print(f"Warning: Failed to load YOLO ONNX model: {e}")

# Fallback Detection Cascades
FACE_FRONT = os.path.join(cv2.data.haarcascades, 'haarcascade_frontalface_default.xml')
FACE_PROFILE = os.path.join(cv2.data.haarcascades, 'haarcascade_profileface.xml')
UPPER_BODY = os.path.join(cv2.data.haarcascades, 'haarcascade_upperbody.xml')

cascades = {
    'face': cv2.CascadeClassifier(FACE_FRONT) if os.path.exists(FACE_FRONT) else None,
    'profile': cv2.CascadeClassifier(FACE_PROFILE) if os.path.exists(FACE_PROFILE) else None,
    'body': cv2.CascadeClassifier(UPPER_BODY) if os.path.exists(UPPER_BODY) else None
}

def detect_subject(frame):
    """
    Detect main subject in a frame using a tiered approach:
    1. YOLO ONNX (OpenCV DNN) - Person/Object detection
    2. Frontal Face
    3. Profile Face
    4. Upper Body
    5. Center of Interest (Saliency fallback)
    """
    # Defensive: Check frame shape/size
    if frame is None or frame.size == 0:
        return None
    
    height, width = frame.shape[:2]
    if height < 10 or width < 10:
        return None

    # --- Tier 1: YOLO ONNX (The "Real" Multi-Subject Detection) ---
    if net is not None:
        try:
            # Pre-process: 640x640, scale 1/255, swapRB
            # Robust blob creation
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
            if blob is None:
                return None
                
            net.setInput(blob)
            outputs = net.forward() # Shape: [1, 84, 8400]
            
            if outputs is None or outputs.size == 0:
                return None

            # Post-process YOLOv8 output
            squeezed = np.squeeze(outputs)
            if squeezed.ndim != 2:
                return None
            predictions = squeezed.T
            
            if predictions.shape[1] < 5:
                return None
            scores = predictions[:, 4:]
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)
            
            # Mask for person class and confidence > 0.2
            mask = (class_ids == 0) & (confidences > 0.2)
            person_preds = predictions[mask]
            
            if len(person_preds) > 0:
                # Find largest person by area (w * h)
                areas = person_preds[:, 2] * person_preds[:, 3]
                best_idx = np.argmax(areas)
                best_person = person_preds[best_idx]
                
                # cx is index 0
                cx_norm = best_person[0] / 640.0
                return int(cx_norm * width)
        except Exception as e:
            # Silent fail to next tier, but print for debugging
            print(f"[DEBUG-YOLO-FAIL] {e}")
            pass

    # --- Tier 2-4: Haar Cascades ---
    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    
    # Try Frontal Face
    if cascades['face'] is not None:
        faces = cascades['face'].detectMultiScale(gray, 1.1, 5)
        if len(faces) > 0:
            x, y, w, h = faces[0]
            return x + w // 2
            
    # Try Profile Face
    if cascades['profile'] is not None:
        profiles = cascades['profile'].detectMultiScale(gray, 1.1, 5)
        if len(profiles) > 0:
            x, y, w, h = profiles[0]
            return x + w // 2
            
    # Try Upper Body
    if cascades['body'] is not None:
        bodies = cascades['body'].detectMultiScale(gray, 1.1, 3)
        if len(bodies) > 0:
            x, y, w, h = bodies[0]
            return x + w // 2

    # --- Tier 5: Saliency / Center Fallback ---
    # Simplified: return center of frame
    return width // 2


def detect_speaker(frames):
    """
    Experimental: Detect the most likely active speaker from a set of frames.
    Uses facial movement and position persistence.
    """
    if not frames:
        return None
        
    width = frames[0].shape[1]
    all_dets = []
    
    for i, frame in enumerate(frames):
        dets = get_detection_candidates(frame)
        for d in dets: d['frame_idx'] = i
        all_dets.append(dets)
        
    if not any(all_dets):
        return None

    # Track subjects across frames (crude matching by x-position/overlap)
    clusters = []
    for frame_dets in all_dets:
        for det in frame_dets:
            matched = False
            for c in clusters:
                if abs(c['avg_x'] - det['cx']) < (width * 0.15):
                    c['dets'].append(det)
                    c['avg_x'] = sum(d['cx'] for d in c['dets'])/len(c['dets'])
                    matched = True
                    break
            if not matched:
                clusters.append({'avg_x': det['cx'], 'dets': [det]})
                
    if not clusters: 
        return None
    
    # Analyze mouth activity (pixel variance in lower face)
    for c in clusters:
        if len(c['dets']) < 1:
            c['score'] = 0
            continue
            
        activity = 0
        for det in c['dets']:
            frame = frames[det['frame_idx']]
            box = det['box'] # cx, cy, w, h (norm) or (x, y, w, h)
            h, w = frame.shape[:2]
            
            # Convert box to pixels
            if len(box) == 4 and box[0] <= 1.0:
                bx, by, bw, bh = box[0]*width, box[1]*h, box[2]*width, box[3]*h
            else:
                bx, by, bw, bh = box[0], box[1], box[2], box[3]
                
            # Mouth region: lower 1/3 of the box
            mx = int(max(0, bx - bw/2))
            my = int(by + bh/6) 
            mw = int(bw)
            mh = int(bh/3)
            
            try:
                mouth_crop = frame[my:my+mh, mx:mx+mw]
                if mouth_crop.size > 0:
                    gray_mouth = cv2.cvtColor(mouth_crop, cv2.COLOR_BGR2GRAY)
                    # Proxy for movement: variance + edge density
                    activity += np.var(gray_mouth) + (cv2.Canny(gray_mouth, 50, 150).sum() / 255.0)
            except:
                pass
                
        c['score'] = activity / len(c['dets'])
        # Weight by persistence: if person is in all frames, they are more likely the speaker
        c['score'] *= (1 + (len(c['dets']) / len(frames)))
        # Weight by area
        avg_area = sum(d['area'] for d in c['dets']) / len(c['dets'])
        c['score'] *= (1 + avg_area / (width * frames[0].shape[0]))

    best_cluster = max(clusters, key=lambda c: c['score'])
    return int(best_cluster['avg_x'])

def get_detection_candidates(frame):
    """Helper to get multiple subjects (person class) from a frame."""
    if frame is None or frame.size == 0:
        return []
    height, width = frame.shape[:2]
    candidates = []
    
    # YOLO ONNX
    if net is not None:
        try:
            blob = cv2.dnn.blobFromImage(frame, 1/255.0, (640, 640), swapRB=True, crop=False)
            if blob is None:
                return []
                
            net.setInput(blob)
            outputs = net.forward()
            
            if outputs is None or outputs.size == 0:
                return []
                
            squeezed = np.squeeze(outputs)
            if squeezed.ndim != 2:
                return []
            predictions = squeezed.T
            
            if predictions.shape[1] < 5:
                return []
                
            scores = predictions[:, 4:]
            class_ids = np.argmax(scores, axis=1)
            confidences = np.max(scores, axis=1)
            
            mask = (class_ids == 0) & (confidences > 0.3)
            person_preds = predictions[mask]
            
            for p in person_preds:
                if len(p) < 4: continue
                cx_norm = p[0] / 640.0
                w_norm = p[2] / 640.0
                h_norm = p[3] / 640.0
                candidates.append({
                    'cx': int(cx_norm * width),
                    'area': w_norm * h_norm * width * height,
                    'box': p[:4] # Store raw box for mouth analysis
                })
        except Exception as e:
            print(f"[DEBUG-YOLO-CANDIDATES-FAIL] {e}")
            pass
            
    # Fallback to faces if no people found via YOLO
    if not candidates and cascades['face']:
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = cascades['face'].detectMultiScale(gray, 1.1, 5)
            for (x, y, w, h) in faces:
                candidates.append({
                    'cx': int(x + w/2),
                    'area': w * h,
                    'box': (x, y, w, h)
                })
        except: pass
            
    return candidates
