class VolatilityMonitor {
    constructor() {
        this.pollInterval = 30000; // 30 seconds
        this.isRefreshing = false;
        this.activeTab = localStorage.getItem('activeTab') || 'stocks';
        this.theme = localStorage.getItem('theme') || 'light';
        this.selectedSymbol = localStorage.getItem('selectedSymbol') || null;
        this.alertPage = 1;
        this.alertPageSize = Number(localStorage.getItem('alertPageSize')) || 10;
        this.alertTotal = 0;
    }

    async init() {
        this.applyTheme(this.theme);
        this.activateTab(this.activeTab);
        this.syncPageSizeSelect();
        this.setupEventListeners();
        await this.updateData();
        if (this.selectedSymbol) {
            await this.loadAlertHistory(this.selectedSymbol);
        }
        this.startPolling();
    }

    syncPageSizeSelect() {
        const select = document.getElementById('alertPageSize');
        if (![10, 20, 50].includes(this.alertPageSize)) {
            this.alertPageSize = 10;
        }
        select.value = String(this.alertPageSize);
    }

    setupEventListeners() {
        document.getElementById('refreshBtn').addEventListener('click', () => this.manualRefresh());

        document.getElementById('themeLightBtn').addEventListener('click', () => this.applyTheme('light'));
        document.getElementById('themeDarkBtn').addEventListener('click', () => this.applyTheme('dark'));

        document.querySelectorAll('.tab-btn:not(:disabled)').forEach(btn => {
            btn.addEventListener('click', () => this.activateTab(btn.dataset.tab));
        });

        document.getElementById('stocksTableBody').addEventListener('click', (event) => {
            // External Nasdaq links handle themselves
            if (event.target.closest('a.nasdaq-link')) return;

            const loadCell = event.target.closest('[data-action="load-alerts"]');
            if (!loadCell) return;

            const row = loadCell.closest('tr[data-symbol]');
            if (!row) return;
            this.selectStock(row.dataset.symbol);
        });

        document.getElementById('alertPageSize').addEventListener('change', (event) => {
            this.alertPageSize = Number(event.target.value) || 10;
            localStorage.setItem('alertPageSize', String(this.alertPageSize));
            this.alertPage = 1;
            if (this.selectedSymbol) {
                this.loadAlertHistory(this.selectedSymbol);
            }
        });

        document.getElementById('alertPrevBtn').addEventListener('click', () => {
            if (this.alertPage <= 1) return;
            this.alertPage -= 1;
            if (this.selectedSymbol) {
                this.loadAlertHistory(this.selectedSymbol);
            }
        });

        document.getElementById('alertNextBtn').addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(this.alertTotal / this.alertPageSize));
            if (this.alertPage >= totalPages) return;
            this.alertPage += 1;
            if (this.selectedSymbol) {
                this.loadAlertHistory(this.selectedSymbol);
            }
        });
    }

    applyTheme(theme) {
        this.theme = theme === 'dark' ? 'dark' : 'light';
        document.documentElement.setAttribute('data-theme', this.theme);
        localStorage.setItem('theme', this.theme);

        document.getElementById('themeLightBtn').classList.toggle('active', this.theme === 'light');
        document.getElementById('themeDarkBtn').classList.toggle('active', this.theme === 'dark');
    }

    activateTab(tab) {
        const allowed = ['stocks', 'configuration'];
        // Options tab is visible but disabled for now
        const next = allowed.includes(tab) ? tab : 'stocks';
        this.activeTab = next;
        localStorage.setItem('activeTab', next);

        document.querySelectorAll('.tab-btn').forEach(btn => {
            const isActive = btn.dataset.tab === next;
            btn.classList.toggle('active', isActive);
            btn.setAttribute('aria-selected', isActive ? 'true' : 'false');
        });

        document.getElementById('panelStocks').hidden = next !== 'stocks';
        document.getElementById('panelOptions').hidden = next !== 'options';
        document.getElementById('panelConfiguration').hidden = next !== 'configuration';
    }

    startPolling() {
        setInterval(() => this.updateData(), this.pollInterval);
    }

    async updateData() {
        await Promise.all([
            this.fetchAndDisplayStocks(),
            this.fetchAndDisplayConfig(),
        ]);
        this.updateTimestamp();
    }

    formatMoney(value) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
        return `$${Number(value).toFixed(2)}`;
    }

    /** Prior close inferred from trigger close and day-over-day % change. */
    priceFrom(alert) {
        const to = alert.price_at_trigger;
        const pct = alert.percent_change;
        if (to === null || to === undefined || pct === null || pct === undefined) return null;
        const factor = 1 + Number(pct) / 100;
        if (!factor) return null;
        return Number(to) / factor;
    }

    formatPct(value) {
        if (value === null || value === undefined || Number.isNaN(Number(value))) return '—';
        const n = Number(value);
        const sign = n > 0 ? '+' : '';
        return `${sign}${n.toFixed(2)}%`;
    }

    async fetchAndDisplayStocks() {
        try {
            const response = await fetch('/api/stocks');
            const stocks = await response.json();
            const body = document.getElementById('stocksTableBody');

            if (!stocks.length) {
                body.innerHTML = '<tr><td colspan="8" class="loading">No stocks configured</td></tr>';
                return;
            }

            body.innerHTML = stocks.map(stock => {
                const selected = stock.symbol === this.selectedSymbol ? 'selected' : '';
                const changeClass = (stock.percent_change || 0) >= 0 ? 'change-up' : 'change-down';
                const alertTitle = stock.alert_severity
                    ? `Latest alert: ${stock.alert_severity}${stock.alert_date ? ` — ${stock.alert_date}` : ''}`
                    : 'No stored alerts';
                const liveTitle = `Live move: ${stock.live_label || 'n/a'} (${this.formatPct(stock.percent_change)})`;
                const alertDotClass = stock.alert_severity
                    ? `alert-dot severity-${stock.alert_severity}`
                    : 'alert-dot alert-none';
                const liveDotClass = stock.live_label && stock.live_label !== 'n/a'
                    ? `alert-dot severity-${stock.live_label}`
                    : `alert-dot alert-${stock.live || 'none'}`;
                const alertDateHtml = stock.alert_date
                    ? `<span class="last-alert-date">${stock.alert_date}</span>`
                    : `<span class="last-alert-date muted">—</span>`;
                const sym = stock.symbol.toLowerCase();
                const stockUrl = `https://www.nasdaq.com/market-activity/stocks/${sym}`;
                const chainUrl = `https://www.nasdaq.com/market-activity/stocks/${sym}/option-chain`;
                return `
                    <tr class="stock-row ${selected}" data-symbol="${stock.symbol}">
                        <td class="col-symbol">
                            <a class="nasdaq-link symbol-link" href="${stockUrl}" target="_blank" rel="noopener noreferrer">${stock.symbol}</a>
                        </td>
                        <td class="col-num num">${this.formatMoney(stock.current_price)}</td>
                        <td class="col-num num">${this.formatMoney(stock.open)}</td>
                        <td class="col-num num">${this.formatMoney(stock.high)}</td>
                        <td class="col-num num">${this.formatMoney(stock.low)}</td>
                        <td class="col-num num">${this.formatMoney(stock.previous_close)}</td>
                        <td class="col-status col-last-alert" data-action="load-alerts" title="${alertTitle}">
                            <span class="${alertDotClass}"></span>
                            ${alertDateHtml}
                        </td>
                        <td class="col-status col-live">
                            <a class="nasdaq-link live-link" href="${chainUrl}" target="_blank" rel="noopener noreferrer" title="${liveTitle}">
                                <span class="${liveDotClass}"></span>
                                <span class="live-change ${changeClass}">${this.formatPct(stock.percent_change)}</span>
                            </a>
                        </td>
                    </tr>
                `;
            }).join('');
        } catch (error) {
            console.error('Error fetching stocks:', error);
            document.getElementById('stocksTableBody').innerHTML =
                `<tr><td colspan="8" class="error">Error loading stocks: ${error.message}</td></tr>`;
        }
    }

    async selectStock(symbol) {
        this.selectedSymbol = symbol;
        localStorage.setItem('selectedSymbol', symbol);
        this.alertPage = 1;

        document.querySelectorAll('.stock-row').forEach(row => {
            row.classList.toggle('selected', row.dataset.symbol === symbol);
        });

        await this.loadAlertHistory(symbol);
    }

    updatePaginationControls() {
        const pagination = document.getElementById('alertPagination');
        const info = document.getElementById('alertPageInfo');
        const prevBtn = document.getElementById('alertPrevBtn');
        const nextBtn = document.getElementById('alertNextBtn');

        if (!this.selectedSymbol) {
            pagination.hidden = true;
            return;
        }

        pagination.hidden = false;
        const totalPages = Math.max(1, Math.ceil(this.alertTotal / this.alertPageSize) || 1);
        const start = this.alertTotal === 0 ? 0 : (this.alertPage - 1) * this.alertPageSize + 1;
        const end = Math.min(this.alertPage * this.alertPageSize, this.alertTotal);

        info.textContent = this.alertTotal === 0
            ? '0 alerts'
            : `${start}–${end} of ${this.alertTotal}`;

        prevBtn.disabled = this.alertPage <= 1;
        nextBtn.disabled = this.alertPage >= totalPages || this.alertTotal === 0;
    }

    async loadAlertHistory(symbol) {
        const title = document.getElementById('alertHistoryTitle');
        const hint = document.getElementById('alertHistoryHint');
        const body = document.getElementById('alertsTableBody');

        title.textContent = `Alert History — ${symbol}`;
        hint.textContent = 'Historical alerts from scheduled volatility analysis.';
        body.innerHTML = '<tr><td colspan="4" class="loading">Loading alerts...</td></tr>';

        const skip = (this.alertPage - 1) * this.alertPageSize;

        try {
            const response = await fetch(
                `/api/alerts?symbol=${encodeURIComponent(symbol)}&limit=${this.alertPageSize}&skip=${skip}`
            );
            const data = await response.json();
            const alerts = data.items || [];
            this.alertTotal = data.total || 0;

            const totalPages = Math.max(1, Math.ceil(this.alertTotal / this.alertPageSize) || 1);
            if (this.alertPage > totalPages) {
                this.alertPage = totalPages;
                if (this.alertTotal > 0) {
                    await this.loadAlertHistory(symbol);
                    return;
                }
            }

            if (!alerts.length) {
                body.innerHTML = '<tr><td colspan="4" class="loading">No alerts for this stock yet</td></tr>';
                this.updatePaginationControls();
                return;
            }

            body.innerHTML = alerts.map(alert => {
                const severity = alert.severity || 'low';
                return `
                <tr>
                    <td class="col-date">${alert.triggered_at_display || alert.triggered_at}</td>
                    <td class="col-num col-change num change-severity-${severity}" title="Severity: ${severity}">${this.formatPct(alert.percent_change)}</td>
                    <td class="col-num col-from num">${this.formatMoney(this.priceFrom(alert))}</td>
                    <td class="col-num col-to num">${this.formatMoney(alert.price_at_trigger)}</td>
                </tr>
            `;
            }).join('');

            this.updatePaginationControls();
        } catch (error) {
            console.error('Error fetching alerts:', error);
            body.innerHTML = `<tr><td colspan="4" class="error">Error loading alerts: ${error.message}</td></tr>`;
            document.getElementById('alertPagination').hidden = true;
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
                <div class="config-item">
                    <div class="config-label">Timezone</div>
                    <div class="config-value">${config.timezone || 'CT'}</div>
                </div>
            `;
        } catch (error) {
            console.error('Error fetching config:', error);
            document.getElementById('configPanel').innerHTML = `<div class="error">Error loading config: ${error.message}</div>`;
        }
    }

    setRefreshButtonState(state) {
        const btn = document.getElementById('refreshBtn');
        const label = btn.querySelector('.btn-label');
        btn.disabled = state === 'loading';
        btn.classList.toggle('is-loading', state === 'loading');

        const labels = {
            idle: 'Refresh data',
            loading: 'Refreshing…',
            success: 'Refreshed',
            error: 'Refresh failed',
        };
        if (label) {
            label.textContent = labels[state] || labels.idle;
        }
    }

    async manualRefresh() {
        if (this.isRefreshing) return;

        this.isRefreshing = true;
        this.setRefreshButtonState('loading');

        try {
            const response = await fetch('/api/refresh', { method: 'POST' });
            const result = await response.json();

            if (result.status === 'success') {
                this.setRefreshButtonState('success');
                setTimeout(async () => {
                    this.setRefreshButtonState('idle');
                    this.isRefreshing = false;
                    await this.updateData();
                    if (this.selectedSymbol) {
                        await this.loadAlertHistory(this.selectedSymbol);
                    }
                }, 1500);
            } else {
                throw new Error(result.error || 'Refresh failed');
            }
        } catch (error) {
            console.error('Error refreshing:', error);
            this.setRefreshButtonState('error');
            setTimeout(() => {
                this.setRefreshButtonState('idle');
                this.isRefreshing = false;
            }, 2000);
        }
    }

    updateTimestamp() {
        const now = new Date();
        document.getElementById('lastUpdate').textContent = `Last update: ${now.toLocaleTimeString()}`;
    }

}

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    const monitor = new VolatilityMonitor();
    monitor.init();
});
