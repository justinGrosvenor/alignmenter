import assert from 'node:assert/strict';
import { createHash } from 'node:crypto';
import { readFileSync } from 'node:fs';
import { createRequire } from 'node:module';
import { dirname, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { verifyBraces } from './braces-probes.mjs';

export const root = resolve(dirname(fileURLToPath(import.meta.url)), '../..');
const manifest = JSON.parse(readFileSync(new URL('./braces-manifest.json', import.meta.url)));
const digest = (path) => createHash('sha256').update(readFileSync(path)).digest('hex');

export function verifyCorrection(directory = root, apply = false) {
  const lock = JSON.parse(readFileSync(resolve(directory, 'package-lock.json')));
  assert.equal(digest(resolve(directory, manifest.patch)), manifest.patchHash, 'Reviewed patch bytes changed');
  const copies = Object.entries(lock.packages).filter(([path]) => path.endsWith('node_modules/braces'));
  assert.ok(copies.length > 0, 'No locked braces package');
  const parents = Object.entries(lock.packages)
    .filter(([, value]) => value.dependencies?.braces || value.optionalDependencies?.braces || value.peerDependencies?.braces)
    .map(([path]) => path).sort();
  assert.deepEqual(parents, manifest.parents, 'Braces consumer set changed; review required');
  const locations = new Set();
  for (const [path, entry] of copies) {
    assert.equal(entry.version, manifest.version, 'Unreviewed locked braces version');
    const location = resolve(directory, path);
    const installed = JSON.parse(readFileSync(resolve(location, 'package.json')));
    assert.equal(installed.version, manifest.version, 'Unreviewed installed braces version');
    const matches = (expected) => Object.entries(expected).every(([source, hash]) => digest(resolve(location, source)) === hash);
    if (apply && !matches(manifest.after)) {
      assert.ok(matches(manifest.before), 'Installed braces is neither reviewed upstream nor patched source');
      const result = spawnSync('patch', ['--batch', '-p1', '--fuzz=0', '-i', resolve(directory, manifest.patch)], { cwd: location, encoding: 'utf8' });
      assert.equal(result.status, 0, `Patch application failed: ${result.stderr}`);
    }
    assert.ok(matches(manifest.after), 'Installed braces security source does not match reviewed patch');
    verifyBraces(createRequire(resolve(location, 'package.json'))('./'));
    locations.add(location);
  }
  for (const parent of parents) {
    const require = createRequire(resolve(directory, parent, 'package.json'));
    const actual = dirname(require.resolve('braces/package.json'));
    assert.ok(locations.has(actual), `Unverified braces resolved by ${parent}`);
  }
  return { package: 'braces', version: manifest.version, advisory: 'GHSA-vfj7-8cjw-p6xm', patchHash: manifest.patchHash, copies: [...locations], status: 'verified local correction; raw advisory retained' };
}

if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  console.log(JSON.stringify(verifyCorrection(root, process.argv.includes('--apply')), null, 2));
}
