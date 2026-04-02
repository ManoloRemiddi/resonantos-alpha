const test = require('node:test');
const assert = require('node:assert/strict');
const fs = require('node:fs');
const os = require('node:os');
const path = require('node:path');
const { spawnSync } = require('node:child_process');

const detector = require('../detector-cli.js');
const clusteringFixture = require('./fixtures/clustering-fixture.json');
const optionsFixture = require('./fixtures/options-fixture.json');

const detectorCliPath = path.join(__dirname, '..', 'detector-cli.js');

function runDetectorCli(args) {
  const result = spawnSync(process.execPath, [detectorCliPath, '--quiet', '--json-only', ...args], {
    encoding: 'utf8',
  });

  if (result.status !== 0) {
    throw new Error([
      `Detector CLI failed with status ${result.status}`,
      result.stdout,
      result.stderr,
    ].filter(Boolean).join('\n'));
  }

  return result;
}

test('fixture-driven clustering reconciles realistic candidates and prioritizes the actionable cluster', () => {
  const clusters = detector.buildInstanceClusters(
    clusteringFixture.configCandidates,
    clusteringFixture.services,
    clusteringFixture.docker,
    clusteringFixture.processes,
    clusteringFixture.environment
  );

  assert.equal(clusters.length, 2);

  const primary = clusters[0];
  assert.equal(primary.instanceName, 'Alpha');
  assert.equal(primary.configCandidateCount, 3);
  assert.equal(primary.openclawConfigPath, '/tmp/resonant-alpha/config/openclaw.json');
  assert.equal(primary.candidateCanonicalLike, true);
  assert.equal(primary.reconciliation.score > 0, true);
  assert.deepEqual(primary.reconciledFromDedupeKeys.sort(), [
    'family_port|/tmp/resonant-alpha|24510',
    'workspace_port|/tmp/workspaces/alpha|24510',
  ]);

  const backupLike = clusters[1];
  assert.equal(backupLike.candidateBackupLike, true);
  assert.equal(detector.selectPrimaryActionableCluster(clusters).dedupeKey, primary.dedupeKey);
  assert.equal(detector.compareResolvedInstancesForPriority(primary, backupLike) < 0, true);
});

test('standard ~/.openclaw layout infers workspace path when config omits it', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'resonantos-workspace-fallback-'));
  const dotOpenclaw = path.join(tempDir, '.openclaw');
  const workspaceDir = path.join(dotOpenclaw, 'workspace');
  fs.mkdirSync(workspaceDir, { recursive: true });

  const configPath = path.join(dotOpenclaw, 'openclaw.json');
  fs.writeFileSync(configPath, JSON.stringify({ gateway: { port: 18820 } }, null, 2), 'utf8');

  assert.equal(detector.deriveWorkspacePathFromConfigPath(configPath), workspaceDir);
});

test('installer options are generated in expected v3 order with lower-confidence possible match last among detected installs', () => {
  const options = detector.buildInstallerOptions(optionsFixture.instanceClusters);
  const optionIds = options.map(option => option.optionId);

  assert.deepEqual(optionIds, [
    'detected:workspace_port|/tmp/workspaces/alpha|24510',
    'detected:workspace_only|/tmp/workspaces/bravo',
    'detected:family_only|/tmp/possible-charlie',
    'new-install',
    'manual-existing-target',
  ]);

  assert.equal(options[0].sortGroup, 'recommendedExisting');
  assert.equal(options[1].sortGroup, 'otherExisting');
  assert.equal(options[2].sortGroup, 'possibleMatches');
  assert.equal(options[2].optionType, 'possibleMatch');
  assert.equal(options[2].confidence, 'low');
  assert.equal(options[2].warningLevel, 'warning');
  assert.match(options[2].warnings[0], /lower/i);

  const summary = detector.buildInstallerOptionSummary(options);
  assert.deepEqual(summary, {
    total: 5,
    recommendedOptionId: 'detected:workspace_port|/tmp/workspaces/alpha|24510',
    recommendedCount: 1,
    existingCount: 2,
    possibleMatchCount: 1,
    newCount: 1,
    manualCount: 1,
  });
});

test('confirmed selection maps possibleMatch back to existing selection semantics', () => {
  const options = detector.buildInstallerOptions(optionsFixture.instanceClusters);
  const possibleMatch = options.find(option => option.optionType === 'possibleMatch');
  assert.ok(possibleMatch);

  const confirmed = detector.resolveConfirmedSelection(options, possibleMatch.optionId);
  assert.deepEqual(confirmed, {
    selectionType: 'existing',
    selectedOptionId: possibleMatch.optionId,
    displayLabel: possibleMatch.displayLabel,
    configPath: '/tmp/possible-charlie/.openclaw/openclaw.json',
    workspacePath: null,
    installRoot: '/tmp/possible-charlie',
    runtimeKind: 'unknown',
    isRunning: false,
    confidence: 'low',
    confirmedByUser: true,
  });
});

test('handoff payload shape includes installerDecision, availableOptions, and confirmedSelection', () => {
  const options = detector.buildInstallerOptions(optionsFixture.instanceClusters);
  const selectedOptionId = options[1].optionId;
  const report = {
    generatedAt: '2026-04-03T00:00:00.000Z',
    detectorVersion: 'v3-identity-runtime-dependency-gates',
    installerOptions: options,
  };

  const handoff = detector.buildInstallerHandoff(report, {
    reportPath: '/tmp/report.json',
    selectedOptionId,
  });

  assert.equal(handoff.schemaVersion, '1.1');
  assert.equal(handoff.reportPath, '/tmp/report.json');
  assert.ok(Array.isArray(handoff.installerDecision.availableOptions));
  assert.equal(handoff.installerDecision.availableOptions.length, 5);
  assert.equal(handoff.installerDecision.optionSummary.recommendedOptionId, options[0].optionId);
  assert.equal(handoff.installerDecision.selectedOptionId, selectedOptionId);
  assert.deepEqual(handoff.installerDecision.confirmedSelection, {
    selectionType: 'existing',
    selectedOptionId,
    displayLabel: options[1].displayLabel,
    configPath: '/tmp/resonant-bravo/config/openclaw.json',
    workspacePath: '/tmp/workspaces/bravo',
    installRoot: '/tmp/resonant-bravo',
    runtimeKind: 'user-process',
    isRunning: false,
    confidence: 'high',
    confirmedByUser: true,
  });
});

test('end-to-end smoke: detector CLI writes installer option output with expected handoff shape', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'resonantos-detector-smoke-'));
  const handoffPath = path.join(tempDir, 'handoff.json');

  runDetectorCli(['--out-dir', tempDir, '--handoff-file', handoffPath]);

  const handoff = JSON.parse(fs.readFileSync(handoffPath, 'utf8'));
  assert.equal(handoff.schemaVersion, '1.1');
  assert.ok(path.isAbsolute(handoff.reportPath));
  assert.ok(fs.existsSync(handoff.reportPath));
  assert.ok(handoff.report);
  assert.ok(handoff.installerDecision);
  assert.ok(Array.isArray(handoff.installerDecision.availableOptions));
  assert.ok(handoff.installerDecision.availableOptions.length >= 2);
  assert.equal(handoff.installerDecision.optionSummary.total, handoff.installerDecision.availableOptions.length);
  assert.equal(handoff.installerDecision.confirmedSelection, null);

  const report = handoff.report;
  assert.ok(report.summary);
  assert.ok(Array.isArray(report.installerOptions));
  assert.equal(report.installerOptions.length, handoff.installerDecision.availableOptions.length);
});

test('end-to-end smoke: --select-option-id produces confirmedSelection in handoff output', () => {
  const tempDir = fs.mkdtempSync(path.join(os.tmpdir(), 'resonantos-detector-select-'));
  const firstHandoffPath = path.join(tempDir, 'handoff-initial.json');
  runDetectorCli(['--out-dir', tempDir, '--handoff-file', firstHandoffPath]);

  const initialHandoff = JSON.parse(fs.readFileSync(firstHandoffPath, 'utf8'));
  const selectable = initialHandoff.installerDecision.availableOptions.find(option => option.optionType === 'existing')
    || initialHandoff.installerDecision.availableOptions.find(option => option.optionType === 'possibleMatch');

  assert.ok(selectable, 'expected at least one detected selectable option');

  const selectedHandoffPath = path.join(tempDir, 'handoff-selected.json');
  runDetectorCli([
    '--out-dir', tempDir,
    '--handoff-file', selectedHandoffPath,
    '--select-option-id', selectable.optionId,
  ]);

  const selectedHandoff = JSON.parse(fs.readFileSync(selectedHandoffPath, 'utf8'));
  const confirmed = selectedHandoff.installerDecision.confirmedSelection;

  assert.ok(confirmed);
  assert.equal(confirmed.selectedOptionId, selectable.optionId);
  assert.equal(confirmed.confirmedByUser, true);
  assert.equal(confirmed.displayLabel, selectable.displayLabel);
  assert.equal(confirmed.selectionType === 'existing' || confirmed.selectionType === selectable.optionType, true);
  assert.equal(selectedHandoff.installerDecision.selectedOptionId, selectable.optionId);
});
