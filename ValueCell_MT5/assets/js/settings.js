/* Settings Page JavaScript */

document.addEventListener('DOMContentLoaded', function() {
    const navBtns = document.querySelectorAll('.settings-nav-btn');
    const sections = document.querySelectorAll('.settings-section');
    
    // Section switching
    navBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            const targetSection = btn.getAttribute('data-section');
            
            // Remove active class
            navBtns.forEach(b => b.classList.remove('active'));
            sections.forEach(s => s.classList.remove('active'));
            
            // Add active class
            btn.classList.add('active');
            document.querySelector(`.settings-section[data-section="${targetSection}"]`).classList.add('active');
        });
    });
    
    // Save button handlers
    const saveBtns = document.querySelectorAll('.btn-save');
    saveBtns.forEach(btn => {
        btn.addEventListener('click', () => {
            alert('Settings saved! (This is a prototype - no actual save occurs)');
        });
    });
    
    // Range slider value display
    const rangeInputs = document.querySelectorAll('.setting-slider');
    rangeInputs.forEach(slider => {
        slider.addEventListener('input', (e) => {
            const helpText = e.target.nextElementSibling;
            if (helpText && helpText.classList.contains('setting-help')) {
                const value = e.target.value;
                helpText.innerHTML = `Minimum confidence: <strong>${value}%</strong>`;
            }
        });
    });
});
