class VolatilityMonitor {
    constructor() {
        this.pollInterval = 30000; // 30 seconds
        this.isRefreshing = false;
    }

    async init() {
        this.setupEventListeners();
        await this.updateData();
        this.startPolling();
    }

    setupEventListeners() {
        document.getElementById('refreshBtn').addEventListener('click', () => this.manualRefresh());
    }

    startPolling() {
        setInterval(() => this.updateData(), this.pollInterval);
    }

    async updateData() {
        await Promise.all([
            this.fetchAndDisplayStocks(),
            this.fetchAndDisplayAlerts(),
            this.fetchAndDisplayConfig(),
        ]);
        this.updateTimestamp();
    }

    async fetchAndDisplayStocks() {
        try {
            const response = await fetch('/api/stocks');
            const stocks = await response.json();

            const container = document.getElementById('stocksList');
            container.innerHTML = stocks.map(stock => `
                <div class="stock-card">
                    <div class="stock-symbol">${stock.symbol}</div>
                    <div class="stock-price">$${stock.price !== null ? stock.price.toFixed(2) : 'N/A'}</div>
                    <div class="stock-update">
                        Updated: ${stock.last_update ? new Date(stock.last_update).toLocaleTimeString() : 'Never'}
                    </div>
                    ${stock.unread_alerts > 0 ? `<div class="stock-alerts">🔴 ${stock.unread_alerts} alerts</div>` : ''}
                </div>
            `).join('');
        } catch (error) {
            console.error('Error fetching stocks:', error);
            document.getElementById('stocksList').innerHTML = `<div class="error">Error loading stocks: ${error.message}</div>`;
        }
    }

    async fetchAndDisplayAlerts() {
        try {
            const response = await fetch('/api/alerts?limit=50');
            const alerts = await response.json();

            const container = document.getElementById('alertsList');

            if (alerts.length === 0) {
                container.innerHTML = '<div class="loading">No alerts yet</div>';
                return;
            }

            container.innerHTML = alerts.map(alert => `
                <div class="alert-item severity-${alert.severity} type-${alert.alert_type.replace('_', '-')}">
                    <div class="alert-header">
                        <span class="alert-symbol">${alert.symbol}</span>
                        <span class="alert-type ${alert.alert_type.replace('_', '-')}">${this.formatAlertType(alert.alert_type)}</span>
                        <span class="alert-severity severity-${alert.severity}">${alert.severity.toUpperCase()}</span>
                    </div>
                    <div class="alert-message">${alert.message}</div>
                    <div class="alert-details">
                        <div class="alert-detail">
                            <strong>Price:</strong> $${alert.price_at_trigger?.toFixed(2) || 'N/A'}
                        </div>
                        <div class="alert-detail">
                            <strong>Change:</strong> ${alert.percent_change?.toFixed(2) || 'N/A'}%
                        </div>
                    </div>
                    <div class="alert-timestamp">${new Date(alert.triggered_at).toLocaleString()}</div>
                </div>
            `).join('');
        } catch (error) {
            console.error('Error fetching alerts:', error);
            document.getElementById('alertsList').innerHTML = `<div class="error">Error loading alerts: ${error.message}</div>`;
        }
    }

    async fetchAndDisplayConfig() {
        try {
            const response = await fetch('/api/config');
            const config = await response.json();

            const container = document.getElementById('configPanel');
            container.innerHTML = `
                <div class="config-item">
                    <div class="config-label">Monitored Symbols</div>
                    <div class="config-value">${config.symbols.join(', ')}</div>
                </div>
                <div class="config-item">
                    <div class="config-label">Volatility Threshold</div>
                    <div class="config-value">${config.volatility_threshold}%</div>
                </div>
                <div class="config-item">
                    <div class="config-label">Lookback Period</div>
                    <div class="config-value">${config.lookback_days} days</div>
                </div>
                <div class="config-item">
                    <div class="config-label">Analysis Interval</div>
                    <div class="config-value">Every ${config.scheduler_interval_hours} hours</div>
                </div>
            `;
        } catch (error) {
            console.error('Error fetching config:', error);
            document.getElementById('configPanel').innerHTML = `<div class="error">Error loading config: ${error.message}</div>`;
        }
    }

    async manualRefresh() {
        if (this.isRefreshing) return;

        const btn = document.getElementById('refreshBtn');
        this.isRefreshing = true;
        btn.disabled = true;
        btn.textContent = '⏳ Refreshing...';

        try {
            const response = await fetch('/api/refresh', { method: 'POST' });
            const result = await response.json();

            if (result.status === 'success') {
                btn.textContent = '✅ Refreshed!';
                setTimeout(() => {
                    btn.textContent = '🔄 Refresh Now';
                    btn.disabled = false;
                    this.isRefreshing = false;
                    this.updateData();
                }, 2000);
            } else {
                throw new Error(result.error || 'Refresh failed');
            }
        } catch (error) {
            console.error('Error refreshing:', error);
            btn.textContent = '❌ Error';
            setTimeout(() => {
                btn.textContent = '🔄 Refresh Now';
                btn.disabled = false;
                this.isRefreshing = false;
            }, 2000);
        }
    }

    updateTimestamp() {
        const now = new Date();
        document.getElementById('lastUpdate').textContent = `Last update: ${now.toLocaleTimeString()}`;
    }

    formatAlertType(type) {
        const types = {
            'sharp_up': '📈 Sharp Up',
            'sharp_down': '📉 Sharp Down',
            'pattern': '🔄 Pattern',
        };
        return types[type] || type;
    }
}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const monitor = new VolatilityMonitor();
    monitor.init();
});
