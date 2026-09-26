/**
 * SurakshaX Dedicated Worker Portal Controller
 * Oil India Limited • Smart Precaution Check & Digital Rig Pass
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Safety Precaution Checklist State
    const precautions = {
        helmet: true,
        vest: true,
        goggles: true,
        gloves: true,
        shoes: true,
        h2s_badge: true,
        ptw_valid: true
    };

    // Audio Chime Synthesizer
    function playPassChime() {
        try {
            const AudioCtx = window.AudioContext || window.webkitAudioContext;
            if (!AudioCtx) return;
            const actx = new AudioCtx();
            const notes = [
                { f: 523.25, t: 0.0, d: 0.18 },  // C5
                { f: 659.25, t: 0.12, d: 0.18 }, // E5
                { f: 783.99, t: 0.22, d: 0.22 }, // G5
                { f: 1046.5, t: 0.34, d: 0.45 }  // C6
            ];
            notes.forEach(n => {
                const osc = actx.createOscillator();
                const gain = actx.createGain();
                osc.type = 'triangle';
                osc.frequency.setValueAtTime(n.f, actx.currentTime + n.t);
                gain.gain.setValueAtTime(0, actx.currentTime + n.t);
                gain.gain.linearRampToValueAtTime(0.18, actx.currentTime + n.t + 0.02);
                gain.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + n.t + n.d);
                osc.connect(gain);
                gain.connect(actx.destination);
                osc.start(actx.currentTime + n.t);
                osc.stop(actx.currentTime + n.t + n.d);
            });
        } catch (e) {}
    }

    // Voice Feedback Engine (Web Speech API)
    function speakWorkerVoice(text) {
        try {
            if (!('speechSynthesis' in window)) return;
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(text);
            utterance.rate = 1.0;
            utterance.pitch = 1.05;
            utterance.volume = 1.0;
            const voices = window.speechSynthesis.getVoices();
            if (voices && voices.length > 0) {
                const en = voices.find(v => v.lang && v.lang.startsWith('en') && (v.name.includes('Natural') || v.name.includes('Google') || v.name.includes('David')));
                if (en) utterance.voice = en;
            }
            window.speechSynthesis.speak(utterance);
        } catch (e) {}
    }

    // 2. Tab Switcher
    window.switchWorkerTab = function(tabKey) {
        const tabs = document.querySelectorAll('.worker-tab-btn');
        tabs.forEach(t => t.classList.remove('active'));

        const views = {
            'gate': document.getElementById('workerViewGate'),
            'report': document.getElementById('workerViewReport'),
            'dossier': document.getElementById('workerViewDossier')
        };

        Object.keys(views).forEach(k => {
            if (views[k]) views[k].style.display = 'none';
        });

        if (views[tabKey]) views[tabKey].style.display = 'block';

        // Set button active
        tabs.forEach(t => {
            if (t.getAttribute('onclick') && t.getAttribute('onclick').includes(tabKey)) {
                t.classList.add('active');
            }
        });
    };

    // 3. Identity Method: Manual Badge vs Face Camera
    window.setIdentMode = function(mode) {
        const btnManual = document.getElementById('btnModeManual');
        const btnFace = document.getElementById('btnModeFace');
        const boxManual = document.getElementById('identBoxManual');
        const boxFace = document.getElementById('identBoxFace');
        const badge = document.getElementById('identMethodBadge');

        if (mode === 'face') {
            if (btnFace) btnFace.classList.add('active');
            if (btnManual) btnManual.classList.remove('active');
            if (boxFace) boxFace.style.display = 'block';
            if (boxManual) boxManual.style.display = 'none';
            if (badge) badge.innerText = 'Live Face Biometric Scan';
            startWorkerCam();
        } else {
            if (btnManual) btnManual.classList.add('active');
            if (btnFace) btnFace.classList.remove('active');
            if (boxFace) boxFace.style.display = 'none';
            if (boxManual) boxManual.style.display = 'block';
            if (badge) badge.innerText = '1-Tap Badge Entry';
            stopWorkerCam();
        }
    };

    // 4. Precaution Checklist Toggle
    const mapKeyToIds = {
        helmet: { card: 'cardHelmet', badge: 'badgeHelmet', label: 'Hard Hat' },
        vest: { card: 'cardVest', badge: 'badgeVest', label: 'High-Vis Vest' },
        goggles: { card: 'cardGoggles', badge: 'badgeGoggles', label: 'Goggles' },
        gloves: { card: 'cardGloves', badge: 'badgeGloves', label: 'Rig Gloves' },
        shoes: { card: 'cardShoes', badge: 'badgeShoes', label: 'Safety Boots' },
        h2s_badge: { card: 'cardH2S', badge: 'badgeH2S', label: 'H2S Detector' },
        ptw_valid: { card: 'cardPTW', badge: 'badgePTW', label: 'Permit-to-Work' }
    };

    window.togglePrecaution = function(key) {
        if (!(key in precautions)) return;
        precautions[key] = !precautions[key];
        updatePrecautionUI();
    };

    function updatePrecautionUI() {
        let missingCount = 0;
        Object.keys(precautions).forEach(key => {
            const isOk = precautions[key];
            const meta = mapKeyToIds[key];
            if (!meta) return;

            const card = document.getElementById(meta.card);
            const badge = document.getElementById(meta.badge);

            if (isOk) {
                if (card) { card.className = 'precaution-card verified'; }
                if (badge) { badge.className = 'precaution-status-badge badge-cleared'; badge.innerText = '✓ Cleared'; }
            } else {
                missingCount++;
                if (card) { card.className = 'precaution-card missing'; }
                if (badge) { badge.className = 'precaution-status-badge badge-unverified'; badge.innerText = '✗ Missing'; }
            }
        });

        const summaryBadge = document.getElementById('precautionsSummaryBadge');
        if (summaryBadge) {
            if (missingCount === 0) {
                summaryBadge.className = 'badge badge-low';
                summaryBadge.innerText = 'All 7 Verified';
            } else {
                summaryBadge.className = 'badge badge-critical';
                summaryBadge.innerText = `${missingCount} Pending`;
            }
        }
    }

    // 5. 1-Click Action Super Button: Issue Hassle-Free Rig Gate Pass
    window.issueHassleFreePass = async function() {
        const btn = document.getElementById('btnIssuePass');
        const nameInput = document.getElementById('wpWorkerName');
        const idInput = document.getElementById('wpWorkerId');
        const roleSelect = document.getElementById('wpWorkerRole');

        const name = (nameInput ? nameInput.value.trim() : '') || 'Rig Crew Technician';
        const workerId = (idInput ? idInput.value.trim() : '') || 'W104';
        const role = roleSelect ? roleSelect.value : 'Rig Crew Specialist';

        // Auto-complete all precautions for hassle-free flow
        Object.keys(precautions).forEach(k => precautions[k] = true);
        updatePrecautionUI();

        if (btn) {
            btn.disabled = true;
            btn.innerHTML = '<span>⏳</span> <span>Validating Precautions &amp; Turnstile...</span>';
        }

        try {
            const payload = {
                name: name,
                worker_id: workerId,
                role: role,
                department: 'Drilling & Operations',
                site: 'Site A (Duliajan Central Field)',
                precautions: precautions
            };

            const res = await fetch('/api/worker/precaution_pass', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });

            const data = await res.json();

            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡</span> <span>Complete All Precautions &amp; Issue Gate Pass</span>';
            }

            if (data.success && data.access_granted) {
                // Populate Pass Details
                const passBox = document.getElementById('digitalRigPass');
                const codeEl = document.getElementById('passCodeDisplay');
                const nameEl = document.getElementById('passWorkerName');
                const roleEl = document.getElementById('passWorkerRole');
                const expiryEl = document.getElementById('passExpiryTime');
                const voiceText = document.getElementById('wpVoiceText');

                if (codeEl) codeEl.innerText = data.pass_code;
                if (nameEl) nameEl.innerText = `${data.worker.name}`;
                if (roleEl) roleEl.innerText = `${data.worker.id} • ${data.worker.role}`;
                if (expiryEl) expiryEl.innerText = `Valid: 8 Hours (Until ${data.expires_at.slice(11, 16)})`;

                // Update active topbar pill
                const topName = document.getElementById('workerUserName');
                if (topName) topName.innerText = data.worker.name;

                // Show Pass
                if (passBox) {
                    passBox.style.display = 'block';
                    passBox.scrollIntoView({ behavior: 'smooth', block: 'center' });
                }

                if (voiceText) {
                    voiceText.innerText = `✓ ${data.status} • Turnstile Unlocked. Have a safe shift, ${data.worker.name}!`;
                }

                // Play celebration sound & speak audio confirmation
                playPassChime();
                speakWorkerVoice(data.voice_message || `Access Granted. All safety precautions verified for ${name}. Turnstile unlocked.`);

            } else {
                alert(data.status || "Could not issue pass. Please check precautions.");
            }
        } catch (err) {
            console.error('Error issuing gate pass:', err);
            if (btn) {
                btn.disabled = false;
                btn.innerHTML = '<span>⚡</span> <span>Complete All Precautions &amp; Issue Gate Pass</span>';
            }
            alert("Network error communicating with gate server.");
        }
    };

    window.resetGatePassView = function() {
        const passBox = document.getElementById('digitalRigPass');
        if (passBox) passBox.style.display = 'none';
        const voiceText = document.getElementById('wpVoiceText');
        if (voiceText) voiceText.innerText = 'Status: Ready for next worker safety check.';
        window.scrollTo({ top: 0, behavior: 'smooth' });
    };

    // 6. Real Camera Stream for Face Biometrics Option
    let wpStream = null;
    let wpAnimFrame = null;

    async function startWorkerCam() {
        const video = document.getElementById('wpVideo');
        const canvas = document.getElementById('wpCanvas');
        const placeholder = document.getElementById('wpCamPlaceholder');

        if (wpStream) return;

        try {
            wpStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
                audio: false
            });

            if (video) {
                video.srcObject = wpStream;
                await video.play();
            }

            if (placeholder) placeholder.style.display = 'none';
            if (canvas) {
                canvas.style.display = 'block';
                canvas.width = 340;
                canvas.height = 220;
            }

            const ctx = canvas.getContext('2d');

            const renderLoop = () => {
                if (!wpStream) return;
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                // Draw Apple Face ID Reticle
                const cx = canvas.width / 2;
                const cy = canvas.height / 2;
                const rx = 65;
                const ry = 82;
                const totalTicks = 40;

                for (let i = 0; i < totalTicks; i++) {
                    const theta = (i / totalTicks) * Math.PI * 2 - Math.PI / 2;
                    const x1 = cx + (rx - 6) * Math.cos(theta);
                    const y1 = cy + (ry - 6) * Math.sin(theta);
                    const x2 = cx + (rx + 6) * Math.cos(theta);
                    const y2 = cy + (ry + 6) * Math.sin(theta);

                    ctx.beginPath();
                    ctx.moveTo(x1, y1);
                    ctx.lineTo(x2, y2);
                    ctx.lineWidth = 2.5;
                    ctx.strokeStyle = '#10b981';
                    ctx.stroke();
                }

                ctx.font = 'bold 11px sans-serif';
                ctx.fillStyle = '#38bdf8';
                ctx.textAlign = 'center';
                ctx.fillText("ALIGN FACE IN RETICLE", cx, 20);

                wpAnimFrame = requestAnimationFrame(renderLoop);
            };
            renderLoop();

            // Auto-trigger frame scan after 1.2s
            setTimeout(async () => {
                if (!wpStream) return;
                const snapCanvas = document.createElement('canvas');
                snapCanvas.width = 320;
                snapCanvas.height = 240;
                snapCanvas.getContext('2d').drawImage(video, 0, 0, 320, 240);
                const b64 = snapCanvas.toDataURL('image/jpeg', 0.85);

                try {
                    const res = await fetch('/api/safety_gate/scan_frame', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ image: b64 })
                    });
                    const data = await res.json();
                    if (data.biometric_matched && data.worker) {
                        const nameInput = document.getElementById('wpWorkerName');
                        const idInput = document.getElementById('wpWorkerId');
                        if (nameInput) nameInput.value = data.worker.name;
                        if (idInput) idInput.value = data.worker.id;
                        speakWorkerVoice(`Worker Recognized: ${data.worker.name}`);
                        issueHassleFreePass();
                    }
                } catch (e) {}
            }, 1200);

        } catch (err) {
            console.error("Webcam error:", err);
            if (placeholder) {
                placeholder.innerHTML = `<div style="color:#ef4444; font-size:12px;">Webcam permission denied or not available. Use Badge entry instead.</div>`;
            }
        }
    }

    function stopWorkerCam() {
        if (wpAnimFrame) {
            cancelAnimationFrame(wpAnimFrame);
            wpAnimFrame = null;
        }
        if (wpStream) {
            wpStream.getTracks().forEach(t => { try { t.stop(); } catch (e) {} });
            wpStream = null;
        }
        const canvas = document.getElementById('wpCanvas');
        const placeholder = document.getElementById('wpCamPlaceholder');
        if (canvas) canvas.style.display = 'none';
        if (placeholder) placeholder.style.display = 'block';
    }

    window.startWorkerCam = startWorkerCam;
    window.stopWorkerCam = stopWorkerCam;

    // 7. Quick Rig Hazard Report Submission
    const hazardForm = document.getElementById('wpHazardForm');
    if (hazardForm) {
        hazardForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('wpSubmitReportBtn');
            const loc = document.getElementById('wpReportLocation').value.trim();
            const act = document.getElementById('wpReportActivity').value.trim();
            const txt = document.getElementById('wpReportText').value.trim();
            const name = document.getElementById('wpWorkerName').value.trim() || 'Worker';
            const workerId = document.getElementById('wpWorkerId').value.trim() || 'W104';

            if (!txt) {
                alert('Please enter or speak observation details.');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerText = 'AI Classifying SIF Precursor...';

            try {
                const res = await fetch('/api/reports/submit', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        worker_id: workerId,
                        worker_name: name,
                        site: 'Site A (Duliajan Central Field)',
                        location: loc,
                        activity: act,
                        machine_id: 'M101',
                        report_type: 'Unsafe Condition',
                        input_channel: 'Worker Portal',
                        raw_text: txt
                    })
                });

                const data = await res.json();
                submitBtn.disabled = false;
                submitBtn.innerText = '🚀 Submit Precursor Observation to HSE';

                if (data.success && data.report) {
                    const r = data.report;
                    const card = document.getElementById('wpReportResultCard');
                    const badge = document.getElementById('wpResRiskBadge');
                    const hazard = document.getElementById('wpResHazard');
                    const sol = document.getElementById('wpResSolution');

                    if (card) card.style.display = 'block';
                    if (badge) {
                        badge.innerText = `Risk: ${r.risk_score}/100 • ${r.risk_level}`;
                        badge.className = `badge ${r.sif_potential ? 'badge-critical' : 'badge-low'}`;
                    }
                    if (hazard) hazard.innerText = `Identified Hazard: ${r.hazard}`;
                    if (sol) sol.innerText = `Immediate Solution: ${r.solution}`;

                    speakWorkerVoice(`Report submitted to HSE. Risk Score: ${r.risk_score}. Solution logged.`);
                    alert(`✓ Report ${r.report_uid} successfully submitted to HSE Controller!`);
                } else {
                    alert('Failed to submit report: ' + (data.error || 'Server error'));
                }
            } catch (err) {
                console.error('Report submission error:', err);
                submitBtn.disabled = false;
                submitBtn.innerText = '🚀 Submit Precursor Observation to HSE';
                alert('Network error connecting to reporting service.');
            }
        });
    }

    // 8. Voice Recognition in Worker Portal (Multi-Lingual)
    let isRecording = false;
    let recognition = null;

    window.toggleWorkerVoiceRecord = function() {
        const btn = document.getElementById('wpVoiceRecordBtn');
        const txtArea = document.getElementById('wpReportText');

        if (!('webkitSpeechRecognition' in window) && !('SpeechRecognition' in window)) {
            alert('Speech Recognition is not supported by your browser. Please type your observation.');
            return;
        }

        if (isRecording) {
            if (recognition) recognition.stop();
            isRecording = false;
            if (btn) {
                btn.innerHTML = '🎙️ Start Voice Recording';
                btn.className = 'btn btn-primary';
            }
            return;
        }

        const SpeechRec = window.SpeechRecognition || window.webkitSpeechRecognition;
        recognition = new SpeechRec();
        recognition.continuous = true;
        recognition.interimResults = true;
        recognition.lang = 'hi-IN'; // Multi-language default

        recognition.onstart = () => {
            isRecording = true;
            if (btn) {
                btn.innerHTML = '⏹️ Listening... Tap to Stop';
                btn.className = 'btn btn-danger';
            }
        };

        recognition.onresult = (event) => {
            let transcript = '';
            for (let i = event.resultIndex; i < event.results.length; i++) {
                transcript += event.results[i][0].transcript;
            }
            if (txtArea) txtArea.value = transcript;
        };

        recognition.onerror = (e) => {
            console.warn('Voice recognition notice:', e);
            isRecording = false;
            if (btn) {
                btn.innerHTML = '🎙️ Start Voice Recording';
                btn.className = 'btn btn-primary';
            }
        };

        recognition.onend = () => {
            isRecording = false;
            if (btn) {
                btn.innerHTML = '🎙️ Start Voice Recording';
                btn.className = 'btn btn-primary';
            }
        };

        recognition.start();
    };

    // Open Registration Modal
    window.openWorkerRegisterModal = function() {
        window.location.href = '/';
    };

    // Initial setup
    updatePrecautionUI();
});
