#!/usr/bin/env node
/**
 * ResonantOS Installer - Human entrypoint (Phase 1: Detector)
 * User-facing output is intentionally concise.
 */

const fs = require('fs');
const path = require('path');
const readline = require('readline');
const { spawnSync } = require('child_process');

const baseDir = __dirname;
const detectorPath = path.join(baseDir, 'detector-cli.js');
const reportsDir = path.join(baseDir, 'reports', 'human-run');
const handoffPath = path.join(reportsDir, 'latest-handoff.json');

function fail(message, detail) {
  console.error(message);
  if (detail) console.error(detail);
  process.exit(1);
}

function canClearScreen() {
  return Boolean(process.stdin.isTTY && process.stdout.isTTY);
}

function clearScreen() {
  if (!canClearScreen()) return;
  if (typeof console.clear === 'function') {
    console.clear();
    return;
  }

  process.stdout.write('\x1Bc');
}

function printPageHeader(title, subtitle = null) {
  console.log(`ResonantOS Installer — ${title}`);
  if (subtitle) console.log(subtitle);
}

function startPage(title, subtitle = null) {
  clearScreen();
  printPageHeader(title, subtitle);
}

function printDetectionIntroPage() {
  startPage('Welcome', 'Scanning this machine now for installer-ready OpenClaw targets.');
  console.log('\nWhat the installer is checking:');
  console.log('- Existing OpenClaw installs');
  console.log('- Docker availability and related install signals');
  console.log('- Whether this machine already looks ready for an install-over path');
  console.log('\nWhat happens next:');
  console.log('- If a usable instance is found, you can install over it');
  console.log('- If detection misses your install, you can recover it manually');
  console.log('- If nothing is found, you can start a new install');
  console.log('\nThis scan can take about 1–5 minutes. That is normal.');
  console.log('If it lingers for a bit, the installer is still working — feel free to grab a coffee.');
  console.log('\nScan started immediately on launch. Please wait...');
}

async function waitForAnyKey(promptText) {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    console.log(promptText);
    return;
  }

  return new Promise(resolve => {
    const stdin = process.stdin;
    const wasRaw = Boolean(stdin.isRaw);

    const cleanup = () => {
      stdin.removeListener('data', onData);
      if (!wasRaw && typeof stdin.setRawMode === 'function') stdin.setRawMode(false);
      stdin.pause();
    };

    const onData = () => {
      cleanup();
      console.log();
      resolve();
    };

    console.log(promptText);
    if (typeof stdin.setRawMode === 'function') stdin.setRawMode(true);
    stdin.resume();
    stdin.once('data', onData);
  });
}

function readJsonFile(filePath, label) {
  let raw;
  try {
    raw = fs.readFileSync(filePath, 'utf8');
  } catch (error) {
    fail(`Unable to read ${label}: ${filePath}`, error.message);
  }

  try {
    return JSON.parse(raw);
  } catch (error) {
    fail(`Invalid JSON in ${label}: ${filePath}`, error.message);
  }
}

function resetHandoffFile() {
  try {
    if (fs.existsSync(handoffPath)) fs.unlinkSync(handoffPath);
  } catch (error) {
    fail('Unable to reset installer handoff file.', error.message);
  }
}

function runDetector({ selectedOptionId = null, suppressOutput = true, targetConfigPath = null } = {}) {
  resetHandoffFile();

  const args = [detectorPath, '--deep', '--quiet', '--json-only', '--out-dir', reportsDir, '--handoff-file', handoffPath];
  if (selectedOptionId) args.push('--select-option-id', selectedOptionId);
  if (targetConfigPath) args.push('--target-config-path', targetConfigPath);

  const result = spawnSync(process.execPath, args, {
    stdio: suppressOutput ? ['ignore', 'pipe', 'pipe'] : 'inherit',
    encoding: suppressOutput ? 'utf8' : undefined,
    windowsHide: true,
  });

  if (result.error) {
    fail(selectedOptionId ? 'Selection confirmation failed to start.' : 'Assessment failed to start.', result.error.message);
  }

  if (result.status !== 0) {
    const failureDetail = [
      result.signal ? `Detector terminated by signal: ${result.signal}` : null,
      suppressOutput && result.stderr ? String(result.stderr).trim() : null,
      suppressOutput && result.stdout ? String(result.stdout).trim() : null,
    ].filter(Boolean).join('\n\n');

    fail(
      selectedOptionId ? 'Selection confirmation failed.' : 'Assessment failed.',
      failureDetail || null,
    );
  }

  if (!fs.existsSync(handoffPath)) {
    fail(
      selectedOptionId
        ? 'Selection confirmation completed but no installer handoff was written.'
        : 'Assessment completed but no installer handoff was written.',
      handoffPath,
    );
  }

  const handoff = readJsonFile(handoffPath, 'installer handoff');
  if (!handoff || typeof handoff !== 'object') {
    fail('Installer handoff is missing or invalid.', handoffPath);
  }

  const reportPath = handoff.reportPath;
  if (!reportPath || !path.isAbsolute(reportPath)) {
    fail('Installer handoff did not include an absolute reportPath.', JSON.stringify(handoff, null, 2));
  }

  if (!fs.existsSync(reportPath)) {
    fail('Installer handoff referenced a missing report file.', reportPath);
  }

  const report = handoff.report && typeof handoff.report === 'object'
    ? handoff.report
    : readJsonFile(reportPath, 'detector report');

  return { handoff, report, reportPath };
}

function formatPath(value) {
  return value || 'n/a';
}

function depLine(name, d) {
  return `${name}=${d?.version || 'missing'} Status ${(d?.status || 'missing').toUpperCase()}`;
}

function optionSortWeight(option) {
  const sortGroup = String(option?.sortGroup || '');
  const weights = {
    recommendedExisting: 1,
    otherExisting: 2,
    possibleMatches: 3,
    newInstall: 4,
    manualExisting: 5,
  };
  return weights[sortGroup] || 99;
}

function sortedOptions(options) {
  return [...options].sort((a, b) => {
    const groupDiff = optionSortWeight(a) - optionSortWeight(b);
    if (groupDiff) return groupDiff;
    return String(a?.optionId || '').localeCompare(String(b?.optionId || ''));
  });
}

function getDetectedInstances(report) {
  return Array.isArray(report?.instances) ? report.instances.filter((i) => i && i.exists) : [];
}

function getInstallerOptionsFromRun(run) {
  const available = run?.handoff?.installerDecision?.availableOptions;
  if (Array.isArray(available)) return available;
  return Array.isArray(run?.report?.installerOptions) ? run.report.installerOptions : [];
}

function sameResolvedPath(a, b) {
  if (!a || !b) return false;
  try {
    return path.resolve(String(a)) === path.resolve(String(b));
  } catch {
    return false;
  }
}

function getRecoveryOptionFromRun(run, targetConfigPath) {
  const ordered = sortedOptions(getInstallerOptionsFromRun(run));
  if (!ordered.length) return null;

  const exactExisting = ordered.find(option => option.optionType === 'existing' && sameResolvedPath(option.configPath, targetConfigPath));
  if (exactExisting) return exactExisting;

  const exactPossible = ordered.find(option => option.optionType === 'possibleMatch' && sameResolvedPath(option.configPath, targetConfigPath));
  if (exactPossible) return exactPossible;

  return ordered.find(option => option.optionType === 'existing' || option.optionType === 'possibleMatch') || null;
}

function getDetectedInstallOptions(availableOptions) {
  return sortedOptions((availableOptions || []).filter(option => option && option.optionType === 'existing'));
}

function getPossibleMatchOptions(availableOptions) {
  return sortedOptions((availableOptions || []).filter(option => option && option.optionType === 'possibleMatch'));
}

function cardWidth() {
  const columns = Number(process.stdout?.columns || 0);
  if (columns >= 72) return Math.min(columns - 2, 96);
  return 88;
}

function wrapCardText(text, width) {
  const source = String(text ?? '');
  if (!source) return [''];

  const lines = [];
  const paragraphs = source.split(/\r?\n/);

  for (const paragraph of paragraphs) {
    if (!paragraph.trim()) {
      lines.push('');
      continue;
    }

    let current = '';
    for (const word of paragraph.split(/\s+/)) {
      const chunks = [];
      let remaining = word;
      while (remaining.length > width) {
        chunks.push(remaining.slice(0, width));
        remaining = remaining.slice(width);
      }
      if (remaining) chunks.push(remaining);

      for (const chunk of chunks) {
        if (!current) {
          current = chunk;
        } else if ((current + ' ' + chunk).length <= width) {
          current += ` ${chunk}`;
        } else {
          lines.push(current);
          current = chunk;
        }
      }
    }

    if (current) lines.push(current);
  }

  return lines.length ? lines : [''];
}

function cardBorder(width) {
  return `+${'-'.repeat(width - 2)}+`;
}

function cardLine(text, width) {
  return `| ${String(text ?? '').padEnd(width - 4)} |`;
}

function printCardSection(title) {
  console.log(`\n${title}`);
}

function printCardBlock(title, subtitle, lines, badges = []) {
  const width = cardWidth();
  const innerWidth = width - 4;
  console.log(cardBorder(width));

  for (const line of wrapCardText(title, innerWidth)) {
    console.log(cardLine(line, width));
  }

  if (subtitle) {
    console.log(cardLine('', width));
    for (const line of wrapCardText(subtitle, innerWidth)) {
      console.log(cardLine(line, width));
    }
  }

  if (badges.length) {
    console.log(cardLine('', width));
    for (const line of wrapCardText(`[${badges.join(' | ')}]`, innerWidth)) {
      console.log(cardLine(line, width));
    }
  }

  if (lines.length) {
    console.log(cardLine('', width));
    for (const entry of lines) {
      for (const line of wrapCardText(entry, innerWidth)) {
        console.log(cardLine(line, width));
      }
    }
  }

  console.log(cardBorder(width));
}

function instanceLookup(report) {
  return new Map(getDetectedInstances(report).map(instance => [instance.id, instance]));
}

function resonantStatusText(option, instance) {
  const raw = option?.details?.resonantOsInstalled ?? instance?.resonantOsInstalled ?? null;
  if (raw === true) return 'Installed';
  if (raw === false) return 'Not detected';
  return 'Not yet assessed';
}

function gatewaySummary(option, instance) {
  const parts = [];
  if (option?.gatewayPort) parts.push(`Port ${option.gatewayPort}`);

  const statusCode = instance?.gatewayHealth?.statusCode;
  const statusText = instance?.gatewayHealth?.statusText;
  const live = instance?.gatewayHealth?.live;
  if (statusCode || statusText) {
    parts.push(`Health ${[statusCode, statusText].filter(Boolean).join(' ')}`);
  } else if (live) {
    parts.push('Health OK');
  }

  return parts.length ? parts.join(' | ') : 'n/a';
}

function renderInstanceCardLines(option, instance) {
  const lines = [
    `Status: ${option?.isRunning ? 'Running' : 'Not running'}`,
    `ResonantOS: ${resonantStatusText(option, instance)}`,
    `Runtime: ${option?.runtimeKind || instance?.runtimeType || 'unknown'}`,
    `Confidence: ${String(option?.confidence || instance?.confidence || 'unknown').toUpperCase()}`,
    `Config: ${formatPath(option?.configPath || instance?.openclawConfigPath)}`,
    `Workspace: ${formatPath(option?.workspacePath || instance?.workspacePath)}`,
    `Install Root: ${formatPath(option?.installRoot)}`,
    `Gateway: ${gatewaySummary(option, instance)}`,
  ];

  if (option?.evidenceSummary) lines.push(`Evidence: ${option.evidenceSummary}`);
  const warnings = Array.isArray(option?.warnings) ? option.warnings.filter(Boolean) : [];
  warnings.forEach(warning => lines.push(`Warning: ${warning}`));
  return lines;
}

const GENERIC_DEPENDENCY_ORDER = [
  {
    key: 'node',
    name: 'Node',
    explanation: 'Required to run the installer and core JavaScript tooling.',
  },
  {
    key: 'python',
    name: 'Python',
    explanation: 'Used by supporting scripts and system checks.',
  },
  {
    key: 'git',
    name: 'Git',
    explanation: 'Needed for repository and source management tasks.',
  },
];

function shellQuote(value) {
  const text = String(value ?? '');
  if (!text) return "''";
  return `'${text.replace(/'/g, `'"'"'`)}'`;
}

function buildDependencyRemediationPlan(issue) {
  const isWindows = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  const isLinux = process.platform === 'linux';

  if (isWindows) {
    const plans = {
      node: {
        label: 'Install or upgrade Node with winget',
        command: 'winget',
        args: ['install', '--id', 'OpenJS.NodeJS', '-e', '--accept-source-agreements', '--accept-package-agreements'],
      },
      python: {
        label: 'Install or upgrade Python with winget',
        command: 'winget',
        args: ['install', '--id', 'Python.Python.3.11', '-e', '--accept-source-agreements', '--accept-package-agreements'],
      },
      git: {
        label: 'Install or upgrade Git with winget',
        command: 'winget',
        args: ['install', '--id', 'Git.Git', '-e', '--accept-source-agreements', '--accept-package-agreements'],
      },
    };
    return plans[issue.key] || null;
  }

  if (isMac) {
    const plans = {
      node: { label: 'Install or upgrade Node with Homebrew', command: 'brew', args: ['install', 'node'] },
      python: { label: 'Install or upgrade Python with Homebrew', command: 'brew', args: ['install', 'python'] },
      git: { label: 'Install or upgrade Git with Homebrew', command: 'brew', args: ['install', 'git'] },
    };
    return plans[issue.key] || null;
  }

  if (isLinux) {
    const plans = {
      node: {
        label: 'Install or upgrade Node with apt',
        command: 'sudo',
        args: ['apt-get', 'install', '-y', 'nodejs', 'npm'],
      },
      python: {
        label: 'Install or upgrade Python with apt',
        command: 'sudo',
        args: ['apt-get', 'install', '-y', 'python3'],
      },
      git: {
        label: 'Install or upgrade Git with apt',
        command: 'sudo',
        args: ['apt-get', 'install', '-y', 'git'],
      },
    };
    return plans[issue.key] || null;
  }

  return null;
}

function remediationCommandText(plan) {
  if (!plan) return null;
  return [plan.command, ...(Array.isArray(plan.args) ? plan.args : [])].map(shellQuote).join(' ');
}

function runRemediationPlan(plan) {
  if (!plan) return { ok: false, detail: 'No remediation plan was available for this dependency on this platform.' };

  const result = spawnSync(plan.command, plan.args || [], {
    stdio: 'inherit',
    windowsHide: true,
  });

  if (result.error) {
    return { ok: false, detail: result.error.message || 'Remediation command failed to start.' };
  }

  if (result.status !== 0) {
    return {
      ok: false,
      detail: result.signal ? `Command terminated by signal: ${result.signal}` : `Command exited with status ${result.status}`,
    };
  }

  return { ok: true, detail: null };
}

function getRelevantDependencyIssues(report) {
  const deps = report?.dependencies || {};

  return GENERIC_DEPENDENCY_ORDER.map((entry) => {
    const detail = deps[entry.key] || null;
    const status = String(detail?.status || 'missing').toLowerCase();
    if (status === 'pass' || status === 'n/a') return null;

    const issue = {
      ...entry,
      status,
      version: detail?.version || 'missing',
      impact: detail?.impact || null,
    };

    issue.remediationPlan = buildDependencyRemediationPlan(issue);
    return issue;
  }).filter(Boolean);
}

async function maybeShowDependencyIssuesPage(report, branch) {
  if (branch === 'new-user') return false;

  const issues = getRelevantDependencyIssues(report);
  if (!issues.length) return false;

  const rl = createPromptSession();

  try {
    while (true) {
      startPage('Dependency Issues', 'Review these issues before continuing. This page only appears when relevant problems are present.');
      console.log('\nThe installer found non-Docker dependency issues for this path:');

      issues.forEach((issue, index) => {
        console.log(`\n${index + 1}) ${issue.name}`);
        console.log(`   Current State: ${issue.version} (${issue.status.toUpperCase()})`);
        console.log(`   Why it matters: ${issue.explanation}`);
        if (issue.impact) console.log(`   Impact: ${issue.impact}`);
        if (issue.remediationPlan) {
          console.log(`   Quick fix: ${issue.remediationPlan.label}`);
          console.log(`   Command: ${remediationCommandText(issue.remediationPlan)}`);
        } else {
          console.log('   Quick fix: No automatic remediation command is defined for this platform yet.');
        }
      });

      console.log('\nDocker is handled later in the flow if you choose a Docker-based setup.');
      console.log('Type a dependency number to run its quick fix, or type continue to keep going without remediation.');

      const raw = (await askQuestion(rl, 'Dependency action> ')).trim().toLowerCase();
      if (!raw || raw === 'continue' || raw === 'c') return true;
      if (/^q(uit)?$/i.test(raw) || raw === 'exit') fail('Dependency review cancelled by user.');

      const index = Number(raw);
      if (!Number.isInteger(index) || index < 1 || index > issues.length) {
        console.log('Use a dependency number from the list, or type continue.');
        continue;
      }

      const issue = issues[index - 1];
      if (!issue.remediationPlan) {
        console.log(`No automatic remediation command is defined yet for ${issue.name} on this platform.`);
        await waitForAnyKey('Press any key to return to the dependency issues page.');
        continue;
      }

      startPage('Confirm Dependency Remediation', `You chose the quick fix for ${issue.name}.`);
      console.log('\nThis will run:');
      console.log(remediationCommandText(issue.remediationPlan));
      console.log('\nDocker is not part of this page and will still be handled later if chosen.');

      const confirmed = await promptForYesNo(rl, 'Run this remediation command now? [y/N] ');
      if (!confirmed) continue;

      clearScreen();
      printPageHeader('Running Dependency Remediation', `Executing quick fix for ${issue.name}...`);
      const remediationResult = runRemediationPlan(issue.remediationPlan);
      if (!remediationResult.ok) {
        console.log(`\nRemediation did not complete successfully for ${issue.name}.`);
        if (remediationResult.detail) console.log(remediationResult.detail);
        await waitForAnyKey('Press any key to return to the dependency issues page.');
        continue;
      }

      console.log(`\nRemediation completed for ${issue.name}. Re-checking dependencies...`);
      await waitForAnyKey('Press any key to continue. The installer will re-run assessment now.');
      return 'rerun';
    }
  } finally {
    rl.close();
  }
}

function printDetectedInstances(report, availableOptions) {
  const strongMatches = getDetectedInstallOptions(availableOptions);
  const possibleMatches = getPossibleMatchOptions(availableOptions);
  const instancesById = instanceLookup(report);

  printCardSection('Detected OpenClaw Instances');
  if (!strongMatches.length && !possibleMatches.length) {
    console.log('None found');
    return [];
  }

  for (const option of strongMatches) {
    const instance = instancesById.get(option.sourceInstanceId) || null;
    const title = option.displayLabel || option.title || 'Detected OpenClaw instance';
    const subtitle = option.title || 'Install over existing OpenClaw instance';
    const badges = [...new Set([...(Array.isArray(option.badges) ? option.badges : []), option.recommended ? 'Recommended' : null].filter(Boolean))];
    printCardBlock(title, subtitle, renderInstanceCardLines(option, instance), badges);
    console.log();
  }

  if (possibleMatches.length) {
    printCardSection('Possible Matches (review carefully)');
    for (const option of possibleMatches) {
      const instance = instancesById.get(option.sourceInstanceId) || null;
      const title = option.displayLabel || option.title || 'Possible existing install match';
      const subtitle = option.title || 'Possible existing install match';
      const badges = [...new Set([...(Array.isArray(option.badges) ? option.badges : []), 'Needs review'])];
      printCardBlock(title, subtitle, renderInstanceCardLines(option, instance), badges);
      console.log();
    }
  }

  return strongMatches;
}

function resolvedMenuInstanceName(option) {
  const explicit = String(option?.details?.instanceName || '').trim();
  if (explicit) return explicit;

  const label = String(option?.displayLabel || '').trim();
  if (!label) return 'detected instance';
  const atIndex = label.indexOf(' at ');
  if (atIndex > 0) return label.slice(0, atIndex).trim();
  return label;
}

function menuTitleForOption(option, branch) {
  if (!option) return 'Unknown option';

  if (option.optionType === 'existing') return `Install over ${resolvedMenuInstanceName(option)}`;
  if (option.optionType === 'possibleMatch') return `Review possible match: ${resolvedMenuInstanceName(option)}`;
  if (option.optionType === 'manual') {
    if (branch === 'existing-user-recovery') return 'Recover an existing install manually';
    if (branch === 'detected-instances') return 'Correct an instance detail';
    return 'Choose an existing install path manually';
  }
  if (option.optionType === 'new') {
    if (branch === 'new-user') return 'Continue with a new install';
    return 'Start a new install';
  }

  return option.title || option.displayLabel || 'Unknown option';
}

function menuSummaryForOption(option, branch) {
  if (!option) return 'No summary available.';

  if (option.optionType === 'existing' || option.optionType === 'possibleMatch') {
    const state = option.isRunning ? 'Running now' : 'Not currently running';
    const target = option.workspacePath || option.configPath || option.installRoot || null;
    return target ? `${state} • ${target}` : state;
  }

  if (option.optionType === 'manual') {
    return branch === 'existing-user-recovery'
      ? 'Point the installer at an existing OpenClaw target the detector missed.'
      : 'Use this if you want to correct or manually verify an existing target.';
  }

  if (option.optionType === 'new') {
    return branch === 'new-user'
      ? 'Start the new-user install path from here.'
      : 'Create a fresh ResonantOS / OpenClaw install target.';
  }

  return option.summary || 'No summary available.';
}

function printSuggestedChoice(availableOptions, branch) {
  const recommendedOption = availableOptions.find((option) => option && option.recommended) || null;
  if (!recommendedOption) return;

  console.log('\nSuggested first choice:');
  console.log(`- ${menuTitleForOption(recommendedOption, branch)}`);
  console.log(`  ${recommendedOption.displayLabel}`);
  console.log(`  ${recommendedOption.summary}`);
}

function printAssessmentFooter(report, reportPath) {
  const blockers = Array.isArray(report.readiness?.blockers) ? report.readiness.blockers : [];
  console.log('\nAssessment Status:', report.readiness?.level || report.status || 'unknown');
  if (blockers.length) console.log('Blockers:', blockers.join(', '));

  console.log(`\n(Internal handoff saved to ${handoffPath})`);
  console.log(`(Debug report saved to ${reportPath})`);
}

function filterOptionsForZeroDetectionBranch(availableOptions, branch) {
  if (branch === 'new-user') {
    return availableOptions.filter(option => option && option.optionType === 'new');
  }

  if (branch === 'existing-user-recovery') {
    return availableOptions.filter(option => option && (option.optionType === 'manual' || option.optionType === 'new'));
  }

  return availableOptions;
}

function canUseArrowSelector() {
  return Boolean(process.stdin?.isTTY && process.stdout?.isTTY && typeof process.stdin.setRawMode === 'function');
}

function printOptions(availableOptions, branch) {
  const ordered = sortedOptions(availableOptions);
  console.log('\nInstaller Options:');

  if (canUseArrowSelector()) {
    console.log('Use ↑/↓ to move, Enter to confirm, or press I to type a number or option ID manually.');
    return;
  }

  ordered.forEach((option, index) => {
    const badges = [];
    if (option.recommended) badges.push('Recommended');
    if (Array.isArray(option.badges)) badges.push(...option.badges.filter(Boolean));
    const uniqueBadges = [...new Set(badges)];
    const badgeText = uniqueBadges.length ? ` [${uniqueBadges.join(' | ')}]` : '';

    console.log(`\n${index + 1}) ${menuTitleForOption(option, branch)}${badgeText}`);
    console.log(`   ${menuSummaryForOption(option, branch)}`);
    console.log(`   Option ID: ${option.optionId}`);

    const warnings = Array.isArray(option.warnings) ? option.warnings.filter(Boolean) : [];
    if (warnings.length) {
      for (const warning of warnings) {
        console.log(`   Warning: ${warning}`);
      }
    }
  });

  console.log('\nChoose one option by number or option ID.');
}

function createPromptSession() {
  if (!process.stdin.isTTY || !process.stdout.isTTY) {
    console.log('\nInteractive selection requires a terminal (TTY).');
    console.log('Run installer-entry.js in a terminal session so you can complete the installer selection prompts.');
    process.exit(1);
  }

  return readline.createInterface({ input: process.stdin, output: process.stdout });
}

function askQuestion(rl, prompt) {
  return new Promise(resolve => rl.question(prompt, answer => resolve(String(answer || ''))));
}

async function promptForTypedSelection(ordered) {
  const byId = new Map(ordered.map(option => [String(option.optionId), option]));
  const rl = createPromptSession();

  try {
    while (true) {
      const raw = (await askQuestion(rl, 'Selection> ')).trim();
      if (!raw) {
        console.log('Please enter a number or option ID from the list above.');
        continue;
      }

      if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) {
        fail('Selection cancelled by user.');
      }

      let selected = null;
      if (/^\d+$/.test(raw)) {
        const index = Number(raw);
        if (index >= 1 && index <= ordered.length) selected = ordered[index - 1];
      }

      if (!selected) selected = byId.get(raw) || null;

      if (!selected) {
        console.log(`Invalid selection: ${raw}`);
        console.log('Use one of the displayed numbers or option IDs exactly as shown.');
        continue;
      }

      return selected;
    }
  } finally {
    rl.close();
  }
}

function arrowMenuLines(ordered, branch, selectedIndex) {
  const lines = [];

  ordered.forEach((option, index) => {
    const badges = [];
    if (option.recommended) badges.push('Recommended');
    if (Array.isArray(option.badges)) badges.push(...option.badges.filter(Boolean));
    const uniqueBadges = [...new Set(badges)];
    const badgeText = uniqueBadges.length ? ` [${uniqueBadges.join(' | ')}]` : '';
    const marker = index === selectedIndex ? '>' : ' ';

    lines.push(`${marker} ${index + 1}) ${menuTitleForOption(option, branch)}${badgeText}`);
    lines.push(`  ${menuSummaryForOption(option, branch)}`);

    const warnings = Array.isArray(option.warnings) ? option.warnings.filter(Boolean) : [];
    warnings.forEach(warning => lines.push(`  Warning: ${warning}`));
    lines.push('');
  });

  lines.push('Press Enter to confirm, or press I to type a number or option ID manually.');
  return lines;
}

function writeMenuLines(lines) {
  lines.forEach(line => process.stdout.write(`${line}\n`));
}

async function promptForSelection(availableOptions, branch) {
  const ordered = sortedOptions(availableOptions);
  if (!canUseArrowSelector()) {
    return promptForTypedSelection(ordered);
  }

  return new Promise((resolve) => {
    readline.emitKeypressEvents(process.stdin);
    const hadRawMode = Boolean(process.stdin.isRaw);
    process.stdin.resume();
    if (!hadRawMode) process.stdin.setRawMode(true);

    let selectedIndex = Math.max(0, ordered.findIndex(option => option && option.recommended));
    if (selectedIndex < 0 || selectedIndex >= ordered.length) selectedIndex = 0;
    let renderedLines = 0;

    const cleanup = () => {
      process.stdin.off('keypress', onKeypress);
      if (!hadRawMode && process.stdin.isTTY) process.stdin.setRawMode(false);
      process.stdin.pause();
    };

    const render = () => {
      if (renderedLines) {
        readline.moveCursor(process.stdout, 0, -renderedLines);
        readline.clearScreenDown(process.stdout);
      }

      const lines = arrowMenuLines(ordered, branch, selectedIndex);
      renderedLines = lines.length;
      writeMenuLines(lines);
    };

    const fallbackToTyped = async () => {
      cleanup();
      process.stdout.write('\n');
      const result = await promptForTypedSelection(ordered);
      resolve(result);
    };

    const onKeypress = (str, key = {}) => {
      if (key.ctrl && key.name === 'c') {
        cleanup();
        fail('Selection cancelled by user.');
      }

      if (key.name === 'up') {
        selectedIndex = (selectedIndex - 1 + ordered.length) % ordered.length;
        render();
        return;
      }

      if (key.name === 'down') {
        selectedIndex = (selectedIndex + 1) % ordered.length;
        render();
        return;
      }

      if (key.name === 'return' || key.name === 'enter') {
        const selected = ordered[selectedIndex];
        cleanup();
        process.stdout.write(`\nSelected: ${menuTitleForOption(selected, branch)}\n`);
        resolve(selected);
        return;
      }

      if (/^[iI]$/.test(str || '')) {
        fallbackToTyped();
      }
    };

    process.stdin.on('keypress', onKeypress);
    render();
  });
}

function normalizeInputPath(rawValue) {
  const value = String(rawValue || '').trim().replace(/^['"]+|['"]+$/g, '');
  if (!value) return null;
  return path.resolve(value);
}

function statSafe(targetPath) {
  try {
    return fs.statSync(targetPath);
  } catch {
    return null;
  }
}

function existingConfigPathFromInput(rawValue) {
  const normalized = normalizeInputPath(rawValue);
  if (!normalized) return null;
  const stat = statSafe(normalized);
  if (stat && stat.isDirectory()) return path.join(normalized, 'openclaw.json');
  return normalized;
}

function directoryInputToPath(rawValue) {
  const normalized = normalizeInputPath(rawValue);
  if (!normalized) return null;
  if (normalized.endsWith(path.sep)) return normalized.slice(0, -1);
  return normalized;
}

function isRemoteGuidanceRequest(input) {
  return /^(remote|wrong\s*machine|wrong\s*host|other\s*machine|other\s*host|vps|lan)$/i.test(String(input || '').trim());
}

async function showWrongMachineGuidance(rl) {
  startPage('Wrong Machine / Remote Setup', 'Use this when you realize the target OpenClaw instance is not on the machine running this installer.');
  console.log('\nWhat this means:');
  console.log('- The installer needs to run on the same machine as the OpenClaw instance you want to install over.');
  console.log('- If the real target lives on a VPS, another LAN machine, or another host, stop here and run the installer there instead.');
  console.log('- For advanced or remote topologies, follow the tutorial once it is available.');
  console.log('\nTutorial link placeholder: <to be added>');
  console.log('\nOptions:');
  console.log('1) Go back and continue recovery on this machine');
  console.log('2) Exit for now');

  while (true) {
    const raw = (await askQuestion(rl, 'Choice> ')).trim();
    if (raw === '1') return 'back';
    if (raw === '2' || /^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) return 'exit';
    console.log('Choose 1 to go back, or 2 to exit.');
  }
}

function pathIsInside(child, parent) {
  const relative = path.relative(parent, child);
  return relative === '' || (!relative.startsWith('..') && !path.isAbsolute(relative));
}

function deriveInstallRootFromConfig(configPath) {
  if (!configPath) return null;
  const configDir = path.dirname(configPath);
  if (path.basename(configDir).toLowerCase() === 'config') return path.dirname(configDir);
  return configDir;
}

function summarizeValidationErrors(errors) {
  return errors.map(error => `- ${error}`).join('\n');
}

function validateManualSelectionPaths({ configPath, workspacePath }) {
  const errors = [];
  const configStat = configPath ? statSafe(configPath) : null;
  const workspaceStat = workspacePath ? statSafe(workspacePath) : null;

  if (!configPath) {
    errors.push('Config path is required.');
  } else if (!path.isAbsolute(configPath)) {
    errors.push('Config path must be absolute after normalization.');
  } else if (!configStat) {
    errors.push(`Config path does not exist: ${configPath}`);
  } else if (!configStat.isFile()) {
    errors.push(`Config path is not a file: ${configPath}`);
  } else if (path.basename(configPath).toLowerCase() !== 'openclaw.json') {
    errors.push('Config path must point to openclaw.json (or a directory containing it).');
  }

  if (!workspacePath) {
    errors.push('Workspace path is required.');
  } else if (!path.isAbsolute(workspacePath)) {
    errors.push('Workspace path must be absolute after normalization.');
  } else if (!workspaceStat) {
    errors.push(`Workspace path does not exist: ${workspacePath}`);
  } else if (!workspaceStat.isDirectory()) {
    errors.push(`Workspace path is not a directory: ${workspacePath}`);
  }

  const installRoot = deriveInstallRootFromConfig(configPath);
  const installRootStat = installRoot ? statSafe(installRoot) : null;

  if (!installRoot) {
    errors.push('Install root could not be derived from the config path.');
  } else if (!path.isAbsolute(installRoot)) {
    errors.push('Install root must be absolute after normalization.');
  } else if (!installRootStat || !installRootStat.isDirectory()) {
    errors.push(`Derived install root is missing or not a directory: ${installRoot}`);
  }

  if (workspacePath && installRoot && !pathIsInside(configPath, installRoot)) {
    errors.push('Config path is not inside the derived install root.');
  }

  return {
    ok: errors.length === 0,
    errors,
    normalized: {
      configPath,
      workspacePath,
      installRoot,
    },
  };
}

function validateNewSelectionPaths({ installRoot, workspacePath }) {
  const errors = [];
  const installRootStat = installRoot ? statSafe(installRoot) : null;
  const workspaceStat = workspacePath ? statSafe(workspacePath) : null;
  const configPath = installRoot ? path.join(installRoot, 'config', 'openclaw.json') : null;
  const configStat = configPath ? statSafe(configPath) : null;

  if (!installRoot) {
    errors.push('Install root is required.');
  } else if (!path.isAbsolute(installRoot)) {
    errors.push('Install root must be absolute after normalization.');
  } else if (installRootStat && !installRootStat.isDirectory()) {
    errors.push(`Install root exists but is not a directory: ${installRoot}`);
  }

  if (!workspacePath) {
    errors.push('Workspace path is required.');
  } else if (!path.isAbsolute(workspacePath)) {
    errors.push('Workspace path must be absolute after normalization.');
  } else if (workspaceStat && !workspaceStat.isDirectory()) {
    errors.push(`Workspace path exists but is not a directory: ${workspacePath}`);
  }

  if (installRoot && workspacePath && installRoot === workspacePath) {
    errors.push('Workspace path must be distinct from the install root for a new install target.');
  }

  if (configStat && configStat.isFile()) {
    errors.push(`A config file already exists at the new-install target: ${configPath}`);
  }

  return {
    ok: errors.length === 0,
    errors,
    normalized: {
      configPath,
      workspacePath,
      installRoot,
    },
  };
}

function buildCompletedSelection(baseSelection, overrides) {
  return {
    ...baseSelection,
    ...overrides,
    confirmedByUser: true,
  };
}

async function promptForYesNo(rl, prompt) {
  while (true) {
    const raw = (await askQuestion(rl, prompt)).trim().toLowerCase();
    if (!raw) return false;
    if (['y', 'yes'].includes(raw)) return true;
    if (['n', 'no'].includes(raw)) return false;
    console.log('Please answer yes or no.');
  }
}

async function promptForZeroDetectionBranch() {
  const rl = createPromptSession();

  try {
    startPage('No OpenClaw Instances Detected');
    console.log('\nNo detected instances of OpenClaw.');
    console.log('Are you new to OpenClaw and ResonantOS?');
    console.log('\nAnswer Yes for a first-time setup, or No if detection likely missed an existing install.');

    const isNewUser = await promptForYesNo(rl, 'Answer [y/N] ');
    return isNewUser ? 'new-user' : 'existing-user-recovery';
  } finally {
    rl.close();
  }
}

function installStyleLabel(style) {
  return style === 'custom' ? 'Custom install' : 'Recommended install';
}

function createOnboardingState(kind = 'new-user') {
  const now = new Date().toISOString();

  return {
    kind,
    version: 1,
    currentStep: 'install-style',
    choices: {
      installStyle: null,
      dockerEnabled: null,
      dockerMode: null,
      providerMode: null,
      setupAgentMode: null,
      authMethod: null,
      modelSource: null,
      setupAgentProvisioning: null,
      manualProvisioning: null,
      installRoot: null,
      workspacePath: null,
      gatewayPort: null,
      gatewayConfig: null,
    },
    completedSteps: [],
    invalidationLog: [],
    stepHistory: ['install-style'],
    metadata: {
      startedAt: now,
      updatedAt: now,
    },
  };
}

function touchOnboardingState(state) {
  if (!state) return state;
  if (!state.metadata) state.metadata = {};
  state.metadata.updatedAt = new Date().toISOString();
  return state;
}

function setOnboardingCurrentStep(state, step, { trackHistory = true } = {}) {
  if (!state) return state;
  state.currentStep = step || state.currentStep || null;
  if (!Array.isArray(state.stepHistory)) state.stepHistory = [];
  if (trackHistory && step && state.stepHistory[state.stepHistory.length - 1] !== step) {
    state.stepHistory.push(step);
  }
  return touchOnboardingState(state);
}

function completeOnboardingStep(state, step) {
  if (!state) return state;
  if (!Array.isArray(state.completedSteps)) state.completedSteps = [];
  if (step && !state.completedSteps.includes(step)) state.completedSteps.push(step);
  return setOnboardingCurrentStep(state, step, { trackHistory: false });
}

const ONBOARDING_STEP_ORDER = [
  'install-style',
  'docker-choice',
  'docker-readiness',
  'docker-management',
  'paths-and-ports',
  'provider-choice',
  'agent-readiness',
  'target-confirmation',
];

const ONBOARDING_CHOICE_TO_STEP = {
  installStyle: 'install-style',
  dockerEnabled: 'docker-choice',
  dockerMode: 'docker-management',
  installRoot: 'paths-and-ports',
  workspacePath: 'paths-and-ports',
  gatewayPort: 'paths-and-ports',
  providerMode: 'provider-choice',
  setupAgentMode: 'agent-readiness',
  authMethod: 'agent-readiness',
  modelSource: 'agent-readiness',
  setupAgentProvisioning: 'agent-readiness',
  manualProvisioning: 'agent-readiness',
  gatewayConfig: 'agent-readiness',
};

function detectDockerState() {
  const dockerVersion = spawnSync('docker', ['--version'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
    windowsHide: true,
  });

  if (dockerVersion.error || dockerVersion.status !== 0) {
    return {
      detected: false,
      running: false,
      version: null,
      source: 'live-probe',
    };
  }

  const dockerInfo = spawnSync('docker', ['info', '--format', '{{json .}}'], {
    stdio: ['ignore', 'pipe', 'pipe'],
    encoding: 'utf8',
    windowsHide: true,
  });

  return {
    detected: true,
    running: dockerInfo.status === 0,
    version: String(dockerVersion.stdout || '').trim() || null,
    source: 'live-probe',
  };
}

function getDockerState(report = null) {
  const dependencyDocker = report?.dependencies?.docker || null;
  if (dependencyDocker) {
    return {
      detected: Boolean(dependencyDocker.detected),
      running: Boolean(dependencyDocker.running),
      version: dependencyDocker.version || null,
      source: 'assessment',
    };
  }

  return detectDockerState();
}

function buildDockerRemediationPlan(dockerState) {
  const isWindows = process.platform === 'win32';
  const isMac = process.platform === 'darwin';
  const isLinux = process.platform === 'linux';

  if (!dockerState?.detected) {
    if (isWindows) {
      return {
        label: 'Install Docker Desktop with winget',
        command: 'winget',
        args: ['install', '--id', 'Docker.DockerDesktop', '-e', '--accept-source-agreements', '--accept-package-agreements'],
        kind: 'install',
      };
    }

    if (isMac) {
      return {
        label: 'Install Docker Desktop with Homebrew',
        command: 'brew',
        args: ['install', '--cask', 'docker'],
        kind: 'install',
      };
    }

    if (isLinux) {
      return {
        label: 'Install Docker with apt',
        command: 'sudo',
        args: ['apt-get', 'install', '-y', 'docker.io'],
        kind: 'install',
      };
    }
  }

  if (dockerState?.detected && !dockerState?.running) {
    return {
      label: 'Docker is installed but not ready yet',
      command: null,
      args: [],
      kind: 'start-required',
      detail: 'Start Docker Desktop or the Docker daemon, then re-check readiness from this page.',
    };
  }

  if (dockerState?.detected && dockerState?.running) {
    if (isWindows) {
      return {
        label: 'Docker looks ready (winget can be used later to update Docker Desktop if needed)',
        command: 'winget',
        args: ['upgrade', '--id', 'Docker.DockerDesktop', '-e', '--accept-source-agreements', '--accept-package-agreements'],
        kind: 'ready',
      };
    }

    if (isMac) {
      return {
        label: 'Docker looks ready (Homebrew can be used later to update Docker Desktop if needed)',
        command: 'brew',
        args: ['upgrade', '--cask', 'docker'],
        kind: 'ready',
      };
    }

    if (isLinux) {
      return {
        label: 'Docker looks ready (apt can be used later to update Docker if needed)',
        command: 'sudo',
        args: ['apt-get', 'install', '-y', 'docker.io'],
        kind: 'ready',
      };
    }
  }

  return null;
}

function dockerReadinessSummary(dockerState) {
  if (!dockerState?.detected) return 'Docker is not installed on this machine.';
  if (!dockerState?.running) return 'Docker is installed but not currently ready.';
  return `Docker is installed and ready${dockerState.version ? ` (${dockerState.version})` : ''}.`;
}

function getActiveOnboardingSteps(state) {
  const active = ['install-style', 'docker-choice', 'paths-and-ports', 'provider-choice', 'agent-readiness', 'target-confirmation'];

  if (getOnboardingChoice(state, 'dockerEnabled') === true) {
    active.splice(2, 0, 'docker-readiness', 'docker-management');
  }

  return active;
}

function onboardingStepsForChoiceKeys(keys) {
  return [...new Set((keys || []).map(key => ONBOARDING_CHOICE_TO_STEP[key]).filter(Boolean))];
}

function reconcileOnboardingStateAfterInvalidation(state) {
  if (!state) return state;

  const activeSteps = new Set(getActiveOnboardingSteps(state));
  state.completedSteps = (state.completedSteps || []).filter(step => activeSteps.has(step));
  state.stepHistory = (state.stepHistory || []).filter(step => activeSteps.has(step));

  if (!state.stepHistory.length && state.currentStep) state.stepHistory = [state.currentStep];
  if (!state.stepHistory.length) state.stepHistory = ['install-style'];

  if (!activeSteps.has(state.currentStep)) {
    const historyFallback = [...(state.stepHistory || [])].reverse().find(step => activeSteps.has(step));
    const fallback = historyFallback || ONBOARDING_STEP_ORDER.find(step => activeSteps.has(step)) || 'install-style';
    state.currentStep = fallback;
    if (state.stepHistory[state.stepHistory.length - 1] !== fallback) state.stepHistory.push(fallback);
  }

  return touchOnboardingState(state);
}

function resetDependentChoices(state, keys, reason) {
  if (!state || !state.choices) return state;
  const cleared = [];

  for (const key of keys) {
    if (state.choices[key] !== null && state.choices[key] !== undefined) {
      state.choices[key] = null;
      cleared.push(key);
    }
  }

  if (cleared.length) {
    if (!Array.isArray(state.invalidationLog)) state.invalidationLog = [];
    state.invalidationLog.push({ reason, cleared, at: new Date().toISOString() });

    const invalidatedSteps = onboardingStepsForChoiceKeys(cleared);
    state.completedSteps = (state.completedSteps || []).filter(step => !invalidatedSteps.includes(step));
    reconcileOnboardingStateAfterInvalidation(state);
    return state;
  }

  return touchOnboardingState(state);
}

function applyOnboardingChoice(state, key, value) {
  if (!state || !state.choices) return state;
  const previousValue = state.choices[key] ?? null;
  const changed = previousValue !== value;
  state.choices[key] = value;

  if (key === 'installStyle') {
    if (changed) {
      resetDependentChoices(state, ['dockerEnabled', 'dockerMode', 'providerMode', 'installRoot', 'workspacePath', 'gatewayPort', 'gatewayConfig'], 'installStyle changed');
    }
    completeOnboardingStep(state, 'install-style');
    return state;
  }

  if (key === 'dockerEnabled') {
    if (changed && value === false) {
      resetDependentChoices(state, ['dockerMode'], 'docker disabled');
    }
    reconcileOnboardingStateAfterInvalidation(state);
    return state;
  }

  return touchOnboardingState(state);
}

function getOnboardingChoice(state, key) {
  return state?.choices?.[key] ?? null;
}

function printInstallStyleHelp() {
  startPage('Install Style Help', 'Use this help page if you want a quick explanation before choosing.');
  console.log('\nRecommended install:');
  console.log('- Best for most new users');
  console.log('- Faster path with sensible defaults');
  console.log('- You can still adjust key settings later in onboarding');
  console.log('\nCustom install:');
  console.log('- More control over Docker, paths, ports, and provider/model setup');
  console.log('- Better if you already know you want a non-default layout');
  console.log('- Still guided, just less opinionated');
}

function printOnboardingNavigation({ showBack = true, showNext = true } = {}) {
  console.log('\nNavigation:');
  if (showNext) console.log('- n = next / continue');
  if (showBack) console.log('- b = back');
  console.log('- h = help');
  console.log('- q = cancel');
}

function printOnboardingStepSummary(state) {
  const installStyle = getOnboardingChoice(state, 'installStyle');
  const dockerEnabled = getOnboardingChoice(state, 'dockerEnabled');
  const installRoot = getOnboardingChoice(state, 'installRoot');
  const workspacePath = getOnboardingChoice(state, 'workspacePath');
  const gatewayPort = getOnboardingChoice(state, 'gatewayPort');
  const setupAgentMode = getOnboardingChoice(state, 'setupAgentMode');
  const modelSource = getOnboardingChoice(state, 'modelSource');
  const authMethod = getOnboardingChoice(state, 'authMethod');
  const setupAgentProvisioning = getOnboardingChoice(state, 'setupAgentProvisioning');
  const manualProvisioning = getOnboardingChoice(state, 'manualProvisioning');

  console.log('\nCurrent onboarding choices:');
  console.log(`- Install style: ${installStyle ? installStyleLabel(installStyle) : 'Not chosen yet'}`);
  console.log(`- Docker: ${dockerChoiceLabel(dockerEnabled)}`);
  if (installRoot || workspacePath || gatewayPort) {
    console.log(`- Install root: ${installRoot || 'Not chosen yet'}`);
    console.log(`- Workspace: ${workspacePath || 'Not chosen yet'}`);
    console.log(`- Gateway port: ${gatewayPort || 'Not chosen yet'}`);
  }
  if (setupAgentMode || modelSource || authMethod) {
    console.log(`- Setup agent mode: ${setupAgentMode || 'Not chosen yet'}`);
    console.log(`- Model source: ${modelSource || 'Not chosen yet'}`);
    console.log(`- Auth method: ${authMethod || 'Not chosen yet'}`);
    if (setupAgentProvisioning?.mode === 'auto') {
      console.log(`- Auto provisioning: ${setupAgentProvisioning.modelProfile}`);
    }
    if (manualProvisioning?.mode === 'manual') {
      console.log(`- Manual provider path: ${manualProvisioning.providerLabel}`);
    }
  }
}

function defaultNewUserPaths(state) {
  const installStyle = getOnboardingChoice(state, 'installStyle');
  const baseRoot = installStyle === 'custom' ? '/opt/resonantos' : '/srv/resonantos';
  return {
    installRoot: baseRoot,
    workspacePath: path.join(baseRoot, 'workspace'),
    gatewayPort: '18820',
  };
}

function summarizePathValue(value, defaultValue) {
  if (!value) return `Default: ${defaultValue}`;
  if (String(value) === String(defaultValue)) return `Default: ${defaultValue}`;
  return `Custom: ${value}`;
}

function validateGatewayPort(value) {
  const text = String(value ?? '').trim();
  if (!/^\d+$/.test(text)) return { ok: false, error: `Gateway port must be a number: ${value}` };
  const port = Number(text);
  if (!Number.isInteger(port) || port < 1 || port > 65535) {
    return { ok: false, error: `Gateway port must be between 1 and 65535: ${value}` };
  }
  return { ok: true, value: String(port) };
}

function defaultGatewayConfig(state) {
  const gatewayPort = getOnboardingChoice(state, 'gatewayPort') || defaultNewUserPaths(state).gatewayPort;
  return {
    mode: 'local-gateway',
    host: '127.0.0.1',
    port: String(gatewayPort),
    dashboardUrl: `http://127.0.0.1:${String(gatewayPort)}/dashboard`,
  };
}

function buildAutoProvisioningPlan(state) {
  const gatewayConfig = defaultGatewayConfig(state);
  return {
    mode: 'auto',
    modelProfile: 'small local setup model',
    provisioningSteps: [
      'Download the small local setup model',
      'Register the model for first-run setup-agent use',
      'Bind the setup agent to the local gateway session',
      'Carry the dashboard handoff forward to the welcome screen',
    ],
    gatewayConfig,
    handoffSummary: `Dashboard will open at ${gatewayConfig.dashboardUrl} with the setup agent using a small local model.`,
  };
}

function summarizeAutoProvisioningPlan(plan) {
  if (!plan) return null;
  return [
    `Mode: ${plan.mode}`,
    `Model profile: ${plan.modelProfile}`,
    `Dashboard handoff: ${plan.gatewayConfig?.dashboardUrl || 'unknown'}`,
  ];
}

function buildManualProvisioningPlan(state, manualMode = 'api-key') {
  const gatewayConfig = defaultGatewayConfig(state);
  const planMap = {
    'api-key': {
      providerLabel: 'API key provider',
      modelSource: 'API key provider/model selection',
      authMethod: 'API key',
      provisioningSteps: [
        'Choose the API-backed provider',
        'Collect/store the API key for first-run setup-agent use',
        'Choose the provider model before dashboard launch',
        'Carry the configured gateway handoff into the dashboard welcome screen',
      ],
      handoffSummary: `Dashboard will open at ${gatewayConfig.dashboardUrl} after API key + provider model setup is prepared.`,
    },
    oauth: {
      providerLabel: 'OAuth-backed provider',
      modelSource: 'OAuth provider/model selection',
      authMethod: 'OAuth',
      provisioningSteps: [
        'Choose the OAuth-backed provider',
        'Prepare the OAuth sign-in handshake for first run',
        'Choose the provider model before dashboard launch',
        'Carry the configured gateway handoff into the dashboard welcome screen',
      ],
      handoffSummary: `Dashboard will open at ${gatewayConfig.dashboardUrl} after OAuth-backed provider setup is prepared.`,
    },
    'local-curated': {
      providerLabel: 'Curated local model menu',
      modelSource: 'curated local model menu',
      authMethod: 'local model selection',
      provisioningSteps: [
        'Open the curated local model menu',
        'Choose the local model for setup-agent use',
        'Bind the chosen local model to the gateway-backed setup agent',
        'Carry the configured gateway handoff into the dashboard welcome screen',
      ],
      handoffSummary: `Dashboard will open at ${gatewayConfig.dashboardUrl} after curated local model selection is prepared.`,
    },
  };

  const selected = planMap[manualMode] || planMap['api-key'];
  return {
    mode: 'manual',
    manualMode,
    providerLabel: selected.providerLabel,
    modelSource: selected.modelSource,
    authMethod: selected.authMethod,
    provisioningSteps: selected.provisioningSteps,
    gatewayConfig,
    handoffSummary: selected.handoffSummary,
  };
}

function summarizeManualProvisioningPlan(plan) {
  if (!plan) return null;
  return [
    `Mode: ${plan.mode}`,
    `Provider path: ${plan.providerLabel}`,
    `Auth method: ${plan.authMethod}`,
    `Dashboard handoff: ${plan.gatewayConfig?.dashboardUrl || 'unknown'}`,
  ];
}

function dockerChoiceLabel(enabled) {
  if (enabled === true) return 'Use Docker';
  if (enabled === false) return 'Do not use Docker';
  return 'Not chosen yet';
}

function runCommandCapture(command, args = [], timeout = 5000) {
  const result = spawnSync(command, args, {
    encoding: 'utf8',
    windowsHide: true,
    timeout,
  });

  if (result.error) {
    return {
      ok: false,
      stdout: String(result.stdout || '').trim(),
      stderr: String(result.stderr || '').trim(),
      error: result.error.message || String(result.error),
      status: result.status ?? null,
      signal: result.signal ?? null,
    };
  }

  return {
    ok: result.status === 0,
    stdout: String(result.stdout || '').trim(),
    stderr: String(result.stderr || '').trim(),
    error: null,
    status: result.status ?? null,
    signal: result.signal ?? null,
  };
}

function detectDockerReadiness() {
  const version = runCommandCapture('docker', ['--version']);
  if (!version.ok) {
    return {
      status: 'missing',
      detected: false,
      running: false,
      version: null,
      recommendedAction: 'install',
      summary: 'Docker does not appear to be installed on this machine yet.',
      detail: version.error || version.stderr || version.stdout || 'docker --version did not succeed.',
    };
  }

  const info = runCommandCapture('docker', ['info', '--format', '{{json .}}']);
  if (!info.ok) {
    return {
      status: 'installed-not-ready',
      detected: true,
      running: false,
      version: version.stdout || null,
      recommendedAction: 'fix-or-update',
      summary: 'Docker is installed, but it is not ready to use yet.',
      detail: info.error || info.stderr || info.stdout || 'docker info did not succeed.',
    };
  }

  return {
    status: 'ready',
    detected: true,
    running: true,
    version: version.stdout || null,
    recommendedAction: 'confirm-ready',
    summary: 'Docker is installed and responding normally.',
    detail: null,
  };
}

function dockerRecommendedActionLabel(action) {
  if (action === 'install') return 'Install Docker in the Docker flow';
  if (action === 'fix-or-update') return 'Update or repair Docker in the Docker flow';
  if (action === 'confirm-ready') return 'Docker looks ready; continue with Docker setup';
  if (action === 'compose') return 'Use Docker Compose style setup';
  if (action === 'single-container') return 'Use a single-container Docker setup';
  return 'Review Docker status';
}

function getDockerPlanSummary(state) {
  const dockerMode = getOnboardingChoice(state, 'dockerMode');

  if (dockerMode === 'compose') {
    return {
      modeLabel: 'Docker Compose layout',
      commands: [
        'docker --version',
        'docker info --format {{json .}}',
        'docker compose version',
      ],
      progress: [
        'Verify Docker CLI',
        'Verify Docker daemon',
        'Verify Docker Compose support',
        'Prepare later container configuration steps',
      ],
    };
  }

  if (dockerMode === 'single-container') {
    return {
      modeLabel: 'Single-container Docker layout',
      commands: [
        'docker --version',
        'docker info --format {{json .}}',
        'docker ps',
      ],
      progress: [
        'Verify Docker CLI',
        'Verify Docker daemon',
        'Verify container runtime access',
        'Prepare later container configuration steps',
      ],
    };
  }

  return {
    modeLabel: dockerRecommendedActionLabel(dockerMode),
    commands: ['docker --version', 'docker info --format {{json .}}'],
    progress: [
      'Verify Docker CLI',
      'Verify Docker daemon',
      'Prepare later Docker remediation/setup steps',
    ],
  };
}

function printDockerPlanSummary(state) {
  const plan = getDockerPlanSummary(state);

  console.log('\nCurrent Docker plan:');
  console.log(`- Mode: ${plan.modeLabel}`);
  console.log('- Intended command checks/actions:');
  plan.commands.forEach(command => console.log(`  - ${command}`));
  console.log('- Progress framing:');
  plan.progress.forEach(step => console.log(`  - ${step}`));
}

function printDockerChoiceHelp() {
  startPage('Docker Choice Help', 'Use this help page if you want a plain-language explanation before choosing.');
  console.log('\nUse Docker:');
  console.log('- Good if you want the install contained and easier to move/manage later');
  console.log('- The installer will later check Docker and help install/update it if needed');
  console.log('- Docker-specific setup and confirmation happens later, not on this page');
  console.log('\nDo not use Docker:');
  console.log('- Simpler host-managed path');
  console.log('- Better if you do not want container management involved right now');
  console.log('- You can still continue the guided install without Docker');
}

async function promptForNewUserInstallStyle(rl, state) {
  setOnboardingCurrentStep(state, 'install-style');

  while (true) {
    startPage('New User Onboarding — Step 1 of 2', 'Choose how you want to begin. You can adjust details later as the installer guides you through setup.');
    printOnboardingStepSummary(state);
    console.log('\n1) Recommended install');
    console.log('   Fastest guided path using sensible defaults. Best for most new users.');
    console.log('\n2) Custom install');
    console.log('   More control over Docker, paths, ports, and provider/model setup.');
    printOnboardingNavigation({ showBack: false, showNext: true });
    console.log('\nStep action: choose 1 or 2, then press n to continue.');

    const raw = (await askQuestion(rl, '\nInstall style> ')).trim();
    if (raw === '1') {
      state = applyOnboardingChoice(state, 'installStyle', 'recommended');
      console.log('\nSaved: Recommended install. Press n when you want to continue.');
      continue;
    }
    if (raw === '2') {
      state = applyOnboardingChoice(state, 'installStyle', 'custom');
      console.log('\nSaved: Custom install. Press n when you want to continue.');
      continue;
    }
    if (/^[h?]$/i.test(raw)) {
      printInstallStyleHelp();
      await askQuestion(rl, '\nPress Enter to return to the install-style page. ');
      continue;
    }
    if (/^[n]$/i.test(raw)) {
      if (!getOnboardingChoice(state, 'installStyle')) {
        console.log('Choose Recommended or Custom first.');
        continue;
      }
      return { action: 'next', state };
    }
    if (/^[b]$/i.test(raw)) {
      console.log('You are already on the first onboarding step.');
      continue;
    }
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Please choose 1 or 2 first, then use n / h / q.');
  }
}

async function promptForNewUserDockerChoice(rl, state) {
  setOnboardingCurrentStep(state, 'docker-choice');

  while (true) {
    startPage('New User Onboarding — Step 2 of 3', 'Choose whether this install should use Docker. Docker setup details still come later if you enable it.');
    printOnboardingStepSummary(state);
    console.log('\n1) Use Docker');
    console.log('   Good if you want a more contained and portable install layout.');
    console.log('\n2) Do not use Docker');
    console.log('   Good if you want a simpler host-managed path right now.');
    printOnboardingNavigation({ showBack: true, showNext: true });
    console.log('\nStep action: choose 1 or 2, then press n to continue.');

    const raw = (await askQuestion(rl, '\nDocker choice> ')).trim();
    if (raw === '1') {
      state = applyOnboardingChoice(state, 'dockerEnabled', true);
      console.log('\nSaved: Use Docker. Press n when you want to continue.');
      continue;
    }
    if (raw === '2') {
      state = applyOnboardingChoice(state, 'dockerEnabled', false);
      console.log('\nSaved: Do not use Docker. Press n when you want to continue.');
      continue;
    }
    if (/^[h?]$/i.test(raw)) {
      printDockerChoiceHelp();
      await askQuestion(rl, '\nPress Enter to return to the Docker choice page. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return { action: 'back', state };
    if (/^[n]$/i.test(raw)) {
      if (getOnboardingChoice(state, 'dockerEnabled') === null) {
        console.log('Choose whether to use Docker first.');
        continue;
      }
      state = completeOnboardingStep(state, 'docker-choice');
      return { action: 'next', state };
    }
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Please choose 1 or 2 first, then use n / b / h / q.');
  }
}

async function promptForNewUserDockerReadiness(rl, state) {
  setOnboardingCurrentStep(state, 'docker-readiness');

  while (true) {
    const readiness = detectDockerReadiness();
    const remediationPlan = buildDockerRemediationPlan({
      detected: readiness.detected,
      running: readiness.running,
      version: readiness.version,
    });

    startPage('New User Onboarding — Step 3 of 4', 'Docker is enabled for this install. Check Docker readiness here before choosing the container layout.');
    printOnboardingStepSummary(state);
    console.log('\nDocker readiness:');
    console.log(`- Status: ${readiness.status}`);
    console.log(`- Version: ${readiness.version || 'Not detected'}`);
    console.log(`- Summary: ${readiness.summary}`);
    if (readiness.detail) console.log(`- Detail: ${readiness.detail}`);
    if (remediationPlan) {
      console.log(`- Recommended action: ${remediationPlan.label}`);
      if (remediationPlan.command) console.log(`- Command: ${remediationCommandText(remediationPlan)}`);
      if (remediationPlan.detail) console.log(`- Note: ${remediationPlan.detail}`);
    }

    console.log('\nDocker-specific remediation stays inside this Docker flow, not the generic dependency page.');
    console.log('1) Re-check Docker readiness');
    if (remediationPlan?.command) console.log('2) Run the recommended Docker install/update command');
    if (!remediationPlan?.command) console.log('2) Acknowledge the readiness note');
    console.log('3) Continue once Docker is ready enough for your plan');
    printOnboardingNavigation({ showBack: true, showNext: false });

    const raw = (await askQuestion(rl, '\nDocker readiness> ')).trim();
    if (raw === '1') continue;
    if (raw === '2') {
      if (!remediationPlan?.command) {
        console.log(`\n${remediationPlan?.detail || 'No automatic Docker command is defined for this state on this platform yet.'}`);
        await askQuestion(rl, 'Press Enter to return to the Docker readiness page. ');
        continue;
      }

      startPage('Confirm Docker Remediation', 'Review the Docker command before the installer runs it.');
      console.log('\nThis will run:');
      console.log(remediationCommandText(remediationPlan));
      const confirmed = await promptForYesNo(rl, 'Run this Docker remediation command now? [y/N] ');
      if (!confirmed) continue;

      clearScreen();
      printPageHeader('Running Docker Remediation', `Executing: ${remediationPlan.label}`);
      const remediationResult = runRemediationPlan(remediationPlan);
      if (!remediationResult.ok) {
        console.log('\nDocker remediation did not complete successfully.');
        if (remediationResult.detail) console.log(remediationResult.detail);
        await waitForAnyKey('Press any key to return to the Docker readiness page.');
        continue;
      }

      console.log('\nDocker remediation completed. Re-checking readiness next.');
      await waitForAnyKey('Press any key to continue.');
      continue;
    }
    if (raw === '3') {
      state = completeOnboardingStep(state, 'docker-readiness');
      return { action: 'next', state };
    }
    if (/^[h?]$/i.test(raw)) {
      printDockerChoiceHelp();
      console.log('\nThis readiness page checks whether Docker is installed and running, and offers Docker-specific remediation only inside the Docker branch.');
      await askQuestion(rl, '\nPress Enter to return to the Docker readiness page. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return { action: 'back', state };
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Use 1/2/3, or b / h / q.');
  }
}

async function promptForNewUserDockerManagement(rl, state) {
  setOnboardingCurrentStep(state, 'docker-management');

  while (true) {
    const readiness = detectDockerReadiness();
    const currentDockerMode = getOnboardingChoice(state, 'dockerMode');
    if (!currentDockerMode || ['install', 'fix-or-update', 'confirm-ready'].includes(currentDockerMode)) {
      state = applyOnboardingChoice(state, 'dockerMode', readiness.recommendedAction);
    }

    startPage('New User Onboarding — Step 4 of 4', 'Choose the Docker setup path before later install execution.');
    printOnboardingStepSummary(state);
    console.log(`\nCurrent Docker readiness: ${readiness.summary}`);

    console.log('\nSetup choices:');
    console.log('1) Docker Compose layout');
    console.log('   Best when you want a multi-service layout and clearer service separation later.');
    console.log('2) Single-container Docker layout');
    console.log('   Best when you want the simplest container setup the installer can prepare.');
    console.log('3) Keep the installer-recommended readiness action');
    console.log(`   Current recommendation: ${dockerRecommendedActionLabel(readiness.recommendedAction)}`);

    printDockerPlanSummary(state);
    console.log('\nDocker-specific remediation stays inside this Docker flow, not the generic dependency page.');
    printOnboardingNavigation({ showBack: true, showNext: true });
    console.log('\nStep action: choose 1/2/3 to set the Docker plan, then press n to continue.');

    const raw = (await askQuestion(rl, '\nDocker setup> ')).trim();
    if (raw === '1') {
      state = applyOnboardingChoice(state, 'dockerMode', 'compose');
      console.log('\nSaved: Docker Compose layout. Press n when you want to continue.');
      continue;
    }
    if (raw === '2') {
      state = applyOnboardingChoice(state, 'dockerMode', 'single-container');
      console.log('\nSaved: Single-container Docker layout. Press n when you want to continue.');
      continue;
    }
    if (raw === '3') {
      state = applyOnboardingChoice(state, 'dockerMode', readiness.recommendedAction);
      console.log(`\nSaved: ${dockerRecommendedActionLabel(readiness.recommendedAction)}. Press n when you want to continue.`);
      continue;
    }
    if (/^[h?]$/i.test(raw)) {
      printDockerChoiceHelp();
      console.log('\nThis setup page records the Docker plan, previews the intended checks/actions, and asks for one final confirmation before continuing.');
      await askQuestion(rl, '\nPress Enter to return to the Docker setup page. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return { action: 'back', state };
    if (/^[n]$/i.test(raw)) {
      if (!getOnboardingChoice(state, 'dockerMode')) {
        console.log('Choose a Docker plan first.');
        continue;
      }

      startPage('Confirm Docker Plan', 'Review the Docker setup intent before the installer continues.');
      printOnboardingStepSummary(state);
      printDockerPlanSummary(state);
      console.log('\nConfirmation rule: this does not run the later install yet, but it does lock in the Docker setup intent for the next phase.');
      const confirmed = await promptForYesNo(rl, 'Confirm this Docker setup plan? [y/N] ');
      if (!confirmed) {
        console.log('Okay — returning to the Docker setup page so you can adjust the plan.');
        await askQuestion(rl, 'Press Enter to continue. ');
        continue;
      }

      state = completeOnboardingStep(state, 'docker-management');
      return { action: 'next', state };
    }
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Use 1/2/3 to choose a Docker plan, n to continue, b to go back, h for help, or q to cancel.');
  }
}

async function promptForNewUserPathsAndPorts(rl, state) {
  setOnboardingCurrentStep(state, 'paths-and-ports');

  while (true) {
    const defaults = defaultNewUserPaths(state);
    const currentInstallRoot = getOnboardingChoice(state, 'installRoot') || defaults.installRoot;
    const currentWorkspacePath = getOnboardingChoice(state, 'workspacePath') || defaults.workspacePath;
    const currentGatewayPort = getOnboardingChoice(state, 'gatewayPort') || defaults.gatewayPort;

    startPage('New User Onboarding — Paths and Ports', 'Review the planned install location, workspace, and gateway port. Defaults are shown clearly and can be changed here.');
    printOnboardingStepSummary(state);
    console.log('\nCurrent values:');
    console.log(`1) Install root   — ${summarizePathValue(currentInstallRoot, defaults.installRoot)}`);
    console.log(`2) Workspace path — ${summarizePathValue(currentWorkspacePath, defaults.workspacePath)}`);
    console.log(`3) Gateway port   — ${summarizePathValue(currentGatewayPort, defaults.gatewayPort)}`);
    console.log('\nShortcuts:');
    console.log('- 1 / 2 / 3 = edit that field');
    console.log('- d = reset all three values to defaults for this install style');
    printOnboardingNavigation({ showBack: true, showNext: true });
    console.log('\nStep action: edit any field you want, then press n to continue.');

    const raw = (await askQuestion(rl, '\nPaths and ports> ')).trim();
    if (raw === '1') {
      const entered = await askQuestion(rl, `Install root [${currentInstallRoot}]> `);
      const nextValue = directoryInputToPath(entered.trim() || currentInstallRoot);
      if (!nextValue || !path.isAbsolute(nextValue)) {
        console.log('Install root must be an absolute path.');
        continue;
      }
      state = applyOnboardingChoice(state, 'installRoot', nextValue);
      console.log(`Saved install root: ${nextValue}`);
      continue;
    }
    if (raw === '2') {
      const entered = await askQuestion(rl, `Workspace path [${currentWorkspacePath}]> `);
      const nextValue = directoryInputToPath(entered.trim() || currentWorkspacePath);
      if (!nextValue || !path.isAbsolute(nextValue)) {
        console.log('Workspace path must be an absolute path.');
        continue;
      }
      state = applyOnboardingChoice(state, 'workspacePath', nextValue);
      console.log(`Saved workspace path: ${nextValue}`);
      continue;
    }
    if (raw === '3') {
      const entered = await askQuestion(rl, `Gateway port [${currentGatewayPort}]> `);
      const validation = validateGatewayPort(entered.trim() || currentGatewayPort);
      if (!validation.ok) {
        console.log(validation.error);
        continue;
      }
      state = applyOnboardingChoice(state, 'gatewayPort', validation.value);
      console.log(`Saved gateway port: ${validation.value}`);
      continue;
    }
    if (/^[d]$/i.test(raw)) {
      state = applyOnboardingChoice(state, 'installRoot', defaults.installRoot);
      state = applyOnboardingChoice(state, 'workspacePath', defaults.workspacePath);
      state = applyOnboardingChoice(state, 'gatewayPort', defaults.gatewayPort);
      console.log('Reset install root, workspace path, and gateway port to defaults.');
      continue;
    }
    if (/^[h?]$/i.test(raw)) {
      startPage('Paths and Ports Help', 'This page lets you keep the default layout or replace it with your own.');
      console.log('\nInstall root:');
      console.log('- Main folder where ResonantOS files will live');
      console.log(`- Default for this style: ${defaults.installRoot}`);
      console.log('\nWorkspace path:');
      console.log('- Working area for OpenClaw / ResonantOS content');
      console.log(`- Default for this style: ${defaults.workspacePath}`);
      console.log('\nGateway port:');
      console.log('- Port the local gateway/dashboard flow will use');
      console.log(`- Default for this style: ${defaults.gatewayPort}`);
      await askQuestion(rl, '\nPress Enter to return to the paths and ports page. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return { action: 'back', state };
    if (/^[n]$/i.test(raw)) {
      const installRoot = getOnboardingChoice(state, 'installRoot') || defaults.installRoot;
      const workspacePath = getOnboardingChoice(state, 'workspacePath') || defaults.workspacePath;
      const gatewayPortValidation = validateGatewayPort(getOnboardingChoice(state, 'gatewayPort') || defaults.gatewayPort);
      if (!installRoot || !path.isAbsolute(installRoot)) {
        console.log('Install root must be an absolute path before continuing.');
        continue;
      }
      if (!workspacePath || !path.isAbsolute(workspacePath)) {
        console.log('Workspace path must be an absolute path before continuing.');
        continue;
      }
      if (!gatewayPortValidation.ok) {
        console.log(gatewayPortValidation.error);
        continue;
      }
      state = applyOnboardingChoice(state, 'installRoot', installRoot);
      state = applyOnboardingChoice(state, 'workspacePath', workspacePath);
      state = applyOnboardingChoice(state, 'gatewayPort', gatewayPortValidation.value);
      state = completeOnboardingStep(state, 'paths-and-ports');
      return { action: 'next', state };
    }
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Use 1/2/3 to edit, d to reset defaults, n to continue, b to go back, h for help, or q to cancel.');
  }
}

async function promptForManualSetupAgentProvisioning(rl, state) {
  while (true) {
    startPage('Manual Setup-Agent Provider / Model', 'Choose how manual setup should source the setup agent backend before installation completes.');
    printOnboardingStepSummary(state);
    console.log('\nManual setup choices:');
    console.log('1) API key provider');
    console.log('   Use a provider that needs an API key and pick the model before dashboard launch.');
    console.log('2) OAuth-backed provider');
    console.log('   Use a provider that signs in through OAuth before dashboard launch.');
    console.log('3) Curated local model menu');
    console.log('   Choose from a local-model shortlist the installer can prepare for first run.');
    printOnboardingNavigation({ showBack: true, showNext: false });
    console.log('\nStep action: choose 1/2/3 to define the manual provider/model path.');

    const raw = (await askQuestion(rl, '\nManual setup> ')).trim();
    let manualMode = null;
    if (raw === '1') manualMode = 'api-key';
    if (raw === '2') manualMode = 'oauth';
    if (raw === '3') manualMode = 'local-curated';

    if (manualMode) {
      const manualPlan = buildManualProvisioningPlan(state, manualMode);
      state = applyOnboardingChoice(state, 'setupAgentMode', 'manual');
      state = applyOnboardingChoice(state, 'providerMode', 'manual');
      state = applyOnboardingChoice(state, 'modelSource', manualPlan.modelSource);
      state = applyOnboardingChoice(state, 'authMethod', manualPlan.authMethod);
      state = applyOnboardingChoice(state, 'manualProvisioning', manualPlan);
      state = applyOnboardingChoice(state, 'setupAgentProvisioning', null);
      state = applyOnboardingChoice(state, 'gatewayConfig', manualPlan.gatewayConfig);
      console.log('\nSaved: Manual mode.');
      summarizeManualProvisioningPlan(manualPlan).forEach(line => console.log(`- ${line}`));
      console.log(`- ${manualPlan.handoffSummary}`);
      await askQuestion(rl, '\nPress Enter to return to the setup-agent readiness page. ');
      return state;
    }

    if (/^[h?]$/i.test(raw)) {
      startPage('Manual Setup Help', 'Manual mode lets you choose how the setup agent gets its backend and model before first dashboard launch.');
      console.log('\nAPI key provider: best when you already expect to use a hosted model service.');
      console.log('OAuth-backed provider: best when the provider uses sign-in instead of a pasted key.');
      console.log('Curated local model menu: best when you want the installer to keep setup local and choose from a shortlist.');
      await askQuestion(rl, '\nPress Enter to return to manual setup choices. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return null;
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Use 1/2/3, or b / h / q.');
  }
}

async function promptForNewUserAgentReadiness(rl, state) {
  setOnboardingCurrentStep(state, 'agent-readiness');

  while (true) {
    const gatewayConfig = getOnboardingChoice(state, 'gatewayConfig') || defaultGatewayConfig(state);
    const currentMode = getOnboardingChoice(state, 'setupAgentMode');
    const currentModelSource = getOnboardingChoice(state, 'modelSource');
    const currentAuthMethod = getOnboardingChoice(state, 'authMethod');

    startPage('New User Onboarding — Setup Agent Readiness', 'This page bridges the installer into the minimum OpenClaw onboarding needed to land you on the dashboard with a ready setup agent.');
    printOnboardingStepSummary(state);
    console.log('\nMinimum OpenClaw onboarding elements this installer is preparing:');
    console.log(`- Model setup: ${currentModelSource || 'Not chosen yet'}`);
    console.log(`- OAuth / token / auth: ${currentAuthMethod || 'Not chosen yet'}`);
    console.log(`- Gateway: ${gatewayConfig.dashboardUrl}`);
    console.log('\nSetup-agent modes:');
    console.log('1) Auto mode');
    console.log('   Fast path. The installer prepares a small local model and a local gateway-backed setup agent for first run.');
    console.log('2) Manual mode');
    console.log('   You decide how the setup agent gets its model/backend, while the installer still carries the gateway handoff forward.');
    console.log('\nExtra actions:');
    console.log('3) Review or refresh the gateway handoff details');
    printOnboardingNavigation({ showBack: true, showNext: true });
    console.log('\nStep action: choose 1 or 2, then press n to continue.');

    const raw = (await askQuestion(rl, '\nSetup agent readiness> ')).trim();
    if (raw === '1') {
      const autoProvisioningPlan = buildAutoProvisioningPlan(state);
      state = applyOnboardingChoice(state, 'setupAgentMode', 'auto');
      state = applyOnboardingChoice(state, 'providerMode', 'auto');
      state = applyOnboardingChoice(state, 'modelSource', autoProvisioningPlan.modelProfile);
      state = applyOnboardingChoice(state, 'authMethod', 'local gateway session');
      state = applyOnboardingChoice(state, 'setupAgentProvisioning', autoProvisioningPlan);
      state = applyOnboardingChoice(state, 'gatewayConfig', autoProvisioningPlan.gatewayConfig);
      console.log('\nSaved: Auto mode.');
      summarizeAutoProvisioningPlan(autoProvisioningPlan).forEach(line => console.log(`- ${line}`));
      console.log(`- ${autoProvisioningPlan.handoffSummary}`);
      continue;
    }
    if (raw === '2') {
      const updatedState = await promptForManualSetupAgentProvisioning(rl, state);
      if (updatedState) state = updatedState;
      continue;
    }
    if (raw === '3') {
      const refreshedGatewayConfig = defaultGatewayConfig(state);
      state = applyOnboardingChoice(state, 'gatewayConfig', refreshedGatewayConfig);
      console.log('\nGateway handoff details:');
      console.log(`- Host: ${refreshedGatewayConfig.host}`);
      console.log(`- Port: ${refreshedGatewayConfig.port}`);
      console.log(`- Dashboard URL: ${refreshedGatewayConfig.dashboardUrl}`);
      console.log('- This is the local gateway/dashboard handoff the installer will use unless you change paths/ports earlier.');
      await askQuestion(rl, '\nPress Enter to return to the setup-agent readiness page. ');
      continue;
    }
    if (/^[h?]$/i.test(raw)) {
      startPage('Setup Agent Readiness Help', 'This stage defines what the installer itself must prepare before dashboard onboarding takes over.');
      console.log('\nWhy this page exists:');
      console.log('- ResonantOS should not drop a new user into a blank dashboard.');
      console.log('- The installer is responsible for handing off a ready setup-agent path.');
      console.log('- The minimum OpenClaw onboarding pieces are model setup, auth setup, and gateway setup.');
      console.log('\nAuto mode: fastest path with a small local setup model.');
      console.log('Manual mode: keeps the gateway handoff but lets later onboarding choose API key, OAuth, or a curated local model path.');
      await askQuestion(rl, '\nPress Enter to return to the setup-agent readiness page. ');
      continue;
    }
    if (/^[b]$/i.test(raw)) return { action: 'back', state };
    if (/^[n]$/i.test(raw)) {
      if (!getOnboardingChoice(state, 'setupAgentMode')) {
        console.log('Choose Auto mode or Manual mode first.');
        continue;
      }
      state = completeOnboardingStep(state, 'agent-readiness');
      return { action: 'next', state };
    }
    if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('New-user onboarding cancelled by user.');
    console.log('Use 1/2/3, or n / b / h / q.');
  }
}

async function promptForNewUserOnboarding(state) {
  const rl = createPromptSession();
  let steps = getActiveOnboardingSteps(state).filter(step => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(step));
  let index = 0;

  try {
    while (index < steps.length) {
      const step = steps[index];
      let result;

      if (step === 'install-style') {
        result = await promptForNewUserInstallStyle(rl, state);
        if (result?.action === 'next') {
          state = completeOnboardingStep(result.state, 'install-style');
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else if (step === 'docker-choice') {
        result = await promptForNewUserDockerChoice(rl, state);
        if (result?.action === 'back') {
          state = result.state;
          index = Math.max(0, index - 1);
          continue;
        }
        if (result?.action === 'next') {
          state = result.state;
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else if (step === 'docker-readiness') {
        result = await promptForNewUserDockerReadiness(rl, state);
        if (result?.action === 'back') {
          state = result.state;
          index = Math.max(0, index - 1);
          continue;
        }
        if (result?.action === 'next') {
          state = result.state;
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else if (step === 'docker-management') {
        result = await promptForNewUserDockerManagement(rl, state);
        if (result?.action === 'back') {
          state = result.state;
          index = Math.max(0, index - 1);
          continue;
        }
        if (result?.action === 'next') {
          state = result.state;
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else if (step === 'paths-and-ports') {
        result = await promptForNewUserPathsAndPorts(rl, state);
        if (result?.action === 'back') {
          state = result.state;
          index = Math.max(0, index - 1);
          continue;
        }
        if (result?.action === 'next') {
          state = result.state;
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else if (step === 'agent-readiness') {
        result = await promptForNewUserAgentReadiness(rl, state);
        if (result?.action === 'back') {
          state = result.state;
          index = Math.max(0, index - 1);
          continue;
        }
        if (result?.action === 'next') {
          state = result.state;
          steps = getActiveOnboardingSteps(state).filter(activeStep => ['install-style', 'docker-choice', 'docker-readiness', 'docker-management', 'paths-and-ports', 'agent-readiness'].includes(activeStep));
          index += 1;
          continue;
        }
      } else {
        fail('Unknown onboarding step encountered.', step);
      }

      state = result?.state || state;
    }

    return state;
  } finally {
    rl.close();
  }
}

async function completeManualSelection(baseSelection) {
  const rl = createPromptSession();

  try {
    startPage('Manual Existing Target', 'Provide paths for an existing OpenClaw install. Nothing will be changed yet.');
    console.log('\nIf you discover the real target is on another machine, type REMOTE at a prompt for guidance.');

    while (true) {
      const configInput = await askQuestion(rl, 'Existing config path (openclaw.json or its folder)> ');
      if (/^q(uit)?$/i.test(configInput.trim()) || /^exit$/i.test(configInput.trim())) fail('Manual path entry cancelled by user.');
      if (isRemoteGuidanceRequest(configInput)) {
        const action = await showWrongMachineGuidance(rl);
        if (action === 'exit') fail('Recovery cancelled so you can restart the installer on the correct machine.');
        startPage('Manual Existing Target', 'Provide paths for an existing OpenClaw install. Nothing will be changed yet.');
        console.log('\nIf you discover the real target is on another machine, type REMOTE at a prompt for guidance.');
        continue;
      }

      const workspaceInput = await askQuestion(rl, 'Existing workspace path> ');
      if (/^q(uit)?$/i.test(workspaceInput.trim()) || /^exit$/i.test(workspaceInput.trim())) fail('Manual path entry cancelled by user.');
      if (isRemoteGuidanceRequest(workspaceInput)) {
        const action = await showWrongMachineGuidance(rl);
        if (action === 'exit') fail('Recovery cancelled so you can restart the installer on the correct machine.');
        startPage('Manual Existing Target', 'Provide paths for an existing OpenClaw install. Nothing will be changed yet.');
        console.log('\nIf you discover the real target is on another machine, type REMOTE at a prompt for guidance.');
        continue;
      }

      const configPath = existingConfigPathFromInput(configInput);
      const workspacePath = directoryInputToPath(workspaceInput);
      const validation = validateManualSelectionPaths({ configPath, workspacePath });

      if (!validation.ok) {
        console.log('\nThose paths are not usable for an existing install target:');
        console.log(summarizeValidationErrors(validation.errors));
        console.log('Please try again.');
        continue;
      }

      const recoveryRun = runDetector({ suppressOutput: true, targetConfigPath: validation.normalized.configPath });
      const recoveryOption = getRecoveryOptionFromRun(recoveryRun, validation.normalized.configPath);

      if (recoveryOption) {
        startPage('Recovered Existing Target', 'The installer checked the config you provided directly and built the target below.');
        console.log('\nThis recovery check only inspected the location you provided, not a wide scan.');
        printDetectedInstances(recoveryRun.report, getInstallerOptionsFromRun(recoveryRun));

        if (recoveryOption.workspacePath && !sameResolvedPath(recoveryOption.workspacePath, validation.normalized.workspacePath)) {
          console.log('\nNote:');
          console.log(`- Detector workspace: ${formatPath(recoveryOption.workspacePath)}`);
          console.log(`- Your entered workspace: ${formatPath(validation.normalized.workspacePath)}`);
          console.log('- Your entered workspace will be used for confirmation unless you re-enter the paths.');
        }

        console.log('\nRecovered existing-target summary:');
        console.log(`- Selection Type: existing`);
        console.log(`- Label: ${recoveryOption.displayLabel || `Recovered target at ${validation.normalized.installRoot}`}`);
        console.log(`- Config: ${validation.normalized.configPath}`);
        console.log(`- Workspace: ${validation.normalized.workspacePath}`);
        console.log(`- Install Root: ${recoveryOption.installRoot || validation.normalized.installRoot}`);
        console.log(`- Runtime: ${recoveryOption.runtimeKind || baseSelection.runtimeKind || 'manual-existing-target'}`);
        console.log(`- Running: ${recoveryOption.isRunning ? 'yes' : 'no'}`);
        console.log(`- Confidence: ${String(recoveryOption.confidence || 'manual').toUpperCase()}`);

        const confirmed = await promptForYesNo(rl, 'Confirm this recovered existing-install target? [y/N] ');
        if (!confirmed) {
          console.log('Okay, let\'s try again.');
          continue;
        }

        return buildCompletedSelection(baseSelection, {
          selectionType: 'existing',
          selectedOptionId: recoveryOption.optionId || baseSelection.selectedOptionId,
          displayLabel: recoveryOption.displayLabel || `Recovered target at ${validation.normalized.installRoot}`,
          configPath: validation.normalized.configPath,
          workspacePath: validation.normalized.workspacePath,
          installRoot: recoveryOption.installRoot || validation.normalized.installRoot,
          runtimeKind: recoveryOption.runtimeKind || baseSelection.runtimeKind || 'manual-existing-target',
          isRunning: Boolean(recoveryOption.isRunning),
          confidence: recoveryOption.confidence || 'manual',
        });
      }

      console.log('\nManual existing-target summary:');
      console.log('- Selection Type: manual');
      console.log(`- Config: ${validation.normalized.configPath}`);
      console.log(`- Workspace: ${validation.normalized.workspacePath}`);
      console.log(`- Install Root: ${validation.normalized.installRoot}`);
      console.log('- Targeted detection did not produce a reusable recovered instance card, so these confirmed manual paths will be used.');

      const confirmed = await promptForYesNo(rl, 'Confirm these existing-install paths? [y/N] ');
      if (!confirmed) {
        console.log('Okay, let\'s try again.');
        continue;
      }

      return buildCompletedSelection(baseSelection, {
        displayLabel: `Manual existing target at ${validation.normalized.installRoot}`,
        configPath: validation.normalized.configPath,
        workspacePath: validation.normalized.workspacePath,
        installRoot: validation.normalized.installRoot,
        runtimeKind: baseSelection.runtimeKind || 'manual-existing-target',
        isRunning: false,
        confidence: 'manual',
      });
    }
  } finally {
    rl.close();
  }
}

async function completeNewSelection(baseSelection, onboardingState = null) {
  const rl = createPromptSession();

  try {
    const defaults = defaultNewUserPaths(onboardingState || { choices: {} });

    while (true) {
      const prefilledInstallRoot = getOnboardingChoice(onboardingState, 'installRoot') || defaults.installRoot;
      const prefilledWorkspacePath = getOnboardingChoice(onboardingState, 'workspacePath') || defaults.workspacePath;
      const prefilledGatewayPort = getOnboardingChoice(onboardingState, 'gatewayPort') || defaults.gatewayPort;

      startPage('New Install Target', 'Confirm the fresh install target gathered during onboarding. You can keep the current values or edit them here.');
      console.log('\nCurrent new-install target:');
      console.log(`- Install Root: ${prefilledInstallRoot}`);
      console.log(`- Workspace: ${prefilledWorkspacePath}`);
      console.log(`- Gateway Port: ${prefilledGatewayPort}`);
      console.log('\nPress Enter to keep a shown value.');

      const installRootInput = await askQuestion(rl, `New install root path [${prefilledInstallRoot}]> `);
      if (/^q(uit)?$/i.test(installRootInput.trim()) || /^exit$/i.test(installRootInput.trim())) fail('New-install path entry cancelled by user.');
      const workspaceInput = await askQuestion(rl, `New workspace path [${prefilledWorkspacePath}]> `);
      if (/^q(uit)?$/i.test(workspaceInput.trim()) || /^exit$/i.test(workspaceInput.trim())) fail('New-install path entry cancelled by user.');
      const gatewayPortInput = await askQuestion(rl, `Gateway port [${prefilledGatewayPort}]> `);
      if (/^q(uit)?$/i.test(gatewayPortInput.trim()) || /^exit$/i.test(gatewayPortInput.trim())) fail('New-install path entry cancelled by user.');

      const installRoot = directoryInputToPath(installRootInput.trim() || prefilledInstallRoot);
      const workspacePath = directoryInputToPath(workspaceInput.trim() || prefilledWorkspacePath);
      const gatewayPortValidation = validateGatewayPort(gatewayPortInput.trim() || prefilledGatewayPort);
      const validation = validateNewSelectionPaths({ installRoot, workspacePath });

      if (!validation.ok) {
        console.log('\nThose paths are not usable for a new install target:');
        console.log(summarizeValidationErrors(validation.errors));
        console.log('Please try again.');
        continue;
      }

      if (!gatewayPortValidation.ok) {
        console.log(`\n${gatewayPortValidation.error}`);
        console.log('Please try again.');
        continue;
      }

      console.log('\nNew install target summary:');
      console.log(`- Selection Type: new`);
      console.log(`- Install Root: ${validation.normalized.installRoot}`);
      console.log(`- Workspace: ${validation.normalized.workspacePath}`);
      console.log(`- Gateway Port: ${gatewayPortValidation.value}`);
      console.log(`- Planned Config Path: ${validation.normalized.configPath}`);
      console.log('- Existing install detection check: no openclaw.json currently exists at the planned config path.');

      const confirmed = await promptForYesNo(rl, 'Confirm this new-install target? [y/N] ');
      if (!confirmed) {
        console.log('Okay, let\'s try again.');
        continue;
      }

      if (onboardingState) {
        onboardingState = applyOnboardingChoice(onboardingState, 'installRoot', validation.normalized.installRoot);
        onboardingState = applyOnboardingChoice(onboardingState, 'workspacePath', validation.normalized.workspacePath);
        onboardingState = applyOnboardingChoice(onboardingState, 'gatewayPort', gatewayPortValidation.value);
      }

      return buildCompletedSelection(baseSelection, {
        displayLabel: `New install target at ${validation.normalized.installRoot}`,
        configPath: validation.normalized.configPath,
        workspacePath: validation.normalized.workspacePath,
        installRoot: validation.normalized.installRoot,
        gatewayPort: gatewayPortValidation.value,
        runtimeKind: 'new-install',
        isRunning: false,
        confidence: 'new',
        onboardingState: onboardingState ? JSON.parse(JSON.stringify(onboardingState)) : baseSelection.onboardingState,
      });
    }
  } finally {
    rl.close();
  }
}

function printConfirmedSelection(confirmedSelection, selectedOption) {
  console.log('\nChosen Installer Option:');
  console.log(`- ${selectedOption.title}`);
  console.log(`  Option ID: ${selectedOption.optionId}`);
  console.log(`  Label: ${confirmedSelection.displayLabel || selectedOption.displayLabel}`);
  console.log(`  Selection Type: ${confirmedSelection.selectionType}`);
  console.log(`  Runtime: ${confirmedSelection.runtimeKind || 'unknown'}`);
  console.log(`  Running: ${confirmedSelection.isRunning ? 'yes' : 'no'}`);
  console.log(`  Confidence: ${confirmedSelection.confidence || 'unknown'}`);
  console.log(`  Config: ${formatPath(confirmedSelection.configPath)}`);
  console.log(`  Workspace: ${formatPath(confirmedSelection.workspacePath)}`);
  console.log(`  Install Root: ${formatPath(confirmedSelection.installRoot)}`);
  if (confirmedSelection.gatewayPort) console.log(`  Gateway Port: ${confirmedSelection.gatewayPort}`);

  const readiness = confirmedSelection.onboardingState?.choices || null;
  if (readiness?.setupAgentMode || readiness?.modelSource || readiness?.authMethod || readiness?.gatewayConfig) {
    console.log('  Setup Agent Readiness:');
    if (readiness.setupAgentMode) console.log(`    Mode: ${readiness.setupAgentMode}`);
    if (readiness.modelSource) console.log(`    Model: ${readiness.modelSource}`);
    if (readiness.authMethod) console.log(`    Auth: ${readiness.authMethod}`);
    if (readiness.gatewayConfig?.dashboardUrl) console.log(`    Dashboard Handoff: ${readiness.gatewayConfig.dashboardUrl}`);
  }
}

function buildReviewSummary(selectionBranch, selectedOption, onboardingState, baseSelection = null) {
  const choices = onboardingState?.choices || {};
  const gatewayConfig = choices.gatewayConfig || defaultGatewayConfig(onboardingState || { choices: {} });

  return {
    selectionBranch,
    optionTitle: selectedOption?.title || null,
    optionLabel: selectedOption?.displayLabel || selectedOption?.summary || null,
    installStyle: choices.installStyle || null,
    dockerEnabled: choices.dockerEnabled,
    dockerMode: choices.dockerMode || null,
    installRoot: choices.installRoot || baseSelection?.installRoot || null,
    workspacePath: choices.workspacePath || baseSelection?.workspacePath || null,
    gatewayPort: choices.gatewayPort || baseSelection?.gatewayPort || gatewayConfig?.port || null,
    setupAgentMode: choices.setupAgentMode || null,
    modelSource: choices.modelSource || null,
    authMethod: choices.authMethod || null,
    dashboardUrl: gatewayConfig?.dashboardUrl || null,
    setupAgentProvisioning: choices.setupAgentProvisioning || null,
    manualProvisioning: choices.manualProvisioning || null,
    installReady: Boolean((choices.installRoot || baseSelection?.installRoot) && (choices.workspacePath || baseSelection?.workspacePath) && (choices.setupAgentMode || selectionBranch !== 'new-user')),
  };
}

function printReviewSummary(summary) {
  console.log('\nReview Summary:');
  if (summary.optionTitle) console.log(`- Install mode: ${summary.optionTitle}`);
  if (summary.optionLabel) console.log(`- Selected path: ${summary.optionLabel}`);
  if (summary.installStyle) console.log(`- Install style: ${installStyleLabel(summary.installStyle)}`);
  console.log(`- Docker: ${dockerChoiceLabel(summary.dockerEnabled)}`);
  if (summary.dockerMode) console.log(`- Docker plan: ${dockerRecommendedActionLabel(summary.dockerMode)}`);
  if (summary.installRoot) console.log(`- Install root: ${summary.installRoot}`);
  if (summary.workspacePath) console.log(`- Workspace: ${summary.workspacePath}`);
  if (summary.gatewayPort) console.log(`- Gateway port: ${summary.gatewayPort}`);
  if (summary.setupAgentMode) console.log(`- Setup agent mode: ${summary.setupAgentMode}`);
  if (summary.modelSource) console.log(`- Model source: ${summary.modelSource}`);
  if (summary.authMethod) console.log(`- Auth method: ${summary.authMethod}`);
  if (summary.dashboardUrl) console.log(`- Dashboard handoff: ${summary.dashboardUrl}`);
  if (summary.setupAgentProvisioning?.mode === 'auto') {
    console.log(`- Auto provisioning plan: ${summary.setupAgentProvisioning.modelProfile}`);
  }
  if (summary.manualProvisioning?.mode === 'manual') {
    console.log(`- Manual provider path: ${summary.manualProvisioning.providerLabel}`);
  }
  console.log(`- Install-ready state: ${summary.installReady ? 'ready for later execution phase' : 'not ready yet'}`);
}

async function maybeShowReviewPage(selectionBranch, selectedOption, onboardingState, baseSelection = null) {
  if (selectionBranch !== 'new-user' || !onboardingState) return true;

  const rl = createPromptSession();
  try {
    while (true) {
      const summary = buildReviewSummary(selectionBranch, selectedOption, onboardingState, baseSelection);
      startPage('Final Review', 'Review the chosen install path, Docker plan, paths/ports, and setup-agent readiness before the installer confirms the target.');
      printReviewSummary(summary);
      console.log('\nThis page is still read-only. No install or filesystem mutation has been performed yet.');
      console.log('Commands:');
      console.log('- c = continue with this reviewed plan');
      console.log('- b = go back and change onboarding choices');
      console.log('- h = show a compact explanation of this review page');
      console.log('- q = cancel');

      const raw = (await askQuestion(rl, '\nReview> ')).trim();
      if (/^[c]$/i.test(raw)) return true;
      if (/^[b]$/i.test(raw)) return false;
      if (/^[h?]$/i.test(raw)) {
        startPage('Review Help', 'This page is the final compact checklist before the later execution phase.');
        console.log('\nIt brings together the major decisions you already made:');
        console.log('- install mode');
        console.log('- Docker choice and plan');
        console.log('- paths and ports');
        console.log('- setup-agent readiness');
        console.log('- whether the installer has enough information to proceed later');
        await askQuestion(rl, '\nPress Enter to return to the review page. ');
        continue;
      }
      if (/^q(uit)?$/i.test(raw) || /^exit$/i.test(raw)) fail('Installer review cancelled by user.');
      console.log('Use c to continue, b to go back, h for help, or q to cancel.');
    }
  } finally {
    rl.close();
  }
}

async function main() {
  if (!fs.existsSync(detectorPath)) {
    fail('Detector not found:', detectorPath);
  }

  try {
    fs.mkdirSync(reportsDir, { recursive: true });
  } catch (error) {
    fail('Unable to create reports directory.', error.message);
  }

  let initialRun;
  let selectionBranch;
  let availableOptions;
  let dependencyPageShown = false;
  let onboardingState = null;

  while (true) {
    printDetectionIntroPage();

    initialRun = runDetector({ suppressOutput: true });
    console.log('\nScan complete.');
    await waitForAnyKey('Press any key to continue. This page will clear, so finish reading first.');

    const allAvailableOptions = Array.isArray(initialRun.handoff?.installerDecision?.availableOptions)
      ? initialRun.handoff.installerDecision.availableOptions
      : (Array.isArray(initialRun.report?.installerOptions) ? initialRun.report.installerOptions : []);

    if (!allAvailableOptions.length) {
      fail('Assessment completed but no installer options were produced.');
    }

    const detectedInstances = getDetectedInstances(initialRun.report);
    selectionBranch = 'detected-instances';
    if (!detectedInstances.length) {
      selectionBranch = await promptForZeroDetectionBranch();
    }

    availableOptions = filterOptionsForZeroDetectionBranch(allAvailableOptions, selectionBranch);
    if (!availableOptions.length) {
      fail('The selected installer branch did not produce any selectable options.');
    }

    const dependencyResult = await maybeShowDependencyIssuesPage(initialRun.report, selectionBranch);
    if (dependencyResult === 'rerun') continue;
    dependencyPageShown = Boolean(dependencyResult);
    break;
  }

  if (selectionBranch === 'detected-instances') {
    startPage('Choose Install Target', 'Review the assessed targets below, then choose the installer option to confirm.');
    if (dependencyPageShown) console.log('Dependency issues were reviewed for this branch before target selection.');
    printDetectedInstances(initialRun.report, availableOptions);
    printSuggestedChoice(availableOptions, selectionBranch);
    printOptions(availableOptions, selectionBranch);
    printAssessmentFooter(initialRun.report, initialRun.reportPath);
  } else if (selectionBranch === 'new-user') {
    onboardingState = createOnboardingState('new-user');
    onboardingState = await promptForNewUserOnboarding(onboardingState);

    startPage('New User Install Path', 'The installer has your starting choices and can now continue into the guided new-user setup path.');
    console.log(`\nInstall style selected: ${installStyleLabel(getOnboardingChoice(onboardingState, 'installStyle'))}`);
    console.log(`Docker choice selected: ${dockerChoiceLabel(getOnboardingChoice(onboardingState, 'dockerEnabled'))}`);
    console.log('The generic dependency issues page is skipped at this stage.');
    console.log('Paths, ports, and provider/model choices will be guided later in onboarding.');
    printOptions(availableOptions, selectionBranch);
    printAssessmentFooter(initialRun.report, initialRun.reportPath);
  } else {
    startPage('Existing User Recovery', 'No instance was detected, so the installer is prioritizing recovery of an existing target first.');
    console.log('\nNo detected instances of OpenClaw.');
    console.log('You said you have used OpenClaw or ResonantOS before.');
    console.log('\nRecovery comes first here. If detection missed your install, choose the manual existing-target path.');
    console.log('If you discover you actually want a fresh install instead, you can pivot to the new-install path from here.');
    if (dependencyPageShown) console.log('\nDependency issues were reviewed for this branch before recovery choices.');
    printOptions(availableOptions, selectionBranch);
    printAssessmentFooter(initialRun.report, initialRun.reportPath);
  }

  let selectedOption = await promptForSelection(availableOptions, selectionBranch);

  while (!(await maybeShowReviewPage(selectionBranch, selectedOption, onboardingState, selectedOption))) {
    if (selectionBranch !== 'new-user') break;
    onboardingState = await promptForNewUserOnboarding(onboardingState);

    startPage('New User Install Path', 'The installer has your updated onboarding choices and can now continue into the guided new-user setup path.');
    console.log(`\nInstall style selected: ${installStyleLabel(getOnboardingChoice(onboardingState, 'installStyle'))}`);
    console.log(`Docker choice selected: ${dockerChoiceLabel(getOnboardingChoice(onboardingState, 'dockerEnabled'))}`);
    console.log('Use the same install option below after reviewing the updated onboarding state.');
    printOptions(availableOptions, selectionBranch);
    printAssessmentFooter(initialRun.report, initialRun.reportPath);
    selectedOption = await promptForSelection(availableOptions, selectionBranch);
  }

  const confirmedRun = runDetector({ selectedOptionId: selectedOption.optionId, suppressOutput: true });
  const detectorConfirmedSelection = confirmedRun.handoff?.installerDecision?.confirmedSelection || confirmedRun.report?.confirmedSelection || null;

  if (!detectorConfirmedSelection) {
    fail('Selected option was accepted, but no confirmed selection object was produced.', selectedOption.optionId);
  }

  if (detectorConfirmedSelection.selectedOptionId !== selectedOption.optionId) {
    fail('Confirmed selection did not match the chosen option.', JSON.stringify(detectorConfirmedSelection, null, 2));
  }

  let finalConfirmedSelection = detectorConfirmedSelection;
  const selectedInstallStyle = getOnboardingChoice(onboardingState, 'installStyle');
  if (selectionBranch === 'new-user' && selectedInstallStyle) {
    onboardingState = setOnboardingCurrentStep(onboardingState, 'target-confirmation');
    finalConfirmedSelection = {
      ...finalConfirmedSelection,
      installStyle: selectedInstallStyle,
      onboardingState: JSON.parse(JSON.stringify(onboardingState)),
    };
  }

  if (detectorConfirmedSelection.selectionType === 'manual') {
    finalConfirmedSelection = await completeManualSelection(detectorConfirmedSelection);
  } else if (detectorConfirmedSelection.selectionType === 'new') {
    finalConfirmedSelection = await completeNewSelection(detectorConfirmedSelection, onboardingState);
  }

  startPage('Selection Confirmed', 'The installer has a confirmed target ready for the next phase.');
  printConfirmedSelection(finalConfirmedSelection, selectedOption);

  if (finalConfirmedSelection.selectionType === 'manual') {
    console.log('\nManual existing-install target is confirmed and ready for the next installer phase.');
    console.log('(No install or filesystem mutation has been performed yet.)');
    return;
  }

  if (finalConfirmedSelection.selectionType === 'new') {
    console.log('\nNew-install target paths are confirmed and ready for the next installer phase.');
    console.log('(No install or filesystem mutation has been performed yet.)');
    return;
  }

  console.log('\nConfirmed existing install target is ready for the next installer phase.');
}

if (require.main === module) {
  main().catch((error) => {
    fail('Installer entry failed.', error?.message || String(error));
  });
}

module.exports = {
  applyOnboardingChoice,
  buildAutoProvisioningPlan,
  buildManualProvisioningPlan,
  buildReviewSummary,
  completeOnboardingStep,
  createOnboardingState,
  defaultGatewayConfig,
  dockerChoiceLabel,
  dockerRecommendedActionLabel,
  getActiveOnboardingSteps,
  getDockerPlanSummary,
  getOnboardingChoice,
  installStyleLabel,
  promptForNewUserDockerReadiness,
  promptForNewUserOnboarding,
  reconcileOnboardingStateAfterInvalidation,
  resetDependentChoices,
  setOnboardingCurrentStep,
};
