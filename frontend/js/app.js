class App {
    constructor() {
        this.graph = null;
        this.alertPanel = null;
        this.uploadManager = null;

        this.init();
    }

    async init() {
        this.graph = new GraphVisualization('graph-container');
        this.alertPanel = new AlertPanel();
        this.uploadManager = new UploadManager();

        this.bindEvents();
        this.setupWebSocket();
        await this.loadInitialData();
        this.startAutoRefresh();
    }

    bindEvents() {
        document.getElementById('btn-refresh-graph').addEventListener('click', () => this.refreshGraph());
        document.getElementById('account-select').addEventListener('change', (e) => {
            if (e.target.value) this.loadAccountGraph(e.target.value);
        });
    }

    setupWebSocket() {
        window.wsClient.on('alert', (alert) => this.alertPanel.addNewAlert(alert));
        window.wsClient.on('transaction', () => this.updateStats());
        window.wsClient.on('connect', () => {
            document.getElementById('ws-status') && (document.getElementById('ws-status').textContent = 'Connected');
        });
        window.wsClient.connect();
    }

    async loadInitialData() {
        await this.loadAccounts();
        await this.loadFullGraph();
        await this.updateStats();
    }

    async loadAccounts() {
        try {
            const response = await fetch('/transactions?limit=500');
            const data = await response.json();

            const accounts = new Set();
            const txCount = data.transactions ? data.transactions.length : 0;

            if (data.transactions) {
                data.transactions.forEach(tx => {
                    accounts.add(tx.sender);
                    accounts.add(tx.receiver);
                });
            }

            document.getElementById('tx-count').textContent = txCount;
            document.getElementById('account-count').textContent = accounts.size;

            const select = document.getElementById('account-select');
            select.innerHTML = '<option value="">All Accounts</option>';

            Array.from(accounts).sort().forEach(accountId => {
                const option = document.createElement('option');
                option.value = accountId;
                option.textContent = accountId;
                select.appendChild(option);
            });
        } catch (error) {
            console.error('Failed to load accounts:', error);
        }
    }

    async loadFullGraph() {
        try {
            const response = await fetch('/graph/full');
            const graphData = await response.json();
            this.graph.update(graphData);
        } catch (error) {
            console.error('Failed to load graph:', error);
        }
    }

    async refreshGraph() {
        const select = document.getElementById('account-select');
        if (select.value) {
            await this.loadAccountGraph(select.value);
        } else {
            await this.loadFullGraph();
        }
    }

    async loadAccountGraph(accountId) {
        try {
            const response = await fetch(`/graph/${accountId}?hops=2`);
            const graphData = await response.json();
            this.graph.update(graphData);
        } catch (error) {
            console.error('Failed to load account graph:', error);
        }
    }

    async updateStats() {
        try {
            const txResponse = await fetch('/transactions?limit=500');
            const txData = await txResponse.json();
            const txCount = txData.transactions ? txData.transactions.length : 0;
            document.getElementById('tx-count').textContent = txCount;

            const accounts = new Set();
            if (txData.transactions) {
                txData.transactions.forEach(tx => {
                    accounts.add(tx.sender);
                    accounts.add(tx.receiver);
                });
            }
            document.getElementById('account-count').textContent = accounts.size;

            const alertResponse = await fetch('/alerts?status=open');
            const alertData = await alertResponse.json();
            document.getElementById('alert-count').textContent = alertData.alerts ? alertData.alerts.length : 0;
        } catch (error) {
            console.error('Failed to update stats:', error);
        }
    }

    startAutoRefresh() {
        setInterval(() => this.updateStats(), 5000);
        setInterval(() => this.alertPanel.loadAlerts(), 5000);
    }
}

document.addEventListener('DOMContentLoaded', () => {
    window.app = new App();
});
