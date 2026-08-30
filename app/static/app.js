class VolatilityMonitor {
    constructor() {
        this.pollInterval = 30000; // 30 seconds
        this.isRefreshing = false;
        this.activeTab = localStorage.getItem('activeTab') || 'stocks';
        this.theme = localStorage.getItem('theme') || 'dark';
        this.selectedSymbol = localStorage.getItem('selectedSymbol') || null;
        this.stocks = [];
        this.stocksPage = 1;
        this.stocksPageSize = Number(localStorage.getItem('stocksPageSize')) || 5;
        this.alertPage = 1;
        this.alertPageSize = Number(localStorage.getItem('alertPageSize')) || 10;
        this.alertTotal = 0;
        this.logsOpen = false;
        this.logsExpanded = false;
        this.logsContainer = 'stocks-dashboard';
        this.logsPollTimer = null;
        this.logsPollInterval = 2500;
    }

    async init() {
        this.applyTheme(this.theme);
        this.activateTab(this.activeTab);
        this.syncStocksPageSizeSelect();
        this.syncAlertPageSizeSelect();
        this.setupEventListeners();
        this.setupLogsPanel();
        await this.updateData();
        if (this.selectedSymbol) {
            await this.loadAlertHistory(this.selectedSymbol);
        }
        this.startPolling();
    }

    syncStocksPageSizeSelect() {
        const select = document.getElementById('stocksPageSize');
        if (![5, 10, 20, 50].includes(this.stocksPageSize)) {
            this.stocksPageSize = 5;
        }
        select.value = String(this.stocksPageSize);
    }

    syncAlertPageSizeSelect() {
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
            const pinBtn = event.target.closest('[data-action="toggle-pin"]');
            if (pinBtn) {
                event.preventDefault();
                const row = pinBtn.closest('tr[data-symbol]');
                if (row) {
                    this.toggleStockPin(row.dataset.symbol, pinBtn.dataset.pinned === 'true');
                }
                return;
            }

            // External Nasdaq links handle themselves
            if (event.target.closest('a.nasdaq-link')) return;

            const loadCell = event.target.closest('[data-action="load-alerts"]');
            if (!loadCell) return;

            const row = loadCell.closest('tr[data-symbol]');
            if (!row) return;
            this.selectStock(row.dataset.symbol);
        });

        document.getElementById('stocksPageSize').addEventListener('change', (event) => {
            this.stocksPageSize = Number(event.target.value) || 5;
            localStorage.setItem('stocksPageSize', String(this.stocksPageSize));
            this.stocksPage = 1;
            this.renderStocksPage();
        });

        document.getElementById('stocksPrevBtn').addEventListener('click', () => {
            if (this.stocksPage <= 1) return;
            this.stocksPage -= 1;
            this.renderStocksPage();
        });

        document.getElementById('stocksNextBtn').addEventListener('click', () => {
            const totalPages = Math.max(1, Math.ceil(this.stocks.length / this.stocksPageSize));
            if (this.stocksPage >= totalPages) return;
            this.stocksPage += 1;
            this.renderStocksPage();
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

    setupLogsPanel() {
        const toggle = document.getElementById('logsToggle');
        const drawer = document.getElementById('logsDrawer');
        const closeBtn = document.getElementById('logsCloseBtn');
        const expandBtn = document.getElementById('logsExpandBtn');
        if (!toggle || !drawer) return;

        this.logsOpen = false;
        this.logsExpanded = false;
        this.syncLogsPanel();

        toggle.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.logsOpen = !this.logsOpen;
            if (this.logsOpen) {
                this.setLogsLoading();
            }
            this.syncLogsPanel();
        });

        closeBtn?.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.logsOpen = false;
            this.syncLogsPanel();
        });

        expandBtn?.addEventListener('click', (event) => {
            event.preventDefault();
            event.stopPropagation();
            this.logsExpanded = !this.logsExpanded;
            this.syncLogsPanel();
        });

        document.querySelectorAll('.logs-tab').forEach(btn => {
            btn.addEventListener('click', (event) => {
                event.preventDefault();
                event.stopPropagation();
                this.logsContainer = btn.dataset.container || 'stocks-dashboard';
                document.querySelectorAll('.logs-tab').forEach(tab => {
                    const active = tab.dataset.container === this.logsContainer;
                    tab.classList.toggle('active', active);
                    tab.setAttribute('aria-selected', active ? 'true' : 'false');
                });
                const output = document.getElementById('logsOutput');
                if (output) delete output.dataset.primed;
                if (this.logsOpen) {
                    this.setLogsLoading();
                    this.fetchLogs();
                }
            });
        });
    }

    setLogsLoading() {
        const output = document.getElementById('logsOutput');
        const status = document.getElementById('logsStatus');
        if (output) output.textContent = 'Loading…';
        if (status) status.textContent = '';
    }

    syncLogsPanel() {
        const toggle = document.getElementById('logsToggle');
        const drawer = document.getElementById('logsDrawer');
        const expandBtn = document.getElementById('logsExpandBtn');
        if (!toggle || !drawer) return;

        toggle.setAttribute('aria-expanded', this.logsOpen ? 'true' : 'false');
        drawer.classList.toggle('is-open', this.logsOpen);
        drawer.classList.toggle('logs-drawer--expanded', this.logsOpen && this.logsExpanded);

        if (expandBtn) {
            expandBtn.setAttribute('aria-label', this.logsExpanded ? 'Smaller view' : 'Larger view');
            expandBtn.title = this.logsExpanded ? 'Smaller view' : 'Larger view';
            expandBtn.textContent = this.logsExpanded ? '▭' : '⛶';
        }

        if (this.logsOpen) {
            if (!this.logsPollTimer) {
                this.logsPollTimer = setInterval(() => this.fetchLogs(), this.logsPollInterval);
            }
            this.fetchLogs();
        } else {
            if (this.logsPollTimer) {
                clearInterval(this.logsPollTimer);
                this.logsPollTimer = null;
            }
            const output = document.getElementById('logsOutput');
            const status = document.getElementById('logsStatus');
            if (output) {
                output.textContent = '';
                delete output.dataset.primed;
            }
            if (status) status.textContent = '';
        }
    }

    async fetchLogs() {
        if (!this.logsOpen) return;

        const output = document.getElementById('logsOutput');
        const status = document.getElementById('logsStatus');
        const stickToBottom = output
            && (output.scrollTop + output.clientHeight >= output.scrollHeight - 24);

        try {
            const res = await fetch(`/api/logs/${encodeURIComponent(this.logsContainer)}?tail=250`);
            const data = await res.json();
            if (!res.ok) {
                throw new Error(data.detail || 'Failed to load logs');
            }

            const lines = Array.isArray(data.lines) ? data.lines : [];
            output.textContent = lines.length ? lines.join('\n') : '(no log output)';
            if (status) {
                const name = data.resolved_name ? ` · ${data.resolved_name}` : '';
                status.textContent = `${data.status || ''}${name}`;
            }
            if (stickToBottom) {
                output.scrollTop = output.scrollHeight;
            }
            if (!output.dataset.primed) {
                output.scrollTop = output.scrollHeight;
                output.dataset.primed = '1';
            }
        } catch (err) {
            output.textContent = `Error: ${err.message}`;
            if (status) status.textContent = 'error';
        }
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

    /** Rank live severity for sort: high=3, medium=2, low=1, missing=0. */
    liveSeverityRank(stock) {
        const label = stock.live_label;
        if (label === 'high') return 3;
        if (label === 'medium') return 2;
        if (label === 'low') return 1;
        return 0;
    }

    sortStocksByLiveSeverity(stocks) {
        return [...stocks].sort((a, b) => {
            const pinA = a.pinned ? (a.pin_order ?? 0) : Number.MAX_SAFE_INTEGER;
            const pinB = b.pinned ? (b.pin_order ?? 0) : Number.MAX_SAFE_INTEGER;
            if (pinA !== pinB) return pinA - pinB;

            const rankDiff = this.liveSeverityRank(b) - this.liveSeverityRank(a);
            if (rankDiff !== 0) return rankDiff;
            const absA = Math.abs(Number(a.percent_change) || 0);
            const absB = Math.abs(Number(b.percent_change) || 0);
            if (absB !== absA) return absB - absA;
            return String(a.symbol || '').localeCompare(String(b.symbol || ''));
        });
    }

    async toggleStockPin(symbol, currentlyPinned) {
        try {
            const response = await fetch(`/api/stocks/${encodeURIComponent(symbol)}/pin`, {
                method: 'PUT',
                credentials: 'same-origin',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ pinned: !currentlyPinned }),
            });
            if (!response.ok) {
                const payload = await response.json().catch(() => ({}));
                throw new Error(payload.detail || `Pin failed (${response.status})`);
            }
            await this.fetchAndDisplayStocks();
        } catch (error) {
            console.error('Error toggling pin:', error);
            alert(error.message || 'Could not update pin');
        }
    }

    renderPinButton(stock) {
        const pinned = Boolean(stock.pinned);
        const label = pinned ? `Unpin ${stock.symbol}` : `Pin ${stock.symbol}`;
        const iconClass = pinned ? 'pin-btn pin-btn--active' : 'pin-btn';
        return `
            <button type="button"
                class="${iconClass}"
                data-action="toggle-pin"
                data-pinned="${pinned}"
                aria-label="${label}"
                title="${label}">
                <svg viewBox="0 0 24 24" fill="currentColor" aria-hidden="true">
                    <path d="M16 12V4h1V2H7v2h1v8l-2 2v2h5.2v6h1.6v-6H18v-2l-2-2z"/>
                </svg>
            </button>
        `;
    }

    async fetchAndDisplayStocks() {
        try {
            const response = await fetch('/api/stocks');
            const stocks = await response.json();
            this.stocks = this.sortStocksByLiveSeverity(Array.isArray(stocks) ? stocks : []);
            this.renderStocksPage();
        } catch (error) {
            console.error('Error fetching stocks:', error);
            this.stocks = [];
            document.getElementById('stocksPagination').hidden = true;
            document.getElementById('stocksTableBody').innerHTML =
                `<tr><td colspan="9" class="error">Error loading stocks: ${error.message}</td></tr>`;
        }
    }

    updateStocksPaginationControls() {
        const pagination = document.getElementById('stocksPagination');
        const info = document.getElementById('stocksPageInfo');
        const prevBtn = document.getElementById('stocksPrevBtn');
        const nextBtn = document.getElementById('stocksNextBtn');
        const total = this.stocks.length;

        if (!total) {
            pagination.hidden = true;
            return;
        }

        pagination.hidden = false;
        const totalPages = Math.max(1, Math.ceil(total / this.stocksPageSize));
        if (this.stocksPage > totalPages) {
            this.stocksPage = totalPages;
        }
        const start = (this.stocksPage - 1) * this.stocksPageSize + 1;
        const end = Math.min(this.stocksPage * this.stocksPageSize, total);

        info.textContent = `${start}–${end} of ${total}`;
        prevBtn.disabled = this.stocksPage <= 1;
        nextBtn.disabled = this.stocksPage >= totalPages;
    }

    renderStocksPage() {
        const body = document.getElementById('stocksTableBody');

        if (!this.stocks.length) {
            body.innerHTML = '<tr><td colspan="9" class="loading">No stocks configured</td></tr>';
            this.updateStocksPaginationControls();
            return;
        }

        this.updateStocksPaginationControls();
        const start = (this.stocksPage - 1) * this.stocksPageSize;
        const pageStocks = this.stocks.slice(start, start + this.stocksPageSize);

        body.innerHTML = pageStocks.map(stock => {
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
            const pinnedClass = stock.pinned ? ' stock-row--pinned' : '';
            return `
                <tr class="stock-row ${selected}${pinnedClass}" data-symbol="${stock.symbol}">
                    <td class="col-pin">${this.renderPinButton(stock)}</td>
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
