/* ========================================
   VALUECELL TRADING DASHBOARD - JAVASCRIPT
   Modern • Interactive • Animated
   ======================================== */

// Initialize on DOM ready
document.addEventListener('DOMContentLoaded', function() {
    initProgressBars();
    initLiveClock();
    initUptimeCounter();
    init3DCardEffects();
    initScrollAnimations();
});

/* ========================================
   PROGRESS BAR ANIMATIONS
   ======================================== */
function initProgressBars() {
    const progressBars = document.querySelectorAll('.progress-fill');
    
    progressBars.forEach((bar, index) => {
        const targetWidth = bar.getAttribute('data-progress') || 0;
        
        // Staggered animation
        setTimeout(() => {
            bar.style.width = targetWidth + '%';
        }, index * 100);
    });
}

/* ========================================
   LIVE CLOCK
   ======================================== */
function initLiveClock() {
    const clockElement = document.querySelector('.live-clock');
    
    if (!clockElement) return;
    
    function updateClock() {
        const now = new Date();
        const hours = String(now.getHours()).padStart(2, '0');
        const minutes = String(now.getMinutes()).padStart(2, '0');
        const seconds = String(now.getSeconds()).padStart(2, '0');
        
        clockElement.textContent = `${hours}:${minutes}:${seconds}`;
    }
    
    // Update immediately
    updateClock();
    
    // Update every second
    setInterval(updateClock, 1000);
}

/* ========================================
   UPTIME COUNTER
   ======================================== */
function initUptimeCounter() {
    const uptimeElement = document.querySelector('.uptime-counter');
    
    if (!uptimeElement) return;
    
    const startTime = new Date();
    
    function updateUptime() {
        const now = new Date();
        const diff = Math.floor((now - startTime) / 1000); // seconds
        
        const hours = Math.floor(diff / 3600);
        const minutes = Math.floor((diff % 3600) / 60);
        const seconds = diff % 60;
        
        uptimeElement.textContent = `${hours}h ${minutes}m ${seconds}s`;
    }
    
    // Update immediately
    updateUptime();
    
    // Update every second
    setInterval(updateUptime, 1000);
}

/* ========================================
   3D CARD MOUSE TRACKING
   ======================================== */
function init3DCardEffects() {
    const cards = document.querySelectorAll('.card-3d');
    
    cards.forEach(card => {
        card.addEventListener('mousemove', handleCardMouseMove);
        card.addEventListener('mouseleave', handleCardMouseLeave);
    });
}

function handleCardMouseMove(e) {
    const card = e.currentTarget;
    const rect = card.getBoundingClientRect();
    
    // Calculate mouse position relative to card center
    const centerX = rect.left + rect.width / 2;
    const centerY = rect.top + rect.height / 2;
    
    const mouseX = e.clientX - centerX;
    const mouseY = e.clientY - centerY;
    
    // Calculate rotation angles (subtle effect)
    const rotateX = (mouseY / rect.height) * -10; // -10 to 10 degrees
    const rotateY = (mouseX / rect.width) * 10;   // -10 to 10 degrees
    
    // Apply transform
    card.style.transform = `
        perspective(1000px)
        rotateX(${rotateX}deg)
        rotateY(${rotateY}deg)
        translateZ(10px)
    `;
}

function handleCardMouseLeave(e) {
    const card = e.currentTarget;
    
    // Reset transform with smooth transition
    card.style.transform = `
        perspective(1000px)
        rotateX(0deg)
        rotateY(0deg)
        translateZ(0px)
    `;
}

/* ========================================
   SCROLL ANIMATIONS
   ======================================== */
function initScrollAnimations() {
    const observer = new IntersectionObserver((entries) => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                entry.target.style.opacity = '1';
                entry.target.style.transform = 'translateY(0)';
            }
        });
    }, {
        threshold: 0.1
    });
    
    // Observe all glass cards
    document.querySelectorAll('.glass-card').forEach(card => {
        card.style.opacity = '0';
        card.style.transform = 'translateY(20px)';
        card.style.transition = 'opacity 0.6s ease, transform 0.6s ease';
        observer.observe(card);
    });
}

/* ========================================
   UTILITY FUNCTIONS
   ======================================== */

// Format number with commas
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Format currency
function formatCurrency(amount, decimals = 2) {
    return '$' + amount.toFixed(decimals).replace(/\B(?=(\d{3})+(?!\d))/g, ',');
}

// Format percentage
function formatPercentage(value, decimals = 2) {
    return value.toFixed(decimals) + '%';
}

// Smooth scroll to element
function smoothScrollTo(elementId) {
    const element = document.getElementById(elementId);
    if (element) {
        element.scrollIntoView({ behavior: 'smooth', block: 'start' });
    }
}

// Show notification (for future use)
function showNotification(message, type = 'info') {
    console.log(`[${type.toUpperCase()}] ${message}`);
    // TODO: Implement toast notification UI
}

/* ========================================
   EXPORT FOR OTHER MODULES
   ======================================== */
window.ValueCell = {
    formatNumber,
    formatCurrency,
    formatPercentage,
    smoothScrollTo,
    showNotification
};
