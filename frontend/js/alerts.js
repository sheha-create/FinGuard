class AlertPanel {
    constructor() {
        this.alerts = [];
        this.currentFilter = 'open';
        this.selectedAlert = null;
        
        this.init();
    }

    init() {
        this.bindEvents();
        this.loadAlerts();
    }

    bindEvents() {
        document.querySelectorAll('.btn-filter').forEach(btn => {
            btn.addEventListener('click', (e) => {
                document.querySelectorAll('.btn-filter').forEach(b => b.classList.remove('active'));
                e.target.classList.add('active');
                this.currentFilter = e.target.dataset.status;
                this.loadAlerts();
            });
        });
        
        document.getElementById('btn-close-modal').addEventListener('click', () => {
            this.closeModal();
        });
        
        document.getElementById('btn-false-positive').addEventListener('click', () => {
            this.resolveAlert('resolved_false_positive');
        });
        
        document.getElementById('btn-confirm').addEventListener('click', () => {
            this.resolveAlert('confirmed');
        });
        
        document.getElementById('alert-modal').addEventListener('click', (e) => {
            if (e.target.id === 'alert-modal') {
                this.closeModal();
            }
        });
    }

    async loadAlerts() {
        try {
            const statusParam = this.currentFilter ? `?status=${this.currentFilter}` : '';
            const response = await fetch(`/alerts${statusParam}`);
            const data = await response.json();
            this.alerts = data.alerts || [];
            this.renderAlerts();
            this.updateAlertCount();
        } catch (error) {
            console.error('Failed to load alerts:', error);
        }
    }

    renderAlerts() {
        const container = document.getElementById('alert-list');
        
        if (this.alerts.length === 0) {
            container.innerHTML = '<div class="loading">No alerts found</div>';
            return;
        }
        
        container.innerHTML = this.alerts.map(alert => this.createAlertCard(alert)).join('');
        
        container.querySelectorAll('.alert-card').forEach(card => {
            card.addEventListener('click', () => {
                const alertId = card.dataset.alertId;
                const alert = this.alerts.find(a => a.id === alertId);
                if (alert) {
                    this.openAlertDetails(alert);
                }
            });
        });
    }

    createAlertCard(alert) {
        const riskClass = alert.risk_score > 0.8 ? 'high' : 
                         alert.risk_score > 0.6 ? 'medium' : 'low';
        
        const accounts = Array.isArray(alert.involved_accounts) 
            ? alert.involved_accounts 
            : JSON.parse(alert.involved_accounts || '[]');
        
        const accountsPreview = accounts.slice(0, 3).map(a => a.substring(0, 15)).join(', ');
        const moreAccounts = accounts.length > 3 ? ` +${accounts.length - 3} more` : '';
        
        return `
            <div class="alert-card ${alert.status === 'open' ? 'flagged' : ''}" 
                 data-alert-id="${alert.id}">
                <div class="alert-header">
                    <span class="pattern-badge ${alert.pattern}">${alert.pattern.replace('_', ' ')}</span>
                    <span class="risk-score ${riskClass}">${(alert.risk_score * 100).toFixed(1)}%</span>
                </div>
                <div class="accounts">${accountsPreview}${moreAccounts}</div>
                <div class="description">${alert.description || 'No description'}</div>
            </div>
        `;
    }

    openAlertDetails(alert) {
        this.selectedAlert = alert;
        
        document.getElementById('modal-title').textContent = `Alert ${alert.id}`;
        document.getElementById('detail-pattern').textContent = alert.pattern.replace('_', ' ');
        
        const riskEl = document.getElementById('detail-risk');
        riskEl.textContent = `${(alert.risk_score * 100).toFixed(1)}%`;
        riskEl.className = `value risk-badge ${alert.risk_score > 0.8 ? 'high' : 'medium'}`;
        
        const accounts = Array.isArray(alert.involved_accounts) 
            ? alert.involved_accounts 
            : JSON.parse(alert.involved_accounts || '[]');
        document.getElementById('detail-accounts').textContent = accounts.join(', ');
        
        const txIds = Array.isArray(alert.tx_ids) 
            ? alert.tx_ids 
            : JSON.parse(alert.tx_ids || '[]');
        document.getElementById('detail-txs').textContent = txIds.join(', ');
        
        document.getElementById('detail-description').textContent = alert.description || 'No description';
        
        document.getElementById('alert-modal').classList.remove('hidden');
        
        this.loadAlertGraph(alert);
    }

    async loadAlertGraph(alert) {
        const accounts = Array.isArray(alert.involved_accounts) 
            ? alert.involved_accounts 
            : JSON.parse(alert.involved_accounts || '[]');
        
        if (accounts.length === 0) return;
        
        try {
            const graphContainer = document.getElementById('modal-graph');
            graphContainer.innerHTML = '';
            
            const modalGraph = new GraphVisualization('modal-graph');
            
            const graphData = {
                nodes: accounts.map(id => ({
                    id: id,
                    label: id.substring(0, 12),
                    is_center: false,
                    out_degree: 0,
                    in_degree: 0
                })),
                edges: []
            };
            
            for (const accountId of accounts) {
                try {
                    const response = await fetch(`/graph/${accountId}?hops=1`);
                    const data = await response.json();
                    
                    if (data.nodes) {
                        data.nodes.forEach(node => {
                            if (!graphData.nodes.find(n => n.id === node.id)) {
                                graphData.nodes.push(node);
                            }
                        });
                    }
                    
                    if (data.edges) {
                        data.edges.forEach(edge => {
                            if (!graphData.edges.find(e => e.tx_id === edge.tx_id)) {
                                graphData.edges.push(edge);
                            }
                        });
                    }
                } catch (e) {
                    console.error(`Failed to load graph for ${accountId}:`, e);
                }
            }
            
            modalGraph.update(graphData);
        } catch (error) {
            console.error('Failed to load alert graph:', error);
        }
    }

    closeModal() {
        document.getElementById('alert-modal').classList.add('hidden');
        this.selectedAlert = null;
    }

    async resolveAlert(resolution) {
        if (!this.selectedAlert) return;
        
        try {
            await fetch(`/alerts/${this.selectedAlert.id}/resolve?resolution=${resolution}`, {
                method: 'POST'
            });
            
            this.closeModal();
            this.loadAlerts();
        } catch (error) {
            console.error('Failed to resolve alert:', error);
        }
    }

    addNewAlert(alert) {
        if (this.currentFilter === '' || this.currentFilter === 'open') {
            this.alerts.unshift(alert);
            this.renderAlerts();
        }
        this.updateAlertCount();
    }

    updateAlertCount() {
        const countEl = document.getElementById('alert-count');
        if (countEl) {
            const openAlerts = this.alerts.filter(a => a.status === 'open').length;
            countEl.textContent = openAlerts;
        }
    }
}

window.AlertPanel = AlertPanel;
