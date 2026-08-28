const fs = require('fs');

const htmlPath = 'B:\\Project MT5\\Other\\Dokumen\\diagram_arsitektur.html';
const html = fs.readFileSync(htmlPath, 'utf8');

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
    console.error('ERROR: No script tag found in HTML!');
    process.exit(1);
}

const scriptCode = scriptMatch[1];
const lines = scriptCode.split('\n');

// Write script to scratch/temp_script.js and run node --check
fs.writeFileSync('B:\\Project MT5\\scratch\\temp_script.js', scriptCode, 'utf8');
console.log('Wrote scratch/temp_script.js');
