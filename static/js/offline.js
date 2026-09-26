/**
 * SurakshaX Offline-First & Hybrid Edge Computing Module
 * Provides localStorage queuing for safety reports in low/no-connectivity oilfield environments,
 * automatic background synchronization when online, and offline status indicator.
 */

class SIFGuardOffline {
    constructor() {
        this.STORAGE_KEY = 'surakshax_offline_queue';
        this.networkPill = document.getElementById('networkStatusPill');
        this.pendingCountBadge = document.getElementById('offlinePendingBadge');
        this.cloudHubStatusBadge = document.getElementById('cloudHubStatusBadge');
        this.cloudPendingCount = document.getElementById('cloudPendingCount');
        this.cloudSimulateOfflineBtn = document.getElementById('cloudSimulateOfflineBtn');
        this.isSimulatedOffline = false;

        this.init();
    }

    init() {
        window.addEventListener('online', () => this.handleNetworkChange(true));
        window.addEventListener('offline', () => this.handleNetworkChange(false));
        
        if (this.networkPill) {
            this.networkPill.addEventListener('click', () => this.toggleSimulatedNetwork());
        }

        this.updatePill();
        this.updateBadge();

        // Attempt initial sync if online
        if (navigator.onLine && !this.isSimulatedOffline) {
            this.syncQueue();
        }
    }

    isOnline() {
        return navigator.onLine && !this.isSimulatedOffline;
    }

    toggleSimulatedNetwork() {
        this.isSimulatedOffline = !this.isSimulatedOffline;
        this.updatePill();
        if (this.isOnline()) {
            this.syncQueue();
        }
    }

    toggleSimulation() {
        this.toggleSimulatedNetwork();
    }

    syncAll() {
        return this.syncQueue();
    }

    handleNetworkChange(online) {
        this.updatePill();
        if (online && !this.isSimulatedOffline) {
            this.syncQueue();
        }
    }

    updatePill() {
        const online = this.isOnline();
        if (this.networkPill) {
            if (online) {
                this.networkPill.className = 'network-pill';
                this.networkPill.innerHTML = '<span class="pulse-dot"></span><span>SYSTEM ONLINE</span>';
                this.networkPill.title = 'Online: Direct API connected (Click to simulate offline)';
            } else {
                this.networkPill.className = 'network-pill offline';
                this.networkPill.innerHTML = '<span class="pulse-dot"></span><span>OFFLINE MODE</span>';
                this.networkPill.title = 'Offline: Reports queued locally (Click to reconnect)';
            }
        }

        // HSE Portal Cloud Hub Widget UI Sync
        const hubBadge = document.getElementById('cloudHubStatusBadge');
        const simBtn = document.getElementById('cloudSimulateOfflineBtn');
        if (hubBadge) {
            if (online) {
                hubBadge.className = 'badge badge-low';
                hubBadge.innerText = '● Cloud Connected';
            } else {
                hubBadge.className = 'badge badge-critical';
                hubBadge.innerText = '⚡ Local Edge Mode (Offline)';
            }
        }
        if (simBtn) {
            simBtn.innerText = online ? '📶 Simulate Edge Disconnect' : '📶 Reconnect Cloud Node';
        }
    }

    getQueue() {
        try {
            // Also check legacy key if exists
            let raw = localStorage.getItem(this.STORAGE_KEY);
            if (!raw) {
                raw = localStorage.getItem('sifguard_offline_queue');
            }
            return raw ? JSON.parse(raw) : [];
        } catch (e) {
            return [];
        }
    }

    saveToQueue(reportData) {
        const queue = this.getQueue();
        reportData.temp_uid = `OFFLINE-${Date.now()}`;
        reportData.created_at = new Date().toISOString().replace('T', ' ').substring(0, 19);
        reportData.sync_status = 'Pending Sync';
        queue.push(reportData);
        localStorage.setItem(this.STORAGE_KEY, JSON.stringify(queue));
        this.updateBadge();
        return reportData;
    }

    updateBadge() {
        const queue = this.getQueue();
        if (this.pendingCountBadge) {
            if (queue.length > 0) {
                this.pendingCountBadge.style.display = 'inline-block';
                this.pendingCountBadge.innerText = `${queue.length} Pending Sync`;
            } else {
                this.pendingCountBadge.style.display = 'none';
            }
        }
        const cloudPending = document.getElementById('cloudPendingCount');
        if (cloudPending) {
            cloudPending.innerText = queue.length.toString();
        }
    }

    async syncQueue() {
        const queue = this.getQueue();
        if (!queue || queue.length === 0) return;

        console.log(`[SurakshaX Offline Sync] Synchronizing ${queue.length} pending offline reports...`);
        try {
            const res = await fetch('/api/reports/sync', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ reports: queue })
            });
            const data = await res.json();
            if (data.success) {
                localStorage.removeItem(this.STORAGE_KEY);
                localStorage.removeItem('sifguard_offline_queue');
                this.updateBadge();
                if (window.showToast) {
                    window.showToast(`📡 Synced Successfully: ${data.synced_count} offline report(s) uploaded to OIL central cloud.`, 'success');
                }
                // Notify application to refresh data
                window.dispatchEvent(new CustomEvent('surakshax:synced', { detail: data }));
                window.dispatchEvent(new CustomEvent('sifguard:synced', { detail: data }));
            }
        } catch (e) {
            console.warn('[SurakshaX Offline Sync] Failed to sync offline queue:', e);
        }
    }

    // Industrial P2P Edge Mesh Network Simulation
    getMeshNodes() {
        return [
            { id: 'OIL-GATEWAY-ALPHA', role: 'Duliajan Central Cloud Gateway', status: this.isOnline() ? 'SYNCED' : 'WAN DISCONNECTED', latency: this.isOnline() ? '18ms' : 'OFFLINE', hops: 0 },
            { id: 'SAFETY-GATE-EDGE-01', role: 'Smart Gate Entry Vision Node', status: 'ACTIVE MESH', latency: '2ms', hops: 1 },
            { id: 'RIG-MESH-NODE-04', role: 'Moran Wellhead Sub-GHz Node', status: 'ACTIVE MESH', latency: '8ms', hops: 1 },
            { id: 'MOBILE-PATROL-NODE-7', role: 'HSE Field Tablet Relay', status: 'P2P GOSSIPING', latency: '12ms', hops: 2 }
        ];
    }

    triggerMeshGossipSync() {
        const queue = this.getQueue();
        const nodes = this.getMeshNodes();
        console.log(`[SurakshaX Mesh Network] P2P Gossip Broadcast to ${nodes.length} nodes. Replicating ${queue.length} reports across edge peers.`);
        if (window.showToast) {
            window.showToast(`🛡️ P2P Mesh Sync Active: Replicated ${queue.length} observation(s) across 4 localized field nodes over LoRa/Sub-GHz gossip.`, 'info');
        }
        window.dispatchEvent(new CustomEvent('surakshax:mesh_gossip', { detail: { nodes, queueCount: queue.length } }));
        return { success: true, nodesReplicated: nodes.length, queuedItems: queue.length };
    }
}

class SurakshaXOffline extends SIFGuardOffline {}

window.SurakshaXOffline = SurakshaXOffline;
window.SIFGuardOffline = SIFGuardOffline;
