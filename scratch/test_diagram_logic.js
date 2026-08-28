const fs = require('fs');

const HTML_PATH = 'B:\\Project MT5\\Other\\Dokumen\\diagram_arsitektur.html';
const html = fs.readFileSync(HTML_PATH, 'utf8');

const checks = [
    { name: 'updateFlowHighlights defined', pattern: /function updateFlowHighlights\(\)/ },
    { name: 'drawLines defined', pattern: /function drawLines\(\)/ },
    { name: 'card mouseenter calls updateFlowHighlights', pattern: /card\.addEventListener\('mouseenter',[\s\S]*?updateFlowHighlights\(\)/ },
    { name: 'card mouseleave calls updateFlowHighlights', pattern: /card\.addEventListener\('mouseleave',[\s\S]*?updateFlowHighlights\(\)/ },
    { name: 'selectNode calls updateFlowHighlights', pattern: /function selectNode[\s\S]*?updateFlowHighlights\(\)/ },
    { name: 'closeSidePanel calls updateFlowHighlights', pattern: /function closeSidePanel[\s\S]*?updateFlowHighlights\(\)/ },
    { name: 'routePathAroundCards removed', pattern: /routePathAroundCards/, shouldNotExist: true },
    { name: 'fitView defined', pattern: /function fitView\(\)/ },
    { name: 'handleWheelZoom defined', pattern: /function handleWheelZoom/ }
];

let allPassed = true;
checks.forEach(check => {
    const exists = check.pattern.test(html);
    if (check.shouldNotExist) {
        if (exists) {
            console.error(`FAIL: ${check.name} still exists in the file!`);
            allPassed = false;
        } else {
            console.log(`PASS: ${check.name} is cleanly removed.`);
        }
    } else {
        if (exists) {
            console.log(`PASS: ${check.name}`);
        } else {
            console.error(`FAIL: ${check.name} not found!`);
            allPassed = false;
        }
    }
});

if (allPassed) {
    console.log('\nALL VERIFICATION CHECKS PASSED SUCCESSFULLY!');
    process.exit(0);
} else {
    process.exit(1);
}
