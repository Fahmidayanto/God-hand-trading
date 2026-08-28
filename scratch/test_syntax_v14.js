const fs = require('fs');
const html = fs.readFileSync('Other/Dokumen/diagram_arsitektur.html', 'utf8');

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
    console.error("No script tag found!");
    process.exit(1);
}

try {
    new Function(scriptMatch[1]);
    console.log("JavaScript syntax in diagram_arsitektur.html is 100% VALID!");
} catch (e) {
    console.error("JS Syntax Error:", e);
    process.exit(1);
}
