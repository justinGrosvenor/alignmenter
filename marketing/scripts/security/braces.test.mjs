import assert from 'node:assert/strict';
import { test } from 'node:test';
import { cpSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { resolve } from 'node:path';
import { createRequire } from 'node:module';
import { root, verifyCorrection } from './braces.mjs';
import { verifyBraces } from './braces-probes.mjs';
import { classifyAudit } from './audit.mjs';

const require = createRequire(import.meta.url);
const advisory = { source: 1240992, name: 'braces', dependency: 'braces', url: 'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm', range: '<=3.0.3', severity: 'high' };
const report = () => ({ auditReportVersion: 2, vulnerabilities: { braces: { name: 'braces', via: [{ ...advisory }] }, micromatch: { name: 'micromatch', via: ['braces'] } }, metadata: { vulnerabilities: { total: 2 } } });

test('installed backport rejects excessive strings, attempted bound overrides and direct ASTs while retaining normal patterns', () => {
  verifyBraces(require('braces'));
  verifyCorrection();
  const micromatch = require('micromatch');
  assert.deepEqual(micromatch(['src/a.ts', 'src/b.ts', 'src/c.js'], 'src/{a,b}.ts'), ['src/a.ts', 'src/b.ts']);
  assert.throws(() => micromatch.braceExpand('{'.repeat(101) + 'a,b' + '}'.repeat(101)), /exceeds max depth/);
});

test('verification fails for missing/tampered patch, changed installed source, version or consumer set', () => {
  const temp = mkdtempSync(resolve(tmpdir(), 'alignmenter-braces-'));
  try {
    cpSync(resolve(root, 'patches'), resolve(temp, 'patches'), { recursive: true });
    cpSync(resolve(root, 'package-lock.json'), resolve(temp, 'package-lock.json'));
    const patch = resolve(temp, 'patches/braces@3.0.3.patch');
    writeFileSync(patch, readFileSync(patch, 'utf8') + '\n');
    assert.throws(() => verifyCorrection(temp), /patch bytes changed/);
    cpSync(resolve(root, 'patches/braces@3.0.3.patch'), patch);
    const lock = JSON.parse(readFileSync(resolve(temp, 'package-lock.json')));
    lock.packages['node_modules/unreviewed'] = { dependencies: { braces: '^3.0.3' } };
    writeFileSync(resolve(temp, 'package-lock.json'), JSON.stringify(lock));
    assert.throws(() => verifyCorrection(temp), /consumer set changed/);
    delete lock.packages['node_modules/unreviewed'];
    lock.packages['node_modules/braces'].version = '3.0.4';
    writeFileSync(resolve(temp, 'package-lock.json'), JSON.stringify(lock));
    assert.throws(() => verifyCorrection(temp), /Unreviewed locked/);
    lock.packages['node_modules/braces'].version = '3.0.3';
    writeFileSync(resolve(temp, 'package-lock.json'), JSON.stringify(lock));
    cpSync(resolve(root, 'node_modules/braces'), resolve(temp, 'node_modules/braces'), { recursive: true });
    writeFileSync(resolve(temp, 'node_modules/braces/lib/compile.js'), 'module.exports = () => "tampered";');
    assert.throws(() => verifyCorrection(temp), /security source does not match/);
  } finally { rmSync(temp, { recursive: true, force: true }); }
});

test('audit retains only the exact verified advisory and fully derived findings', () => {
  assert.deepEqual(classifyAudit(report(), 1).remaining, []);
  assert.deepEqual(classifyAudit(report(), 1).verifiedLocalCorrections, ['braces', 'micromatch']);
  const changed = report();
  changed.vulnerabilities.braces.via[0].source++;
  assert.deepEqual(classifyAudit(changed, 1).remaining, ['braces', 'micromatch']);
});

test('new advisories, mixed causes and causal cycles stay unresolved', () => {
  const extra = report();
  extra.vulnerabilities.micromatch.via.push({ ...advisory, name: 'micromatch', source: 999 });
  assert.deepEqual(classifyAudit(extra, 1).remaining, ['micromatch']);
  const cycle = report();
  cycle.vulnerabilities.braces.via = ['micromatch'];
  assert.deepEqual(classifyAudit(cycle, 1).remaining, ['braces', 'micromatch']);
  assert.throws(() => classifyAudit(report(), 2), /audit failed/);
  assert.throws(() => classifyAudit(report(), 0), /Inconsistent audit exit status/);
  assert.throws(() => classifyAudit({ ...report(), metadata: { vulnerabilities: { total: 0 } } }, 1), /Inconsistent audit totals/);
  assert.throws(() => classifyAudit({}, 0), /Unexpected audit format/);
  assert.throws(() => classifyAudit({ ...report(), error: {} }, 1), /Registry returned/);
});
