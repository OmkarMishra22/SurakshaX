import os
import cv2
import numpy as np
import base64
import threading
import database.database
from .ppe_yolo_engine import PPEVisionEngine, PPE_CLASSES

import json

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, "models")
DATASET_DIR = os.path.join(BASE_DIR, "data", "dataset")
CASCADE_PATH = os.path.join(MODELS_DIR, "haarcascade_frontalface_default.xml")
TRAINER_PATH = os.path.join(MODELS_DIR, "trainer", "trainer.yml")
EMBEDDINGS_PATH = os.path.join(MODELS_DIR, "trainer", "face_embeddings.json")

os.makedirs(MODELS_DIR, exist_ok=True)
os.makedirs(os.path.join(MODELS_DIR, "trainer"), exist_ok=True)
os.makedirs(DATASET_DIR, exist_ok=True)

class FaceEmbeddingRecognizer:
    """
    High-Accuracy Biometric Recognizer:
    Combines CLAHE adaptive illumination standardization, Multi-Scale Spatial Local
    Binary Patterns (LBP) texture extraction, and directional gradient orientation
    descriptors across spatial cells for illumination- and angle-invariant matching.
    """
    def __init__(self, storage_path):
        self.storage_path = storage_path
        self.templates = {}
        self.clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        self.load()

    def extract_embedding(self, img_gray):
        # Resize to standard 160x160 and apply CLAHE adaptive contrast
        resized = cv2.resize(img_gray, (160, 160), interpolation=cv2.INTER_AREA)
        eq = self.clahe.apply(resized)
        blurred = cv2.GaussianBlur(eq, (3, 3), 0)

        h, w = blurred.shape
        center = blurred[1:h-1, 1:w-1].astype(np.int16)
        lbp = np.zeros((h-2, w-2), dtype=np.uint8)
        offsets = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, 1), (1, 1), (1, 0),
            (1, -1), (0, -1)
        ]
        for i, (dy, dx) in enumerate(offsets):
            n = blurred[1+dy:h-1+dy, 1+dx:w-1+dx].astype(np.int16)
            lbp |= ((n >= center).astype(np.uint8) << i)

        features = []
        cell_h, cell_w = lbp.shape[0] // 4, lbp.shape[1] // 4
        for r in range(4):
            for c in range(4):
                cell = lbp[r*cell_h:(r+1)*cell_h, c*cell_w:(c+1)*cell_w]
                hist = np.histogram(cell, bins=16, range=(0, 256))[0].astype(np.float32)
                norm = np.linalg.norm(hist) + 1e-6
                features.extend(hist / norm)

        # Directional gradient orientation (HOG-style contours)
        gx = cv2.Sobel(blurred, cv2.CV_32F, 1, 0, ksize=3)
        gy = cv2.Sobel(blurred, cv2.CV_32F, 0, 1, ksize=3)
        mag, ang = cv2.cartToPolar(gx, gy, angleInDegrees=True)
        ang_cell_h, ang_cell_w = mag.shape[0] // 4, mag.shape[1] // 4
        for r in range(4):
            for c in range(4):
                m = mag[r*ang_cell_h:(r+1)*ang_cell_h, c*ang_cell_w:(c+1)*ang_cell_w]
                a = ang[r*ang_cell_h:(r+1)*ang_cell_h, c*ang_cell_w:(c+1)*ang_cell_w]
                h_ang = np.histogram(a, bins=8, range=(0, 360), weights=m)[0].astype(np.float32)
                norm = np.linalg.norm(h_ang) + 1e-6
                features.extend(h_ang / norm)

        emb = np.array(features, dtype=np.float32)
        norm_val = np.linalg.norm(emb) + 1e-6
        return (emb / norm_val).tolist()

    def train(self, face_samples, ids):
        for img, uid in zip(face_samples, ids):
            uid_str = str(uid)
            if uid_str not in self.templates:
                self.templates[uid_str] = []
            self.templates[uid_str].append(self.extract_embedding(img))
        self.save()

    def save(self):
        with open(self.storage_path, "w") as f:
            json.dump(self.templates, f)

    def load(self):
        if os.path.exists(self.storage_path):
            try:
                with open(self.storage_path, "r") as f:
                    self.templates = json.load(f)
            except Exception:
                self.templates = {}

    def predict(self, face_crop):
        if not self.templates or face_crop is None or face_crop.size == 0:
            return None, 999.0
        query_emb = np.array(self.extract_embedding(face_crop), dtype=np.float32)
        try:
            query_flip = np.array(self.extract_embedding(cv2.flip(face_crop, 1)), dtype=np.float32)
        except Exception:
            query_flip = query_emb

        best_uid = None
        best_sim = -1.0
        for uid_str, embs in self.templates.items():
            if not embs:
                continue
            mat = np.array(embs, dtype=np.float32)
            sims_orig = np.dot(mat, query_emb)
            sims_flip = np.dot(mat, query_flip)
            sims = np.maximum(sims_orig, sims_flip)

            max_sim = float(np.max(sims))
            top_k = np.sort(sims)[-min(3, len(sims)):]
            top_k_mean = float(np.mean(top_k))
            combined_sim = (0.65 * max_sim) + (0.35 * top_k_mean)

            if combined_sim > best_sim:
                best_sim = combined_sim
                best_uid = int(uid_str)
        dist = max(0.0, (1.0 - best_sim) * 100.0)
        return best_uid, dist

class FaceGateEngine:
    def __init__(self):
        self.face_cascade = None
        self.recognizer = None
        self.embedding_recognizer = FaceEmbeddingRecognizer(EMBEDDINGS_PATH)
        self.is_trained = False
        self._last_loaded_mtime = 0
        self._bg_training = False
        self.ppe_engine = PPEVisionEngine()
        self.load_models()

    def reload_if_needed(self):
        """
        Dynamically synchronizes model state with disk.
        If a user registered or updated face biometric data,
        this immediately reloads the trained weights without requiring a server restart.
        """
        if getattr(self, '_bg_training', False):
            return
        trainer_exists = os.path.exists(TRAINER_PATH)
        embeddings_exists = os.path.exists(EMBEDDINGS_PATH)

        if not trainer_exists and not embeddings_exists:
            if self.is_trained:
                self.is_trained = False
                self.recognizer = None
                self.embedding_recognizer.templates = {}
                self._last_loaded_mtime = 0
            return

        current_mtime = 0
        if trainer_exists:
            try:
                current_mtime = max(current_mtime, os.path.getmtime(TRAINER_PATH))
            except Exception:
                pass
        if embeddings_exists:
            try:
                current_mtime = max(current_mtime, os.path.getmtime(EMBEDDINGS_PATH))
            except Exception:
                pass

        if not self.is_trained or current_mtime != getattr(self, '_last_loaded_mtime', 0):
            self.load_models()
            self._last_loaded_mtime = current_mtime

    def load_models(self):
        # 1. Try CascadeClassifier (Frontal & Profile)
        if hasattr(cv2, 'CascadeClassifier'):
            try:
                if os.path.exists(CASCADE_PATH):
                    self.face_cascade = cv2.CascadeClassifier(CASCADE_PATH)
                elif hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                    self.face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            except Exception:
                self.face_cascade = None

            try:
                profile_path = os.path.join(MODELS_DIR, "haarcascade_profileface.xml")
                if os.path.exists(profile_path):
                    self.profile_cascade = cv2.CascadeClassifier(profile_path)
                elif hasattr(cv2, 'data') and hasattr(cv2.data, 'haarcascades'):
                    self.profile_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + "haarcascade_profileface.xml")
            except Exception:
                self.profile_cascade = None

        # Always reload embedding templates
        self.embedding_recognizer.load()

        # 2. Try OpenCV LBPH or fallback to FaceEmbeddingRecognizer
        try:
            if hasattr(cv2, 'face') and hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
                self.recognizer = cv2.face.LBPHFaceRecognizer_create()
                if os.path.exists(TRAINER_PATH):
                    self.recognizer.read(TRAINER_PATH)
                    self.is_trained = True
                    print("[FaceGateEngine] Loaded OpenCV LBPH face recognizer.")
                elif self.embedding_recognizer.templates:
                    self.is_trained = True
                    print(f"[FaceGateEngine] Loaded Pure-Python Face Biometric Recognizer with {len(self.embedding_recognizer.templates)} enrolled users.")
                else:
                    self.is_trained = False
            else:
                self.recognizer = self.embedding_recognizer
                if self.embedding_recognizer.templates:
                    self.is_trained = True
                    print(f"[FaceGateEngine] Loaded Pure-Python Face Biometric Recognizer with {len(self.embedding_recognizer.templates)} enrolled users.")
                else:
                    self.is_trained = False
        except Exception as e:
            print(f"[FaceGateEngine] Recognizer fallback active: {e}")
            self.recognizer = self.embedding_recognizer
            self.is_trained = bool(self.embedding_recognizer.templates)

        current_mtime = 0
        if os.path.exists(TRAINER_PATH):
            try:
                current_mtime = max(current_mtime, os.path.getmtime(TRAINER_PATH))
            except Exception:
                pass
        if os.path.exists(EMBEDDINGS_PATH):
            try:
                current_mtime = max(current_mtime, os.path.getmtime(EMBEDDINGS_PATH))
            except Exception:
                pass
        self._last_loaded_mtime = current_mtime

    def clear_all_registrations(self) -> dict:
        """Completely purges all saved face sample images, trainer files, and resets trained state."""
        purged_samples = 0
        if os.path.exists(DATASET_DIR):
            for f in os.listdir(DATASET_DIR):
                if f.endswith(".jpg"):
                    try:
                        os.remove(os.path.join(DATASET_DIR, f))
                        purged_samples += 1
                    except Exception:
                        pass

        if os.path.exists(TRAINER_PATH):
            try:
                os.remove(TRAINER_PATH)
            except Exception:
                pass

        if os.path.exists(EMBEDDINGS_PATH):
            try:
                os.remove(EMBEDDINGS_PATH)
            except Exception:
                pass

        self.embedding_recognizer.templates = {}
        self.is_trained = False
        self._last_loaded_mtime = 0
        self.load_models()
        print(f"[FaceGateEngine] Cleared {purged_samples} face samples and reset biometric recognizers.")
        return {"success": True, "purged_samples": purged_samples}

    def delete_worker_registration(self, worker_id: str) -> dict:
        """Purges saved face sample images and biometric templates for a single worker."""
        worker_id = str(worker_id).strip().upper()
        purged_samples = 0
        if os.path.exists(DATASET_DIR):
            for f in os.listdir(DATASET_DIR):
                if worker_id in f.upper():
                    try:
                        os.remove(os.path.join(DATASET_DIR, f))
                        purged_samples += 1
                    except Exception:
                        pass

        # Remove from embedding recognizer (keys could be worker_id or user DB id)
        changed = False
        for k in list(self.embedding_recognizer.templates.keys()):
            if str(k).upper() == worker_id:
                del self.embedding_recognizer.templates[k]
                changed = True

        if changed:
            self.embedding_recognizer.save()

        self._last_loaded_mtime = 0
        self.load_models()
        return {"success": True, "worker_id": worker_id, "purged_samples": purged_samples}

    def detect_faces(self, gray: np.ndarray, image_bgr: np.ndarray) -> list[tuple[int, int, int, int]]:
        """Strict face detection: Rejects blank frames, uses multi-scale cascade classifier."""
        if image_bgr is None or np.max(image_bgr) == 0:
            return []

        # 1. Frontal Cascade classifier (multi-pass for optimal sensitivity)
        if self.face_cascade is not None:
            try:
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=4, minSize=(35, 35))
                if len(faces) > 0:
                    faces_list = list(faces)
                    faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
                    return faces_list
            except Exception:
                pass

            try:
                faces = self.face_cascade.detectMultiScale(gray, scaleFactor=1.05, minNeighbors=3, minSize=(30, 30))
                if len(faces) > 0:
                    faces_list = list(faces)
                    faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
                    return faces_list
            except Exception:
                pass

        # 2. Profile Cascade for angled/turned faces (Face ID turn left / right)
        if getattr(self, 'profile_cascade', None) is not None:
            try:
                p_faces = self.profile_cascade.detectMultiScale(gray, scaleFactor=1.1, minNeighbors=3, minSize=(35, 35))
                if len(p_faces) > 0:
                    faces_list = list(p_faces)
                    faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
                    return faces_list
            except Exception:
                pass

            try:
                # Flipped profile for opposite angle turn
                gray_flipped = cv2.flip(gray, 1)
                p_faces_flipped = self.profile_cascade.detectMultiScale(gray_flipped, scaleFactor=1.1, minNeighbors=3, minSize=(35, 35))
                if len(p_faces_flipped) > 0:
                    w_img = gray.shape[1]
                    faces_list = [(w_img - (fx + fw), fy, fw, fh) for fx, fy, fw, fh in p_faces_flipped]
                    faces_list.sort(key=lambda f: f[2] * f[3], reverse=True)
                    return faces_list
            except Exception:
                pass

        # 3. Skin tone HSV segmentation fallback
        hsv = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2HSV)
        lower_skin = np.array([0, 30, 60], dtype=np.uint8)
        upper_skin = np.array([25, 200, 255], dtype=np.uint8)
        mask = cv2.inRange(hsv, lower_skin, upper_skin)
        kernel = np.ones((5, 5), np.uint8)
        mask = cv2.morphologyEx(mask, cv2.MORPH_OPEN, kernel)
        mask = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)

        if np.sum(mask > 0) < 1200:
            return []

        contours, _ = cv2.findContours(mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        valid_faces = []
        h_img, w_img = image_bgr.shape[:2]
        for cnt in contours:
            area = cv2.contourArea(cnt)
            if area > 1200:
                x, y, w, h = cv2.boundingRect(cnt)
                if y < h_img * 0.75 and 0.6 <= (h / (w + 1e-5)) <= 2.2:
                    valid_faces.append((int(x), int(y), int(w), int(h)))

        if valid_faces:
            valid_faces.sort(key=lambda f: f[2] * f[3], reverse=True)
            return [valid_faces[0]]

        return []

    def decode_base64_image(self, base64_str: str) -> np.ndarray:
        """Decodes base64 string from browser canvas to BGR OpenCV image."""
        if "," in base64_str:
            base64_str = base64_str.split(",", 1)[1]
        img_bytes = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_bytes, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img

    def enroll_and_train_user(self, user_id_int: int, worker_id: str, name: str, base64_samples: list[str]) -> dict:
        """
        Ultra-fast multi-angle biometric enrollment:
        1. Samples up to 15 diverse multi-angle frames across all 5 pose stages.
        2. Caches face bounding boxes across burst frames to avoid redundant cascade scans.
        3. Immediately extracts biometric embeddings in memory and persists face_embeddings.json (<50ms).
        4. Offloads heavy disk JPEG writes and OpenCV LBPH YAML serialization to a background thread.
        """
        if not base64_samples:
            return {"success": False, "error": "No face samples provided."}

        # Subsample up to 15 evenly spaced frames if a larger array was sent
        if len(base64_samples) > 15:
            step = max(1, len(base64_samples) // 15)
            sampled_b64 = [base64_samples[i] for i in range(0, len(base64_samples), step)][:15]
        else:
            sampled_b64 = base64_samples

        crops_to_save = []
        new_embeddings = []
        cached_box = None

        for idx, b64_frame in enumerate(sampled_b64):
            try:
                bgr = self.decode_base64_image(b64_frame)
                if bgr is None:
                    continue
                gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

                # Run face detection on first frame of each 3-frame stage or if no cached box exists
                if idx % 3 == 0 or cached_box is None:
                    faces = []
                    if self.face_cascade is not None:
                        det = self.face_cascade.detectMultiScale(gray, scaleFactor=1.2, minNeighbors=4, minSize=(36, 36))
                        if len(det) > 0:
                            faces = list(det)
                    if not faces:
                        faces = self.detect_faces(gray, bgr)
                    if len(faces) > 0:
                        cached_box = max(faces, key=lambda f: f[2] * f[3])

                if cached_box is not None:
                    x, y, w, h = cached_box
                    pad_w = int(w * 0.12)
                    pad_h = int(h * 0.12)
                    x1 = max(0, x - pad_w)
                    y1 = max(0, y - pad_h)
                    x2 = min(gray.shape[1], x + w + pad_w)
                    y2 = min(gray.shape[0], y + h + pad_h)
                    face_crop = gray[y1 : y2, x1 : x2]
                else:
                    h_img, w_img = gray.shape[:2]
                    face_crop = gray[int(h_img * 0.12) : int(h_img * 0.72), int(w_img * 0.18) : int(w_img * 0.82)]

                if face_crop.size == 0:
                    continue

                resized = cv2.resize(face_crop, (160, 160), interpolation=cv2.INTER_AREA)
                eq_crop = cv2.equalizeHist(resized)
                flipped_crop = cv2.flip(eq_crop, 1)

                for acrop in (eq_crop, flipped_crop):
                    crops_to_save.append(acrop)
                    new_embeddings.append(self.embedding_recognizer.extract_embedding(acrop))
            except Exception as ex:
                print(f"[FaceGateEngine] Error processing sample {idx}: {ex}")

        saved_count = len(crops_to_save)
        if saved_count == 0:
            return {"success": False, "error": "Could not detect face in camera samples. Please ensure face is centered."}

        # Immediately update in-memory biometric templates & persist lightweight JSON (<5ms)
        uid_str = str(user_id_int)
        self.embedding_recognizer.templates[uid_str] = new_embeddings
        try:
            self.embedding_recognizer.save()
        except Exception as e:
            print(f"[FaceGateEngine] Embedding save notice: {e}")

        self.is_trained = True
        if self.recognizer is None:
            self.recognizer = self.embedding_recognizer

        # Offload disk JPEG writes and heavy LBPH YAML training to background thread
        def _bg_persist_and_train(uid_val, crops_list):
            self._bg_training = True
            try:
                for s_idx, acrop in enumerate(crops_list, start=1):
                    sample_file = os.path.join(DATASET_DIR, f"User.{uid_val}.{s_idx}.jpg")
                    cv2.imwrite(sample_file, acrop)
                self.train_model_on_dataset()
                current_mtime = 0
                if os.path.exists(TRAINER_PATH):
                    current_mtime = max(current_mtime, os.path.getmtime(TRAINER_PATH))
                if os.path.exists(EMBEDDINGS_PATH):
                    current_mtime = max(current_mtime, os.path.getmtime(EMBEDDINGS_PATH))
                self._last_loaded_mtime = current_mtime
            except Exception as bg_err:
                print(f"[FaceGateEngine] Background training notice: {bg_err}")
            finally:
                self._bg_training = False

        threading.Thread(target=_bg_persist_and_train, args=(user_id_int, crops_to_save), daemon=True).start()

        total_users = len(self.embedding_recognizer.templates)
        return {
            "success": True,
            "samples_saved": saved_count,
            "total_faces_trained": saved_count,
            "users_count": total_users,
            "message": f"Biometric model enrolled instantaneously with {saved_count} samples for {name} ({worker_id})."
        }

    def train_model_on_dataset(self) -> dict:
        """Trains/retrains the biometric model on all samples in DATASET_DIR."""
        try:
            image_paths = [os.path.join(DATASET_DIR, f) for f in os.listdir(DATASET_DIR) if f.endswith(".jpg")]
            face_samples = []
            ids = []

            for ipath in image_paths:
                try:
                    img_gray = cv2.imread(ipath, cv2.IMREAD_GRAYSCALE)
                    if img_gray is None:
                        continue
                    img_standard = cv2.resize(cv2.equalizeHist(img_gray), (160, 160), interpolation=cv2.INTER_AREA)
                    parts = os.path.split(ipath)[-1].split(".")
                    if len(parts) >= 3 and parts[0] == "User" and parts[1].isdigit():
                        uid = int(parts[1])
                        face_samples.append(img_standard)
                        ids.append(uid)
                except Exception:
                    continue

            if face_samples and ids:
                # Train OpenCV LBPH recognizer
                if hasattr(cv2, 'face') and hasattr(cv2.face, 'LBPHFaceRecognizer_create'):
                    try:
                        self.recognizer = cv2.face.LBPHFaceRecognizer_create(radius=1, neighbors=8, grid_x=8, grid_y=8)
                        self.recognizer.train(face_samples, np.array(ids))
                        self.recognizer.write(TRAINER_PATH)
                        print(f"[FaceGateEngine] OpenCV LBPH (8x8 grid) trained and written to {TRAINER_PATH}")
                    except Exception as ex_lbph:
                        print(f"[FaceGateEngine] LBPH write error: {ex_lbph}")

                # Also train Embedding recognizer as parallel backup
                self.embedding_recognizer.templates = {}
                self.embedding_recognizer.train(face_samples, ids)
                self.embedding_recognizer.save()

                self.is_trained = True
                print(f"[FaceGateEngine] Successfully trained {len(face_samples)} face samples for {len(np.unique(ids))} registered users.")
                return {"success": True, "faces_trained": len(face_samples), "users_count": len(np.unique(ids))}
            
            self.is_trained = False
            return {"success": False, "error": "No valid dataset images found."}
        except Exception as e:
            print(f"[FaceGateEngine] Training error: {e}")
            self.is_trained = False
            return {"success": False, "error": str(e)}

    def detect_ppe_in_frame(self, image_bgr: np.ndarray, face_box: dict, worker_info: dict) -> dict:
        """
        Delegates to PPEVisionEngine for accurate 6-class detection:
        helmet, safety_vest, goggles, gloves, safety_boots, and face.
        """
        ppe_boxes = self.ppe_engine.detect_ppe_pixel_level(image_bgr, face_box, worker_info)
        return {"ppe_boxes": ppe_boxes}

    def analyze_frame(self, image_bgr: np.ndarray, preferred_worker_id: str = None) -> dict:
        """
        Strict Registered-Only Biometric & Real PPE Vision Pipeline:
        1. Detects live face in frame.
        2. Strictly checks against registered users in biometric database.
        3. Rejects unregistered faces with ACCESS DENIED.
        4. When matched, checks registered user credentials and evaluates real PPE compliance.
        """
        if image_bgr is None:
            return {"success": False, "error": "Invalid camera frame."}

        h, w = image_bgr.shape[:2]
        gray = cv2.cvtColor(image_bgr, cv2.COLOR_BGR2GRAY)

        faces = self.detect_faces(gray, image_bgr)

        # 1. STRICT CHECK: No Face in camera view
        if len(faces) == 0:
            return {
                "success": True,
                "face_detected": False,
                "biometric_matched": False,
                "face_box": None,
                "match_score": 0,
                "worker": None,
                "access_granted": False,
                "safe_to_enter": False,
                "status": "NO FACE DETECTED",
                "issues_detected": [
                    "NO FACE IN CAMERA VIEW: Please stand inside the target reticle",
                    "BIOMETRIC IDENTIFICATION PENDING: Align face to camera to verify credentials"
                ],
                "missing_precautions": ["Face alignment required before biometric gate pass"],
                "ppe_boxes": [],
                "camera_source": "Live Offline Camera"
            }

        x, y, fw, fh = max(faces, key=lambda f: f[2] * f[3])
        face_box = {"x": int(x), "y": int(y), "w": int(fw), "h": int(fh)}

        # Dummy fallback worker info if unregistered
        initial_worker_info = {
            "id": "PENDING",
            "name": "Verifying Identity...",
            "role": "Personnel",
            "department": "Plant",
            "site": "Gate 1",
            "training_valid": 1,
            "cert_valid": 1,
            "helmet_assigned": 1,
            "vest_assigned": 1,
            "goggles_assigned": 1,
            "gloves_assigned": 1,
            "shoes_assigned": 1
        }

        # 2. CHECK: Is Biometric Model Trained with Any Registered Users?
        self.reload_if_needed()
        if not self.is_trained:
            ppe_data = self.detect_ppe_in_frame(image_bgr, face_box, initial_worker_info)
            ppe_boxes = ppe_data["ppe_boxes"]
            decision = self.ppe_engine.evaluate_safe_to_enter(ppe_boxes, initial_worker_info)
            return {
                "success": True,
                "face_detected": True,
                "biometric_matched": False,
                "face_box": face_box,
                "match_score": 0,
                "worker": {
                    "id": "UNREGISTERED",
                    "name": "No Registered Personnel in Database",
                    "role": "Unenrolled Visitor",
                    "department": "Unassigned",
                    "site": "Gate 1",
                    "training_valid": 0,
                    "cert_valid": 0
                },
                "access_granted": False,
                "safe_to_enter": False,
                "status": "NO REGISTERED BIOMETRIC DATA (ACCESS DENIED)",
                "issues_detected": [
                    "DATABASE NOTICE: All registration data has been cleared. No enrolled worker biometric records found.",
                    "Please self-register at the top navigation portal to enroll your face."
                ],
                "missing_precautions": ["Face Biometric Self-Registration Required"],
                "ppe_boxes": ppe_boxes,
                "classes_verified": decision.get("classes_verified", {}),
                "camera_source": "Live Offline Camera"
            }

        # 3. RUN BIOMETRIC PREDICTION AGAINST REGISTERED DATA
        face_crop = gray[y : y + fh, x : x + fw]
        face_crop_resized = cv2.resize(face_crop, (160, 160), interpolation=cv2.INTER_AREA)
        face_crop_eq = self.embedding_recognizer.clahe.apply(face_crop_resized)

        predicted_user_id = None
        is_matched = False
        match_score = 0
        confidence = 999.0

        # Try LBPH Recognizer first
        if hasattr(self.recognizer, 'predict') and os.path.exists(TRAINER_PATH):
            try:
                p_uid, p_conf = self.recognizer.predict(face_crop_eq)
                # LBPH: Distance <= 84.0 indicates a genuine biometric match under varied camera lighting
                if p_conf <= 84.0:
                    predicted_user_id = p_uid
                    confidence = p_conf
                    is_matched = True
                    match_score = max(62, min(99, round(100 - (confidence * 0.46))))
            except Exception as e_pred:
                print(f"[FaceGateEngine] LBPH predict exception: {e_pred}")

        # Fallback & High-Accuracy Multi-Angle Embedding Recognizer (pass raw face_crop so CLAHE runs once cleanly)
        if self.embedding_recognizer.templates:
            try:
                emb_uid, emb_dist = self.embedding_recognizer.predict(face_crop)
                if emb_dist <= 40.0:
                    if not is_matched or emb_uid == predicted_user_id:
                        predicted_user_id = emb_uid
                        confidence = min(confidence, emb_dist)
                        is_matched = True
                        score_from_emb = max(68, min(99, round(100 - emb_dist)))
                        match_score = max(match_score, score_from_emb)
                    elif is_matched and emb_dist <= 28.0:
                        predicted_user_id = emb_uid
                        match_score = max(match_score, round(100 - emb_dist))
            except Exception as e_emb:
                print(f"[FaceGateEngine] Embedding predict exception: {e_emb}")

        # 4. STRICT: IF FACE DOES NOT MATCH ANY REGISTERED WORKER -> REJECT!
        if not is_matched or not predicted_user_id:
            ppe_data = self.detect_ppe_in_frame(image_bgr, face_box, initial_worker_info)
            ppe_boxes = ppe_data["ppe_boxes"]
            decision = self.ppe_engine.evaluate_safe_to_enter(ppe_boxes, initial_worker_info)
            return {
                "success": True,
                "face_detected": True,
                "biometric_matched": False,
                "face_box": face_box,
                "match_score": 0,
                "worker": {
                    "id": "UNREGISTERED",
                    "name": "Unregistered / Unknown Worker",
                    "role": "Unverified Visitor",
                    "department": "Unassigned",
                    "site": "Site Gate",
                    "training_valid": 0,
                    "cert_valid": 0
                },
                "access_granted": False,
                "safe_to_enter": False,
                "status": "UNREGISTERED WORKER (ACCESS DENIED)",
                "issues_detected": [
                    "BIOMETRIC RECOGNITION FAILED: Face is not registered in the OIL Personnel Database.",
                    "Access Denied: Unregistered worker detected. Turnstile locked. Please register at the registration portal before entry."
                ],
                "missing_precautions": ["Mandatory Worker Biometric Registration Required"],
                "ppe_boxes": ppe_boxes,
                "classes_verified": decision.get("classes_verified", {}),
                "camera_source": "Live Offline Camera"
            }

        # 5. RETRIEVE MATCHED WORKER PROFILE FROM DATABASE
        conn = database.database.get_db()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (predicted_user_id,))
        urow = cursor.fetchone()

        if not urow:
            conn.close()
            decision = self.ppe_engine.evaluate_safe_to_enter(ppe_boxes, initial_worker_info)
            return {
                "success": True,
                "face_detected": True,
                "biometric_matched": False,
                "face_box": face_box,
                "match_score": 0,
                "worker": None,
                "access_granted": False,
                "safe_to_enter": False,
                "status": "UNREGISTERED WORKER (USER ID NOT FOUND)",
                "issues_detected": ["Registered user ID not found in database"],
                "missing_precautions": ["Re-registration required"],
                "ppe_boxes": ppe_boxes,
                "classes_verified": decision.get("classes_verified", {}),
                "camera_source": "Live Offline Camera"
            }

        u = dict(urow)
        detected_worker_id = u["worker_id"] or f"W{u['id']:03d}"

        # Retrieve or construct worker compliance row
        cursor.execute("SELECT * FROM workers WHERE id = ?", (detected_worker_id,))
        worker_row = cursor.fetchone()

        if worker_row:
            worker_info = dict(worker_row)
        else:
            worker_info = {
                "id": detected_worker_id,
                "name": u["name"],
                "role": u["role"],
                "department": u["department"] or "Plant Operations",
                "site": u["site"] or "Site A (Duliajan)",
                "training_valid": 1,
                "cert_valid": 1,
                "helmet_assigned": 1,
                "vest_assigned": 1,
                "goggles_assigned": 1,
                "gloves_assigned": 1,
                "shoes_assigned": 1
            }

        conn.close()

        # Re-evaluate PPE with genuine worker credentials
        ppe_data = self.detect_ppe_in_frame(image_bgr, face_box, worker_info)
        ppe_boxes = ppe_data["ppe_boxes"]
        decision = self.ppe_engine.evaluate_safe_to_enter(ppe_boxes, worker_info)

        return {
            "success": True,
            "face_detected": True,
            "biometric_matched": True,
            "face_box": face_box,
            "match_score": match_score,
            "worker": worker_info,
            "access_granted": decision["access_granted"],
            "safe_to_enter": decision["safe_to_enter"],
            "status": decision["status"],
            "issues_detected": decision["issues_detected"],
            "missing_precautions": decision["missing_precautions"],
            "ppe_boxes": ppe_boxes,
            "classes_verified": decision.get("classes_verified", {}),
            "camera_source": "Live Offline Camera"
        }

# Global Shared Singleton
_shared_face_engine = None

def get_face_engine() -> FaceGateEngine:
    global _shared_face_engine
    if _shared_face_engine is None:
        _shared_face_engine = FaceGateEngine()
    return _shared_face_engine
