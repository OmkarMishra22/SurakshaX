/**
 * SIFGuard Master Application Controller
 * Connects all UI components, roles, workflows, APIs, and real-time HSE updates.
 */

document.addEventListener('DOMContentLoaded', () => {
    // 1. Initialize Subsystems
    const offlineManager = new SIFGuardOffline();
    const voiceManager = new SIFGuardVoice({
        micBtnId: 'voiceMicBtn',
        statusId: 'voiceTranscriptStatus',
        targetInputId: 'reportDescription'
    });
    const safetyGate = new SafetyGate();
    const safetyCharts = new SafetyCharts();

    window.offlineManager = offlineManager;
    window.voiceManager = voiceManager;
    window.safetyGate = safetyGate;
    window.safetyCharts = safetyCharts;

    // Safety Gate Camera Lifecycle Manager:
    // Starts the camera only when the user is actively on the Safety Gate employee scanner page.
    // Immediately shuts down camera and releases hardware if user leaves, switches tab, or minimizes page.
    function syncSafetyGateCameraState() {
        if (!window.safetyGate) return;

        const activeTab = document.querySelector('.page-tab.active');
        const isOnGateTab = activeTab && (activeTab.id === 'tab-safety-gate' || activeTab.getAttribute('id') === 'tab-safety-gate');

        const secEmp = document.getElementById('gateSubSectionEmployee');
        const isEmployeeSubTab = secEmp ? (secEmp.style.display !== 'none') : true;

        const authModal = document.getElementById('authPortalModal');
        const isAuthModalOpen = authModal && authModal.classList.contains('show');

        const isDocumentVisible = !document.hidden;

        const shouldCameraBeActive = isOnGateTab && isEmployeeSubTab && !isAuthModalOpen && isDocumentVisible;

        if (shouldCameraBeActive) {
            if (!window.safetyGate.isRealCameraActive && !window.safetyGate.userManuallyStopped) {
                window.safetyGate.startRealCamera(false);
            }
        } else {
            if (window.safetyGate.isRealCameraActive || window.safetyGate.isStartingCamera) {
                window.safetyGate.stopRealCamera();
            }
        }
    }
    window.syncSafetyGateCameraState = syncSafetyGateCameraState;

    // 2. State
    let currentUser = null;
    try {
        const saved = localStorage.getItem('surakshax_user');
        if (saved) {
            currentUser = JSON.parse(saved);
        }
    } catch (e) {}
    let currentReportUnderReview = null;

    // Toast helper
    window.showToast = function(message, type = 'info') {
        const toast = document.createElement('div');
        toast.style.position = 'fixed';
        toast.style.bottom = '24px';
        toast.style.right = '24px';
        toast.style.padding = '12px 20px';
        toast.style.borderRadius = '6px';
        toast.style.color = '#ffffff';
        toast.style.fontSize = '13px';
        toast.style.fontWeight = '600';
        toast.style.zIndex = '9999';
        toast.style.boxShadow = '0 10px 15px -3px rgba(0,0,0,0.2)';
        toast.style.transition = 'all 0.3s ease';

        if (type === 'success') toast.style.backgroundColor = '#10b981';
        else if (type === 'danger') toast.style.backgroundColor = '#ef4444';
        else if (type === 'warning') toast.style.backgroundColor = '#f59e0b';
        else toast.style.backgroundColor = '#1e40af';

        toast.innerText = message;
        document.body.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 3500);
    };

    // 3. Navigation & Tab Switching
    const navLinks = document.querySelectorAll('.nav-link[data-tab]');
    const pageTabs = document.querySelectorAll('.page-tab');

    function switchTab(tabId) {
        navLinks.forEach(link => {
            if (link.getAttribute('data-tab') === tabId) {
                link.classList.add('active');
            } else {
                link.classList.remove('active');
            }
        });

        pageTabs.forEach(tab => {
            if (tab.id === `tab-${tabId}`) {
                tab.classList.add('active');
            } else {
                tab.classList.remove('active');
            }
        });

        // Trigger contextual refresh
        if (tabId === 'dashboard') {
            loadDashboard();
            safetyCharts.initAll();
            loadSiteConditions();
        } else if (tabId === 'safety-gate') {
            loadSiteConditions();
        } else if (tabId === 'priority') {
            loadPriorityList();
        } else if (tabId === 'intervention') {
            loadInterventions();
        } else if (tabId === 'machines') {
            loadMachines();
        } else if (tabId === 'site-conditions') {
            loadSiteConditions();
        } else if (tabId === 'hse-review') {
            loadHSEReviewQueue();
        } else if (tabId === 'reports') {
            loadReportsHistory();
        } else if (tabId === 'analytics') {
            safetyCharts.initAll();
        } else if (tabId === 'feedback') {
            loadLearningStats();
        } else if (tabId === 'repair-review') {
            loadRepairReviews();
        } else if (tabId === 'profile') {
            loadUserProfile();
        }

        // Auto-manage Safety Gate webcam stream when entering or leaving pages
        if (window.safetyGate) {
            window.safetyGate.userManuallyStopped = false;
        }
        syncSafetyGateCameraState();
    }
    window.switchTab = switchTab;

    // Attach click handler to topbar profile badge (Image 2)
    const topbarProfileBtn = document.getElementById('topbarUserProfileBtn');
    if (topbarProfileBtn) {
        topbarProfileBtn.addEventListener('click', (e) => {
            e.preventDefault();
            switchTab('profile');
        });
    }

    navLinks.forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const tabId = link.getAttribute('data-tab');
            switchTab(tabId);
        });
    });

    // 4. User Display & Two-Menu Portal Switcher (Worker Direct vs HSE/Admin Sign-In)
    function updatePortalMenuHighlight(mode) {
        const sbWorker = document.getElementById('sidebarMenuWorkerBtn');
        const sbHse = document.getElementById('sidebarMenuHseBtn');
        const tbWorker = document.getElementById('topbarMenuWorkerBtn');
        const tbHse = document.getElementById('topbarMenuHseBtn');

        if (mode === 'hse') {
            if (sbWorker) {
                sbWorker.style.background = 'transparent';
                sbWorker.style.color = '#cbd5e1';
                sbWorker.style.boxShadow = 'none';
            }
            if (sbHse) {
                sbHse.style.background = '#0284c7';
                sbHse.style.color = '#ffffff';
                sbHse.style.boxShadow = '0 2px 6px rgba(2, 132, 199, 0.35)';
            }
            if (tbWorker) {
                tbWorker.style.background = 'transparent';
                tbWorker.style.color = '#334155';
                tbWorker.style.boxShadow = 'none';
            }
            if (tbHse) {
                tbHse.style.background = '#0284c7';
                tbHse.style.color = '#ffffff';
                tbHse.style.boxShadow = '0 1px 3px rgba(0,0,0,0.12)';
            }
        } else {
            if (sbWorker) {
                sbWorker.style.background = '#10b981';
                sbWorker.style.color = '#ffffff';
                sbWorker.style.boxShadow = '0 2px 6px rgba(16, 185, 129, 0.35)';
            }
            if (sbHse) {
                sbHse.style.background = 'transparent';
                sbHse.style.color = '#cbd5e1';
                sbHse.style.boxShadow = 'none';
            }
            if (tbWorker) {
                tbWorker.style.background = '#10b981';
                tbWorker.style.color = '#ffffff';
                tbWorker.style.boxShadow = '0 1px 3px rgba(0,0,0,0.12)';
            }
            if (tbHse) {
                tbHse.style.background = 'transparent';
                tbHse.style.color = '#334155';
                tbHse.style.boxShadow = 'none';
            }
        }
    }

    window.openRoleGatePopup = function() {
        const authModal = document.getElementById('authPortalModal');
        const viewRoleGate = document.getElementById('authViewRoleGate');
        const viewSignIn = document.getElementById('authViewSignIn');
        const viewRegister = document.getElementById('authViewRegister');
        const viewSuccess = document.getElementById('authViewSuccess');
        const tabsRow = document.getElementById('authTabsRow');
        const header = document.getElementById('authPortalHeader');
        const titleEl = document.getElementById('authPortalTitleText');
        const subEl = document.getElementById('authPortalSubText');

        if (header) header.style.display = 'block';
        if (titleEl) titleEl.innerText = 'Welcome to SurakshaX Portal';
        if (subEl) subEl.innerText = 'Select your access type below to continue.';
        if (viewRoleGate) viewRoleGate.style.display = 'block';
        if (tabsRow) tabsRow.style.display = 'none';
        if (viewSignIn) viewSignIn.style.display = 'none';
        if (viewRegister) viewRegister.style.display = 'none';
        if (viewSuccess) viewSuccess.style.display = 'none';
        if (authModal) authModal.classList.add('show');

        if (typeof syncSafetyGateCameraState === 'function') {
            syncSafetyGateCameraState();
        }
    };

    window.chooseOtherRoleAndSignIn = function(roleLabel, roleKey) {
        const noticeEl = document.getElementById('loginContextNotice');
        const roleSelect = document.getElementById('portalRoleSelect');
        if (roleSelect && roleKey) {
            roleSelect.value = roleKey;
        }
        window.openAuthPortal('signin', roleKey || 'hse');
        if (noticeEl) {
            noticeEl.innerHTML = `🛡️ <strong>Selected Role: ${roleLabel}</strong> — Please sign in with your credentials below (or click <em>New Face Registration</em> above).`;
            noticeEl.style.display = 'block';
        }
    };

    window.openAuthPortal = function(tab = 'signin', context = '') {
        const authModal = document.getElementById('authPortalModal');
        const viewRoleGate = document.getElementById('authViewRoleGate');
        const noticeEl = document.getElementById('loginContextNotice');
        const roleSelect = document.getElementById('portalRoleSelect');
        const titleEl = document.getElementById('authPortalTitleText');
        const subEl = document.getElementById('authPortalSubText');

        if (viewRoleGate) viewRoleGate.style.display = 'none';
        if (titleEl) titleEl.innerText = 'SurakshaX Identity & Access';
        if (subEl) subEl.innerText = 'Sign in with your credentials or enroll Face ID biometrics.';

        if (noticeEl) {
            if (context) {
                noticeEl.innerHTML = '🛡️ <strong>HSE / Admin Portal Protected:</strong> Please sign in with your official credentials to continue.';
                noticeEl.style.display = 'block';
            } else {
                noticeEl.style.display = 'none';
            }
        }
        if (context && roleSelect) {
            roleSelect.value = context;
        }
        if (authModal) {
            authModal.classList.add('show');
        }
        if (typeof window.switchAuthTab === 'function') {
            window.switchAuthTab(tab);
        }
        if (typeof syncSafetyGateCameraState === 'function') {
            syncSafetyGateCameraState();
        }
    };

    window.selectPortalMenu = function(mode) {
        const workerSections = document.querySelectorAll('.role-worker-section');
        const workerItems = document.querySelectorAll('.role-worker-item');
        const hseSections = document.querySelectorAll('.role-hse-section');
        const hseItems = document.querySelectorAll('.role-hse-item');

        if (mode === 'worker') {
            // Simple Worker Safety Portal — No Sign-In Required
            if (typeof window.closeAuthModal === 'function') {
                window.closeAuthModal();
            } else {
                const authModal = document.getElementById('authPortalModal');
                if (authModal) authModal.classList.remove('show');
            }
            updatePortalMenuHighlight('worker');
            workerSections.forEach(el => el.style.display = 'block');
            workerItems.forEach(el => el.style.display = 'block');
            hseSections.forEach(el => el.style.display = 'none');
            hseItems.forEach(el => el.style.display = 'none');

            const activeTab = document.querySelector('.page-tab.active');
            const workerTabIds = ['tab-safety-gate', 'tab-submit-report', 'tab-repair-review', 'tab-profile'];
            if (!activeTab || !workerTabIds.includes(activeTab.id)) {
                switchTab('safety-gate');
            } else {
                syncSafetyGateCameraState();
            }
            return;
        }

        if (mode === 'hse') {
            // Check if already signed in as HSE Officer or Admin
            const roleUpper = (currentUser && currentUser.is_logged_in !== false && currentUser.role) ? currentUser.role.toUpperCase() : '';
            const isHseOrAdmin = roleUpper.includes('HSE') || roleUpper.includes('ADMIN');

            if (isHseOrAdmin) {
                if (typeof window.closeAuthModal === 'function') {
                    window.closeAuthModal();
                }
                updatePortalMenuHighlight('hse');
                workerSections.forEach(el => el.style.display = 'none');
                workerItems.forEach(el => el.style.display = 'none');
                hseSections.forEach(el => el.style.display = 'block');
                hseItems.forEach(el => el.style.display = 'block');
                switchTab('dashboard');
                loadDashboard();
            } else {
                // Ask what role and open Sign-In page
                window.openRoleGatePopup();
            }
        }
    };

    function updateUserDisplay() {
        const nameEl = document.getElementById('userNameDisplay');
        const roleEl = document.getElementById('userRoleDisplay');
        const avatarEl = document.getElementById('userAvatarDisplay');
        if (currentUser && currentUser.is_logged_in !== false && currentUser.name && currentUser.name !== 'Guest / Not Logged In') {
            if (nameEl) nameEl.innerText = currentUser.name;
            if (roleEl) roleEl.innerText = (currentUser.role || 'WORKER').toUpperCase();
            if (avatarEl) avatarEl.innerText = (currentUser.name || 'U').charAt(0).toUpperCase();
        } else {
            if (nameEl) nameEl.innerText = 'Worker Mode';
            if (roleEl) roleEl.innerText = 'DIRECT ACCESS';
            if (avatarEl) avatarEl.innerText = '👷';
        }
    }

    async function handleUserLogout() {
        try {
            await fetch('/api/auth/logout', { method: 'POST' });
        } catch (e) {}
        currentUser = null;
        try {
            localStorage.removeItem('surakshax_user');
            sessionStorage.clear();
        } catch (e) {}
        updateUserDisplay();

        const avatarEl = document.getElementById('dossierAvatar');
        const nameEl = document.getElementById('dossierName');
        const workerIdEl = document.getElementById('dossierWorkerId');
        const usernameEl = document.getElementById('dossierUsername');
        const deptEl = document.getElementById('dossierDepartment');
        const siteEl = document.getElementById('dossierSite');
        const phoneEl = document.getElementById('dossierPhone');
        const addrEl = document.getElementById('dossierAddress');
        const createdEl = document.getElementById('dossierCreatedAt');
        if (avatarEl) avatarEl.innerText = '👤';
        if (nameEl) nameEl.innerText = 'Not Logged In';
        if (workerIdEl) workerIdEl.innerText = '—';
        if (usernameEl) usernameEl.innerText = '—';
        if (deptEl) deptEl.innerText = '—';
        if (siteEl) siteEl.innerText = '—';
        if (phoneEl) phoneEl.innerText = '—';
        if (addrEl) addrEl.innerText = '—';
        if (createdEl) createdEl.innerText = '—';

        window.showToast('Logged out of SurakshaX.', 'info');
        window.openRoleGatePopup();
    }
    window.handleUserLogout = handleUserLogout;

    function applyRolePermissions(role) {
        const roleUpper = (role || '').toUpperCase();
        const workerSections = document.querySelectorAll('.role-worker-section');
        const workerItems = document.querySelectorAll('.role-worker-item');
        const hseSections = document.querySelectorAll('.role-hse-section');
        const hseItems = document.querySelectorAll('.role-hse-item');

        if (roleUpper.includes('HSE') || roleUpper.includes('ADMIN')) {
            // HSE Officer / Admin sees ONLY HSE Command Center sections (Worker Portal hidden)
            updatePortalMenuHighlight('hse');
            workerSections.forEach(el => el.style.display = 'none');
            workerItems.forEach(el => el.style.display = 'none');
            hseSections.forEach(el => el.style.display = 'block');
            hseItems.forEach(el => el.style.display = 'block');
            switchTab('dashboard');
            loadDashboard();
        } else if (roleUpper === 'MECHANIC') {
            updatePortalMenuHighlight('worker');
            workerSections.forEach(el => el.style.display = 'block');
            workerItems.forEach(el => el.style.display = 'block');
            hseSections.forEach(el => el.style.display = 'none');
            hseItems.forEach(el => el.style.display = 'none');
            switchTab('safety-gate');
            if (window.switchGateSubTab) window.switchGateSubTab('mechanic');
        } else {
            // Worker or Guest defaults to Simple Worker Portal without forcing Sign-In
            updatePortalMenuHighlight('worker');
            workerSections.forEach(el => el.style.display = 'block');
            workerItems.forEach(el => el.style.display = 'block');
            hseSections.forEach(el => el.style.display = 'none');
            hseItems.forEach(el => el.style.display = 'none');
            switchTab('safety-gate');
            if (window.switchGateSubTab) window.switchGateSubTab('employee');
        }
    }

    // Initial Session Check & First Popup Window
    async function syncAuthSession() {
        try {
            const res = await fetch('/api/auth/current');
            const data = await res.json();
            if (data && data.is_logged_in) {
                currentUser = data;
                try { localStorage.setItem('surakshax_user', JSON.stringify(currentUser)); } catch (e) {}
                updateUserDisplay();
                applyRolePermissions(currentUser.role);
                const authModal = document.getElementById('authPortalModal');
                if (authModal) authModal.classList.remove('show');
                syncSafetyGateCameraState();
            } else if (currentUser && currentUser.name) {
                updateUserDisplay();
                applyRolePermissions(currentUser.role);
                const authModal = document.getElementById('authPortalModal');
                if (authModal) authModal.classList.remove('show');
                syncSafetyGateCameraState();
            } else {
                updateUserDisplay();
                // Show the First Popup Window: Worker (Direct) vs Other Role (Select & Sign In)
                window.openRoleGatePopup();
            }
        } catch (e) {
            updateUserDisplay();
            window.openRoleGatePopup();
        }
    }
    syncAuthSession();

    // 4.1 Auth Portal Modal & Biometric Face Registration
    let regStream = null;
    let capturedFaceSamples = [];
    let regAnimFrame = null;
    let regStepCaptureTimer = null;
    let regCurrentStageIndex = 0;
    let regStagePhase = 'WAITING_POSE'; // 'WAITING_POSE' | 'CAPTURING_BURST' | 'DONE'
    let regStageStartTime = 0;
    let regPoseDetectedFlash = 0;

    let motionCanvas = null;
    let motionCtx = null;
    let prevMotionFrame = null;

    function analyzeFaceMovement(videoEl) {
        if (!videoEl || !videoEl.videoWidth) {
            return { total: 0, left: 0, right: 0, top: 0, isTurningLeft: false, isTurningRight: false, isTiltingUp: false, isStable: true };
        }
        if (!motionCanvas) {
            motionCanvas = document.createElement('canvas');
            motionCanvas.width = 48;
            motionCanvas.height = 36;
            motionCtx = motionCanvas.getContext('2d', { willReadFrequently: true });
        }
        motionCtx.drawImage(videoEl, 0, 0, 48, 36);
        const curr = motionCtx.getImageData(0, 0, 48, 36).data;
        if (!prevMotionFrame) {
            prevMotionFrame = curr;
            return { total: 0, left: 0, right: 0, top: 0, isTurningLeft: false, isTurningRight: false, isTiltingUp: false, isStable: true };
        }

        let leftDiff = 0;
        let rightDiff = 0;
        let topDiff = 0;
        let totalDiff = 0;

        for (let y = 6; y < 30; y++) {
            for (let x = 8; x < 40; x++) {
                const idx = (y * 48 + x) * 4;
                const lumP = 0.299 * prevMotionFrame[idx] + 0.587 * prevMotionFrame[idx+1] + 0.114 * prevMotionFrame[idx+2];
                const lumC = 0.299 * curr[idx] + 0.587 * curr[idx+1] + 0.114 * curr[idx+2];
                const d = Math.abs(lumC - lumP);
                if (d > 12) {
                    totalDiff += d;
                    if (x < 24) leftDiff += d;
                    else rightDiff += d;
                    if (y < 18) topDiff += d;
                }
            }
        }
        prevMotionFrame = curr;

        return {
            total: totalDiff,
            left: leftDiff,
            right: rightDiff,
            top: topDiff,
            isTurningLeft: (leftDiff > 110 || (totalDiff > 220 && leftDiff > rightDiff * 0.7)),
            isTurningRight: (rightDiff > 110 || (totalDiff > 220 && rightDiff > leftDiff * 0.7)),
            isTiltingUp: (topDiff > 100 || (totalDiff > 220 && topDiff > (totalDiff - topDiff) * 0.5)),
            isStable: totalDiff < 650
        };
    }

    // Voice commands disabled per user preference
    function speakVoiceCommand() {}

    const ANGLE_GUIDES = [
        {
            stage: 0,
            min: 0,
            max: 10,
            voicePrompt: "Look straight at the camera.",
            label: "STAGE 1/5: LOOK STRAIGHT AT THE CAMERA",
            subLabel: "Center your face in the circle",
            icon: "👁️",
            direction: "center",
            color: "#10b981"
        },
        {
            stage: 1,
            min: 10,
            max: 20,
            voicePrompt: "Turn slightly left.",
            label: "STAGE 2/5: SLIGHTLY TURN YOUR FACE LEFT ⬅️",
            subLabel: "Turn face 15° to the left",
            icon: "⬅️",
            direction: "left",
            color: "#38bdf8"
        },
        {
            stage: 2,
            min: 20,
            max: 30,
            voicePrompt: "Turn slightly right.",
            label: "STAGE 3/5: SLIGHTLY TURN YOUR FACE RIGHT ➡️",
            subLabel: "Turn face 15° to the right",
            icon: "➡️",
            direction: "right",
            color: "#f59e0b"
        },
        {
            stage: 3,
            min: 30,
            max: 40,
            voicePrompt: "Tilt your head slightly up.",
            label: "STAGE 4/5: TILT YOUR HEAD SLIGHTLY UP ⬆️",
            subLabel: "Tilt your chin slightly upwards",
            icon: "⬆️",
            direction: "up",
            color: "#a855f7"
        },
        {
            stage: 4,
            min: 40,
            max: 50,
            voicePrompt: "Slightly nod your face.",
            label: "STAGE 5/5: SLOWLY NOD & CIRCLE YOUR FACE 🔄",
            subLabel: "Quick nod for 3D depth",
            icon: "🔄",
            direction: "nod",
            color: "#f97316"
        }
    ];

    function getCurrentAngleGuide(sampleCount) {
        for (const g of ANGLE_GUIDES) {
            if (sampleCount < g.max) return g;
        }
        return {
            stage: 5,
            min: 50,
            max: 50,
            voicePrompt: "Face enrollment complete!",
            label: "",
            subLabel: "Face ID Biometric Template Complete",
            icon: "✓",
            direction: "done",
            color: "#10b981"
        };
    }

    let sharedAudioCtx = null;
    function getSharedAudioCtx() {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return null;
        if (!sharedAudioCtx || sharedAudioCtx.state === 'closed') {
            sharedAudioCtx = new AudioCtx();
        }
        if (sharedAudioCtx.state === 'suspended') {
            sharedAudioCtx.resume().catch(() => {});
        }
        return sharedAudioCtx;
    }

    function playAudioChirp(freq = 660, duration = 0.08) {
        try {
            const actx = getSharedAudioCtx();
            if (!actx) return;
            const osc = actx.createOscillator();
            const gain = actx.createGain();
            osc.connect(gain);
            gain.connect(actx.destination);
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, actx.currentTime);
            gain.gain.setValueAtTime(0.05, actx.currentTime);
            gain.gain.exponentialRampToValueAtTime(0.001, actx.currentTime + duration);
            osc.start();
            osc.stop(actx.currentTime + duration);
        } catch (e) {}
    }

    let regSuccessCountdownTimer = null;
    let regConfettiAnimationId = null;

    function playSuccessFanfare() {
        try {
            const actx = getSharedAudioCtx();
            if (!actx) return;
            const notes = [
                { f: 523.25, t: 0.0, d: 0.22 },   // C5
                { f: 659.25, t: 0.12, d: 0.22 },  // E5
                { f: 783.99, t: 0.24, d: 0.26 },  // G5
                { f: 1046.50, t: 0.38, d: 0.65 }, // C6
                { f: 659.25, t: 0.38, d: 0.55 }   // harmonic accompaniment
            ];
            notes.forEach(n => {
                const osc = actx.createOscillator();
                const gain = actx.createGain();
                osc.type = 'triangle';
                const ctxTime = actx.currentTime + n.t;
                osc.frequency.setValueAtTime(n.f, ctxTime);
                gain.gain.setValueAtTime(0, ctxTime);
                gain.gain.linearRampToValueAtTime(0.18, ctxTime + 0.03);
                gain.gain.exponentialRampToValueAtTime(0.001, ctxTime + n.d);
                osc.connect(gain);
                gain.connect(actx.destination);
                osc.start(ctxTime);
                osc.stop(ctxTime + n.d);
            });
        } catch (e) {}
    }

    function launchCelebrationConfetti() {
        const canvas = document.getElementById('regConfettiCanvas');
        if (!canvas) return;
        const parent = canvas.parentElement;
        canvas.width = parent ? parent.clientWidth : 480;
        canvas.height = parent ? parent.clientHeight : 560;
        canvas.style.display = 'block';
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        const colors = ['#10b981', '#38bdf8', '#fbbf24', '#f43f5e', '#a855f7', '#34d399', '#60a5fa'];
        const particles = [];
        const particleCount = 75;

        for (let i = 0; i < particleCount; i++) {
            particles.push({
                x: canvas.width / 2 + (Math.random() - 0.5) * 140,
                y: canvas.height * 0.2 + (Math.random() - 0.5) * 40,
                vx: (Math.random() - 0.5) * 9,
                vy: Math.random() * -7 - 2,
                gravity: 0.16 + Math.random() * 0.08,
                rotation: Math.random() * 360,
                rotationSpeed: (Math.random() - 0.5) * 8,
                color: colors[Math.floor(Math.random() * colors.length)],
                size: Math.random() * 7 + 5,
                opacity: 1,
                decay: 0.007 + Math.random() * 0.006
            });
        }

        if (regConfettiAnimationId) cancelAnimationFrame(regConfettiAnimationId);

        const render = () => {
            ctx.clearRect(0, 0, canvas.width, canvas.height);
            let active = 0;
            particles.forEach(p => {
                p.x += p.vx;
                p.y += p.vy;
                p.vy += p.gravity;
                p.vx *= 0.98;
                p.rotation += p.rotationSpeed;
                p.opacity -= p.decay;

                if (p.opacity > 0) {
                    active++;
                    ctx.save();
                    ctx.translate(p.x, p.y);
                    ctx.rotate((p.rotation * Math.PI) / 180);
                    ctx.fillStyle = p.color;
                    ctx.globalAlpha = Math.max(0, p.opacity);
                    ctx.fillRect(-p.size / 2, -p.size / 2, p.size, p.size * 0.6);
                    ctx.restore();
                }
            });

            if (active > 0) {
                regConfettiAnimationId = requestAnimationFrame(render);
            } else {
                canvas.style.display = 'none';
            }
        };
        render();
    }

    window.switchAuthTab = function(tab) {
        const viewRoleGate = document.getElementById('authViewRoleGate');
        const viewSignIn = document.getElementById('authViewSignIn');
        const viewRegister = document.getElementById('authViewRegister');
        const viewSuccess = document.getElementById('authViewSuccess');
        const tabBtnSignIn = document.getElementById('tabBtnSignIn');
        const tabBtnRegister = document.getElementById('tabBtnRegister');
        const header = document.getElementById('authPortalHeader');
        const roleGroup = document.getElementById('authRoleSelectGroup');
        const tabsRow = document.getElementById('authTabsRow');
        const confettiCanvas = document.getElementById('regConfettiCanvas');

        if (viewRoleGate) viewRoleGate.style.display = 'none';
        if (viewSuccess) viewSuccess.style.display = 'none';
        if (header) header.style.display = 'block';
        if (tabsRow) tabsRow.style.display = 'flex';
        if (confettiCanvas) confettiCanvas.style.display = 'none';
        if (regSuccessCountdownTimer) {
            clearInterval(regSuccessCountdownTimer);
            regSuccessCountdownTimer = null;
        }
        if (regConfettiAnimationId) {
            cancelAnimationFrame(regConfettiAnimationId);
            regConfettiAnimationId = null;
        }

        if (tab === 'signin') {
            if (viewSignIn) viewSignIn.style.display = 'block';
            if (viewRegister) viewRegister.style.display = 'none';
            if (tabBtnSignIn) tabBtnSignIn.classList.add('active');
            if (tabBtnRegister) tabBtnRegister.classList.remove('active');
        } else {
            if (viewSignIn) viewSignIn.style.display = 'none';
            if (viewRegister) viewRegister.style.display = 'block';
            if (tabBtnSignIn) tabBtnSignIn.classList.remove('active');
            if (tabBtnRegister) tabBtnRegister.classList.add('active');
        }
    };

    let reusableSnapCanvas = null;
    let reusableSnapCtx = null;

    window.startRegCamera = async function() {
        const video = document.getElementById('regVideoElement');
        const canvas = document.getElementById('regCanvasElement');
        const placeholder = document.getElementById('regCameraPlaceholder');
        const btn = document.getElementById('regStartCamBtn');
        const promptBanner = document.getElementById('regAnglePromptBanner');
        const badge = document.getElementById('regFaceCounterBadge');
        const snapBtn = document.getElementById('regCaptureFaceBtn');

        if (regStream) {
            if (regStepCaptureTimer) {
                clearTimeout(regStepCaptureTimer);
                regStepCaptureTimer = null;
            }
            if (regAnimFrame) {
                cancelAnimationFrame(regAnimFrame);
                regAnimFrame = null;
            }
            try {
                if ('speechSynthesis' in window) window.speechSynthesis.cancel();
            } catch (e) {}
            regStream.getTracks().forEach(t => t.stop());
            regStream = null;
            regStagePhase = 'WAITING_POSE';
            if (video) video.style.display = 'none';
            if (canvas) canvas.style.display = 'none';
            if (placeholder) placeholder.style.display = 'block';
            if (btn) btn.innerHTML = '📹 Start Camera';
            if (snapBtn) snapBtn.innerHTML = '📸 Recognizing';
            if (typeof syncSafetyGateCameraState === 'function') syncSafetyGateCameraState();
            return;
        }

        // Release Safety Gate camera if active to prevent camera device conflicts
        if (window.safetyGate && (window.safetyGate.isRealCameraActive || window.safetyGate.isStartingCamera)) {
            window.safetyGate.stopRealCamera();
        }

        try {
            regStream = await navigator.mediaDevices.getUserMedia({
                video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: 'user' },
                audio: false
            });
            if (video) {
                video.srcObject = regStream;
                video.style.opacity = '0';
                video.style.position = 'absolute';
                video.style.pointerEvents = 'none';
                await video.play();
            }
            if (placeholder) placeholder.style.display = 'none';
            if (canvas) {
                canvas.style.display = 'block';
                canvas.width = 340;
                canvas.height = 220;
            }
            if (btn) btn.innerHTML = '⏹️ Stop Camera';
            if (snapBtn) snapBtn.innerHTML = '📸 Recognizing';

            if (!reusableSnapCanvas) {
                reusableSnapCanvas = document.createElement('canvas');
                reusableSnapCanvas.width = 200;
                reusableSnapCanvas.height = 150;
                reusableSnapCtx = reusableSnapCanvas.getContext('2d');
            }

            const ctx = canvas.getContext('2d');
            let flashCountdown = 0;
            capturedFaceSamples = [];
            regCurrentStageIndex = 0;
            regStagePhase = 'WAITING_POSE';
            regStageStartTime = Date.now();
            regPoseDetectedFlash = 0;
            prevMotionFrame = null;

            if (badge) {
                badge.className = 'badge badge-low';
                badge.innerText = '0 / 50 Samples';
            }

            // Silent Fast Capture Routine: Captures 50 samples smoothly without voice commands or camera watermarks
            executeStageBurst = function() {
                if (!regStream) return;
                if (regStagePhase === 'CAPTURING_BURST' || regStagePhase === 'DONE') return;

                regStagePhase = 'CAPTURING_BURST';
                const targetEnd = Math.min((regCurrentStageIndex + 1) * 10, 50);

                function snapNext() {
                    if (!regStream) return;

                    if (capturedFaceSamples.length < targetEnd) {
                        reusableSnapCtx.drawImage(video, 0, 0, 200, 150);
                        capturedFaceSamples.push(reusableSnapCanvas.toDataURL('image/jpeg', 0.72));

                        const c = capturedFaceSamples.length;
                        if (badge) badge.innerText = `${c} / 50 Samples`;
                        if (snapBtn) snapBtn.innerHTML = '📸 Recognizing';

                        regStepCaptureTimer = setTimeout(snapNext, 22);
                    } else {
                        const count = capturedFaceSamples.length;
                        if (count >= 50) {
                            regStagePhase = 'DONE';
                            if (badge) {
                                badge.className = 'badge badge-low';
                                badge.innerText = '✓ 50 Samples Ready';
                            }
                            if (snapBtn) {
                                snapBtn.innerHTML = '✓ Ready';
                                snapBtn.disabled = true;
                            }
                            window.showToast('✓ 50 Face ID samples captured! Click "Register".', 'success');
                        } else {
                            regCurrentStageIndex++;
                            regStagePhase = 'WAITING_POSE';
                            regStageStartTime = Date.now();
                        }
                    }
                }
                snapNext();
            };

            const renderRegFrame = () => {
                if (!regStream) return;
                // Draw clean, watermark-free camera preview
                ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

                const count = capturedFaceSamples.length;
                if (regStagePhase === 'WAITING_POSE' && count < 50) {
                    const elapsed = Date.now() - regStageStartTime;
                    if (elapsed > 140) {
                        executeStageBurst();
                    }
                }

                regAnimFrame = requestAnimationFrame(renderRegFrame);
            };
            renderRegFrame();

            window.showToast('Camera Active — Capturing face samples...', 'info');

        } catch (err) {
            console.error('Registration webcam error:', err);
            window.showToast('Webcam access error or permission denied.', 'warning');
        }
    };

    window.captureFaceSample = function() {
        if (!regStream) {
            window.showToast('Please start camera first.', 'warning');
            return;
        }

        if (capturedFaceSamples.length >= 50) {
            window.showToast('50 samples already recorded! Ready to register.', 'info');
            return;
        }

        if (regStagePhase === 'WAITING_POSE' && typeof executeStageBurst === 'function') {
            executeStageBurst();
            window.showToast('Recognizing face pose and capturing fine-tuned samples...', 'info');
        } else {
            window.showToast(`Capturing in progress (${capturedFaceSamples.length}/50)...`, 'info');
        }
    };

    // Password Toggle Helper
    window.togglePasswordVisibility = function(inputId) {
        const el = document.getElementById(inputId);
        if (el) {
            el.type = el.type === 'password' ? 'text' : 'password';
        }
    };

    // Registration Form submit (Single Button: Recognizing + Register & Train Biometric Model)
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('regSubmitBtn');
            const roleSelect = document.getElementById('portalRoleSelect');
            const regErrorAlert = document.getElementById('regErrorAlert');

            const name = document.getElementById('regName').value.trim();
            const workerIdEl = document.getElementById('regWorkerId');
            const workerId = workerIdEl ? workerIdEl.value.trim() : '';
            const username = workerId
                ? workerId.toLowerCase().replace(/[^a-z0-9_]/g, '')
                : name.toLowerCase().replace(/[^a-z0-9]/g, '');
            const passEl = document.getElementById('regPassword');
            const confPassEl = document.getElementById('regConfirmPassword');
            const password = passEl ? passEl.value : '';
            const confirmPassword = confPassEl ? confPassEl.value : '';

            if (regErrorAlert) regErrorAlert.style.display = 'none';

            if (!name) {
                if (regErrorAlert) {
                    regErrorAlert.innerHTML = '⚠️ <strong>Validation Error:</strong> Please enter your Full Name.';
                    regErrorAlert.style.display = 'block';
                } else {
                    alert('Please enter your Full Name.');
                }
                return;
            }

            if (!password || password.length < 4) {
                if (regErrorAlert) {
                    regErrorAlert.innerHTML = '⚠️ <strong>Password Error:</strong> Password must be at least 4 characters long.';
                    regErrorAlert.style.display = 'block';
                } else {
                    alert('Password must be at least 4 characters long.');
                }
                if (passEl) passEl.focus();
                return;
            }

            if (password !== confirmPassword) {
                if (regErrorAlert) {
                    regErrorAlert.innerHTML = '⚠️ <strong>Password Mismatch:</strong> Passwords do not match. Please re-enter identical passwords.';
                    regErrorAlert.style.display = 'block';
                } else {
                    alert('Passwords do not match.');
                }
                if (confPassEl) confPassEl.focus();
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Registering....';

            // Unified 1-Click Flow: If face samples are not yet captured, auto-start camera & capture frames now
            if (!capturedFaceSamples || capturedFaceSamples.length < 10) {
                if (!regStream && typeof window.startRegCamera === 'function') {
                    await window.startRegCamera();
                }
                if (regStream) {
                    const video = document.getElementById('regVideoElement');
                    const badge = document.getElementById('regFaceCounterBadge');
                    if (!reusableSnapCanvas) {
                        reusableSnapCanvas = document.createElement('canvas');
                        reusableSnapCanvas.width = 200;
                        reusableSnapCanvas.height = 150;
                        reusableSnapCtx = reusableSnapCanvas.getContext('2d');
                    }
                    // Wait briefly for camera exposure and capture up to 50 samples rapidly
                    await new Promise((resolve) => {
                        let attempts = 0;
                        const fastTimer = setInterval(() => {
                            attempts++;
                            if (video && video.readyState >= 2 && capturedFaceSamples.length < 50) {
                                reusableSnapCtx.drawImage(video, 0, 0, 200, 150);
                                capturedFaceSamples.push(reusableSnapCanvas.toDataURL('image/jpeg', 0.75));
                                if (badge) badge.innerText = `${capturedFaceSamples.length} / 50 Samples`;
                            }
                            if (capturedFaceSamples.length >= 25 || attempts >= 35) {
                                clearInterval(fastTimer);
                                if (badge && capturedFaceSamples.length >= 25) {
                                    badge.innerText = '✓ 50 Samples Ready';
                                }
                                resolve();
                            }
                        }, 28);
                    });
                }
            }

            if (!capturedFaceSamples || capturedFaceSamples.length < 5) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Register';
                if (regErrorAlert) {
                    regErrorAlert.innerHTML = '⚠️ <strong>Biometric Face Enrollment Required:</strong> Please permit camera access so your face biometrics can be enrolled.';
                    regErrorAlert.style.display = 'block';
                }
                return;
            }

            // Send 15 evenly spaced multi-angle frames across all pose stages for fast upload & training
            const compactSamples = capturedFaceSamples.length > 15
                ? capturedFaceSamples.filter((_, idx) => idx % Math.max(1, Math.floor(capturedFaceSamples.length / 15)) === 0).slice(0, 15)
                : capturedFaceSamples;

            const payload = {
                name: name,
                username: username,
                worker_id: workerId,
                password: password,
                role: roleSelect ? roleSelect.value : 'worker',
                department: document.getElementById('regDepartment') ? document.getElementById('regDepartment').value.trim() : 'Drilling & Operations',
                phone: document.getElementById('regPhone') ? document.getElementById('regPhone').value.trim() : '',
                face_samples: compactSamples
            };

            try {
                const res = await fetch('/api/auth/register', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Register';

                if (data.success) {
                    if (regStream) {
                        if (regStepCaptureTimer) { clearTimeout(regStepCaptureTimer); regStepCaptureTimer = null; }
                        if (regAnimFrame) { cancelAnimationFrame(regAnimFrame); regAnimFrame = null; }
                        try { if ('speechSynthesis' in window) window.speechSynthesis.cancel(); } catch(e) {}
                        regStream.getTracks().forEach(t => { try { t.stop(); } catch(e) {} });
                        regStream = null;
                        regStagePhase = 'DONE';
                    }
                    currentUser = data.user;
                    try { localStorage.setItem('surakshax_user', JSON.stringify(currentUser)); } catch (e) {}
                    updateUserDisplay();
                    applyRolePermissions(currentUser.role);
                    if (safetyGate && safetyGate.loadWorkers) safetyGate.loadWorkers();
                    if (passEl) passEl.value = '';
                    if (confPassEl) confPassEl.value = '';

                    // Populate Success Celebration Card details
                    const nameEl = document.getElementById('regSuccessName');
                    const workerIdEl = document.getElementById('regSuccessWorkerId');
                    const roleEl = document.getElementById('regSuccessRole');
                    const deptEl = document.getElementById('regSuccessDept');

                    if (nameEl) nameEl.innerText = currentUser.name || name;
                    if (workerIdEl) workerIdEl.innerText = currentUser.worker_id || ('W' + String(currentUser.id || 1).padStart(3, '0'));
                    
                    const roleLabels = {
                        'worker': '👷 Worker / Rig Technician',
                        'hse': '🛡️ HSE Officer / Inspector',
                        'admin': '⚙️ Digital Safety Admin',
                        'mechanic': '🔧 Visiting Mechanic / Contractor'
                    };
                    if (roleEl) {
                        const rKey = (currentUser.role || 'worker').toLowerCase();
                        roleEl.innerText = roleLabels[rKey] || (currentUser.role ? currentUser.role.toUpperCase() : 'Worker');
                    }
                    if (deptEl) deptEl.innerText = currentUser.department || 'Drilling & Operations';

                    // Switch modal view to celebration state
                    const header = document.getElementById('authPortalHeader');
                    const roleGroup = document.getElementById('authRoleSelectGroup');
                    const tabsRow = document.getElementById('authTabsRow');
                    const viewRegister = document.getElementById('authViewRegister');
                    const viewSignIn = document.getElementById('authViewSignIn');
                    const viewSuccess = document.getElementById('authViewSuccess');

                    if (header) header.style.display = 'none';
                    if (roleGroup) roleGroup.style.display = 'none';
                    if (tabsRow) tabsRow.style.display = 'none';
                    if (viewRegister) viewRegister.style.display = 'none';
                    if (viewSignIn) viewSignIn.style.display = 'none';
                    if (viewSuccess) viewSuccess.style.display = 'block';

                    // Trigger Audio Fanfare and Confetti
                    playSuccessFanfare();
                    launchCelebrationConfetti();

                    // Fast 1.2-second auto-proceed countdown to Safety Gate Turnstile
                    let countdown = 1;
                    const timerEl = document.getElementById('regSuccessTimer');
                    const barEl = document.getElementById('regSuccessProgressBar');
                    if (timerEl) timerEl.innerText = `${countdown}s`;
                    if (barEl) {
                        barEl.style.transition = 'none';
                        barEl.style.width = '100%';
                        setTimeout(() => {
                            if (barEl) {
                                barEl.style.transition = 'width 1.2s linear';
                                barEl.style.width = '0%';
                            }
                        }, 30);
                    }

                    const proceedToSafetyGate = () => {
                        if (regSuccessCountdownTimer) {
                            clearInterval(regSuccessCountdownTimer);
                            regSuccessCountdownTimer = null;
                        }
                        if (regConfettiAnimationId) {
                            cancelAnimationFrame(regConfettiAnimationId);
                            regConfettiAnimationId = null;
                        }
                        const modal = document.getElementById('authPortalModal');
                        if (modal) modal.classList.remove('show');
                        if (typeof switchTab === 'function') {
                            switchTab('safety-gate');
                        }
                        window.showToast(`Biometric registration verified! Welcome to the AI Safety Gate, ${currentUser.name}.`, 'success');
                    };

                    const proceedBtn = document.getElementById('regSuccessProceedBtn');
                    if (proceedBtn) {
                        proceedBtn.onclick = proceedToSafetyGate;
                    }

                    if (regSuccessCountdownTimer) clearInterval(regSuccessCountdownTimer);
                    regSuccessCountdownTimer = setInterval(() => {
                        countdown--;
                        if (timerEl) timerEl.innerText = `${Math.max(0, countdown)}s`;
                        if (countdown <= 0) {
                            clearInterval(regSuccessCountdownTimer);
                            regSuccessCountdownTimer = null;
                            proceedToSafetyGate();
                        }
                    }, 1200);
                } else {
                    if (regErrorAlert) {
                        regErrorAlert.innerHTML = `⛔ <strong>Registration Failed:</strong> ${data.error}`;
                        regErrorAlert.style.display = 'block';
                    } else {
                        alert(`Registration failed: ${data.error}`);
                    }
                }
            } catch (err) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Register';
                console.error('Registration error:', err);
                if (regErrorAlert) {
                    regErrorAlert.innerHTML = '⚠️ <strong>Network Error:</strong> Registration request failed.';
                    regErrorAlert.style.display = 'block';
                }
            }
        });
    }

    // Sign In Form submit (Strict Authentication: Decline access on wrong password)
    const signInForm = document.getElementById('signInForm');
    if (signInForm) {
        signInForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const usernameInput = document.getElementById('loginUsername');
            const passwordInput = document.getElementById('loginPassword');
            const username = (usernameInput ? usernameInput.value : '').trim();
            const password = (passwordInput ? passwordInput.value : '').trim();
            const loginErrorAlert = document.getElementById('loginErrorAlert');
            const submitBtn = document.getElementById('loginSubmitBtn');

            if (loginErrorAlert) loginErrorAlert.style.display = 'none';

            if (!username) {
                if (loginErrorAlert) {
                    loginErrorAlert.innerHTML = '⚠️ <strong>Access Denied:</strong> Please enter your Username or Worker ID.';
                    loginErrorAlert.style.display = 'block';
                }
                if (usernameInput) usernameInput.focus();
                return;
            }

            if (!password) {
                if (loginErrorAlert) {
                    loginErrorAlert.innerHTML = '⚠️ <strong>Access Denied:</strong> Please enter your password.';
                    loginErrorAlert.style.display = 'block';
                }
                if (passwordInput) passwordInput.focus();
                return;
            }

            if (submitBtn) {
                submitBtn.disabled = true;
                submitBtn.innerHTML = 'Verifying Credentials...';
            }

            try {
                const res = await fetch('/api/auth/login', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ username, password })
                });
                const data = await res.json();
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Enter SurakshaX Portal';
                }

                if (data.success) {
                    currentUser = data.user;
                    try { localStorage.setItem('surakshax_user', JSON.stringify(currentUser)); } catch (e) {}
                    updateUserDisplay();
                    applyRolePermissions(currentUser.role);
                    document.getElementById('authPortalModal').classList.remove('show');
                    window.showToast(`✓ Access Granted: ${currentUser.name} (${currentUser.role})`, 'success');
                    if (passwordInput) passwordInput.value = '';
                    if (typeof syncSafetyGateCameraState === 'function') syncSafetyGateCameraState();
                } else {
                    // Strictly decline access and display dynamic error banner
                    if (loginErrorAlert) {
                        loginErrorAlert.innerHTML = `⛔ <strong>Access Denied:</strong> ${data.error || 'Invalid credentials or unregistered personnel.'}`;
                        loginErrorAlert.style.display = 'block';
                    } else {
                        alert(`Access Denied: ${data.error}`);
                    }
                    if (passwordInput) {
                        passwordInput.value = '';
                        passwordInput.focus();
                    }
                }
            } catch (err) {
                if (submitBtn) {
                    submitBtn.disabled = false;
                    submitBtn.innerHTML = 'Enter SurakshaX Portal';
                }
                console.error('Sign in error:', err);
                if (loginErrorAlert) {
                    loginErrorAlert.innerHTML = '⚠️ <strong>Connection Error:</strong> Could not connect to authentication server.';
                    loginErrorAlert.style.display = 'block';
                }
            }
        });
    }

    // Portal Trigger Button
    const authPortalTriggerBtn = document.getElementById('authPortalTriggerBtn');
    if (authPortalTriggerBtn) {
        authPortalTriggerBtn.addEventListener('click', () => {
            document.getElementById('authPortalModal').classList.add('show');
            if (typeof syncSafetyGateCameraState === 'function') syncSafetyGateCameraState();
        });
    }

    // Modal Close Helper
    window.closeAuthModal = function() {
        if (regSuccessCountdownTimer) {
            clearInterval(regSuccessCountdownTimer);
            regSuccessCountdownTimer = null;
        }
        if (regConfettiAnimationId) {
            cancelAnimationFrame(regConfettiAnimationId);
            regConfettiAnimationId = null;
        }
        const confettiCanvas = document.getElementById('regConfettiCanvas');
        if (confettiCanvas) confettiCanvas.style.display = 'none';

        try {
            if ('speechSynthesis' in window) window.speechSynthesis.cancel();
        } catch (e) {}

        if (regStream) {
            if (regStepCaptureTimer) {
                clearTimeout(regStepCaptureTimer);
                regStepCaptureTimer = null;
            }
            if (regAnimFrame) {
                cancelAnimationFrame(regAnimFrame);
                regAnimFrame = null;
            }
            regStream.getTracks().forEach(t => {
                try { t.stop(); } catch(e) {}
            });
            regStream = null;
            regStagePhase = 'WAITING_POSE';
            const btn = document.getElementById('regStartCamBtn');
            if (btn) btn.innerHTML = '📹 Start Camera';
            const snapBtn = document.getElementById('regCaptureFaceBtn');
            if (snapBtn) snapBtn.innerHTML = '📸 Recognizing';
            const placeholder = document.getElementById('regCameraPlaceholder');
            const canvas = document.getElementById('regCanvasElement');
            if (placeholder) placeholder.style.display = 'block';
            if (canvas) canvas.style.display = 'none';
        }
        const modal = document.getElementById('authPortalModal');
        if (modal) modal.classList.remove('show');
        if (typeof syncSafetyGateCameraState === 'function') {
            syncSafetyGateCameraState();
        }
    };

    // Close on backdrop click (clicking outside dialog on dark overlay)
    const authModalEl = document.getElementById('authPortalModal');
    if (authModalEl) {
        authModalEl.addEventListener('click', (e) => {
            if (e.target === authModalEl) {
                closeAuthModal();
            }
        });
    }

    // Close on Escape key press
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape' || e.key === 'Esc') {
            const modal = document.getElementById('authPortalModal');
            if (modal && modal.classList.contains('show')) {
                closeAuthModal();
            }
        }
    });

    // Auto-stop camera when minimizing browser or switching browser tabs;
    // Auto-resume camera when switching back if active tab is Safety Gate
    document.addEventListener('visibilitychange', () => {
        if (document.hidden) {
            if (window.safetyGate && (window.safetyGate.isRealCameraActive || window.safetyGate.isStartingCamera)) {
                window.safetyGate.stopRealCamera();
            }
        } else {
            if (typeof syncSafetyGateCameraState === 'function') {
                syncSafetyGateCameraState();
            }
        }
    });

    window.addEventListener('pagehide', () => {
        if (window.safetyGate && window.safetyGate.isRealCameraActive) {
            window.safetyGate.stopRealCamera();
        }
    });

    window.addEventListener('beforeunload', () => {
        if (window.safetyGate && window.safetyGate.isRealCameraActive) {
            window.safetyGate.stopRealCamera();
        }
    });

    // 4.2 Smart Gate Sub-Tabs & Mechanic Pass Generator
    window.switchGateSubTab = function(sub) {
        const secEmp = document.getElementById('gateSubSectionEmployee');
        const secMech = document.getElementById('gateSubSectionMechanic');
        const btnEmp = document.getElementById('gateTabEmployeeBtn');
        const btnMech = document.getElementById('gateTabMechanicBtn');

        if (sub === 'employee') {
            if (secEmp) secEmp.style.display = 'block';
            if (secMech) secMech.style.display = 'none';
            if (btnEmp) btnEmp.classList.add('active');
            if (btnMech) btnMech.classList.remove('active');
        } else {
            if (secEmp) secEmp.style.display = 'none';
            if (secMech) secMech.style.display = 'block';
            if (btnEmp) btnEmp.classList.remove('active');
            if (btnMech) btnMech.classList.add('active');
        }

        if (window.safetyGate) {
            window.safetyGate.userManuallyStopped = false;
        }
        if (typeof syncSafetyGateCameraState === 'function') {
            syncSafetyGateCameraState();
        }
    };

    const mechForm = document.getElementById('mechanicEntryForm');
    if (mechForm) {
        mechForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('issueMechPassBtn');
            const name = document.getElementById('mechName').value.trim();
            const phone = document.getElementById('mechPhone').value.trim();
            const address = document.getElementById('mechAddress').value.trim();
            const machine_assigned = document.getElementById('mechMachine').value;

            if (!name || !phone) {
                alert('Please enter mechanic name and contact number.');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = 'Verifying & Generating Gate Pass...';

            try {
                const res = await fetch('/api/safety_gate/mechanic_entry', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ name, phone, address, machine_assigned })
                });
                const data = await res.json();
                btn.disabled = false;
                btn.innerHTML = '🎫 Issue Temporary Mechanic Gate Pass';

                if (data.success) {
                    renderMechanicPass(data);
                    window.showToast(`Pass ${data.pass_code} issued for ${data.name}`, 'success');
                    loadNotifications();
                } else {
                    alert(`Error: ${data.error}`);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '🎫 Issue Temporary Mechanic Gate Pass';
                console.error('Mechanic entry error:', err);
            }
        });
    }

    function renderMechanicPass(entry) {
        const container = document.getElementById('mechPassDisplayContainer');
        if (!container) return;

        container.innerHTML = `
            <div class="mechanic-pass-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; border-bottom: 2px dashed #cbd5e1; padding-bottom: 12px; margin-bottom: 14px;">
                    <div>
                        <div style="font-size: 11px; font-weight: 700; color: #0284c7; letter-spacing: 0.5px;">OIL INDIA LIMITED • DULIAJAN GATE 1</div>
                        <div style="font-size: 18px; font-weight: 800; color: #0f172a; margin-top: 2px;">VISITING MECHANIC ENTRY PASS</div>
                    </div>
                    <div style="text-align: right;">
                        <span class="badge badge-critical" style="font-size: 13px; font-weight: 800; padding: 4px 10px;">${entry.pass_code}</span>
                        <div style="font-size: 10px; color: #64748b; margin-top: 4px;">VALID FOR 24 HOURS</div>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: 2fr 1fr; gap: 14px; margin-bottom: 16px;">
                    <div>
                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Contractor / Mechanic Name</div>
                        <div style="font-size: 15px; font-weight: 700; color: #0f2744; margin-bottom: 8px;">${entry.name}</div>

                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Contact Phone</div>
                        <div style="font-size: 13px; font-weight: 600; color: #1e293b; margin-bottom: 8px;">${entry.phone}</div>

                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Workshop / Registered Address</div>
                        <div style="font-size: 12px; color: #334155; margin-bottom: 8px;">${entry.address}</div>

                        <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Assigned Repair Equipment</div>
                        <div style="font-size: 13px; font-weight: 700; color: #b45309;">${entry.machine_assigned}</div>
                    </div>

                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; background: #ffffff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 12px;">
                        <div style="font-size: 48px;">🎫</div>
                        <div style="font-size: 10px; font-weight: 700; color: #059669; text-align: center; margin-top: 4px;">✓ SECURITY VERIFIED</div>
                        <div style="font-size: 9px; color: #94a3b8; text-align: center; margin-top: 2px;">Entry: ${entry.entry_time}</div>
                    </div>
                </div>

                <div style="background: #fffbeb; border: 1px solid #fef3c7; border-radius: 6px; padding: 10px; font-size: 11.5px; color: #92400e; margin-bottom: 14px;">
                    <strong>Security Notice:</strong> Contractor must wear complete PPE (hard hat, steel-toe boots, hi-vis vest) at all times. Return pass upon exit.
                </div>

                <div style="display: flex; justify-content: flex-end; gap: 8px;">
                    <button class="btn btn-secondary btn-sm" onclick="window.print()">🖨️ Print Pass</button>
                    <button class="btn btn-primary btn-sm" onclick="document.querySelector('[data-tab=\\'repair-review\\']').click()">Go to Post-Repair Verification ➔</button>
                </div>
            </div>
        `;
    }

    // 4.3 Worker Machine Post-Repair Sign-off
    const repairForm = document.getElementById('repairReviewForm');
    if (repairForm) {
        repairForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const btn = document.getElementById('submitRepairBtn');
            const payload = {
                machine_id: document.getElementById('repairMachineId').value,
                worker_id: document.getElementById('repairWorkerId').value.trim() || currentUser.id,
                worker_name: document.getElementById('repairWorkerName').value.trim() || currentUser.name,
                repair_status: document.getElementById('repairStatusSelect').value,
                observations: document.getElementById('repairObservations').value.trim(),
                verified_safe: document.getElementById('repairVerifiedSafe').checked
            };

            if (!payload.observations) {
                alert('Please enter repair inspection observations.');
                return;
            }

            btn.disabled = true;
            btn.innerHTML = 'Saving Sign-off & Updating Machine...';

            try {
                const res = await fetch('/api/machines/repair_review', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                btn.disabled = false;
                btn.innerHTML = '✓ Submit Review & Restore Machine Status';

                if (data.success) {
                    window.showToast(`Repair review recorded for ${payload.machine_id}! Status restored.`, 'success');
                    document.getElementById('repairObservations').value = '';
                    loadRepairReviews();
                    loadMachines();
                    loadDashboard();
                } else {
                    alert(`Submission failed: ${data.error}`);
                }
            } catch (err) {
                btn.disabled = false;
                btn.innerHTML = '✓ Submit Review & Restore Machine Status';
                console.error('Repair review error:', err);
            }
        });
    }

    async function loadRepairReviews() {
        const tbody = document.getElementById('repairReviewsTableBody');
        if (!tbody) return;

        try {
            const res = await fetch('/api/machines/repair_reviews');
            const reviews = await res.json();

            if (reviews.length === 0) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:#94a3b8;">No repair sign-offs recorded yet.</td></tr>';
                return;
            }

            tbody.innerHTML = reviews.map(r => {
                const isSafe = r.verified_safe;
                const statusBadge = r.repair_status.includes('VERIFIED') ? 'badge-low' : 'badge-high';
                return `
                    <tr>
                        <td><strong>${r.machine_id}</strong></td>
                        <td>${r.worker_name} <small style="color:#64748b;">(${r.worker_id})</small></td>
                        <td><span class="badge ${statusBadge}">${r.repair_status}</span></td>
                        <td style="font-size: 12px; max-width: 240px;">${r.observations}</td>
                        <td style="font-size: 11px; color: #64748b;">${r.created_at}</td>
                    </tr>
                `;
            }).join('');
        } catch (err) {
            console.error('Failed loading repair reviews:', err);
        }
    }

    // 5. Dashboard Data Loading
    async function loadDashboard() {
        const kpiTotal = document.getElementById('kpiTotalReports');
        if (!kpiTotal) return;
        try {
            const res = await fetch('/api/dashboard/kpis');
            const kpis = await res.json();
            
            if (kpiTotal) kpiTotal.innerText = kpis.total_reports;
            const elSif = document.getElementById('kpiSifReports');
            if (elSif) elSif.innerText = kpis.sif_reports;
            const elCrit = document.getElementById('kpiCriticalRisks');
            if (elCrit) elCrit.innerText = kpis.critical_risks;
            const elHigh = document.getElementById('kpiHighRisks');
            if (elHigh) elHigh.innerText = kpis.high_risks;
            const elHse = document.getElementById('kpiPendingHSE');
            if (elHse) elHse.innerText = kpis.pending_hse_actions;
            const elOverdue = document.getElementById('kpiOverdueMachines');
            if (elOverdue) elOverdue.innerText = kpis.overdue_machines;
            const elLocked = document.getElementById('kpiLockedMachines');
            if (elLocked) elLocked.innerText = kpis.locked_machines;
            const elAwait = document.getElementById('kpiAwaitingReview');
            if (elAwait) elAwait.innerText = kpis.reports_awaiting_review;
        } catch (e) {
            console.error('Failed to load dashboard KPIs:', e);
        }
    }

    // 6. Submit Safety Report Flow
    const reportForm = document.getElementById('safetyReportForm');
    const demoSelect = document.getElementById('demoReportSelect');
    const loadDemoBtn = document.getElementById('loadDemoBtn');
    const aiResultCard = document.getElementById('aiAnalysisResultCard');

    if (loadDemoBtn) {
        loadDemoBtn.addEventListener('click', async () => {
            const demoId = demoSelect.value;
            try {
                const res = await fetch('/api/demo_reports');
                const demos = await res.json();
                const found = demos.find(d => d.id === demoId);
                if (found) {
                    document.getElementById('reportWorkerId').value = found.worker_id;
                    document.getElementById('reportSite').value = found.site;
                    document.getElementById('reportLocation').value = found.location;
                    document.getElementById('reportActivity').value = found.activity;
                    document.getElementById('reportMachineId').value = found.machine_id;
                    document.getElementById('reportType').value = found.report_type;
                    document.getElementById('reportDescription').value = found.text;
                    window.showToast(`Loaded ${found.title}`, 'info');
                }
            } catch (e) {
                console.error('Failed loading demo:', e);
            }
        });
    }

    // Photographic Evidence Handling (Webcam Snapshot & File Upload)
    const reportPhotoInput = document.getElementById('reportPhotoInput');
    const btnReportSnapWebcam = document.getElementById('btnReportSnapWebcam');
    const btnReportClearPhoto = document.getElementById('btnReportClearPhoto');
    const reportPhotoPreviewContainer = document.getElementById('reportPhotoPreviewContainer');
    const reportPhotoPreview = document.getElementById('reportPhotoPreview');
    const reportPhotoData = document.getElementById('reportPhotoData');

    if (reportPhotoInput) {
        reportPhotoInput.addEventListener('change', (e) => {
            const file = e.target.files && e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                const b64 = evt.target.result;
                if (reportPhotoData) reportPhotoData.value = b64;
                if (reportPhotoPreview) reportPhotoPreview.src = b64;
                if (reportPhotoPreviewContainer) reportPhotoPreviewContainer.style.display = 'block';
                if (btnReportClearPhoto) btnReportClearPhoto.style.display = 'inline-block';
            };
            reader.readAsDataURL(file);
        });
    }

    if (btnReportClearPhoto) {
        btnReportClearPhoto.addEventListener('click', () => {
            if (reportPhotoInput) reportPhotoInput.value = '';
            if (reportPhotoData) reportPhotoData.value = '';
            if (reportPhotoPreview) reportPhotoPreview.src = '';
            if (reportPhotoPreviewContainer) reportPhotoPreviewContainer.style.display = 'none';
            btnReportClearPhoto.style.display = 'none';
        });
    }

    if (btnReportSnapWebcam) {
        btnReportSnapWebcam.addEventListener('click', async () => {
            try {
                let activeStream = (window.safetyGate && window.safetyGate.stream) ? window.safetyGate.stream : null;
                let tempStream = null;
                if (!activeStream) {
                    tempStream = await navigator.mediaDevices.getUserMedia({
                        video: { width: { ideal: 480 }, height: { ideal: 360 } },
                        audio: false
                    });
                    activeStream = tempStream;
                }

                const snapVideo = document.createElement('video');
                snapVideo.srcObject = activeStream;
                snapVideo.muted = true;
                await snapVideo.play();

                const snapCanvas = document.createElement('canvas');
                snapCanvas.width = snapVideo.videoWidth || 480;
                snapCanvas.height = snapVideo.videoHeight || 360;
                const ctx = snapCanvas.getContext('2d');
                ctx.drawImage(snapVideo, 0, 0, snapCanvas.width, snapCanvas.height);
                const b64 = snapCanvas.toDataURL('image/jpeg', 0.82);

                if (tempStream) {
                    tempStream.getTracks().forEach(t => t.stop());
                }

                if (reportPhotoData) reportPhotoData.value = b64;
                if (reportPhotoPreview) reportPhotoPreview.src = b64;
                if (reportPhotoPreviewContainer) reportPhotoPreviewContainer.style.display = 'block';
                if (btnReportClearPhoto) btnReportClearPhoto.style.display = 'inline-block';
                window.showToast('Field camera snapshot captured & attached!', 'success');
            } catch (err) {
                console.warn('Webcam capture error:', err);
                window.showToast('Camera snapshot unavailable. Please select a photo file instead.', 'warning');
            }
        });
    }

    if (reportForm) {
        reportForm.addEventListener('submit', async (e) => {
            e.preventDefault();
            const submitBtn = document.getElementById('submitReportBtn');
            const payload = {
                worker_id: document.getElementById('reportWorkerId').value.trim(),
                site: document.getElementById('reportSite').value,
                location: document.getElementById('reportLocation').value.trim() || 'General Area',
                activity: document.getElementById('reportActivity').value,
                machine_id: document.getElementById('reportMachineId').value.trim(),
                report_type: document.getElementById('reportType').value,
                text: document.getElementById('reportDescription').value.trim(),
                input_channel: voiceManager.isRecording ? 'Voice' : 'Text',
                image_data: reportPhotoData ? reportPhotoData.value : ''
            };

            if (!payload.text) {
                alert('Please describe what happened in the text box or use voice recording.');
                return;
            }

            submitBtn.disabled = true;
            submitBtn.innerHTML = 'Analyzing Risk via NLP...';

            // Check if Offline
            if (!offlineManager.isOnline()) {
                offlineManager.saveToQueue(payload);
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Analyze & Submit Report';
                window.showToast('📡 Saved Offline. Report added to Pending Sync queue.', 'warning');
                document.getElementById('reportDescription').value = '';
                if (btnReportClearPhoto) btnReportClearPhoto.click();
                return;
            }

            try {
                const res = await fetch('/api/reports/analyze', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(payload)
                });
                const data = await res.json();
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Analyze & Submit Report';

                if (data.is_invalid_input) {
                    if (aiResultCard) {
                        aiResultCard.style.display = 'block';
                        aiResultCard.innerHTML = `
                            <div style="background: #fef2f2; border: 2px solid #f87171; border-radius: 8px; padding: 22px; text-align: center;">
                                <div style="font-size: 40px; margin-bottom: 8px;">⚠️</div>
                                <h3 style="font-size: 16px; font-weight: 800; color: #991b1b; margin-bottom: 6px;">Invalid Safety Observation</h3>
                                <p style="font-size: 13px; color: #b91c1c; line-height: 1.5; max-width: 480px; margin: 0 auto 12px auto;">
                                    ${data.error || 'No genuine industrial hazard or safety problem detected regarding the oil camp or worksite.'}
                                </p>
                                <div style="font-size: 12px; color: #7f1d1d; background: rgba(254, 226, 226, 0.6); padding: 8px 14px; border-radius: 6px; display: inline-block;">
                                    <strong>Notice:</strong> Off-topic conversation or casual speech is automatically filtered out. Please describe an actual operational hazard, equipment defect, or field safety issue.
                                </div>
                            </div>
                        `;
                        aiResultCard.scrollIntoView({ behavior: 'smooth' });
                    }
                    window.showToast('Invalid Input: No genuine oilfield safety problem detected.', 'warning');
                    return;
                }

                if (data.success) {
                    renderAIAnalysisResult(data.report);
                    window.showToast(`Report ${data.report.report_uid} analyzed and saved!`, 'success');
                    if (btnReportClearPhoto) btnReportClearPhoto.click();
                    // Cross-portal Live Sync: Refresh dashboard, priority list, and notifications
                    loadDashboard();
                    loadNotifications();
                    loadReportsHistory();
                    loadPriorityList();
                    loadInterventions();
                } else {
                    alert(`Submission failed: ${data.error}`);
                }
            } catch (e) {
                submitBtn.disabled = false;
                submitBtn.innerHTML = 'Analyze & Submit Report';
                // Fallback to offline save
                offlineManager.saveToQueue(payload);
                window.showToast('Network issue encountered. Report saved to offline queue.', 'warning');
            }
        });
    }

    function renderAIAnalysisResult(report) {
        if (!aiResultCard) return;
        aiResultCard.style.display = 'block';

        const isSif = report.sif_potential;
        const levelBadgeClass = report.risk_level === 'CRITICAL' ? 'badge-critical' :
                                report.risk_level === 'HIGH' ? 'badge-high' :
                                report.risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low';

        // Render Explainable Drivers
        const drivers = report.drivers_summary || [];
        const driversHtml = drivers.map(d => `
            <div class="xai-bar-container">
                <div class="xai-bar-label">
                    <span>${d.label}</span>
                    <strong>${d.score} / ${d.max} pts</strong>
                </div>
                <div class="xai-progress-track">
                    <div class="xai-progress-fill" style="width: ${(d.score / d.max) * 100}%; background-color: ${d.score >= 25 ? '#ef4444' : d.score >= 15 ? '#f97316' : '#1e40af'};"></div>
                </div>
                <div style="font-size: 11px; color: #64748b; margin-top: 2px;">${d.desc}</div>
            </div>
        `).join('');

        const precautionsHtml = (report.precautions || []).map((p, idx) => `
            <li style="margin-bottom: 6px;"><strong>${idx + 1}.</strong> ${p}</li>
        `).join('');

        let multilingualHtml = '';
        if (report.is_translated) {
            multilingualHtml = `
                <div style="background: #f0fdf4; border: 1px solid #86efac; border-radius: 8px; padding: 12px; margin-bottom: 14px;">
                    <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                        <span style="font-weight: 700; color: #166534; font-size: 13px;">🌐 MULTILINGUAL SAFETY INGESTION</span>
                        <span class="badge badge-low" style="text-transform: uppercase;">Language: ${report.detected_lang || 'Vernacular'} (${report.trans_method || 'AI Neural'})</span>
                    </div>
                    <div style="font-size: 12px; color: #14532d; margin-bottom: 4px;">
                        <strong>Original Input:</strong> <em>"${report.raw_text}"</em>
                    </div>
                    <div style="font-size: 12px; color: #166534;">
                        <strong>Canonical English:</strong> <em>"${report.canonical_text || report.text}"</em>
                    </div>
                </div>
            `;
        }

        let photoHtml = '';
        if (report.image_data) {
            photoHtml = `
                <div style="margin-bottom: 14px; text-align: center; background: #0f172a; padding: 10px; border-radius: 8px; border: 1px solid #1e293b;">
                    <div style="font-size: 11px; color: #94a3b8; margin-bottom: 6px; text-transform: uppercase; font-weight: 600;">📸 Photographic Evidence Attached</div>
                    <img src="${report.image_data}" alt="Field Evidence" style="max-height: 160px; max-width: 100%; border-radius: 4px; object-fit: contain;">
                </div>
            `;
        }

        aiResultCard.innerHTML = `
            <div style="display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid #e2e8f0; padding-bottom: 12px; margin-bottom: 14px;">
                <div>
                    <span class="badge ${levelBadgeClass}" style="font-size: 13px;">${report.risk_level} RISK (${report.risk_score}%)</span>
                    <span class="badge ${isSif ? 'badge-sif-yes' : 'badge-sif-no'}" style="margin-left: 8px; font-size: 13px;">
                        ${isSif ? '🚨 SIF POTENTIAL: YES' : '✓ SIF POTENTIAL: NO'}
                    </span>
                </div>
                <div style="font-size: 12px; color: #64748b;">
                    Report ID: <strong>${report.report_uid}</strong>
                </div>
            </div>

            ${multilingualHtml}
            ${photoHtml}

            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 12px; margin-bottom: 16px;">
                <div style="background: #f8fafc; padding: 10px; border-radius: 6px;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Detected Hazard</div>
                    <div style="font-size: 13px; font-weight: 700; color: #0f2744; margin-top: 2px;">${report.hazard}</div>
                </div>
                <div style="background: #f8fafc; padding: 10px; border-radius: 6px;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Dangerous Energy</div>
                    <div style="font-size: 13px; font-weight: 700; color: #0f2744; margin-top: 2px;">${report.energy_source}</div>
                </div>
                <div style="background: #f8fafc; padding: 10px; border-radius: 6px;">
                    <div style="font-size: 11px; color: #64748b; text-transform: uppercase;">Worker Exposure</div>
                    <div style="font-size: 13px; font-weight: 700; color: ${report.worker_exposure ? '#ef4444' : '#10b981'}; margin-top: 2px;">
                        ${report.worker_exposure ? '⚠️ Line of Fire (Yes)' : '✓ Controlled (No)'}
                    </div>
                </div>
            </div>

            <div style="background: #f1f5f9; padding: 12px; border-radius: 6px; margin-bottom: 16px;">
                <div style="font-size: 12px; font-weight: 700; color: #0f2744; margin-bottom: 4px;">
                    🧠 EXPLAINABLE AI REASONING (XAI):
                </div>
                <div style="font-size: 12.5px; color: #334155;">
                    ${report.explanation}
                </div>
            </div>

            <div style="margin-bottom: 16px;">
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #475569; margin-bottom: 8px;">
                    Risk Driver Weights:
                </div>
                ${driversHtml}
            </div>

            <div style="background: #eff6ff; border: 1px solid #bfdbfe; border-radius: 6px; padding: 14px; margin-bottom: 14px;">
                <div style="font-size: 13px; font-weight: 700; color: #1e40af; margin-bottom: 6px;">
                    ⚡ REQUIRED IMMEDIATE ACTION:
                </div>
                <div style="font-size: 13px; color: #1e3a8a; font-weight: 600; line-height: 1.5;">
                    ${report.solution}
                </div>
            </div>

            <div>
                <div style="font-size: 12px; font-weight: 700; text-transform: uppercase; color: #475569; margin-bottom: 8px;">
                    Mandatory Safety Precautions:
                </div>
                <ul style="list-style: none; padding-left: 0; font-size: 12.5px; color: #1e293b; line-height: 1.6;">
                    ${precautionsHtml}
                </ul>
            </div>

            <div style="display: flex; justify-content: flex-end; gap: 10px; margin-top: 18px; border-top: 1px solid #e2e8f0; padding-top: 12px;">
                <button class="btn btn-secondary btn-sm" onclick="document.getElementById('aiAnalysisResultCard').style.display='none'">Dismiss</button>
                <button class="btn btn-primary btn-sm" onclick="window.openHSEReviewModal(${report.id})">Open HSE Review</button>
            </div>
        `;

        aiResultCard.scrollIntoView({ behavior: 'smooth' });
    }

    // 7. HSE Risk Priority List
    async function loadPriorityList() {
        const tbody = document.getElementById('priorityTableBody');
        if (!tbody) return;
        if (!tbody.children.length) {
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; padding: 20px;">Loading HSE Risk Priority ranking...</td></tr>';
        }

        try {
            const res = await fetch('/api/hse/priority');
            const items = await res.json();

            tbody.innerHTML = items.map(item => {
                const sifBadge = item.sif_potential ? 
                    '<span class="badge badge-sif-yes">SIF: YES</span>' : 
                    '<span class="badge badge-sif-no">SIF: NO</span>';
                const levelBadge = item.risk_level === 'CRITICAL' ? 'badge-critical' :
                                   item.risk_level === 'HIGH' ? 'badge-high' :
                                   item.risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low';

                let machineBadge = '—';
                if (item.machine_id) {
                    if (item.machine_overdue) {
                        machineBadge = `<span class="badge badge-critical">${item.machine_id} (OVERDUE)</span>`;
                    } else {
                        machineBadge = `<span class="badge badge-low">${item.machine_id}</span>`;
                    }
                }

                return `
                    <tr>
                        <td><strong style="color: #1e40af; font-size: 14px;">#${item.rank}</strong></td>
                        <td><strong>${item.report_uid}</strong></td>
                        <td>${item.site}</td>
                        <td><strong>${item.hazard}</strong></td>
                        <td><span class="badge ${levelBadge}">${item.risk_score}% (${item.risk_level})</span></td>
                        <td>${sifBadge}</td>
                        <td>${item.worker_exposure ? '<span style="color:#ef4444; font-weight:700;">YES</span>' : '<span style="color:#10b981;">NO</span>'}</td>
                        <td>${machineBadge}</td>
                        <td>
                            <button class="btn btn-secondary btn-sm" onclick="window.showWhyRanked('${item.report_uid}', '${item.why_ranked.replace(/'/g, "\\'")}')">
                                ℹ️ Why #${item.rank}?
                            </button>
                        </td>
                        <td>
                            <button class="btn btn-primary btn-sm" onclick="window.openHSEReviewModal(${item.id})">
                                Review
                            </button>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (e) {
            console.error('Failed to load priority items:', e);
            tbody.innerHTML = '<tr><td colspan="10" style="text-align:center; color:#ef4444;">Failed to load risk priority.</td></tr>';
        }
    }

    window.showWhyRanked = function(uid, explanation) {
        alert(`Ranking Rationale for ${uid}:\n\n${explanation}`);
    };

    // 8. Intervention Priority Kanban
    async function loadInterventions() {
        try {
            const res = await fetch('/api/hse/interventions');
            const data = await res.json();

            const renderCards = (list) => {
                if (!list || list.length === 0) {
                    return '<div style="font-size: 12px; color: #94a3b8; text-align: center; padding: 20px;">No pending actions</div>';
                }
                return list.map(item => `
                    <div class="kanban-card">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 6px;">
                            <strong style="font-size: 12px; color: #0f2744;">${item.report_uid}</strong>
                            <span class="badge ${item.risk_level === 'CRITICAL' ? 'badge-critical' : 'badge-high'}">${item.risk_score}%</span>
                        </div>
                        <div style="font-size: 12px; font-weight: 600; color: #1e293b; margin-bottom: 4px;">
                            ${item.hazard}
                        </div>
                        <div style="font-size: 11px; color: #64748b; margin-bottom: 8px;">
                            Site: ${item.site} ${item.machine_id ? `• Machine: ${item.machine_id}` : ''}
                        </div>
                        <div style="font-size: 11px; background: #f8fafc; padding: 6px; border-radius: 4px; margin-bottom: 8px; color: #334155;">
                            ${item.solution}
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #f1f5f9; padding-top: 6px;">
                            <span style="font-size: 10.5px; color: #64748b;">${item.status}</span>
                            <button class="btn btn-primary btn-sm" style="font-size: 10.5px; padding: 2px 8px;" onclick="window.openHSEReviewModal(${item.id})">
                                Intervene
                            </button>
                        </div>
                    </div>
                `).join('');
            };

            const imm = document.getElementById('kanbanImmediate');
            if (imm) imm.innerHTML = renderCards(data.immediate);
            const w24 = document.getElementById('kanbanWithin24h');
            if (w24) w24.innerHTML = renderCards(data.within_24h);
            const w3d = document.getElementById('kanbanWithin3d');
            if (w3d) w3d.innerHTML = renderCards(data.within_3d);
            const pl = document.getElementById('kanbanPlanned');
            if (pl) pl.innerHTML = renderCards(data.planned);
        } catch (e) {
            console.error('Failed loading interventions:', e);
        }
    }

    // 9. Machine Maintenance & Interlock Simulation
    async function loadMachines() {
        const container = document.getElementById('machinesTableBody');
        if (!container) return;

        try {
            const res = await fetch('/api/machines');
            const machines = await res.json();

            container.innerHTML = machines.map(m => `
                <tr>
                    <td><strong>${m.id}</strong></td>
                    <td>${m.name}</td>
                    <td>${m.site}</td>
                    <td>${m.last_maintenance}</td>
                    <td><strong>${m.due_date}</strong></td>
                    <td>
                        <span class="badge ${m.overdue ? 'badge-critical' : 'badge-low'}">
                            ${m.urgency}
                        </span>
                    </td>
                    <td><span class="badge ${m.base_risk >= 85 ? 'badge-critical' : m.base_risk >= 65 ? 'badge-high' : 'badge-medium'}">${m.base_risk}%</span></td>
                    <td>
                        <span class="badge ${m.locked ? 'badge-critical' : 'badge-low'}">
                            ${m.locked ? '🔒 LOCKED' : '✓ OPERATING'}
                        </span>
                    </td>
                    <td>
                        <button class="btn ${m.locked ? 'btn-secondary' : 'btn-danger'} btn-sm" onclick="window.toggleMachineLock('${m.id}')">
                            ${m.locked ? 'Release Lock' : 'Simulate Interlock'}
                        </button>
                    </td>
                </tr>
            `).join('');
        } catch (e) {
            console.error('Failed loading machines:', e);
        }
    }

    window.toggleMachineLock = async function(machineId) {
        try {
            const res = await fetch(`/api/machines/toggle_lock/${machineId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reason: 'Simulated HSE emergency trip / overdue maintenance lockout' })
            });
            const data = await res.json();
            if (data.success) {
                window.showToast(`Machine ${machineId} interlock updated: ${data.locked ? 'LOCKED' : 'UNLOCKED'}`, data.locked ? 'warning' : 'success');
                loadMachines();
                loadDashboard();
            }
        } catch (e) {
            console.error('Interlock toggle error:', e);
        }
    };

    // 10. Site Conditions & Weather Context
    async function loadSiteConditions() {
        const container = document.getElementById('siteConditionsGrid');
        const gateStatusText = document.getElementById('gateWeatherStatusText');
        const gateBadge = document.getElementById('gateWeatherBadge');
        const adversePopup = document.getElementById('adverseWeatherPopup');
        const adversePopupText = document.getElementById('adverseWeatherPopupText');

        if (container && !container.children.length) {
            container.innerHTML = '<div style="grid-column: 1 / -1; text-align:center; padding: 20px;">Fetching live meteorological observations for OIL fields...</div>';
        }

        try {
            let weatherUrl = '/api/site_conditions';
            if (window.userDeviceCoords && window.userDeviceCoords.latitude && window.userDeviceCoords.longitude) {
                weatherUrl += `?lat=${window.userDeviceCoords.latitude}&lon=${window.userDeviceCoords.longitude}`;
            }
            const res = await fetch(weatherUrl);
            const sites = await res.json();

            if (container) {
                container.innerHTML = sites.map(s => {
                    const isLive = s.is_live !== false;
                    const isGps = s.is_device_gps === true;
                    const statusBadge = s.condition_status === 'UNSAFE' ? 'badge-critical' : 
                                        s.condition_status === 'CAUTION' ? 'badge-medium' : 'badge-low';
                    const borderColor = isGps ? '#2563eb' : (s.condition_status === 'UNSAFE' ? '#ef4444' : 
                                        s.condition_status === 'CAUTION' ? '#f59e0b' : '#10b981');

                    return `
                        <div class="card" style="border-left: 4px solid ${borderColor}; ${isGps ? 'background: linear-gradient(180deg, #f0fdf4 0%, #ffffff 100%); border-top: 1px solid #93c5fd;' : ''}">
                            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 12px;">
                                <div>
                                    <h3 style="font-size: 16px; font-weight: 700; color: #0f2744;">
                                        ${s.site_name}
                                    </h3>
                                    <div style="font-size: 11px; color: #64748b; margin-top: 2px;">
                                        ${isGps ? '<span style="color:#2563eb; font-weight:700;">📍 YOUR LIVE DEVICE LOCATION (OPEN-METEO)</span> • ' : ''}
                                        ${isLive ? '<span style="color:#059669; font-weight:700;">● LIVE METEOROLOGICAL FEED</span>' : '<span style="color:#64748b;">CACHED OFFLINE WEATHER</span>'}
                                        ${s.last_updated ? ` • Updated: ${s.last_updated}` : ''}
                                    </div>
                                </div>
                                <div style="display: flex; gap: 6px; align-items: center;">
                                    ${isGps ? '<span class="badge" style="background:#2563eb; color:#fff; font-size:11px;">Device GPS</span>' : ''}
                                    <span class="badge ${statusBadge}" style="font-size: 13px; padding: 5px 12px;">
                                        ${s.condition_status}
                                    </span>
                                </div>
                            </div>

                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; font-size: 12.5px; margin-bottom: 12px;">
                                <div style="background: #f8fafc; padding: 8px 12px; border-radius: 6px;">
                                    <span style="color: #64748b;">Temperature:</span> 
                                    <strong style="font-size: 14px; float: right; color: #0f2744;">${s.temperature}°C</strong>
                                </div>
                                <div style="background: #f8fafc; padding: 8px 12px; border-radius: 6px;">
                                    <span style="color: #64748b;">Relative Humidity:</span> 
                                    <strong style="font-size: 14px; float: right; color: #0f2744;">${s.humidity}%</strong>
                                </div>
                                <div style="background: #f8fafc; padding: 8px 12px; border-radius: 6px;">
                                    <span style="color: #64748b;">Wind Velocity:</span> 
                                    <strong style="font-size: 14px; float: right; color: #0f2744;">${s.wind_speed} km/h</strong>
                                </div>
                                <div style="background: #f8fafc; padding: 8px 12px; border-radius: 6px;">
                                    <span style="color: #64748b;">Condition:</span> 
                                    <strong style="font-size: 13px; float: right; color: #0f2744;">${s.rain_status}</strong>
                                </div>
                            </div>

                            <div style="background: #eff6ff; border: 1px solid #bfdbfe; padding: 10px 12px; border-radius: 6px; font-size: 12px; margin-bottom: 10px; color: #1e40af;">
                                <div>
                                    ⚡ Context Risk Multiplier: <strong>${s.risk_multiplier}x</strong>
                                    ${s.risk_multiplier > 1.0 ? '<span style="color:#b91c1c; font-weight:700;"> (Adverse weather elevated risk)</span>' : ' (Nominal)'}
                                </div>
                                <div style="font-size: 11.5px; color: #1e3a8a; margin-top: 4px; line-height: 1.4;">
                                    <strong>HSE Guidance:</strong> ${s.advice || 'Standard operations permitted.'}
                                </div>
                            </div>
                        </div>
                    `;
                }).join('');
            }

            // Sync Worker Entry Gate Weather Clearance Banner & Adverse Alert
            if (sites && sites.length > 0) {
                const primarySite = sites[0];
                const isAdverse = sites.some(s => s.condition_status === 'UNSAFE' || s.condition_status === 'CAUTION' || s.wind_speed > 30);
                
                if (gateStatusText) {
                    gateStatusText.innerText = `${primarySite.site_name}: ${primarySite.temperature}°C • Wind: ${primarySite.wind_speed} km/h • Humidity: ${primarySite.humidity}% • Condition: ${primarySite.rain_status} — Weather conditions are ${isAdverse ? 'ALERT: Adverse weather detected. Caution advised.' : 'NOMINAL & SAFE for rig entry.'}`;
                }

                if (gateBadge) {
                    if (isAdverse) {
                        gateBadge.className = 'badge badge-critical';
                        gateBadge.innerText = '⚠️ ADVERSE WEATHER ACTIVE';
                    } else {
                        gateBadge.className = 'badge badge-low';
                        gateBadge.innerText = 'WEATHER NOMINAL';
                    }
                }

                if (adversePopup) {
                    if (isAdverse) {
                        adversePopup.style.display = 'block';
                        if (adversePopupText) {
                            adversePopupText.innerText = `Elevated Wind Velocity (${primarySite.wind_speed} km/h) or Rain (${primarySite.rain_status}) detected at ${primarySite.site_name}. Crane hoisting & Working at Height are SUSPENDED. All workers must equip anti-slip boots, waterproof hoods, and tethering gear.`;
                        }
                    } else {
                        adversePopup.style.display = 'none';
                    }
                }
            }

        } catch (e) {
            console.error('Failed loading site conditions:', e);
            if (container) {
                container.innerHTML = '<div style="color:#ef4444; padding:20px;">Failed to load site weather conditions.</div>';
            }
        }
    }

    window.testToggleAdverseWeather = function() {
        const adversePopup = document.getElementById('adverseWeatherPopup');
        const gateBadge = document.getElementById('gateWeatherBadge');
        const gateStatusText = document.getElementById('gateWeatherStatusText');

        if (!adversePopup) return;

        if (adversePopup.style.display === 'none' || !adversePopup.style.display) {
            adversePopup.style.display = 'block';
            if (gateBadge) {
                gateBadge.className = 'badge badge-critical';
                gateBadge.innerText = '⚠️ ADVERSE WEATHER ACTIVE';
            }
            if (gateStatusText) {
                gateStatusText.innerText = 'Duliajan Central Field: 29°C • Wind: 38 km/h (GUSTS) • Monsoon Storm Rain — ADVERSE WEATHER ALERT: High-elevation rig operations halted.';
            }
            if (window.showToast) {
                window.showToast('⛈️ ADVERSE WEATHER ALERT: High wind & storm triggered for Smart Entry Gate!', 'danger');
            }
        } else {
            adversePopup.style.display = 'none';
            if (gateBadge) {
                gateBadge.className = 'badge badge-low';
                gateBadge.innerText = 'WEATHER NOMINAL';
            }
            if (gateStatusText) {
                gateStatusText.innerText = 'Duliajan Central Field: 28°C • Wind: 12 km/h • Humidity: 68% • Clear Sky — Weather conditions are NOMINAL & SAFE for rig entry.';
            }
            if (window.showToast) {
                window.showToast('🌤️ Weather conditions restored to Nominal & Safe.', 'success');
            }
        }
    };

    window.refreshLiveWeather = async function() {
        if (window.showToast) window.showToast('Fetching latest meteorological observations...', 'info');
        try {
            const res = await fetch('/api/site_conditions/refresh', { method: 'POST' });
            const data = await res.json();
            if (data.success) {
                if (window.showToast) window.showToast('Live weather updated successfully!', 'success');
                loadSiteConditions();
            }
        } catch (e) {
            console.error('Weather refresh error:', e);
        }
    };

    // 11. HSE Review Modal & Human-in-the-Loop Actions
    const reviewModal = document.getElementById('hseReviewModal');
    window.openHSEReviewModal = async function(reportId) {
        try {
            const res = await fetch(`/api/reports/${reportId}`);
            const report = await res.json();
            currentReportUnderReview = report;

            document.getElementById('modalReportUid').innerText = report.report_uid;
            document.getElementById('modalRawText').innerText = report.raw_text;
            document.getElementById('modalHazard').value = report.hazard;
            document.getElementById('modalRiskScore').value = report.risk_score;
            document.getElementById('modalSifSelect').value = report.sif_potential ? '1' : '0';
            document.getElementById('modalResponsible').value = report.responsible_role || 'Area Safety Officer';
            document.getElementById('modalActionAssigned').value = report.solution;
            document.getElementById('modalNotes').value = '';

            // Render Photographic Evidence Attachment if available
            const photoContainer = document.getElementById('modalReportPhotoContainer');
            const photoImg = document.getElementById('modalReportPhoto');
            if (photoContainer && photoImg) {
                if (report.image_data) {
                    photoImg.src = report.image_data;
                    photoContainer.style.display = 'block';
                } else {
                    photoContainer.style.display = 'none';
                }
            }

            // Render Lifecycle breadcrumbs
            renderLifecycleTracker(report.status);

            if (reviewModal) reviewModal.classList.add('show');
        } catch (e) {
            console.error('Failed to load report for review:', e);
        }
    };

    window.closeHSEReviewModal = function() {
        if (reviewModal) reviewModal.classList.remove('show');
    };

    window.deleteActiveReport = async function() {
        if (!currentReportUnderReview || !currentReportUnderReview.id) return;
        const rId = currentReportUnderReview.id;
        const rUid = currentReportUnderReview.report_uid;
        if (!confirm(`Are you sure you want to permanently delete report ${rUid}? This action removes it from the HSE system.`)) {
            return;
        }

        try {
            const res = await fetch(`/api/reports/${rId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                window.showToast(data.message, 'success');
                window.closeHSEReviewModal();
                loadReportsHistory();
                loadPriorityList();
                loadInterventions();
                loadDashboard();
            } else {
                window.showToast(data.error || 'Failed to delete report', 'warning');
            }
        } catch (err) {
            console.error('Error deleting report:', err);
            window.showToast('Network error while deleting report.', 'critical');
        }
    };

    window.deleteReportById = async function(reportId) {
        if (!confirm(`Are you sure you want to permanently delete report ID #${reportId}?`)) return;
        try {
            const res = await fetch(`/api/reports/${reportId}`, { method: 'DELETE' });
            const data = await res.json();
            if (data.success) {
                window.showToast(data.message, 'success');
                loadReportsHistory();
                loadPriorityList();
                loadInterventions();
                loadDashboard();
            } else {
                window.showToast(data.error || 'Failed to delete report', 'warning');
            }
        } catch (err) {
            console.error('Error deleting report:', err);
        }
    };

    function renderLifecycleTracker(currentStatus) {
        const container = document.getElementById('modalLifecycleTracker');
        if (!container) return;

        const stages = ['NEW', 'AI ANALYZED', 'HSE REVIEW', 'ACTION REQUIRED', 'ACTION IN PROGRESS', 'RESOLVED', 'HSE VERIFIED', 'CLOSED'];
        const currentIdx = stages.indexOf(currentStatus);

        container.innerHTML = stages.map((st, idx) => {
            const isCompleted = idx <= currentIdx;
            const isCurrent = idx === currentIdx;
            return `
                <div style="display: flex; flex-direction: column; align-items: center; flex: 1; position: relative;">
                    <div style="width: 22px; height: 22px; border-radius: 50%; background: ${isCurrent ? '#1e40af' : isCompleted ? '#10b981' : '#e2e8f0'}; color: #ffffff; display: flex; align-items: center; justify-content: center; font-size: 10px; font-weight: 700; z-index: 2;">
                        ${isCompleted ? '✓' : idx + 1}
                    </div>
                    <div style="font-size: 9px; font-weight: 600; color: ${isCurrent ? '#1e40af' : isCompleted ? '#0f172a' : '#94a3b8'}; text-align: center; margin-top: 4px;">
                        ${st}
                    </div>
                </div>
            `;
        }).join('');
    }

    window.submitReviewDecision = async function(decision) {
        if (!currentReportUnderReview) return;
        const reportId = currentReportUnderReview.id;

        const payload = {
            decision: decision,
            officer_name: currentUser.name,
            corrected_hazard: document.getElementById('modalHazard').value,
            corrected_risk: parseInt(document.getElementById('modalRiskScore').value, 10),
            corrected_sif: document.getElementById('modalSifSelect').value === '1',
            responsible_person: document.getElementById('modalResponsible').value,
            action_assigned: document.getElementById('modalActionAssigned').value,
            notes: document.getElementById('modalNotes').value
        };

        try {
            const res = await fetch(`/api/hse/review/${reportId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            const data = await res.json();
            if (data.success) {
                window.showToast(`HSE Review recorded: ${decision}`, 'success');
                window.closeHSEReviewModal();
                loadPriorityList();
                loadInterventions();
                loadDashboard();
                loadLearningStats();
            }
        } catch (e) {
            console.error('Review submit failed:', e);
        }
    };

    // 12. Continuous Learning & AI Feedback Stats
    async function loadLearningStats() {
        const elPred = document.getElementById('learnPredictionsCount');
        if (!elPred) return;
        try {
            const res = await fetch('/api/hse/learning_stats');
            const data = await res.json();

            if (elPred) elPred.innerText = data.total_ai_predictions;
            const elAcc = document.getElementById('learnAcceptedCount');
            if (elAcc) elAcc.innerText = data.hse_accepted;
            const elCorr = document.getElementById('learnCorrectedCount');
            if (elCorr) elCorr.innerText = data.hse_corrected;
            const elInit = document.getElementById('learnInitialAcc');
            if (elInit) elInit.innerText = data.initial_model_accuracy;
            const elCurr = document.getElementById('learnCurrentAcc');
            if (elCurr) elCurr.innerText = data.current_model_accuracy;

            const feedbackTbody = document.getElementById('learningFeedbackTableBody');
            if (feedbackTbody) {
                feedbackTbody.innerHTML = (data.recent_feedback || []).map(f => `
                    <tr>
                        <td><strong>#${f.report_id}</strong></td>
                        <td>${f.feedback_note}</td>
                        <td><span class="badge badge-low">${f.model_version}</span></td>
                        <td style="font-size: 11px; color: #64748b;">${f.timestamp}</td>
                    </tr>
                `).join('');
            }
        } catch (e) {
            console.error('Failed loading learning stats:', e);
        }
    }

    // 13. Reports History
    async function loadReportsHistory() {
        const tbody = document.getElementById('reportsHistoryTableBody');
        if (!tbody) return;

        const riskFilter = document.getElementById('historyRiskFilter') ? document.getElementById('historyRiskFilter').value : '';
        const sifFilter = document.getElementById('historySifFilter') ? document.getElementById('historySifFilter').value : '';
        const searchVal = document.getElementById('globalSearchInput') ? document.getElementById('globalSearchInput').value : '';

        let url = `/api/reports?search=${encodeURIComponent(searchVal)}`;
        if (riskFilter) url += `&risk_level=${riskFilter}`;
        if (sifFilter) url += `&sif=${sifFilter}`;

        try {
            const res = await fetch(url);
            const reports = await res.json();

            tbody.innerHTML = reports.map(r => `
                <tr>
                    <td><strong>${r.report_uid}</strong></td>
                    <td style="font-size: 11px; color: #64748b;">${r.created_at}</td>
                    <td>${r.worker_id}</td>
                    <td>${r.site}</td>
                    <td><span class="badge ${r.input_channel === 'Voice' ? 'badge-high' : 'badge-low'}">${r.input_channel}</span></td>
                    <td><strong>${r.hazard}</strong></td>
                    <td><span class="badge ${r.risk_level === 'CRITICAL' ? 'badge-critical' : r.risk_level === 'HIGH' ? 'badge-high' : r.risk_level === 'MEDIUM' ? 'badge-medium' : 'badge-low'}">${r.risk_score}% (${r.risk_level})</span></td>
                    <td>${r.sif_potential ? '<span class="badge badge-sif-yes">YES</span>' : '<span class="badge badge-sif-no">NO</span>'}</td>
                    <td><span class="badge ${r.status === 'RESOLVED' || r.status === 'CLOSED' ? 'badge-low' : 'badge-high'}">${r.status}</span></td>
                    <td>
                        <div style="display: flex; gap: 6px; align-items: center;">
                            <button class="btn btn-secondary btn-sm" style="padding: 3px 8px; font-size: 11.5px;" onclick="window.openHSEReviewModal(${r.id})">
                                🔍 Details
                            </button>
                            <button class="btn btn-outline btn-sm" style="color: #ef4444; border-color: #ef4444; padding: 3px 7px; font-size: 11px;" title="Delete Report" onclick="window.deleteReportById(${r.id})">
                                🗑️
                            </button>
                        </div>
                    </td>
                </tr>
            `).join('');
        } catch (e) {
            console.error('Failed loading reports history:', e);
        }
    }

    // 14. Global Search & Notifications
    const globalSearchInput = document.getElementById('globalSearchInput');
    let searchDebounceTimer = null;
    if (globalSearchInput) {
        globalSearchInput.addEventListener('input', () => {
            if (searchDebounceTimer) clearTimeout(searchDebounceTimer);
            searchDebounceTimer = setTimeout(() => {
                loadReportsHistory();
            }, 150);
        });
    }

    async function loadNotifications() {
        try {
            const res = await fetch('/api/notifications');
            const notifs = await res.json();
            const unread = notifs.filter(n => !n.read_status).length;
            const badgeEl = document.getElementById('notifBadge');
            if (badgeEl) {
                badgeEl.innerText = unread;
                badgeEl.style.display = unread > 0 ? 'flex' : 'none';
            }

            const listEl = document.getElementById('notificationsDropdownList');
            if (listEl) {
                listEl.innerHTML = notifs.map(n => `
                    <div style="padding: 10px 14px; border-bottom: 1px solid #f1f5f9; font-size: 12px; background: ${n.read_status ? '#ffffff' : '#f8fafc'};">
                        <div style="font-weight: 700; color: ${n.type === 'CRITICAL' ? '#ef4444' : '#0f2744'}; margin-bottom: 2px;">
                            ${n.title}
                        </div>
                        <div style="color: #475569; line-height: 1.4;">${n.message}</div>
                        <div style="font-size: 10.5px; color: #94a3b8; margin-top: 4px;">${n.timestamp}</div>
                    </div>
                `).join('');
            }
        } catch (e) {
            console.error('Failed loading notifications:', e);
        }
    }

    const notifBtn = document.getElementById('notifBellBtn');
    const notifModal = document.getElementById('notificationsModal');
    if (notifBtn && notifModal) {
        notifBtn.addEventListener('click', () => {
            notifModal.classList.toggle('show');
            // Mark read on open
            fetch('/api/notifications/mark_read', { method: 'POST' }).then(() => {
                const badgeEl = document.getElementById('notifBadge');
                if (badgeEl) badgeEl.style.display = 'none';
            });
        });
    }

    // Offline event listener to reload
    const handleSyncRefresh = () => {
        loadDashboard();
        loadPriorityList();
        loadReportsHistory();
        loadSiteConditions();
    };
    window.addEventListener('sifguard:synced', handleSyncRefresh);
    window.addEventListener('surakshax:synced', handleSyncRefresh);

    function escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    // 15. Personnel Profile & Safety Dossier (Dedicated Registered User Record)
    async function loadUserProfile() {
        const avatarEl = document.getElementById('dossierAvatar');
        const nameEl = document.getElementById('dossierName');
        const roleBadgeEl = document.getElementById('dossierRoleBadge');
        const workerIdEl = document.getElementById('dossierWorkerId');
        const usernameEl = document.getElementById('dossierUsername');
        const deptEl = document.getElementById('dossierDepartment');
        const siteEl = document.getElementById('dossierSite');
        const phoneEl = document.getElementById('dossierPhone');
        const addrEl = document.getElementById('dossierAddress');
        const createdEl = document.getElementById('dossierCreatedAt');
        const faceBadgeEl = document.getElementById('dossierFaceBadge');

        const kpiReports = document.getElementById('dossierKpiReports');
        const kpiSifs = document.getElementById('dossierKpiSifs');
        const kpiClosed = document.getElementById('dossierKpiClosed');
        const kpiRepairs = document.getElementById('dossierKpiRepairs');

        const workerView = document.getElementById('dossierWorkerView');
        const hseView = document.getElementById('dossierHSEView');

        try {
            if (!currentUser) {
                if (avatarEl) avatarEl.innerText = '👤';
                if (nameEl) nameEl.innerText = 'Not Signed In';
                if (workerIdEl) workerIdEl.innerText = '—';
                if (usernameEl) usernameEl.innerText = '—';
                if (roleBadgeEl) roleBadgeEl.innerText = 'GUEST';
                if (deptEl) deptEl.innerText = '—';
                if (siteEl) siteEl.innerText = '—';
                if (phoneEl) phoneEl.innerText = '—';
                if (addrEl) addrEl.innerText = '—';
                if (createdEl) createdEl.innerText = '—';
                return;
            }

            const userId = currentUser.db_id || currentUser.id || currentUser.username || '';
            const res = await fetch(`/api/auth/user_dossier?user_id=${encodeURIComponent(userId)}`);
            const data = await res.json();
            if (!data.success) {
                console.warn('Could not load user dossier:', data.error);
                if (avatarEl) avatarEl.innerText = (currentUser.name || 'U').charAt(0).toUpperCase();
                if (nameEl) nameEl.innerText = currentUser.name || 'Personnel';
                if (roleBadgeEl) roleBadgeEl.innerText = currentUser.role || 'WORKER';
                if (workerIdEl) workerIdEl.innerText = currentUser.worker_id || currentUser.id || '—';
                if (usernameEl) usernameEl.innerText = currentUser.username || '—';
                return;
            }

            const u = data.user || {};
            const comp = data.compliance || {};
            const stats = data.stats || {};
            const reports = data.past_reports || [];
            const reviews = data.hse_reviews || [];
            const repairs = data.repair_reviews || [];

            // Identity info
            if (avatarEl) avatarEl.innerText = (u.name || currentUser.name || 'U').charAt(0).toUpperCase();
            if (nameEl) nameEl.innerText = u.name || currentUser.name || 'Personnel';
            if (roleBadgeEl) roleBadgeEl.innerText = u.role || currentUser.role || 'WORKER';
            if (workerIdEl) workerIdEl.innerText = u.id || u.worker_id || currentUser.worker_id || currentUser.id || 'N/A';
            if (usernameEl) usernameEl.innerText = u.username || currentUser.username || 'user';
            if (deptEl) deptEl.innerText = u.department || currentUser.department || 'Operations';
            if (siteEl) siteEl.innerText = u.site || currentUser.site || 'Site A (Duliajan)';
            if (phoneEl) phoneEl.innerText = u.phone || currentUser.phone || 'N/A';
            if (addrEl) addrEl.innerText = u.address || currentUser.address || 'Field Base';
            if (createdEl) createdEl.innerText = u.created_at || 'Registered';

            // Biometric badge
            if (faceBadgeEl) {
                if (u.face_enrolled) {
                    faceBadgeEl.className = 'badge badge-low';
                    faceBadgeEl.innerHTML = '✓ 📷 Biometrics Enrolled &amp; Trained';
                } else {
                    faceBadgeEl.className = 'badge badge-high';
                    faceBadgeEl.innerHTML = '⚠️ Biometrics Pending Enrollment';
                }
            }

            // Compliance status
            const setComp = (id, valid, okText, failText) => {
                const el = document.getElementById(id);
                if (!el) return;
                if (valid) {
                    el.style.color = '#059669';
                    el.innerText = `✓ ${okText}`;
                } else {
                    el.style.color = '#ef4444';
                    el.innerText = `⚠️ ${failText}`;
                }
            };
            setComp('dossierTrainingCert', comp.training_valid, 'Certified Valid', 'Overdue / Required');
            setComp('dossierMedicalCert', comp.cert_valid, 'Fit for Duty', 'Medical Exam Overdue');
            setComp('dossierPpeHelmet', comp.helmet_assigned, 'Hard Hat Verified', 'Missing Hard Hat');
            if (document.getElementById('dossierPpeGoggles')) {
                setComp('dossierPpeGoggles', comp.goggles_assigned, 'Impact Goggles Verified', 'Missing Goggles');
            }
            setComp('dossierPpeGloves', comp.gloves_assigned, 'Industrial Gloves Verified', 'Missing Gloves');
            setComp('dossierPpeShoes', comp.shoes_assigned, 'Safety Boots Verified', 'Missing Boots');

            const allComp = comp.training_valid && comp.cert_valid && comp.helmet_assigned && comp.vest_assigned && comp.gloves_assigned && comp.shoes_assigned;
            const compStatusEl = document.getElementById('dossierComplianceStatus');
            if (compStatusEl) {
                compStatusEl.className = allComp ? 'badge badge-low' : 'badge badge-critical';
                compStatusEl.innerText = allComp ? '100% COMPLIANT' : 'ACTION REQUIRED';
            }

            // KPIs
            if (kpiReports) kpiReports.innerText = stats.total_reports !== undefined ? stats.total_reports : reports.length;
            if (kpiSifs) kpiSifs.innerText = stats.critical_sifs !== undefined ? stats.critical_sifs : 0;
            if (kpiClosed) kpiClosed.innerText = stats.closed_actions !== undefined ? stats.closed_actions : 0;
            if (kpiRepairs) kpiRepairs.innerText = stats.repairs_signed !== undefined ? stats.repairs_signed : repairs.length;

            const isHseOrAdmin = (u.role || '').toUpperCase().includes('HSE') || (u.role || '').toUpperCase().includes('ADMIN');

            if (isHseOrAdmin) {
                if (hseView) hseView.style.display = 'block';
                if (workerView) workerView.style.display = 'none';

                const hseBadge = document.getElementById('dossierHseReviewCount');
                if (hseBadge) hseBadge.innerText = `${reviews.length} Audits`;

                const hseTable = document.getElementById('dossierHseReviewsTableBody');
                if (hseTable) {
                    if (reviews.length === 0) {
                        hseTable.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 24px;">No human-in-the-loop review audits recorded yet for this officer.</td></tr>`;
                    } else {
                        hseTable.innerHTML = reviews.map(rev => {
                            const decColor = rev.decision === 'ACCEPTED' ? 'badge-low' : (rev.decision === 'CORRECTED' ? 'badge-high' : 'badge-critical');
                            return `
                                <tr>
                                    <td><code>#REV-${rev.id}</code></td>
                                    <td>
                                        <strong style="color: #0f2744;">${escapeHtml(rev.report_uid || ('REP-' + rev.report_id))}</strong><br>
                                        <small style="color: #64748b;">${escapeHtml(rev.hazard || 'Hazard Observation')}</small>
                                    </td>
                                    <td><span class="badge ${decColor}">${rev.decision}</span></td>
                                    <td>
                                        <span style="color: #64748b;">${rev.initial_risk_score || 0}%</span> ➔ <strong style="color: #0f172a;">${rev.final_risk_score || 0}%</strong>
                                    </td>
                                    <td>
                                        ${rev.sif_potential ? '<span class="badge badge-critical">YES (SIF Precursor)</span>' : '<span class="badge badge-low">NO (Controlled)</span>'}
                                    </td>
                                    <td>
                                        <div style="max-width: 260px; font-size: 12px; color: #334155; line-height: 1.4;">
                                            ${escapeHtml(rev.notes || rev.action_assigned || 'Concurred with automated AI model recommendations.')}
                                        </div>
                                    </td>
                                    <td><small style="color: #64748b;">${rev.reviewed_at || 'Recent'}</small></td>
                                </tr>
                            `;
                        }).join('');
                    }
                }
            } else {
                if (workerView) workerView.style.display = 'block';
                if (hseView) hseView.style.display = 'none';

                const repBadge = document.getElementById('dossierWorkerReportCount');
                if (repBadge) repBadge.innerText = `${reports.length} Reports`;

                const repTable = document.getElementById('dossierWorkerReportsTableBody');
                if (repTable) {
                    if (reports.length === 0) {
                        repTable.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 24px;">No safety observations reported yet by this personnel.</td></tr>`;
                    } else {
                        repTable.innerHTML = reports.map(r => {
                            const riskBadgeClass = (r.risk_score >= 80) ? 'badge-critical' : (r.risk_score >= 60 ? 'badge-high' : 'badge-low');
                            const statusBadgeClass = (r.status === 'VERIFIED & CLOSED') ? 'badge-low' : (r.status === 'IN PROGRESS' ? 'badge-high' : 'badge-critical');
                            return `
                                <tr>
                                    <td>
                                        <code style="font-weight: 700; color: #0284c7;">${escapeHtml(r.report_uid || ('REP-' + r.id))}</code>
                                        ${r.sif_potential ? '<br><span class="badge badge-critical" style="font-size: 9px; padding: 2px 4px; margin-top: 2px;">SIF PRECURSOR</span>' : ''}
                                    </td>
                                    <td>
                                        <div style="font-size: 12px; font-weight: 600;">${r.created_at ? r.created_at.substring(0, 10) : 'Recent'}</div>
                                        <small style="color: #64748b;">${escapeHtml(r.site || 'Site A')}</small>
                                    </td>
                                    <td>
                                        <div style="max-width: 250px; font-size: 12px; color: #1e293b; line-height: 1.35;">
                                            ${escapeHtml(r.raw_text || 'Observation narrative')}
                                        </div>
                                    </td>
                                    <td>
                                        <strong style="color: #0f2744; font-size: 12.5px;">${escapeHtml(r.hazard || 'General Hazard')}</strong><br>
                                        <small style="color: #64748b;">Energy: ${escapeHtml(r.energy_source || 'Mechanical')}</small>
                                    </td>
                                    <td>
                                        <span class="badge ${riskBadgeClass}">${r.risk_score || 0}% (${r.risk_level || 'MED'})</span>
                                    </td>
                                    <td>
                                        <div style="max-width: 240px; font-size: 11.5px; color: #0f766e; background: #f0fdfa; padding: 5px 8px; border-radius: 4px; border: 1px solid #ccfbf1; line-height: 1.35;">
                                            <strong>Action:</strong> ${escapeHtml(r.solution || r.precautions || 'Enforce safety barriers & PPE')}
                                        </div>
                                    </td>
                                    <td>
                                        <span class="badge ${statusBadgeClass}">${r.status || 'REPORTED'}</span>
                                    </td>
                                </tr>
                            `;
                        }).join('');
                    }
                }
            }

            // Post Repair common list
            const repTableCount = document.getElementById('dossierRepairsCount');
            if (repTableCount) repTableCount.innerText = `${repairs.length} Sign-Offs`;

            const repairsTable = document.getElementById('dossierRepairsTableBody');
            if (repairsTable) {
                if (repairs.length === 0) {
                    repairsTable.innerHTML = `<tr><td colspan="7" style="text-align: center; color: #94a3b8; padding: 20px;">No machine repair sign-offs recorded for this personnel.</td></tr>`;
                } else {
                    repairsTable.innerHTML = repairs.map(rep => `
                        <tr>
                            <td><code>${escapeHtml(rep.machine_id)}</code></td>
                            <td><strong style="color: #0f2744;">${escapeHtml(rep.activity)}</strong></td>
                            <td>${escapeHtml(rep.worker_name)} <small style="color:#64748b;">(${escapeHtml(rep.worker_id)})</small></td>
                            <td>
                                <span class="badge ${rep.guard_installed ? 'badge-low' : 'badge-critical'}">Guard: ${rep.guard_installed ? 'OK' : 'MISSING'}</span>
                                <span class="badge ${rep.interlock_tested ? 'badge-low' : 'badge-critical'}">Interlock: ${rep.interlock_tested ? 'OK' : 'FAIL'}</span>
                            </td>
                            <td>
                                ${rep.cleared_for_operation ? '<span class="badge badge-low">✓ CLEARED SAFE</span>' : '<span class="badge badge-critical">⛔ INTERLOCKED</span>'}
                            </td>
                            <td>
                                <div style="max-width: 220px; font-size: 11.5px; color: #475569;">${escapeHtml(rep.notes || 'Equipment cleared following SOP.')}</div>
                            </td>
                            <td><small style="color: #64748b;">${rep.created_at || 'Recent'}</small></td>
                        </tr>
                    `).join('');
                }
            }

        } catch (err) {
            console.error('Error loading user profile dossier:', err);
        }
    }
    window.loadUserProfile = loadUserProfile;

    // Initial boot & Cross-Portal Live Synchronization
    async function initAuthAndBoot() {
        // Immediately load site conditions without blocking on geolocation prompt/timeout
        loadSiteConditions();
        loadDashboard();
        loadNotifications();
        if (!window.isWorkerPortalPage && document.getElementById('riskDistChart')) {
            safetyCharts.initAll();
        }
        if (typeof syncSafetyGateCameraState === 'function') {
            syncSafetyGateCameraState();
        }

        // Non-blocking Live Geolocation acquisition for Open-Meteo GPS weather
        if (navigator.geolocation) {
            navigator.geolocation.getCurrentPosition(
                (pos) => {
                    window.userDeviceCoords = {
                        latitude: pos.coords.latitude,
                        longitude: pos.coords.longitude
                    };
                    loadSiteConditions();
                },
                () => {},
                { timeout: 4000, maximumAge: 300000 }
            );
        }

        // Cross-Portal Live Sync Poller (pauses automatically when browser tab is hidden)
        setInterval(() => {
            if (document.hidden) return;
            loadDashboard();
            loadNotifications();

            const tabReports = document.getElementById('tab-reports');
            if (tabReports && tabReports.classList.contains('active')) {
                loadReportsHistory();
            }

            const tabPriority = document.getElementById('tab-priority');
            if (tabPriority && tabPriority.classList.contains('active')) {
                loadPriorityList();
            }

            const tabInterventions = document.getElementById('tab-intervention');
            if (tabInterventions && tabInterventions.classList.contains('active')) {
                loadInterventions();
            }
        }, 4000);

        // Listen for offline queue sync & gossip events
        window.addEventListener('surakshax:synced', () => {
            loadDashboard();
            loadReportsHistory();
            loadPriorityList();
            loadNotifications();
        });
    }
    initAuthAndBoot();
});
