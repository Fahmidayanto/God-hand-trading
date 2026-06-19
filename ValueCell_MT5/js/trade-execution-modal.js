/**
 * ValueCell Trade Execution Modal
 * Modal for executing trades with full parameters
 * 
 * Features:
 * - Buy/Sell order placement
 * - Stop Loss / Take Profit calculator
 * - Risk calculator
 * - Real-time price updates
 */

class TradeExecutionModal {
    constructor(options = {}) {
        this.API_BASE_URL = options.apiBaseUrl || 'http://localhost:8000/api/v1';
        this.modal = null;
        this.currentPrice = 0;
        this.accountBalance = 1000;
        this.riskPercent = 1.5;
        
        this.init();
    }

    init() {
        this.createModalHTML();
        this.attachEventListeners();
    }

    createModalHTML() {
        const modal = document.createElement('div');
        modal.id = 'trade-execution-modal';
        modal.style.cssText = `
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0, 0, 0, 0.8);
            backdrop-filter: blur(10px);
            z-index: 10000;
            align-items: center;
            justify-content: center;
        `;

        modal.innerHTML = `
            <div class="modal-content" style="
                background: linear-gradient(135deg, rgba(17, 24, 39, 0.95), rgba(31, 41, 55, 0.95));
                backdrop-filter: blur(20px);
                border: 1px solid rgba(59, 130, 246, 0.3);
                border-radius: 20px;
                padding: 32px;
                max-width: 600px;
                width: 90%;
                max-height: 90vh;
                overflow-y: auto;
                box-shadow: 0 20px 60px rgba(0,0,0,0.5);
                animation: modalFadeIn 0.3s ease;
            ">
                <!-- Header -->
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 24px;">
                    <h2 style="
                        font-size: 24px;
                        font-weight: 700;
                        background: linear-gradient(135deg, #3b82f6, #06b6d4);
                        -webkit-background-clip: text;
                        -webkit-text-fill-color: transparent;
                    ">📊 Execute Trade</h2>
                    <button onclick="tradeModal.close()" style="
                        background: none;
                        border: none;
                        color: #cbd5e1;
                        font-size: 28px;
                        cursor: pointer;
                        transition: color 0.3s;
                    ">×</button>
                </div>

                <!-- Symbol & Price -->
                <div style="
                    background: rgba(59, 130, 246, 0.1);
                    border: 1px solid rgba(59, 130, 246, 0.2);
                    border-radius: 12px;
                    padding: 16px;
                    margin-bottom: 24px;
                ">
                    <div style="display: flex; justify-content: space-between; align-items: center;">
                        <div>
                            <div style="font-size: 12px; color: #94a3b8; margin-bottom: 4px;">SYMBOL</div>
                            <div id="modal-symbol" style="font-size: 20px; font-weight: 700; color: #f8fafc;">XAUUSD</div>
                        </div>
                        <div style="text-align: right;">
                            <div style="font-size: 12px; color: #94a3b8; margin-bottom: 4px;">CURRENT PRICE</div>
                            <div id="modal-price" style="
                                font-family: 'JetBrains Mono', monospace;
                                font-size: 24px;
                                font-weight: 700;
                                color: #3b82f6;
                            ">4106.50</div>
                        </div>
                    </div>
                </div>

                <!-- Order Type -->
                <div style="margin-bottom: 20px;">
                    <label style="display: block; font-size: 13px; color: #94a3b8; margin-bottom: 8px; font-weight: 600;">ORDER TYPE</label>
                    <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 12px;">
                        <button id="btn-buy" class="order-type-btn" data-type="buy" style="
                            padding: 16px;
                            border: 2px solid rgba(16, 185, 129, 0.3);
                            border-radius: 12px;
                            background: rgba(16, 185, 129, 0.1);
                            color: #10b981;
                            font-size: 16px;
                            font-weight: 700;
                            cursor: pointer;
                            transition: all 0.3s ease;
                        ">📈 BUY</button>
                        <button id="btn-sell" class="order-type-btn" data-type="sell" style="
                            padding: 16px;
                            border: 2px solid rgba(239, 68, 68, 0.3);
                            border-radius: 12px;
                            background: rgba(239, 68, 68, 0.1);
                            color: #ef4444;
                            font-size: 16px;
                            font-weight: 700;
                            cursor: pointer;
                            transition: all 0.3s ease;
                        ">📉 SELL</button>
                    </div>
                </div>

                <!-- Lot Size -->
                <div style="margin-bottom: 20px;">
                    <label style="display: block; font-size: 13px; color: #94a3b8; margin-bottom: 8px; font-weight: 600;">LOT SIZE</label>
                    <div style="display: flex; gap: 12px; align-items: center;">
                        <input type="number" id="lot-size" value="0.10" step="0.01" min="0.01" max="10.00" style="
                            flex: 1;
                            padding: 12px;
                            background: rgba(31, 41, 55, 0.5);
                            border: 1px solid rgba(59, 130, 246, 0.2);
                            border-radius: 10px;
                            color: #f8fafc;
                            font-family: 'JetBrains Mono', monospace;
                            font-size: 16px;
                            font-weight: 600;
                        ">
                        <button onclick="tradeModal.calculateLotSize()" style="
                            padding: 12px 20px;
                            background: rgba(59, 130, 246, 0.2);
                            border: 1px solid rgba(59, 130, 246, 0.3);
                            border-radius: 10px;
                            color: #3b82f6;
                            font-size: 13px;
                            font-weight: 600;
                            cursor: pointer;
                            transition: all 0.3s;
                            white-space: nowrap;
                        ">Calculate</button>
                    </div>
                </div>

                <!-- Stop Loss -->
                <div style="margin-bottom: 20px;">
                    <label style="display: block; font-size: 13px; color: #94a3b8; margin-bottom: 8px; font-weight: 600;">STOP LOSS</label>
                    <input type="number" id="stop-loss" placeholder="e.g., 4100.00" step="0.01" style="
                        width: 100%;
                        padding: 12px;
                        background: rgba(31, 41, 55, 0.5);
                        border: 1px solid rgba(239, 68, 68, 0.2);
                        border-radius: 10px;
                        color: #f8fafc;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 14px;
                    ">
                </div>

                <!-- Take Profit -->
                <div style="margin-bottom: 24px;">
                    <label style="display: block; font-size: 13px; color: #94a3b8; margin-bottom: 8px; font-weight: 600;">TAKE PROFIT</label>
                    <input type="number" id="take-profit" placeholder="e.g., 4120.00" step="0.01" style="
                        width: 100%;
                        padding: 12px;
                        background: rgba(31, 41, 55, 0.5);
                        border: 1px solid rgba(16, 185, 129, 0.2);
                        border-radius: 10px;
                        color: #f8fafc;
                        font-family: 'JetBrains Mono', monospace;
                        font-size: 14px;
                    ">
                </div>

                <!-- Risk Summary -->
                <div id="risk-summary" style="
                    background: rgba(251, 191, 36, 0.1);
                    border: 1px solid rgba(251, 191, 36, 0.2);
                    border-radius: 12px;
                    padding: 16px;
                    margin-bottom: 24px;
                    display: none;
                ">
                    <div style="font-size: 13px; font-weight: 600; color: #fbbf24; margin-bottom: 12px;">⚠️ Risk Analysis</div>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; font-size: 13px;">
                        <div>
                            <span style="color: #94a3b8;">Risk Amount:</span>
                            <span id="risk-amount" style="color: #f8fafc; font-weight: 600; margin-left: 8px;">$0.00</span>
                        </div>
                        <div>
                            <span style="color: #94a3b8;">Risk %:</span>
                            <span id="risk-percent" style="color: #f8fafc; font-weight: 600; margin-left: 8px;">0.00%</span>
                        </div>
                        <div>
                            <span style="color: #94a3b8;">Potential Profit:</span>
                            <span id="potential-profit" style="color: #10b981; font-weight: 600; margin-left: 8px;">$0.00</span>
                        </div>
                        <div>
                            <span style="color: #94a3b8;">Risk/Reward:</span>
                            <span id="risk-reward" style="color: #f8fafc; font-weight: 600; margin-left: 8px;">1:0</span>
                        </div>
                    </div>
                </div>

                <!-- Action Buttons -->
                <div style="display: flex; gap: 12px;">
                    <button onclick="tradeModal.close()" style="
                        flex: 1;
                        padding: 14px;
                        background: rgba(100, 116, 139, 0.2);
                        border: 1px solid rgba(100, 116, 139, 0.3);
                        border-radius: 10px;
                        color: #cbd5e1;
                        font-size: 14px;
                        font-weight: 600;
                        cursor: pointer;
                        transition: all 0.3s;
                    ">Cancel</button>
                    <button id="btn-execute" onclick="tradeModal.executeTrade()" style="
                        flex: 2;
                        padding: 14px;
                        background: linear-gradient(135deg, #3b82f6, #2563eb);
                        border: none;
                        border-radius: 10px;
                        color: white;
                        font-size: 14px;
                        font-weight: 700;
                        cursor: pointer;
                        transition: all 0.3s;
                        box-shadow: 0 4px 20px rgba(59, 130, 246, 0.4);
                    ">Execute Trade</button>
                </div>

                <!-- Warning -->
                <div style="
                    margin-top: 16px;
                    padding: 12px;
                    background: rgba(239, 68, 68, 0.1);
                    border: 1px solid rgba(239, 68, 68, 0.2);
                    border-radius: 8px;
                    font-size: 12px;
                    color: #f87171;
                    text-align: center;
                ">
                    ⚠️ Paper Trading Mode - No real money at risk
                </div>
            </div>
        `;

        document.body.appendChild(modal);
        this.modal = modal;

        // Add animations
        const style = document.createElement('style');
        style.textContent = `
            @keyframes modalFadeIn {
                from {
                    opacity: 0;
                    transform: scale(0.9) translateY(-20px);
                }
                to {
                    opacity: 1;
                    transform: scale(1) translateY(0);
                }
            }
            
            .order-type-btn:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            }
            
            .order-type-btn.active {
                border-width: 3px !important;
                box-shadow: 0 0 30px currentColor !important;
            }
            
            input:focus {
                outline: none;
                border-color: #3b82f6 !important;
                box-shadow: 0 0 20px rgba(59, 130, 246, 0.3);
            }
            
            button:hover {
                transform: translateY(-2px);
                box-shadow: 0 8px 20px rgba(0,0,0,0.3);
            }
            
            #btn-execute:hover {
                box-shadow: 0 8px 30px rgba(59, 130, 246, 0.6) !important;
            }
            
            .modal-content::-webkit-scrollbar {
                width: 8px;
            }
            
            .modal-content::-webkit-scrollbar-track {
                background: rgba(100, 116, 139, 0.1);
                border-radius: 4px;
            }
            
            .modal-content::-webkit-scrollbar-thumb {
                background: rgba(59, 130, 246, 0.3);
                border-radius: 4px;
            }
        `;
        document.head.appendChild(style);
    }

    attachEventListeners() {
        // Order type buttons
        const buyBtn = document.getElementById('btn-buy');
        const sellBtn = document.getElementById('btn-sell');
        
        buyBtn.addEventListener('click', () => {
            buyBtn.classList.add('active');
            sellBtn.classList.remove('active');
            this.orderType = 'buy';
            this.calculateRisk();
        });
        
        sellBtn.addEventListener('click', () => {
            sellBtn.classList.add('active');
            buyBtn.classList.remove('active');
            this.orderType = 'sell';
            this.calculateRisk();
        });

        // Auto-calculate risk on input changes
        ['lot-size', 'stop-loss', 'take-profit'].forEach(id => {
            document.getElementById(id).addEventListener('input', () => {
                this.calculateRisk();
            });
        });

        // Close on outside click
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });

        // Close on Escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && this.modal.style.display === 'flex') {
                this.close();
            }
        });
    }

    async open(symbol = 'XAUUSD', price = null) {
        this.symbol = symbol;
        
        // Fetch current price if not provided
        if (!price) {
            try {
                const response = await fetch(
                    `${this.API_BASE_URL}/trading/chart/data?symbol=${symbol}&timeframe=M1&count=1`
                );
                const data = await response.json();
                if (data.candles && data.candles.length > 0) {
                    this.currentPrice = data.candles[0].close;
                }
            } catch (error) {
                console.error('Error fetching price:', error);
                this.currentPrice = 4106.50; // Fallback
            }
        } else {
            this.currentPrice = price;
        }

        // Update UI
        document.getElementById('modal-symbol').textContent = symbol;
        document.getElementById('modal-price').textContent = this.currentPrice.toFixed(2);
        
        // Reset form
        document.getElementById('btn-buy').classList.add('active');
        document.getElementById('btn-sell').classList.remove('active');
        this.orderType = 'buy';
        document.getElementById('lot-size').value = '0.10';
        document.getElementById('stop-loss').value = '';
        document.getElementById('take-profit').value = '';
        document.getElementById('risk-summary').style.display = 'none';

        // Show modal
        this.modal.style.display = 'flex';
    }

    close() {
        this.modal.style.display = 'none';
    }

    calculateLotSize() {
        // Simple lot size calculator based on risk
        const stopLoss = parseFloat(document.getElementById('stop-loss').value);
        if (!stopLoss) {
            window.notifications?.showWarning('Please enter Stop Loss first');
            return;
        }

        const riskAmount = (this.accountBalance * this.riskPercent) / 100;
        const stopLossPoints = Math.abs(this.currentPrice - stopLoss);
        const lotSize = riskAmount / (stopLossPoints * 10); // Simplified calculation
        
        document.getElementById('lot-size').value = Math.max(0.01, Math.min(10, lotSize)).toFixed(2);
        this.calculateRisk();
        
        window.notifications?.showSuccess(`Lot size calculated: ${lotSize.toFixed(2)}`);
    }

    calculateRisk() {
        const lotSize = parseFloat(document.getElementById('lot-size').value) || 0;
        const stopLoss = parseFloat(document.getElementById('stop-loss').value);
        const takeProfit = parseFloat(document.getElementById('take-profit').value);

        if (!stopLoss || lotSize === 0) {
            document.getElementById('risk-summary').style.display = 'none';
            return;
        }

        // Calculate risk
        const stopLossPoints = Math.abs(this.currentPrice - stopLoss);
        const riskAmount = stopLossPoints * lotSize * 10; // Simplified
        const riskPercent = (riskAmount / this.accountBalance) * 100;

        // Calculate potential profit
        let potentialProfit = 0;
        let riskRewardRatio = 0;
        if (takeProfit) {
            const takeProfitPoints = Math.abs(takeProfit - this.currentPrice);
            potentialProfit = takeProfitPoints * lotSize * 10;
            riskRewardRatio = potentialProfit / riskAmount;
        }

        // Update UI
        document.getElementById('risk-amount').textContent = `$${riskAmount.toFixed(2)}`;
        document.getElementById('risk-percent').textContent = `${riskPercent.toFixed(2)}%`;
        document.getElementById('potential-profit').textContent = `$${potentialProfit.toFixed(2)}`;
        document.getElementById('risk-reward').textContent = `1:${riskRewardRatio.toFixed(2)}`;
        document.getElementById('risk-summary').style.display = 'block';
    }

    async executeTrade() {
        const lotSize = parseFloat(document.getElementById('lot-size').value);
        const stopLoss = parseFloat(document.getElementById('stop-loss').value);
        const takeProfit = parseFloat(document.getElementById('take-profit').value);

        // Validation
        if (!lotSize || lotSize <= 0) {
            window.notifications?.showError('Please enter a valid lot size');
            return;
        }

        if (!stopLoss) {
            window.notifications?.showError('Please enter Stop Loss');
            return;
        }

        // Create trade object
        const trade = {
            symbol: this.symbol,
            type: this.orderType.toUpperCase(),
            entry_price: this.currentPrice,
            lot_size: lotSize,
            stop_loss: stopLoss,
            take_profit: takeProfit || null,
            timestamp: new Date().toISOString()
        };

        // In a real implementation, you would send this to your backend
        console.log('Executing trade:', trade);

        // Show success notification
        window.notifications?.showSuccess(
            `${trade.type} order placed: ${trade.lot_size} lots @ ${trade.entry_price}`
        );

        // Close modal
        this.close();

        // Optionally refresh trades list
        if (window.location.pathname.includes('trades.html')) {
            // Reload trades if on trades page
            setTimeout(() => {
                if (typeof loadTradeHistory === 'function') {
                    loadTradeHistory();
                }
            }, 1000);
        }
    }
}

// Initialize global instance
window.tradeModal = new TradeExecutionModal();

// Example usage:
// tradeModal.open('XAUUSD', 4106.50);
