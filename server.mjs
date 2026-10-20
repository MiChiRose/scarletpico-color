import { createServer } from 'node:http';
import { readFile, readdir, stat } from 'node:fs/promises';
import { extname, join, normalize, relative } from 'node:path';
import { fileURLToPath } from 'node:url';

const root = fileURLToPath(new URL('.', import.meta.url));
const port = Number(process.env.SCARLETPICO_PORT || 4173);
const types = new Map([
  ['.html', 'text/html; charset=utf-8'], ['.css', 'text/css; charset=utf-8'],
  ['.js', 'text/javascript; charset=utf-8'], ['.json', 'application/json; charset=utf-8'],
  ['.wasm', 'application/wasm'], ['.gb', 'application/octet-stream'], ['.gbc', 'application/octet-stream']
]);

function cleanTitle(buffer, fallback) {
  const bytes = buffer.subarray(0x134, 0x144);
  const zero = bytes.indexOf(0);
  const title = Buffer.from(zero >= 0 ? bytes.subarray(0, zero) : bytes).toString('ascii').replace(/[^\x20-\x7e]/g, '').trim();
  return title || fallback.replace(/\.(gbc?|GBC?)$/, '');
}

async function games() {
  const folder = join(root, 'roms');
  const names = (await readdir(folder)).filter((name) => /\.gbc?$/i.test(name)).sort(Intl.Collator('en').compare);
  return Promise.all(names.map(async (name) => {
    const data = await readFile(join(folder, name));
    const colorFlag = data[0x143];
    return {
      id: Buffer.from(name).toString('base64url'),
      name: cleanTitle(data, name),
      fileName: name,
      path: `/roms/${encodeURIComponent(name)}`,
      system: colorFlag === 0x80 || colorFlag === 0xc0 ? 'GBC' : 'GB',
      size: data.length
    };
  }));
}

function safePath(urlPath) {
  const decoded = decodeURIComponent(urlPath === '/' ? '/app/index.html' : urlPath);
  const target = normalize(join(root, decoded));
  return relative(root, target).startsWith('..') ? null : target;
}

const server = createServer(async (request, response) => {
  try {
    if (request.url === '/api/games') {
      const body = JSON.stringify(await games());
      response.writeHead(200, {'content-type': types.get('.json'), 'cache-control': 'no-store'});
      response.end(body);
      return;
    }
    const pathname = new URL(request.url, `http://${request.headers.host}`).pathname;
    const file = safePath(pathname);
    if (!file || !(await stat(file)).isFile()) throw Object.assign(new Error('Not found'), {code: 'ENOENT'});
    response.writeHead(200, {
      'content-type': types.get(extname(file).toLowerCase()) || 'application/octet-stream',
      'cache-control': extname(file) === '.wasm' ? 'public, max-age=3600' : 'no-store'
    });
    response.end(await readFile(file));
  } catch (error) {
    response.writeHead(error.code === 'ENOENT' ? 404 : 500, {'content-type': 'text/plain; charset=utf-8'});
    response.end(error.code === 'ENOENT' ? 'Not found' : 'ScarletPico server error');
  }
});

server.listen(port, '127.0.0.1', () => {
  console.log(`ScarletPico Color is ready at http://127.0.0.1:${port}`);
});
