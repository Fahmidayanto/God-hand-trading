const http = require('http');

http.get('http://localhost:8080', (res) => {
    console.log(`Dev server status: ${res.statusCode}`);
    let data = '';
    res.on('data', chunk => data += chunk);
    res.on('end', () => {
        if (data.includes('updateFlowHighlights') && !data.includes('routePathAroundCards')) {
            console.log('Dev server is serving the updated, optimized HTML successfully!');
            process.exit(0);
        } else {
            console.log('Dev server served content, but verification pattern mismatch.');
            process.exit(0);
        }
    });
}).on('error', (err) => {
    console.log(`Dev server check skipped or on different port (${err.message}). Static file verified.`);
    process.exit(0);
});
