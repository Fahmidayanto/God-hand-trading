/**
 * ValueCell Live Price Ticker
 * Real-time price updates for multiple symbols
 * 
 * Features:
 * - Live price updates
 * - Price change indicators
 * - Multiple symbols support
 * - Smooth animations
 */

class PriceTicker {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.API_BASE_URL = options.apiBaseUrl || 'http://localhost:8000/api/v1';
        this.symbols = options.symbols || ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY'];
        this.updateInterval = options.updateInterval || 2000; // 2 seconds
        this.prices = {};
        this.intervalId = null;
        
        this.init();
    }

    init() {
        if (!this.container) {
            console.error('Price ticker container not found');
            return;
        }

        this.createTickerHTML();
        this.startUpdates();
    }

    createTickerHTML() {
        this.container.innerHTML = `
            <div class="price-ticker-wrapper" style="
                background: linear-gradient(135deg, rgba(59, 130, 246, 0.1), rgba(139, 92, 246, 0.1));
                border: 1px solid rgba(59, 130, 246, 0.2);
                border-radius: 12px;
                padding: 12px 20px;
                display: flex;
                gap: 32px;
                overflow-x: auto;
                align-items: center;
            ">
                <div style="font-weight: 600; color: #cbd5e1; white-space: nowrap;">Live Prices</div>
                <div class="ticker-symbols" style="display: flex; gap: 24px; flex: 1;"></div>
                <div class="ticker-status" style="
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    white-space: nowrap;
                ">
                    <div class="status-dot" style="
                        width: 8px;
                        height: 8px;
                        background: #10b981;
                        border-radius: 50%;
                        animation: pulse 2s infinite;
                    "></div>
                    <span style="font-size: 12px; color: #94a3b8;">LIVE</span>
                </div>
            </div>
        `;

        // Add pulse animation
        const style = document.createElement('style');
        style.textContent = `
            @keyframes pulse {
                0%, 100% { opacity: 1; box-shadow: 0 0 10px #10b981; }
                50% { opacity: 0.7; box-shadow: 0 0 20px #10b981; }
            }
            .price-ticker-wrapper::-webkit-scrollbar {
                height: 4px;
            }
            .price-ticker-wrapper::-webkit-scrollbar-track {
                background: rgba(100, 116, 139, 0.1);
                border-radius: 4px;
            }
            .price-ticker-wrapper::-webkit-scrollbar-thumb {
                background: rgba(59, 130, 246, 0.3);
                border-radius: 4px;
            }
            .price-ticker-wrapper::-webkit-scrollbar-thumb:hover {
                background: rgba(59, 130, 246, 0.5);
            }
        `;
        document.head.appendChild(style);

        this.symbolsContainer = this.container.querySelector('.ticker-symbols');
        
        // Create placeholders for each symbol
        this.symbols.forEach(symbol => {
            this.createSymbolElement(symbol);
        });
    }

    createSymbolElement(symbol) {
        const element = document.createElement('div');
        element.className = `ticker-symbol ticker-${symbol}`;
        element.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 4px; min-width: 100px;">
                <div style="font-size: 11px; color: #94a3b8; font-weight: 600;">${symbol}</div>
                <div style="display: flex; align-items: center; gap: 8px;">
                    <div class="symbol-price" style="
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 16px;
                        font-weight: 600;
                        color: #f8fafc;
                    ">--</div>
                    <div class="symbol-change" style="
                        font-size: 12px;
                        font-weight: 600;
                        padding: 2px 6px;
                        border-radius: 4px;
                        background: rgba(100, 116, 139, 0.2);
                        color: #94a3b8;
                    ">--</div>
                </div>
            </div>
        `;
        this.symbolsContainer.appendChild(element);
    }

    async updatePrices() {
        for (const symbol of this.symbols) {
            try {
                const response = await fetch(
                    `${this.API_BASE_URL}/trading/chart/data?symbol=${symbol}&timeframe=M1&count=2`
                );
                
                if (!response.ok) continue;
                
                const data = await response.json();
                
                if (data.candles && data.candles.length > 0) {
                    const latestCandle = data.candles[data.candles.length - 1];
                    const currentPrice = latestCandle.close;
                    const previousPrice = this.prices[symbol] || currentPrice;
                    
                    this.updateSymbolDisplay(symbol, currentPrice, previousPrice);
                    this.prices[symbol] = currentPrice;
                }
            } catch (error) {
                console.error(`Error fetching price for ${symbol}:`, error);
            }
        }
    }

    updateSymbolDisplay(symbol, currentPrice, previousPrice) {
        const element = this.container.querySelector(`.ticker-${symbol}`);
        if (!element) return;

        const priceElement = element.querySelector('.symbol-price');
        const changeElement = element.querySelector('.symbol-change');

        // Calculate change
        const change = currentPrice - previousPrice;
        const changePercent = previousPrice !== 0 ? (change / previousPrice) * 100 : 0;

        // Determine color
        let color, bgColor, arrow;
        if (change > 0) {
            color = '#10b981';
            bgColor = 'rgba(16, 185, 129, 0.2)';
            arrow = '↑';
        } else if (change < 0) {
            color = '#ef4444';
            bgColor = 'rgba(239, 68, 68, 0.2)';
            arrow = '↓';
        } else {
            color = '#94a3b8';
            bgColor = 'rgba(100, 116, 139, 0.2)';
            arrow = '•';
        }

        // Update price with animation
        priceElement.style.transition = 'color 0.3s ease';
        priceElement.style.color = color;
        priceElement.textContent = currentPrice.toFixed(symbol === 'XAUUSD' ? 2 : 5);
        
        setTimeout(() => {
            priceElement.style.color = '#f8fafc';
        }, 300);

        // Update change indicator
        changeElement.textContent = `${arrow} ${Math.abs(changePercent).toFixed(2)}%`;
        changeElement.style.color = color;
        changeElement.style.background = bgColor;
        changeElement.style.transition = 'all 0.3s ease';
    }

    startUpdates() {
        // Initial update
        this.updatePrices();
        
        // Start interval
        this.intervalId = setInterval(() => {
            this.updatePrices();
        }, this.updateInterval);
    }

    stopUpdates() {
        if (this.intervalId) {
            clearInterval(this.intervalId);
            this.intervalId = null;
        }
    }

    destroy() {
        this.stopUpdates();
        if (this.container) {
            this.container.innerHTML = '';
        }
    }

    addSymbol(symbol) {
        if (!this.symbols.includes(symbol)) {
            this.symbols.push(symbol);
            this.createSymbolElement(symbol);
        }
    }

    removeSymbol(symbol) {
        const index = this.symbols.indexOf(symbol);
        if (index > -1) {
            this.symbols.splice(index, 1);
            const element = this.container.querySelector(`.ticker-${symbol}`);
            if (element) {
                element.remove();
            }
            delete this.prices[symbol];
        }
    }

    setUpdateInterval(interval) {
        this.updateInterval = interval;
        this.stopUpdates();
        this.startUpdates();
    }
}

// Example usage:
// <div id="price-ticker"></div>
// const ticker = new PriceTicker('price-ticker', {
//     symbols: ['XAUUSD', 'EURUSD', 'GBPUSD'],
//     updateInterval: 2000
// });

// Export for use in other files
window.PriceTicker = PriceTicker;
