const fs = require('fs');
const vm = require('vm');

const htmlPath = 'B:\\Project MT5\\Other\\Dokumen\\diagram_arsitektur.html';
const html = fs.readFileSync(htmlPath, 'utf8');

const scriptMatch = html.match(/<script>([\s\S]*?)<\/script>/);
if (!scriptMatch) {
    console.error('ERROR: No script tag found in HTML!');
    process.exit(1);
}

const scriptCode = scriptMatch[1];

try {
    new vm.Script(scriptCode);
    console.log('SUCCESS: JavaScript syntax in diagram_arsitektur.html is 100% valid!');
} catch (e) {
    console.error('SYNTAX ERROR in script:', e.message);
    process.exit(1);
}
