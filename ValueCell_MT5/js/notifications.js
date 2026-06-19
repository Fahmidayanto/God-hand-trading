/**
 * ValueCell Notification System
 * Real-time browser notifications for trading events
 * 
 * Features:
 * - Toast notifications
 * - Browser native notifications
 * - Sound alerts
 * - Notification queue
 */

class NotificationSystem {
    constructor() {
        this.queue = [];
        this.isProcessing = false;
        this.sounds = {
            success: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuHzfPEfS0GLIjP8tqKOQgbb77u5qBRDQpPqOPuslwYAzKR1fHIbycHH3g='), // Success sound
            error: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuHzfPEfS0GLIjP8tqKOQgbb77u5qBRDQpPqOPuslwYAzKR1fHIbycHH3g='), // Error sound
            info: new Audio('data:audio/wav;base64,UklGRnoGAABXQVZFZm10IBAAAAABAAEAQB8AAEAfAAABAAgAZGF0YQoGAACBhYqFbF1fdJivrJBhNjVgodDbq2EcBj+a2/LDciUFLIHO8tiJNwgZaLvt559NEAxQp+PwtmMcBjiR1/LMeSwFJHfH8N2QQAoUXrTp66hVFApGn+DyvmwhBSuHzfPEfS0GLIjP8tqKOQgbb77u5qBRDQpPqOPuslwYAzKR1fHIbycHH3g=')  // Info sound
        };
        this.soundEnabled = false;
        this.browserNotificationsEnabled = false;
        
        this.init();
    }

    async init() {
        // Check if browser notifications are supported
        if ('Notification' in window) {
            const permission = await Notification.requestPermission();
            this.browserNotificationsEnabled = permission === 'granted';
        }

        // Load sound preference
        const settings = JSON.parse(localStorage.getItem('valuecell_settings') || '{}');
        this.soundEnabled = settings.notifications?.soundEffects || false;

        // Create notification container
        this.createNotificationContainer();
    }

    createNotificationContainer() {
        if (document.getElementById('notification-container')) return;

        const container = document.createElement('div');
        container.id = 'notification-container';
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 9999;
            display: flex;
            flex-direction: column;
            gap: 12px;
            max-width: 400px;
        `;
        document.body.appendChild(container);
    }

    /**
     * Show a toast notification
     * @param {string} message - Notification message
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     * @param {number} duration - Duration in milliseconds (default: 3000)
     * @param {object} options - Additional options
     */
    showToast(message, type = 'info', duration = 3000, options = {}) {
        const notification = document.createElement('div');
        notification.className = `toast-notification toast-${type}`;
        
        const icon = this.getIcon(type);
        const colors = this.getColors(type);
        
        notification.innerHTML = `
            <div style="display: flex; align-items: start; gap: 12px;">
                <div style="font-size: 20px;">${icon}</div>
                <div style="flex: 1;">
                    <div style="font-weight: 600; margin-bottom: 4px;">${options.title || this.getTitle(type)}</div>
                    <div style="font-size: 13px; opacity: 0.9;">${message}</div>
                </div>
                <button onclick="this.parentElement.parentElement.remove()" style="background: none; border: none; color: white; font-size: 20px; cursor: pointer; opacity: 0.7; transition: opacity 0.3s;">×</button>
            </div>
        `;
        
        notification.style.cssText = `
            background: ${colors.bg};
            color: white;
            padding: 16px;
            border-radius: 12px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.4);
            animation: slideIn 0.3s ease;
            min-width: 300px;
            border-left: 4px solid ${colors.border};
        `;

        const container = document.getElementById('notification-container');
        container.appendChild(notification);

        // Play sound if enabled
        if (this.soundEnabled && this.sounds[type]) {
            this.sounds[type].play().catch(() => {});
        }

        // Auto remove
        setTimeout(() => {
            notification.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => notification.remove(), 300);
        }, duration);

        return notification;
    }

    /**
     * Show browser notification (native)
     * @param {string} title - Notification title
     * @param {string} message - Notification message
     * @param {string} type - Type: 'success', 'error', 'warning', 'info'
     */
    showBrowserNotification(title, message, type = 'info') {
        if (!this.browserNotificationsEnabled) return;

        const icon = this.getIcon(type);
        
        const notification = new Notification(title, {
            body: message,
            icon: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">🤖</text></svg>',
            badge: 'data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><text y="75" font-size="75">' + icon + '</text></svg>',
            tag: 'valuecell-' + Date.now(),
            requireInteraction: type === 'error',
            silent: !this.soundEnabled
        });

        notification.onclick = () => {
            window.focus();
            notification.close();
        };

        return notification;
    }

    /**
     * Show signal notification
     * @param {object} signal - Signal data
     */
    showSignalNotification(signal) {
        const message = `${signal.signal_type} ${signal.direction} @ ${signal.price} (Confidence: ${signal.confidence.toFixed(0)}%)`;
        const title = `New Trading Signal: ${signal.symbol}`;
        
        this.showToast(message, 'info', 5000, { title });
        
        const settings = JSON.parse(localStorage.getItem('valuecell_settings') || '{}');
        if (settings.notifications?.newSignals) {
            this.showBrowserNotification(title, message, 'info');
        }
    }

    /**
     * Show trade execution notification
     * @param {object} trade - Trade data
     */
    showTradeNotification(trade) {
        const type = trade.pnl >= 0 ? 'success' : 'error';
        const message = `${trade.type} ${trade.symbol} @ ${trade.entry_price} - P&L: $${trade.pnl.toFixed(2)}`;
        const title = trade.status === 'OPEN' ? 'Trade Opened' : 'Trade Closed';
        
        this.showToast(message, type, 5000, { title });
        
        const settings = JSON.parse(localStorage.getItem('valuecell_settings') || '{}');
        if (settings.notifications?.tradeExecution) {
            this.showBrowserNotification(title, message, type);
        }
    }

    /**
     * Show error notification
     * @param {string} message - Error message
     */
    showError(message) {
        this.showToast(message, 'error', 5000);
        
        const settings = JSON.parse(localStorage.getItem('valuecell_settings') || '{}');
        if (settings.notifications?.systemErrors) {
            this.showBrowserNotification('System Error', message, 'error');
        }
    }

    /**
     * Show success notification
     * @param {string} message - Success message
     */
    showSuccess(message) {
        this.showToast(message, 'success', 3000);
    }

    /**
     * Show warning notification
     * @param {string} message - Warning message
     */
    showWarning(message) {
        this.showToast(message, 'warning', 4000);
    }

    /**
     * Show info notification
     * @param {string} message - Info message
     */
    showInfo(message) {
        this.showToast(message, 'info', 3000);
    }

    getIcon(type) {
        const icons = {
            success: '✅',
            error: '❌',
            warning: '⚠️',
            info: 'ℹ️'
        };
        return icons[type] || icons.info;
    }

    getTitle(type) {
        const titles = {
            success: 'Success',
            error: 'Error',
            warning: 'Warning',
            info: 'Information'
        };
        return titles[type] || titles.info;
    }

    getColors(type) {
        const colors = {
            success: { bg: 'linear-gradient(135deg, #10b981, #059669)', border: '#34d399' },
            error: { bg: 'linear-gradient(135deg, #ef4444, #dc2626)', border: '#f87171' },
            warning: { bg: 'linear-gradient(135deg, #f59e0b, #d97706)', border: '#fbbf24' },
            info: { bg: 'linear-gradient(135deg, #3b82f6, #2563eb)', border: '#60a5fa' }
        };
        return colors[type] || colors.info;
    }
}

// Add animation styles
const style = document.createElement('style');
style.textContent = `
    @keyframes slideIn {
        from {
            transform: translateX(400px);
            opacity: 0;
        }
        to {
            transform: translateX(0);
            opacity: 1;
        }
    }
    
    @keyframes slideOut {
        from {
            transform: translateX(0);
            opacity: 1;
        }
        to {
            transform: translateX(400px);
            opacity: 0;
        }
    }
    
    .toast-notification {
        transition: all 0.3s ease;
    }
    
    .toast-notification:hover {
        transform: translateY(-2px);
        box-shadow: 0 12px 40px rgba(0,0,0,0.5) !important;
    }
`;
document.head.appendChild(style);

// Create global instance
window.notifications = new NotificationSystem();

// Example usage:
// notifications.showSuccess('Settings saved!');
// notifications.showError('Failed to connect to MT5');
// notifications.showWarning('High risk detected');
// notifications.showInfo('System update available');
// notifications.showSignalNotification(signalData);
// notifications.showTradeNotification(tradeData);
