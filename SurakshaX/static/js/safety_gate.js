/**
 * SIFGuard Safety Gate Module (Real Offline Camera & Biometric PPE Scanner)
 * Supports real local webcam streaming (100% offline), face detection via OpenCV,
 * real-time PPE compliance scanning, and biometric identity verification.
 */

class SafetyGate {
    constructor() {
        this.scanBtn = document.getElementById('gateScanBtn');
        this.cameraToggleBtn = document.getElementById('gateToggleCameraBtn');
        this.autoScanToggle = document.getElementById('gateAutoScanToggle');
        this.canvas = document.getElementById('gateCameraCanvas');
        this.resultContainer = document.getElementById('gateResultContainer');

        // Real Camera Stream State
        this.video = document.createElement('video');
        this.video.setAttribute('playsinline', '');
        this.video.setAttribute('autoplay', '');
        this.video.muted = true;

        this.isRealCameraActive = false;
        this.isStartingCamera = false;
        this.userManuallyStopped = false;
        this.isScanning = false;
        this.stream = null;
        this.animFrameId = null;
        this.autoScanTimer = null;
        this.lastScanData = null;

        this.initCanvas();
        this.bindEvents();
    }

    initCanvas() {
        if (!this.canvas) return;
        this.ctx = this.canvas.getContext('2d');
        this.canvas.width = 640;
        this.canvas.height = 420;
        this.drawStandbyCanvas();
    }

    bindEvents() {
        if (this.scanBtn) {
            this.scanBtn.addEventListener('click', () => this.runScan());
        }

        if (this.cameraToggleBtn) {
            this.cameraToggleBtn.addEventListener('click', () => this.toggleRealCamera());
        }

        if (this.autoScanToggle) {
            this.autoScanToggle.addEventListener('change', () => {
                if (this.autoScanToggle.checked && this.isRealCameraActive) {
                    this.startAutoScanTimer();
                } else {
                    this.stopAutoScanTimer();
                }
            });
        }
    }

    async startRealCamera(silent = false) {
        if (this.isRealCameraActive || this.isStartingCamera) return;

        // Verify that the user is actively on the Safety Gate tab and employee section
        const activeTab = document.querySelector('.page-tab.active');
        const isOnGateTab = activeTab && (activeTab.id === 'tab-safety-gate' || activeTab.getAttribute('id') === 'tab-safety-gate');
        const secEmp = document.getElementById('gateSubSectionEmployee');
        const isEmployeeSubTab = secEmp ? (secEmp.style.display !== 'none') : true;

        if (!isOnGateTab || !isEmployeeSubTab || document.hidden) {
            return;
        }

        this.isStartingCamera = true;

        try {
            const stream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 640 }, height: { ideal: 480 }, facingMode: 'user' },
                audio: false
            });

            // Guard against race condition: user navigated away or stopped camera while awaiting permission
            if (!this.isStartingCamera) {
                stream.getTracks().forEach(t => {
                    try { t.stop(); } catch (e) {}
                });
                return;
            }

            this.stream = stream;
            this.video.srcObject = this.stream;
            await this.video.play();
            this.isRealCameraActive = true;
            this.isStartingCamera = false;

            if (this.cameraToggleBtn) {
                this.cameraToggleBtn.innerHTML = '⏹️ Stop Camera';
                this.cameraToggleBtn.className = 'btn btn-danger btn-sm';
            }

            const camBadge = document.getElementById('gateCameraBadgeText');
            if (camBadge) camBadge.innerText = 'LIVE OPTICAL FEED ACTIVE';

            if (!silent && window.showToast) {
                window.showToast('📹 Live Webcam connected. Ready for worker detection.', 'success');
            }

            this.renderRealCameraLoop();

            // Auto-scan periodically if enabled
            if (this.autoScanToggle && this.autoScanToggle.checked) {
                this.startAutoScanTimer();
            }

            // Perform initial immediate scan after 200ms
            setTimeout(() => {
                if (this.isRealCameraActive) this.runScan(true);
            }, 200);
        } catch (err) {
            console.warn('Real webcam access error:', err);
            this.isRealCameraActive = false;
            this.isStartingCamera = false;
            if (!silent && window.showToast) {
                window.showToast('Webcam access error. Please permit camera access to use the Safety Gate.', 'danger');
            }
            this.drawStandbyCanvas();
        }
    }

    stopRealCamera() {
        this.isStartingCamera = false;
        this.stopAutoScanTimer();

        if (this.animFrameId) {
            cancelAnimationFrame(this.animFrameId);
            this.animFrameId = null;
        }
        if (this.stream) {
            this.stream.getTracks().forEach(t => {
                try { t.stop(); } catch (e) {}
            });
            this.stream = null;
        }
        if (this.video) {
            this.video.srcObject = null;
        }
        this.isRealCameraActive = false;
        if (this.cameraToggleBtn) {
            this.cameraToggleBtn.innerHTML = '📹 Start Camera';
            this.cameraToggleBtn.className = 'btn btn-primary btn-sm';
        }
        const camBadge = document.getElementById('gateCameraBadgeText');
        if (camBadge) camBadge.innerText = 'LIVE CAMERA STANDBY';

        this.drawStandbyCanvas();
    }

    toggleRealCamera() {
        if (this.isRealCameraActive || this.isStartingCamera) {
            this.userManuallyStopped = true;
            this.stopRealCamera();
        } else {
            this.userManuallyStopped = false;
            this.startRealCamera();
        }
    }

    startAutoScanTimer() {
        this.stopAutoScanTimer();
        this.autoScanTimer = setInterval(() => {
            if (this.isRealCameraActive && !this.isScanning) {
                this.runScan(true);
            }
        }, 1200);
    }

    stopAutoScanTimer() {
        if (this.autoScanTimer) {
            clearInterval(this.autoScanTimer);
            this.autoScanTimer = null;
        }
    }

    renderRealCameraLoop() {
        if (!this.isRealCameraActive || !this.ctx) return;

        const cw = this.canvas.width;
        const ch = this.canvas.height;

        // Draw video frame onto canvas
        this.ctx.drawImage(this.video, 0, 0, cw, ch);

        // Draw animated HUD Reticle
        this.drawHUDOverlays(cw, ch);

        // Overlay active PPE inspection bounding boxes
        if (this.lastScanData && this.lastScanData.ppe_boxes) {
            this.drawPPEBoxes(this.lastScanData.ppe_boxes);
        }

        this.animFrameId = requestAnimationFrame(() => this.renderRealCameraLoop());
    }

    drawHUDOverlays(w, h) {
        this.ctx.strokeStyle = '#0284c7';
        this.ctx.lineWidth = 2;
        const len = 28;

        // Top-left corner
        this.ctx.beginPath();
        this.ctx.moveTo(20, 20 + len);
        this.ctx.lineTo(20, 20);
        this.ctx.lineTo(20 + len, 20);
        this.ctx.stroke();

        // Top-right corner
        this.ctx.beginPath();
        this.ctx.moveTo(w - 20 - len, 20);
        this.ctx.lineTo(w - 20, 20);
        this.ctx.lineTo(w - 20, 20 + len);
        this.ctx.stroke();

        // Bottom-left corner
        this.ctx.beginPath();
        this.ctx.moveTo(20, h - 20 - len);
        this.ctx.lineTo(20, h - 20);
        this.ctx.lineTo(20 + len, h - 20);
        this.ctx.stroke();

        // Bottom-right corner
        this.ctx.beginPath();
        this.ctx.moveTo(w - 20 - len, h - 20);
        this.ctx.lineTo(w - 20, h - 20);
        this.ctx.lineTo(w - 20, h - 20 - len);
        this.ctx.stroke();
    }

    smoothPPEBoxes(prevBoxes, nextBoxes) {
        if (!Array.isArray(prevBoxes) || !Array.isArray(nextBoxes) || prevBoxes.length === 0) {
            return nextBoxes;
        }
        const prevMap = {};
        prevBoxes.forEach(b => {
            if (b && b.class_name && b.box) prevMap[b.class_name] = b.box;
        });
        const alpha = 0.65; // 65% new frame, 35% previous frame for smooth tracking
        return nextBoxes.map(item => {
            const pb = prevMap[item.class_name];
            if (pb && item.box) {
                return {
                    ...item,
                    box: {
                        x: Math.round(alpha * item.box.x + (1 - alpha) * pb.x),
                        y: Math.round(alpha * item.box.y + (1 - alpha) * pb.y),
                        w: Math.round(alpha * item.box.w + (1 - alpha) * pb.w),
                        h: Math.round(alpha * item.box.h + (1 - alpha) * pb.h)
                    }
                };
            }
            return item;
        });
    }

    drawPPEBoxes(boxes) {
        boxes.forEach(p => {
            const b = p.box;
            if (!b || b.w <= 0 || b.h <= 0) return;

            const confPct = p.confidence ? `${Math.round(p.confidence * 100)}%` : '';
            this.ctx.lineWidth = 2;
            if (p.detected) {
                this.ctx.strokeStyle = '#10b981';
                this.ctx.fillStyle = 'rgba(16, 185, 129, 0.15)';
                this.ctx.strokeRect(b.x, b.y, b.w, b.h);
                this.ctx.fillRect(b.x, b.y, b.w, b.h);

                this.ctx.fillStyle = '#10b981';
                this.ctx.fillRect(b.x, Math.max(0, b.y - 16), b.w, 16);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.font = 'bold 9.5px sans-serif';
                this.ctx.textAlign = 'center';
                this.ctx.fillText(`✓ ${p.item}${confPct ? ' ' + confPct : ''}`, b.x + b.w/2, Math.max(11, b.y - 4));
            } else {
                this.ctx.strokeStyle = '#ef4444';
                this.ctx.setLineDash([4, 3]);
                this.ctx.fillStyle = 'rgba(239, 68, 68, 0.15)';
                this.ctx.strokeRect(b.x, b.y, b.w, b.h);
                this.ctx.fillRect(b.x, b.y, b.w, b.h);
                this.ctx.setLineDash([]);

                this.ctx.fillStyle = '#ef4444';
                this.ctx.fillRect(b.x, Math.max(0, b.y - 16), b.w, 16);
                this.ctx.fillStyle = '#ffffff';
                this.ctx.font = 'bold 9.5px sans-serif';
                this.ctx.textAlign = 'center';
                this.ctx.fillText(`✗ ${p.item} MISSING`, b.x + b.w/2, Math.max(11, b.y - 4));
            }
        });
    }

    drawStandbyCanvas() {
        if (!this.ctx) return;
        const w = this.canvas.width = 640;
        const h = this.canvas.height = 420;

        // Dark industrial background
        this.ctx.fillStyle = '#0b1120';
        this.ctx.fillRect(0, 0, w, h);

        // Subtle grid lines
        this.ctx.strokeStyle = '#1e293b';
        this.ctx.lineWidth = 1;
        for (let x = 0; x < w; x += 40) {
            this.ctx.beginPath();
            this.ctx.moveTo(x, 0);
            this.ctx.lineTo(x, h);
            this.ctx.stroke();
        }
        for (let y = 0; y < h; y += 40) {
            this.ctx.beginPath();
            this.ctx.moveTo(0, y);
            this.ctx.lineTo(w, y);
            this.ctx.stroke();
        }

        // Silhouette representation
        this.ctx.fillStyle = '#1e293b';
        this.ctx.beginPath();
        this.ctx.arc(w/2, 110, 45, 0, Math.PI * 2);
        this.ctx.fill();
        this.ctx.beginPath();
        this.ctx.roundRect(w/2 - 60, 165, 120, 160, 10);
        this.ctx.fill();

        this.ctx.fillStyle = '#94a3b8';
        this.ctx.font = 'bold 13px sans-serif';
        this.ctx.textAlign = 'center';
        this.ctx.fillText("LIVE SCANNER STANDBY • AUTO-ACTIVATES ON GATE SCANNER", w/2, h - 35);
        this.ctx.fillStyle = '#10b981';
        this.ctx.font = '11.5px monospace';
        this.ctx.fillText("🛡️ AUTOMATIC BIOMETRIC ID & REAL 6-CLASS PPE VERIFICATION", w/2, h - 16);
    }

    async runScan(isSilentAutoScan = false) {
        if (!this.isRealCameraActive) {
            if (!isSilentAutoScan && window.showToast) {
                window.showToast('Please start the live camera first.', 'warning');
            }
            return;
        }

        if (this.isScanning) return;
        this.isScanning = true;

        if (this.scanBtn && !isSilentAutoScan) {
            this.scanBtn.disabled = true;
            this.scanBtn.innerHTML = '🔍 Scanning Biometrics &amp; PPE...';
        }

        try {
            // Reuse offscreen canvas matching display dimensions for zero-GC fast frame capture
            if (!this._snapCanvas) {
                this._snapCanvas = document.createElement('canvas');
                this._snapCanvas.width = 640;
                this._snapCanvas.height = 420;
                this._snapCtx = this._snapCanvas.getContext('2d');
            }
            this._snapCtx.drawImage(this.video, 0, 0, 640, 420);
            const base64Image = this._snapCanvas.toDataURL('image/jpeg', 0.84);

            const res = await fetch('/api/safety_gate/scan_frame', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ image: base64Image })
            });
            const data = await res.json();
            if (data && data.ppe_boxes && this.lastScanData && this.lastScanData.ppe_boxes) {
                data.ppe_boxes = this.smoothPPEBoxes(this.lastScanData.ppe_boxes, data.ppe_boxes);
            }
            this.lastScanData = data;
            this.renderResult(data);

            if (!isSilentAutoScan && window.showToast) {
                if (data.biometric_matched && data.worker) {
                    window.showToast(`Biometric Matched: ${data.worker.name} (${data.worker.id})`, data.access_granted ? 'success' : 'warning');
                } else if (data.face_detected) {
                    window.showToast(data.status, 'danger');
                } else {
                    window.showToast('No face detected in camera view.', 'warning');
                }
            }
        } catch (err) {
            console.error('Scan frame error:', err);
            if (!isSilentAutoScan && window.showToast) {
                window.showToast('Camera processing error. Please try again.', 'danger');
            }
        } finally {
            this.isScanning = false;
            if (this.scanBtn && !isSilentAutoScan) {
                this.scanBtn.disabled = false;
                this.scanBtn.innerHTML = '🔍 Scan Live Face &amp; PPE';
            }
        }
    }

    renderResult(data) {
        if (!this.resultContainer) return;

        // CASE 1: No Face Detected
        if (data.face_detected === false) {
            this.resultContainer.innerHTML = `
                <div style="background-color: #fffbeb; border: 2px solid #f59e0b; border-radius: 8px; padding: 20px;">
                    <div style="display: flex; align-items: flex-start; gap: 14px;">
                        <span style="font-size: 38px;">👤</span>
                        <div>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <h3 style="font-size: 16px; font-weight: 700; color: #b45309; margin: 0;">NO FACE DETECTED</h3>
                                <span class="badge badge-critical">CAMERA SCAN EMPTY</span>
                            </div>
                            <p style="font-size: 12.5px; color: #92400e; margin-top: 6px; line-height: 1.5;">
                                The optical camera does not detect a worker's face in view.<br>
                                • Please position your face directly inside the target reticle.<br>
                                • Ensure ambient lighting is sufficient.
                            </p>
                        </div>
                    </div>
                </div>
            `;
            return;
        }

        // CASE 2: No Registered Workers in System
        if (data.status && data.status.includes('NO REGISTERED BIOMETRIC DATA')) {
            this.resultContainer.innerHTML = `
                <div style="background-color: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 20px;">
                    <div style="display: flex; align-items: flex-start; gap: 14px;">
                        <span style="font-size: 38px;">🛡️</span>
                        <div>
                            <div style="display: flex; align-items: center; gap: 10px;">
                                <h3 style="font-size: 16px; font-weight: 700; color: #b91c1c; margin: 0;">NO REGISTERED BIOMETRIC PROFILES</h3>
                                <span class="badge badge-critical">ACCESS DENIED</span>
                            </div>
                            <p style="font-size: 12.5px; color: #991b1b; margin-top: 8px; line-height: 1.5;">
                                All previous registration data has been cleared. There are currently no enrolled workers in the biometric database.<br><br>
                                <strong>Action Required:</strong> Click the <strong>Register Face Biometrics</strong> button in the top navigation to register your account and face.
                            </p>
                            <button type="button" class="btn btn-primary btn-sm" style="margin-top: 10px;" onclick="document.getElementById('authPortalModal').classList.add('show'); switchAuthTab('register'); if(window.startRegCamera) startRegCamera();">
                                ➕ Register Your Face Now
                            </button>
                        </div>
                    </div>
                </div>
            `;
            return;
        }

        // CASE 3: Unregistered Worker (Face detected but does not match any registered worker)
        if (!data.biometric_matched || !data.worker || data.worker.id === 'UNREGISTERED') {
            const issues = data.issues_detected || [];
            this.resultContainer.innerHTML = `
                <div style="background-color: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 20px;">
                    <div style="display: flex; align-items: flex-start; gap: 14px;">
                        <span style="font-size: 38px;">🛑</span>
                        <div style="flex: 1;">
                            <div style="display: flex; align-items: center; justify-content: space-between;">
                                <h3 style="font-size: 16px; font-weight: 700; color: #b91c1c; margin: 0;">UNREGISTERED WORKER — ACCESS DENIED</h3>
                                <span class="badge badge-critical">GATE LOCKED</span>
                            </div>
                            <p style="font-size: 12.5px; color: #991b1b; margin-top: 6px; line-height: 1.5;">
                                Biometric verification failed: The detected face does not match any enrolled personnel in the OIL authorized personnel registry.
                            </p>
                            <ul style="margin-top: 8px; margin-left: 20px; font-size: 12px; color: #b91c1c;">
                                ${issues.map(i => `<li><strong>${i}</strong></li>`).join('')}
                            </ul>
                            <div style="margin-top: 14px; display: flex; gap: 10px;">
                                <button type="button" class="btn btn-primary btn-sm" onclick="document.getElementById('registerModal').classList.add('active'); if(window.startRegCamera) startRegCamera();">
                                    ➕ Self-Register Face Biometrics
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
            return;
        }

        // CASE 4: Biometric Matched Registered Worker
        const w = data.worker;
        const granted = data.access_granted;
        const issues = data.issues_detected || data.missing_precautions || [];

        let statusBannerHtml = '';
        if (granted) {
            statusBannerHtml = `
                <div style="background-color: #f0fdf4; border: 2px solid #10b981; border-radius: 6px; padding: 12px 16px; margin-top: 14px; display: flex; align-items: center; gap: 12px;">
                    <span style="font-size: 26px;">✅</span>
                    <div>
                        <strong style="color: #15803d; font-size: 13.5px;">ACCESS GRANTED — ALL SAFETY CHECKS PASSED</strong>
                        <div style="font-size: 12px; color: #166534; margin-top: 2px;">
                            Biometric ID verified for <strong>${w.name}</strong> (${w.id}). All required PPE items and certifications verified. Turnstile unlocked.
                        </div>
                    </div>
                </div>
            `;
        } else {
            statusBannerHtml = `
                <div style="background-color: #fef2f2; border: 2px solid #ef4444; border-radius: 8px; padding: 14px 16px; margin-top: 14px;">
                    <div style="display: flex; align-items: center; gap: 8px; margin-bottom: 8px;">
                        <span style="font-size: 22px;">🛑</span>
                        <div style="font-weight: 700; color: #b91c1c; font-size: 13.5px;">
                            ${issues.length} SAFETY ISSUE(S) DETECTED — GATE ACCESS DENIED:
                        </div>
                    </div>
                    <ul style="margin-left: 24px; font-size: 12.5px; color: #991b1b; line-height: 1.6;">
                        ${issues.map(m => `<li><strong>${m}</strong></li>`).join('')}
                    </ul>
                    <div style="margin-top: 12px; display: flex; gap: 10px;">
                        <button id="gateOverrideBtnAction" class="btn btn-warning btn-sm">
                            ✓ Equip Gear / Mark Precautions Completed &amp; Clear Gate
                        </button>
                    </div>
                </div>
            `;
        }

        const ppeChecklist = (data.ppe_boxes || []).map(b => ({
            item: b.item,
            detected: b.detected,
            standard: b.standard
        }));

        const ppeChecklistHtml = ppeChecklist.map(p => `
            <div style="display: flex; align-items: center; justify-content: space-between; padding: 6px 0; border-bottom: 1px solid #f1f5f9; font-size: 12.5px;">
                <span><strong>${p.item}</strong> <small style="color: #64748b;">(${p.standard})</small></span>
                <span class="badge ${p.detected ? 'badge-low' : 'badge-critical'}">${p.detected ? '✓ Detected' : '✗ Missing'}</span>
            </div>
        `).join('');

        const biometricBadge = data.match_score > 0 ? 
            `<span class="badge badge-low" style="margin-left: 6px;">Biometric Match: ${data.match_score}%</span>` : '';

        this.resultContainer.innerHTML = `
            <div style="margin-bottom: 16px; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px;">
                <div style="display: flex; align-items: center; justify-content: space-between;">
                    <div>
                        <h3 style="font-size: 17px; font-weight: 700; color: #0f2744;">
                            ${w.name} <small style="color: #64748b;">(${w.id})</small>
                        </h3>
                        <p style="font-size: 12px; color: #64748b; margin-top: 2px;">
                            ${w.role} • ${w.department}
                            ${biometricBadge}
                        </p>
                    </div>
                    <div>
                        <span class="badge ${granted ? 'badge-low' : 'badge-critical'}" style="font-size: 13px; padding: 6px 14px; letter-spacing: 0.5px;">
                            ${data.status}
                        </span>
                    </div>
                </div>
            </div>

            <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin-bottom: 14px;">
                <div style="background: #f8fafc; padding: 10px 12px; border-radius: 6px; font-size: 12px;">
                    <span style="color: #64748b;">Safety Training:</span>
                    <strong style="color: ${w.training_valid ? '#047857' : '#b91c1c'}; float: right;">
                        ${w.training_valid ? '✓ VALID' : '✗ EXPIRED'}
                    </strong>
                </div>
                <div style="background: #f8fafc; padding: 10px 12px; border-radius: 6px; font-size: 12px;">
                    <span style="color: #64748b;">Medical Certification:</span>
                    <strong style="color: ${w.cert_valid ? '#047857' : '#b91c1c'}; float: right;">
                        ${w.cert_valid ? '✓ ACTIVE' : '✗ OVERDUE'}
                    </strong>
                </div>
            </div>

            <div style="margin-top: 12px;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #475569; margin-bottom: 6px;">
                    PPE Readiness Verification:
                </div>
                ${ppeChecklistHtml}
            </div>

            ${statusBannerHtml}
        `;

        const actionBtn = document.getElementById('gateOverrideBtnAction');
        if (actionBtn) {
            actionBtn.addEventListener('click', () => this.markPrecautionsCompleted(w.id));
        }
    }

    async markPrecautionsCompleted(workerId) {
        try {
            const res = await fetch(`/api/safety_gate/override/${workerId}`, { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) {
                    window.showToast(`Precautions completed for ${data.worker.name}. Access Granted!`, 'success');
                }
                this.runScan();
            }
        } catch (e) {
            console.error('Error marking precautions completed:', e);
        }
    }
}

// Global Clear Registration Data Helper
window.clearAllBiometricData = async function() {
    if (!confirm("Are you sure you want to clear all registered biometric face samples and reset the database? You will need to register again.")) {
        return;
    }

    try {
        const res = await fetch('/api/auth/clear_all_registrations', { method: 'POST' });
        const data = await res.json();
        if (data.success) {
            if (window.showToast) {
                window.showToast("All registered data and models successfully cleared!", "success");
            }
            // Reset gate result container
            const container = document.getElementById('gateResultContainer');
            if (container) {
                container.innerHTML = `
                    <div style="text-align: center; padding: 60px 20px; color: #94a3b8;">
                        <div style="font-size: 44px; margin-bottom: 12px;">🛡️</div>
                        <h3 style="font-size: 15px; color: #334155; margin-bottom: 6px;">Registration Data Cleared</h3>
                        <p style="font-size: 13px; max-width: 320px; margin: 0 auto; line-height: 1.5;">
                            All registered records cleared. Register your face to test live recognition.
                        </p>
                    </div>
                `;
            }
        } else {
            alert(data.error || "Failed to clear data.");
        }
    } catch (e) {
        console.error("Clear biometrics error:", e);
        alert("Server error while clearing biometrics.");
    }
};

window.SafetyGate = SafetyGate;
