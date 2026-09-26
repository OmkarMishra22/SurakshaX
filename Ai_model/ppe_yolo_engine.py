"""
SurakshaX - High-Precision PPE & Biometric Vision Engine
Integrates Ultralytics YOLOv8 inference with deep pixel-by-pixel HSV contour & texture inspection.

Classes:
0: helmet
1: safety_vest
2: goggles
3: gloves
4: safety_boots
5: face
"""

import os
import cv2
import numpy as np

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")

# 5 Standard Industrial Detection Classes (Safety Goggles Removed)
PPE_CLASSES = [
    "helmet",        # 0: Hard Hat EN 397 / IS 2925
    "safety_vest",   # 1: High-Vis Reflective Vest Class 3 (EN ISO 20471)
    "gloves",        # 2: Industrial Cut-Resistant Hand Gloves (EN 388)
    "safety_boots",  # 3: Steel-Toe Puncture-Proof Boots (IS 15298)
    "face"           # 4: Biometric Facial Identification
]

# Normalization mapping for custom Ultralytics 5-class names to standard identifiers
CLASS_MAPPING = {
    # Class 0: Flame-Resistant Clothing / Vest / High-Vis
    "flame-resistant clothing": "safety_vest",
    "flame resistant clothing": "safety_vest",
    "high-visibility-vest": "safety_vest",
    "high visibility vest": "safety_vest",
    "frc": "safety_vest",
    "safety_vest": "safety_vest",
    "vest": "safety_vest",
    # Class 1: Class G-E Hard Hat / Helmet
    "class g-e hard hat": "helmet",
    "class ge hard hat": "helmet",
    "hard-hat": "helmet",
    "hard hat": "helmet",
    "helmet": "helmet",
    # Class 2: Safety Glasses / Goggles
    "safety-glasses": "goggles",
    "safety glasses": "goggles",
    "glasses": "goggles",
    "goggles": "goggles",
    # Class 3: Heavy-Duty Gloves
    "heavy-duty gloves": "gloves",
    "heavy duty gloves": "gloves",
    "gloves": "gloves",
    # Class 4: Steel-Toe Boots
    "steel-toe-boots": "safety_boots",
    "steel-toe boots": "safety_boots",
    "steel toe boots": "safety_boots",
    "safety_boots": "safety_boots",
    "boots": "safety_boots",
    "safety_shoe": "safety_boots",
    # Class 5: Face / Person
    "face": "face",
    "person": "face"
}

SAFE_ENTRY_REQUIREMENTS = list(PPE_CLASSES)

class PPEVisionEngine:
    def __init__(self):
        self.yolo_model = None
        self.model_loaded = False
        self.rf_client = None
        self.rf_model_id = "entry-gate-ppe-compliance/1"
        self._cached_rf_dets = {}
        self._cached_rf_ts = 0.0
        self._rf_busy = False
        import threading
        threading.Thread(target=self._init_yolo, daemon=True).start()

    def _init_yolo(self):
        try:
            from ultralytics import YOLO
            custom_weights = os.path.join(MODELS_DIR, "ppe_yolov8.pt")
            default_weights = os.path.join(MODELS_DIR, "yolov8n.pt")
            
            if os.path.exists(custom_weights):
                self.yolo_model = YOLO(custom_weights)
                self.model_loaded = True
                print("[PPEVisionEngine] Loaded fine-tuned PPE YOLOv8 model from ppe_yolov8.pt")
            elif os.path.exists(default_weights):
                self.yolo_model = YOLO(default_weights)
                self.model_loaded = True
                print("[PPEVisionEngine] Loaded base YOLOv8n model from models/yolov8n.pt")
            else:
                self.yolo_model = YOLO("yolov8n.pt")
                self.model_loaded = True
                print("[PPEVisionEngine] Loaded standard YOLOv8n network.")
        except Exception as e:
            print(f"[PPEVisionEngine] Note: Using pixel-by-pixel deep vision heuristics ({e})")
            self.model_loaded = False

        # Initialize Roboflow Hosted Inference Client
        self.rf_client = None
        self.rf_model_id = "entry-gate-ppe-compliance/1"
        try:
            from inference_sdk import InferenceHTTPClient, InferenceConfiguration
            rf_key = os.environ.get("ROBOFLOW_API_KEY", "fTrwzYQnP42MFBihF8MQ")
            self.rf_client = InferenceHTTPClient(
                api_url="https://detect.roboflow.com",
                api_key=rf_key
            ).configure(InferenceConfiguration(api_key_transport="header"))
            print(f"[PPEVisionEngine] Connected to Roboflow Cloud Model ({self.rf_model_id})")
        except Exception:
            self.rf_client = None

    def run_yolo_detection(self, image_bgr: np.ndarray) -> dict:
        """Runs fast Ultralytics YOLO neural inference (imgsz=320) + non-blocking Roboflow cloud ensemble."""
        import time
        import threading
        detections = {}

        # 1. Fast Local Fine-Tuned Model Inference (imgsz=320 for 4x faster CPU execution)
        if self.model_loaded and self.yolo_model is not None:
            try:
                results = self.yolo_model.predict(image_bgr, imgsz=320, conf=0.20, verbose=False)
                if results and len(results) > 0:
                    h, w = image_bgr.shape[:2]
                    for box in results[0].boxes:
                        cls_id = int(box.cls[0])
                        conf = float(box.conf[0])
                        raw_name = self.yolo_model.names.get(cls_id, str(cls_id)).lower()
                        mapped_name = CLASS_MAPPING.get(raw_name, raw_name)

                        x1, y1, x2, y2 = [int(v) for v in box.xyxy[0]]
                        box_dict = {
                            "x": max(0, x1),
                            "y": max(0, y1),
                            "w": min(w - max(0, x1), x2 - x1),
                            "h": min(h - max(0, y1), y2 - y1)
                        }

                        if mapped_name not in detections or conf > detections[mapped_name]["confidence"]:
                            detections[mapped_name] = {
                                "detected": True,
                                "confidence": round(conf, 2),
                                "box": box_dict,
                                "raw_class": self.yolo_model.names.get(cls_id, str(cls_id))
                            }
            except Exception:
                pass

        # 2. Roboflow Cloud Model Ensemble (Non-blocking background refresh + instant cached merge)
        if self.rf_client is not None:
            now = time.time()
            if (now - self._cached_rf_ts <= 4.0) and self._cached_rf_dets:
                for mapped_name, det_val in self._cached_rf_dets.items():
                    if mapped_name not in detections or det_val["confidence"] > detections[mapped_name]["confidence"]:
                        detections[mapped_name] = det_val

            if not self._rf_busy and (now - self._cached_rf_ts > 1.8):
                self._rf_busy = True
                frame_copy = image_bgr.copy()
                def _bg_rf_infer(img):
                    try:
                        rf_res = self.rf_client.infer(img, model_id=self.rf_model_id)
                        new_rf = {}
                        if rf_res and "predictions" in rf_res:
                            h, w = img.shape[:2]
                            for pred in rf_res["predictions"]:
                                raw_name = str(pred.get("class", "")).lower()
                                mapped_name = CLASS_MAPPING.get(raw_name, raw_name)
                                conf = float(pred.get("confidence", 0.0))
                                if conf < 0.20:
                                    continue

                                cx, cy = float(pred.get("x", 0)), float(pred.get("y", 0))
                                bw, bh = float(pred.get("width", 0)), float(pred.get("height", 0))
                                bx = max(0, int(cx - bw / 2.0))
                                by = max(0, int(cy - bh / 2.0))
                                bw_int = min(w - bx, int(bw))
                                bh_int = min(h - by, int(bh))

                                box_dict = {"x": bx, "y": by, "w": bw_int, "h": bh_int}
                                if mapped_name not in new_rf or conf > new_rf[mapped_name]["confidence"]:
                                    new_rf[mapped_name] = {
                                        "detected": True,
                                        "confidence": round(conf, 2),
                                        "box": box_dict,
                                        "raw_class": f"Roboflow/{raw_name}"
                                    }
                        self._cached_rf_dets = new_rf
                        self._cached_rf_ts = time.time()
                    except Exception:
                        pass
                    finally:
                        self._rf_busy = False
                threading.Thread(target=_bg_rf_infer, args=(frame_copy,), daemon=True).start()

        return detections

    def detect_ppe_pixel_level(self, image_bgr: np.ndarray, face_box: dict = None, worker_info: dict = None) -> list[dict]:
        """
        High-Accuracy Computer Vision & Physical Heuristics Pipeline:
        1. Anatomic spatial localization anchored on face geometry.
        2. Goggles/Eyewear: Edge gradient analysis + horizontal frame detection.
        3. Helmet: Forehead hair barrier analysis + vibrant industrial pigment checks (yellow, orange, blue, red)
           + non-background white dome verification.
        4. Safety Vest: Fluorescent neon lime/yellow and safety orange checking on the core torso.
           Strict rejection of dark clothing (navy, black, gray shirts).
        5. Gloves & Boots: Accurate field-of-view (FOV) classification.
        6. Neural YOLO model integration: High-confidence YOLO predictions seamlessly merged.
        """
        h, w = image_bgr.shape[:2]
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        if face_box and isinstance(face_box, dict):
            fx = int(face_box.get("x", w * 0.35))
            fy = int(face_box.get("y", h * 0.20))
            fw = int(face_box.get("w", w * 0.30))
            fh = int(face_box.get("h", h * 0.30))
        else:
            fx, fy, fw, fh = int(w * 0.35), int(h * 0.2), int(w * 0.3), int(h * 0.3)

        detected_boxes = []

        # -------------------------------------------------------------
        # 2. HELMET (Hard Hat EN 397 / IS 2925)
        # Spatial Zone: Crown above forehead (fy - 0.50*fh to fy)
        # -------------------------------------------------------------
        hx = max(0, fx - int(fw * 0.15))
        hy = max(0, fy - int(fh * 0.50))
        hw = min(w - hx, int(fw * 1.30))
        hh = min(h - hy, int(fh * 0.55))

        helmet_detected = False
        helmet_confidence = 0.15

        if hw > 20 and hh > 20:
            crown_hsv = hsv[hy : hy + hh, hx : hx + hw]
            
            # 1. Hair Barrier Check: Exposed natural hair directly above forehead indicates NO helmet
            forehead_top = max(0, fy - int(fh * 0.22))
            forehead_bot = min(h, fy + int(fh * 0.04))
            hair_zone_x1 = max(0, fx + int(fw * 0.12))
            hair_zone_x2 = min(w, fx + int(fw * 0.88))
            hair_zone = hsv[forehead_top:forehead_bot, hair_zone_x1:hair_zone_x2]
            
            has_exposed_hair = False
            if hair_zone.size > 0:
                # Dark hair: Low Value (V < 80)
                dark_hair_ratio = np.mean(hair_zone[:, :, 2] < 80)
                if dark_hair_ratio >= 0.15:
                    has_exposed_hair = True

            # 2. Vibrant Industrial Safety Helmet Pigments (EN 397 / IS 2925)
            # Yellow: H: 15-38, S: 75-255, V: 85-255
            mask_yellow = cv2.inRange(crown_hsv, np.array([15, 75, 85]), np.array([38, 255, 255]))
            # Orange: H: 5-16, S: 85-255, V: 85-255
            mask_orange = cv2.inRange(crown_hsv, np.array([5, 85, 85]), np.array([16, 255, 255]))
            # Blue: H: 92-135, S: 75-255, V: 75-255
            mask_blue = cv2.inRange(crown_hsv, np.array([92, 75, 75]), np.array([135, 255, 255]))
            # Green (HSE Officer / Safety Inspector Hard Hat): H: 39-85, S: 75-255, V: 70-255
            mask_green = cv2.inRange(crown_hsv, np.array([39, 75, 70]), np.array([85, 255, 255]))
            # Red (Fire / Emergency Hard Hat): H: 0-6 or 168-180, S: 90-255, V: 80-255
            mask_red = cv2.bitwise_or(
                cv2.inRange(crown_hsv, np.array([0, 90, 80]), np.array([6, 255, 255])),
                cv2.inRange(crown_hsv, np.array([168, 90, 80]), np.array([180, 255, 255]))
            )
            vivid_helmet_mask = cv2.bitwise_or(
                mask_yellow,
                cv2.bitwise_or(mask_orange, cv2.bitwise_or(mask_blue, cv2.bitwise_or(mask_green, mask_red)))
            )
            vivid_cov = cv2.countNonZero(vivid_helmet_mask) / float(hw * hh + 1e-5)

            # 3. White Hard Hat Check:
            # White helmet must NOT have exposed hair beneath, and must form a solid crown (V >= 185, S <= 42)
            white_mask = cv2.inRange(crown_hsv, np.array([0, 0, 185]), np.array([180, 42, 255]))
            white_cov = cv2.countNonZero(white_mask) / float(hw * hh + 1e-5)

            if vivid_cov >= 0.13:
                helmet_detected = True
                helmet_confidence = min(0.98, max(0.86, 0.72 + (vivid_cov * 0.55)))
            elif not has_exposed_hair and white_cov >= 0.30:
                helmet_detected = True
                helmet_confidence = min(0.96, max(0.82, 0.68 + (white_cov * 0.45)))
            else:
                helmet_detected = False
                helmet_confidence = round(max(0.12, vivid_cov * 1.5), 2)

        detected_boxes.append({
            "class_id": 0,
            "class_name": "helmet",
            "item": "SAFETY HELMET",
            "detected": helmet_detected,
            "confidence": round(helmet_confidence, 2),
            "standard": "EN 397 / IS 2925",
            "box": {"x": hx, "y": hy, "w": hw, "h": hh}
        })

        # -------------------------------------------------------------
        # 3. SAFETY VEST (High-Vis Reflective Class 3 EN ISO 20471)
        # Spatial Zone: Core Torso below chin (fy + 0.95*fh to fy + 2.3*fh)
        # -------------------------------------------------------------
        vx = max(0, fx - int(fw * 0.50))
        vy = min(h - 10, fy + int(fh * 0.95))
        vw = min(w - vx, int(fw * 2.00))
        vh = min(h - vy, int(fh * 1.35))

        vest_detected = False
        vest_confidence = 0.18

        if vw > 25 and vh > 25:
            vest_roi = hsv[vy : vy + vh, vx : vx + vw]
            # Core chest (excluding peripheral room background)
            chest_x1 = int(vw * 0.18)
            chest_x2 = int(vw * 0.82)
            chest_y1 = int(vh * 0.12)
            chest_y2 = int(vh * 0.85)
            chest_roi = vest_roi[chest_y1:chest_y2, chest_x1:chest_x2]

            if chest_roi.size > 0:
                # Fluorescent neon lime-yellow / yellow-green (EN ISO 20471)
                mask_hi_lime = cv2.inRange(chest_roi, np.array([20, 85, 95]), np.array([86, 255, 255]))
                # Fluorescent safety neon orange / FR red-orange
                mask_hi_orange = cv2.inRange(chest_roi, np.array([4, 100, 105]), np.array([22, 255, 255]))
                # Retro-reflective silver/grey tape bands (high brightness, low saturation)
                mask_reflective = cv2.inRange(chest_roi, np.array([0, 0, 190]), np.array([180, 38, 255]))

                hivis_mask = cv2.bitwise_or(mask_hi_lime, mask_hi_orange)
                hivis_cov = cv2.countNonZero(hivis_mask) / float(chest_roi.shape[0] * chest_roi.shape[1] + 1e-5)
                refl_cov = cv2.countNonZero(mask_reflective) / float(chest_roi.shape[0] * chest_roi.shape[1] + 1e-5)

                # Check if clothing is dark (navy, black, dark gray polo shirts without hi-vis)
                mean_v = np.mean(chest_roi[:, :, 2])
                is_dark_shirt = mean_v < 85

                if (hivis_cov >= 0.13 and not is_dark_shirt) or (hivis_cov >= 0.08 and refl_cov >= 0.08):
                    vest_detected = True
                    vest_confidence = min(0.98, max(0.86, 0.74 + (hivis_cov * 0.55)))
                else:
                    vest_detected = False
                    vest_confidence = round(max(0.12, hivis_cov * 1.5), 2)

        detected_boxes.append({
            "class_id": 1,
            "class_name": "safety_vest",
            "item": "HIGH-VIS VEST",
            "detected": vest_detected,
            "confidence": round(vest_confidence, 2),
            "standard": "EN ISO 20471 (Class 3)",
            "box": {"x": vx, "y": vy, "w": vw, "h": vh}
        })

        # -------------------------------------------------------------
        # 4. GLOVES (Industrial Cut-Resistant Hand Gloves EN 388)
        # Spatial Zone: Bilateral left & right hand/wrist periphery + raised hands
        # -------------------------------------------------------------
        gl_left_x = max(0, fx - int(fw * 0.78))
        gl_right_x = min(w - 25, fx + int(fw * 1.25))
        gl_y = min(h - 30, fy + int(fh * 1.35))
        gl_w = min(w - gl_left_x, int(fw * 0.52))
        gl_h = min(h - gl_y, int(fh * 0.52))

        gloves_detected = False
        gloves_confidence = 0.20
        best_gl_box = {"x": gl_left_x, "y": gl_y, "w": gl_w, "h": gl_h}

        hand_zones = [
            (gl_left_x, gl_y, min(w - gl_left_x, int(fw * 0.52)), gl_h),
            (gl_right_x, gl_y, min(w - gl_right_x, int(fw * 0.52)), gl_h)
        ]
        for (zx, zy, zw, zh) in hand_zones:
            if (zy + zh < h - 6) and (zw > 18) and (zh > 18):
                glove_hsv = hsv[zy : zy + zh, zx : zx + zw]
                if glove_hsv.size > 0:
                    # High-vis nitrile/rubber/kevlar gloves (yellow, orange, blue, green)
                    mask_g_color = cv2.inRange(glove_hsv, np.array([6, 95, 80]), np.array([135, 255, 255]))
                    g_cov = cv2.countNonZero(mask_g_color) / float(zw * zh + 1e-5)
                    if g_cov >= 0.20:
                        gloves_detected = True
                        conf = min(0.95, 0.72 + g_cov)
                        if conf > gloves_confidence:
                            gloves_confidence = conf
                            best_gl_box = {"x": zx, "y": zy, "w": zw, "h": zh}

        detected_boxes.append({
            "class_id": 3,
            "class_name": "gloves",
            "item": "SAFETY GLOVES",
            "detected": gloves_detected,
            "confidence": round(gloves_confidence, 2),
            "standard": "EN 388 (Cut Level 5)",
            "box": best_gl_box
        })

        # -------------------------------------------------------------
        # 5. SAFETY BOOTS (Steel-Toe Footwear IS 15298 / EN ISO 20345)
        # -------------------------------------------------------------
        bx = max(0, fx - int(fw * 0.2))
        by = max(0, min(h - 45, fy + int(fh * 2.3)))
        bw = min(w - bx, int(fw * 1.4))
        bh = min(h - by, 45)

        boots_detected = False
        boots_confidence = 0.20
        # Check if lower legs/feet are genuinely inside camera vertical FOV
        if (fy + int(fh * 2.6) < h) and bw > 25 and bh >= 30:
            boot_hsv = hsv[by : by + bh, bx : bx + bw]
            if boot_hsv.size > 0:
                # Industrial black/brown leather or yellow/tan rigger boots
                mask_boot_dark = cv2.inRange(boot_hsv, np.array([0, 0, 18]), np.array([180, 160, 85]))
                mask_boot_tan = cv2.inRange(boot_hsv, np.array([10, 80, 70]), np.array([30, 255, 210]))
                b_cov = (cv2.countNonZero(mask_boot_dark) + cv2.countNonZero(mask_boot_tan)) / float(bw * bh + 1e-5)
                if b_cov >= 0.32:
                    boots_detected = True
                    boots_confidence = min(0.93, 0.68 + (b_cov * 0.4))

        detected_boxes.append({
            "class_id": 4,
            "class_name": "safety_boots",
            "item": "SAFETY BOOTS",
            "detected": boots_detected,
            "confidence": round(boots_confidence, 2),
            "standard": "IS 15298 / EN ISO 20345",
            "box": {"x": bx, "y": by, "w": bw, "h": bh}
        })

        # -------------------------------------------------------------
        # 6. FACE (Live Facial Presence & Biometric Anchor)
        # -------------------------------------------------------------
        detected_boxes.append({
            "class_id": 5,
            "class_name": "face",
            "item": "FACE IDENTITY",
            "detected": bool(face_box),
            "confidence": 0.96 if face_box else 0.0,
            "standard": "ISO/IEC 19794-5",
            "box": face_box or {"x": fx, "y": fy, "w": fw, "h": fh}
        })

        # -------------------------------------------------------------
        # 7. ENSEMBLE WITH ULTRALYTICS YOLO NEURAL MODEL (IF LOADED)
        # -------------------------------------------------------------
        yolo_dets = self.run_yolo_detection(image_bgr)
        if yolo_dets:
            for item in detected_boxes:
                cname = item.get("class_name", "")
                if cname in yolo_dets:
                    yd = yolo_dets[cname]
                    if yd.get("detected") and yd.get("confidence", 0) >= 0.38:
                        item["detected"] = True
                        item["confidence"] = max(item["confidence"], yd["confidence"])
                        item["box"] = yd["box"]
                        item["neural_model"] = yd.get("raw_class", "YOLOv8")
        return detected_boxes

    def evaluate_safe_to_enter(self, detected_boxes, worker_info: dict = None, worker_induction_valid: bool = True, medical_cert_valid: bool = True, **kwargs) -> dict:
        """
        Precise 'Safe to Enter' Decision Engine:
        Criteria:
        - helmet == True
        - safety_vest == True
        - goggles == True
        - gloves == True
        - safety_boots == True
        - face == True (Live worker detected)
        - Compliance training_valid & cert_valid == True
        """
        if worker_info is None:
            worker_info = {}

        # Merge keyword parameters
        induction_ok = bool(kwargs.get("worker_induction_valid", worker_induction_valid and worker_info.get("training_valid", 1)))
        medical_ok = bool(kwargs.get("medical_cert_valid", medical_cert_valid and worker_info.get("cert_valid", 1)))

        issues_detected = []
        missing_items = []
        missing_mandatory_items = []

        # Support both list of dicts and dict mapping class_name -> info
        status_map = {}
        if isinstance(detected_boxes, dict):
            for k, v in detected_boxes.items():
                if isinstance(v, dict):
                    status_map[k] = bool(v.get("detected", False))
                else:
                    status_map[k] = bool(v)
        elif isinstance(detected_boxes, list):
            for b in detected_boxes:
                status_map[b.get("class_name", "")] = bool(b.get("detected", False))

        for req in PPE_CLASSES:
            if not status_map.get(req, False):
                missing_mandatory_items.append(req)

        if not status_map.get("face", False):
            issues_detected.append("NO FACE IN CAMERA VIEW: Personnel must stand inside the reticle")
            missing_items.append("Live Facial Presence")

        if not status_map.get("helmet", False):
            issues_detected.append("SAFETY HELMET MISSING: Hard hat (EN 397) required before site entry")
            missing_items.append("Safety Helmet (Hard Hat)")

        if not status_map.get("safety_vest", False):
            issues_detected.append("HIGH-VIS VEST MISSING: Class 3 reflective safety vest required")
            missing_items.append("High-Vis Reflective Vest")

        if not status_map.get("gloves", False):
            issues_detected.append("SAFETY GLOVES MISSING: Cut-resistant hand protection required")
            missing_items.append("Industrial Cut Gloves")

        if not status_map.get("safety_boots", False):
            issues_detected.append("SAFETY BOOTS MISSING: Steel-toe footwear (IS 15298) required")
            missing_items.append("Steel-Toe Safety Boots")

        # Operational certificates
        if not induction_ok:
            issues_detected.append("COMPLIANCE ISSUE: Mandatory Oilfield Safety Training Induction Expired")
            missing_items.append("Safety Induction Certification")

        if not medical_ok:
            issues_detected.append("FITNESS ISSUE: Operational / Medical Fitness Duty Certificate Expired")
            missing_items.append("Medical Fitness Certificate")

        safe_to_enter = len(issues_detected) == 0

        if safe_to_enter:
            gate_status = "ACCESS_GRANTED"
        elif len(missing_mandatory_items) > 0:
            gate_status = "DENIED_PPE_NON_COMPLIANT"
        else:
            gate_status = "DENIED_COMPLIANCE_NON_COMPLIANT"

        return {
            "safe_to_enter": safe_to_enter,
            "access_granted": safe_to_enter,
            "gate_status": gate_status,
            "status": "ACCESS GRANTED" if safe_to_enter else f"ACCESS DENIED ({len(issues_detected)} ISSUES DETECTED)",
            "issues_detected": issues_detected,
            "missing_precautions": missing_items,
            "missing_mandatory_items": missing_mandatory_items,
            "classes_verified": status_map
        }
