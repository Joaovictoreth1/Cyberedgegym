import { execFileSync } from 'node:child_process';
import { copyFile, mkdir, readFile, writeFile } from 'node:fs/promises';

const production = process.argv.includes('--production');
const configuredUrl = process.env.CYBEREDGE_API_URL ?? (production ? '' : 'http://localhost:8000');
if (!configuredUrl) {
    throw new Error('Set CYBEREDGE_API_URL to the deployed HTTPS API origin.');
}

const api = new URL(configuredUrl);
const local = !production && ['localhost', '127.0.0.1', '[::1]'].includes(api.hostname);
if (
    (api.protocol !== 'https:' && !(local && api.protocol === 'http:')) ||
    api.username || api.password || configuredUrl.trim() !== configuredUrl ||
    ![api.origin, api.origin + '/'].includes(configuredUrl)
) {
    throw new Error('CYBEREDGE_API_URL must be an HTTPS origin (localhost HTTP is allowed for development).');
}

let html = await readFile('index.html', 'utf8');
html = html.replace('__API_BASE_URL__', api.origin).replace('__API_ORIGIN__', api.origin);
await mkdir('dist', { recursive: true });
execFileSync(process.execPath, [
    'node_modules/tailwindcss/lib/cli.js', '--input', 'frontend/site.css', '--output', 'dist/site.css',
    '--no-autoprefixer',
], { stdio: 'inherit' });
await Promise.all([
    writeFile('dist/index.html', html),
    writeFile('dist/.nojekyll', ''),
    ...['effects.js', 'lead-form.js'].map(file => copyFile('frontend/' + file, 'dist/' + file)),
]);
