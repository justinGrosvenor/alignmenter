import assert from 'node:assert/strict';
import { spawnSync } from 'node:child_process';
import { mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { root, verifyCorrection } from './braces.mjs';

const advisory = { source: 1240992, name: 'braces', dependency: 'braces', url: 'https://github.com/advisories/GHSA-vfj7-8cjw-p6xm', range: '<=3.0.3', severity: 'high' };

export function classifyAudit(report, status) {
  assert.ok(status === 0 || status === 1, 'npm audit failed before producing a valid result');
  assert.equal(report.auditReportVersion, 2, 'Unexpected audit format');
  assert.ok(report.vulnerabilities && report.metadata?.vulnerabilities, 'Missing audit results');
  assert.equal(report.error, undefined, 'Registry returned an audit error');
  const records = report.vulnerabilities;
  assert.equal(report.metadata.vulnerabilities.total, Object.keys(records).length, "Inconsistent audit totals");
  assert.equal(status, Object.keys(records).length ? 1 : 0, "Inconsistent audit exit status");
  const corrected = new Set();
  const pending = new Set(Object.keys(records));
  // A transitive finding gets credit only when every causal advisory is this
  // exact, installed-and-probed backport. Unknown advisories and cycles fail.
  for (let progress = true; progress;) {
    progress = false;
    for (const name of pending) {
      const record = records[name];
      assert.equal(record.name, name, 'Audit package identity mismatch');
      assert.ok(Array.isArray(record.via) && record.via.length, 'Missing causal advisory');
      const covered = record.via.every((via) => {
        if (typeof via === 'string') return corrected.has(via);
        return name === 'braces' && Object.entries(advisory).every(([key, value]) => via[key] === value);
      });
      if (covered) { corrected.add(name); pending.delete(name); progress = true; }
    }
  }
  return { verifiedLocalCorrections: [...corrected].sort(), remaining: [...pending].sort(), rawAdvisoryRetained: true };
}

export function runAudit() {
  const output = resolve(process.env.DEPENDENCY_AUDIT_OUTPUT_DIR || root);
  mkdirSync(output, { recursive: true });
  const result = spawnSync('npm', ['audit', '--json'], { cwd: root, encoding: 'utf8' });
  writeFileSync(resolve(output, 'dependency-audit.json'), result.stdout || '');
  writeFileSync(resolve(output, 'dependency-audit.stderr.json'), JSON.stringify({ status: result.status, stderr: result.stderr, error: result.error?.message }, null, 2));
  const correction = verifyCorrection();
  const report = JSON.parse(result.stdout);
  const lock = JSON.parse(readFileSync(resolve(root, "package-lock.json")));
  for (const [name, record] of Object.entries(report.vulnerabilities || {})) {
    assert.ok(Array.isArray(record.nodes) && record.nodes.length, "Missing affected package paths");
    for (const path of record.nodes) assert.ok(path.endsWith(`node_modules/${name}`) && lock.packages[path], "Audit contains an unverified installed package path");
  }
  const disposition = classifyAudit(report, result.status);
  writeFileSync(resolve(output, 'dependency-audit-disposition.json'), JSON.stringify({ correction, ...disposition }, null, 2));
  console.log(JSON.stringify(disposition, null, 2));
  return disposition.remaining.length ? 1 : 0;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = runAudit();
