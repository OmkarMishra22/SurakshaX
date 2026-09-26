/**
 * SIFGuard Charts & Safety Analytics Module
 * Renders interactive Chart.js visualizations for enterprise safety intelligence.
 */

class SafetyCharts {
    constructor() {
        this.charts = {};
    }

    async initAll() {
        if (typeof Chart === 'undefined') {
            console.warn('Chart.js library not detected.');
            return;
        }

        try {
            const res = await fetch('/api/analytics/charts');
            const data = await res.json();
            this.renderRiskDistribution(data.risk_distribution);
            this.renderSifComparison(data.sif_comparison);
            this.renderSifTrend(data.sif_trend);
            this.renderTopHazards(data.top_hazards);
            this.renderSiteAnalytics(data.site_analytics);
            this.renderLifecycleStatus(data.lifecycle_status);
            this.renderTopPrecursorsTable(data.top_recurring_precursors);
        } catch (e) {
            console.error('Failed to load chart analytics data:', e);
        }
    }

    destroyChart(key) {
        if (this.charts[key]) {
            this.charts[key].destroy();
            delete this.charts[key];
        }
    }

    renderRiskDistribution(data) {
        const ctx = document.getElementById('chartRiskDist');
        if (!ctx) return;
        this.destroyChart('riskDist');

        this.charts['riskDist'] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: ['#10b981', '#f59e0b', '#f97316', '#ef4444'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    renderSifComparison(data) {
        const ctx = document.getElementById('chartSifCompare');
        if (!ctx) return;
        this.destroyChart('sifCompare');

        this.charts['sifCompare'] = new Chart(ctx, {
            type: 'pie',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: ['#ef4444', '#0284c7'],
                    borderWidth: 2,
                    borderColor: '#ffffff'
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'bottom', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    renderSifTrend(data) {
        const ctx = document.getElementById('chartSifTrend');
        if (!ctx) return;
        this.destroyChart('sifTrend');

        this.charts['sifTrend'] = new Chart(ctx, {
            type: 'line',
            data: {
                labels: data.labels,
                datasets: [
                    {
                        label: 'Critical Precursors',
                        data: data.critical,
                        borderColor: '#ef4444',
                        backgroundColor: 'rgba(239, 68, 68, 0.1)',
                        fill: true,
                        tension: 0.35
                    },
                    {
                        label: 'High Risks',
                        data: data.high,
                        borderColor: '#f97316',
                        backgroundColor: 'transparent',
                        borderDash: [5, 5],
                        tension: 0.35
                    },
                    {
                        label: 'SIF Potential Total',
                        data: data.sif,
                        borderColor: '#1e40af',
                        backgroundColor: 'transparent',
                        tension: 0.35
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true, ticks: { stepSize: 1 } },
                    x: { grid: { display: false } }
                },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    renderTopHazards(data) {
        const ctx = document.getElementById('chartTopHazards');
        if (!ctx) return;
        this.destroyChart('topHazards');

        this.charts['topHazards'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.labels,
                datasets: [{
                    label: 'Reported Incidents',
                    data: data.data,
                    backgroundColor: '#1e40af',
                    borderRadius: 4
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    x: { beginAtZero: true, ticks: { stepSize: 1 } },
                    y: { ticks: { font: { size: 11 } } }
                },
                plugins: {
                    legend: { display: false }
                }
            }
        });
    }

    renderSiteAnalytics(data) {
        const ctx = document.getElementById('chartSiteAnalytics');
        if (!ctx) return;
        this.destroyChart('siteAnalytics');

        this.charts['siteAnalytics'] = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: data.sites,
                datasets: [
                    {
                        label: 'Total Reports',
                        data: data.total,
                        backgroundColor: '#94a3b8',
                        borderRadius: 4
                    },
                    {
                        label: 'SIF Precursors',
                        data: data.sif,
                        backgroundColor: '#ef4444',
                        borderRadius: 4
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                scales: {
                    y: { beginAtZero: true }
                },
                plugins: {
                    legend: { position: 'top', labels: { boxWidth: 12, font: { size: 11 } } }
                }
            }
        });
    }

    renderLifecycleStatus(data) {
        const ctx = document.getElementById('chartLifecycle');
        if (!ctx) return;
        this.destroyChart('lifecycle');

        this.charts['lifecycle'] = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: data.labels,
                datasets: [{
                    data: data.data,
                    backgroundColor: ['#38bdf8', '#fbbf24', '#f87171', '#34d399', '#818cf8', '#94a3b8'],
                    borderWidth: 2
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                plugins: {
                    legend: { position: 'right', labels: { boxWidth: 10, font: { size: 10 } } }
                }
            }
        });
    }

    renderTopPrecursorsTable(items) {
        const container = document.getElementById('topPrecursorsTableBody');
        if (!container || !items) return;

        container.innerHTML = items.map((p, idx) => `
            <tr>
                <td><strong>#${idx + 1}</strong></td>
                <td><strong>${p.name}</strong></td>
                <td><span class="badge badge-critical">${p.frequency} Events</span></td>
                <td><span class="badge ${p.risk_pct >= 85 ? 'badge-critical' : 'badge-high'}">${p.risk_pct}% Risk</span></td>
                <td>${p.sites}</td>
                <td><span style="font-size: 11px; color: ${p.trend.includes('+') ? '#dc2626' : '#16a34a'}; font-weight:600;">${p.trend}</span></td>
            </tr>
        `).join('');
    }
}

window.SafetyCharts = SafetyCharts;
