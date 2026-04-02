const test = require('node:test');
const assert = require('node:assert/strict');

const installer = require('../installer-entry.js');

test('new-user onboarding state tracks install style and docker choice across wizard steps', () => {
  let state = installer.createOnboardingState('new-user');

  assert.equal(state.currentStep, 'install-style');
  assert.deepEqual(state.stepHistory, ['install-style']);

  state = installer.applyOnboardingChoice(state, 'installStyle', 'recommended');
  state = installer.completeOnboardingStep(state, 'install-style');
  state = installer.setOnboardingCurrentStep(state, 'docker-choice');
  state = installer.applyOnboardingChoice(state, 'dockerEnabled', true);
  state = installer.completeOnboardingStep(state, 'docker-choice');

  assert.equal(installer.getOnboardingChoice(state, 'installStyle'), 'recommended');
  assert.equal(installer.getOnboardingChoice(state, 'dockerEnabled'), true);
  assert.deepEqual(state.completedSteps, ['install-style', 'docker-choice']);
  assert.deepEqual(state.stepHistory, ['install-style', 'docker-choice']);
  assert.equal(state.currentStep, 'docker-choice');
});

test('changing install style invalidates dependent docker/provider/path choices but keeps onboarding metadata', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'installStyle', 'recommended');
  state = installer.completeOnboardingStep(state, 'install-style');
  state = installer.setOnboardingCurrentStep(state, 'docker-choice');
  state = installer.applyOnboardingChoice(state, 'dockerEnabled', true);
  state = installer.completeOnboardingStep(state, 'docker-choice');
  state = installer.applyOnboardingChoice(state, 'dockerMode', 'compose');
  state = installer.applyOnboardingChoice(state, 'providerMode', 'auto');
  state = installer.applyOnboardingChoice(state, 'installRoot', '/tmp/resonantos');
  state = installer.applyOnboardingChoice(state, 'workspacePath', '/tmp/workspace');

  state = installer.applyOnboardingChoice(state, 'installStyle', 'custom');

  assert.equal(installer.getOnboardingChoice(state, 'installStyle'), 'custom');
  assert.equal(installer.getOnboardingChoice(state, 'dockerEnabled'), null);
  assert.equal(installer.getOnboardingChoice(state, 'dockerMode'), null);
  assert.equal(installer.getOnboardingChoice(state, 'providerMode'), null);
  assert.equal(installer.getOnboardingChoice(state, 'installRoot'), null);
  assert.equal(installer.getOnboardingChoice(state, 'workspacePath'), null);
  assert.deepEqual(state.completedSteps, ['install-style']);
  assert.equal(state.invalidationLog.length, 1);
  assert.equal(state.invalidationLog[0].reason, 'installStyle changed');
  assert.deepEqual(state.invalidationLog[0].cleared, ['dockerEnabled', 'dockerMode', 'providerMode', 'installRoot', 'workspacePath']);
});

test('disabling docker removes docker-only state and hides the docker-management step without clearing unrelated choices', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'installStyle', 'recommended');
  state = installer.completeOnboardingStep(state, 'install-style');
  state = installer.applyOnboardingChoice(state, 'dockerEnabled', true);
  state = installer.completeOnboardingStep(state, 'docker-choice');
  state = installer.setOnboardingCurrentStep(state, 'docker-management');
  state = installer.applyOnboardingChoice(state, 'dockerMode', 'compose');
  state = installer.applyOnboardingChoice(state, 'providerMode', 'manual');
  state = installer.completeOnboardingStep(state, 'provider-choice');

  assert.deepEqual(installer.getActiveOnboardingSteps(state), [
    'install-style',
    'docker-choice',
    'docker-readiness',
    'docker-management',
    'paths-and-ports',
    'provider-choice',
    'agent-readiness',
    'target-confirmation',
  ]);

  state = installer.applyOnboardingChoice(state, 'dockerEnabled', false);

  assert.equal(installer.getOnboardingChoice(state, 'dockerEnabled'), false);
  assert.equal(installer.getOnboardingChoice(state, 'dockerMode'), null);
  assert.equal(installer.getOnboardingChoice(state, 'providerMode'), 'manual');
  assert.equal(state.currentStep, 'provider-choice');
  assert.deepEqual(installer.getActiveOnboardingSteps(state), [
    'install-style',
    'docker-choice',
    'paths-and-ports',
    'provider-choice',
    'agent-readiness',
    'target-confirmation',
  ]);
  assert.equal(state.invalidationLog.at(-1).reason, 'docker disabled');
});

test('docker plan summary reflects compose and single-container setup modes', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'dockerMode', 'compose');
  let plan = installer.getDockerPlanSummary(state);
  assert.equal(plan.modeLabel, 'Docker Compose layout');
  assert.ok(plan.commands.includes('docker compose version'));

  state = installer.applyOnboardingChoice(state, 'dockerMode', 'single-container');
  plan = installer.getDockerPlanSummary(state);
  assert.equal(plan.modeLabel, 'Single-container Docker layout');
  assert.ok(plan.commands.includes('docker ps'));
});

test('docker recommended action labels remain user-readable for readiness and setup modes', () => {
  assert.equal(installer.dockerRecommendedActionLabel('install'), 'Install Docker in the Docker flow');
  assert.equal(installer.dockerRecommendedActionLabel('fix-or-update'), 'Update or repair Docker in the Docker flow');
  assert.equal(installer.dockerRecommendedActionLabel('confirm-ready'), 'Docker looks ready; continue with Docker setup');
  assert.equal(installer.dockerRecommendedActionLabel('compose'), 'Use Docker Compose style setup');
  assert.equal(installer.dockerRecommendedActionLabel('single-container'), 'Use a single-container Docker setup');
});

test('auto provisioning plan defines the small local setup-model handoff clearly', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'installStyle', 'recommended');
  state = installer.applyOnboardingChoice(state, 'gatewayPort', '18820');

  const plan = installer.buildAutoProvisioningPlan(state);
  assert.equal(plan.mode, 'auto');
  assert.equal(plan.modelProfile, 'small local setup model');
  assert.equal(plan.gatewayConfig.dashboardUrl, 'http://127.0.0.1:18820/dashboard');
  assert.ok(plan.provisioningSteps.some(step => step.includes('Download the small local setup model')));
  assert.match(plan.handoffSummary, /small local model/i);
});

test('manual provisioning plan supports api key, oauth, and curated local model paths', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'gatewayPort', '18820');

  const apiPlan = installer.buildManualProvisioningPlan(state, 'api-key');
  assert.equal(apiPlan.mode, 'manual');
  assert.equal(apiPlan.authMethod, 'API key');
  assert.match(apiPlan.handoffSummary, /API key/i);

  const oauthPlan = installer.buildManualProvisioningPlan(state, 'oauth');
  assert.equal(oauthPlan.authMethod, 'OAuth');
  assert.equal(oauthPlan.providerLabel, 'OAuth-backed provider');

  const localPlan = installer.buildManualProvisioningPlan(state, 'local-curated');
  assert.equal(localPlan.modelSource, 'curated local model menu');
  assert.ok(localPlan.provisioningSteps.some(step => step.includes('curated local model menu')));
});

test('review summary combines install mode, docker, paths, and setup-agent readiness', () => {
  let state = installer.createOnboardingState('new-user');
  state = installer.applyOnboardingChoice(state, 'installStyle', 'recommended');
  state = installer.applyOnboardingChoice(state, 'dockerEnabled', false);
  state = installer.applyOnboardingChoice(state, 'installRoot', '/srv/resonantos');
  state = installer.applyOnboardingChoice(state, 'workspacePath', '/srv/resonantos/workspace');
  state = installer.applyOnboardingChoice(state, 'gatewayPort', '18820');
  state = installer.applyOnboardingChoice(state, 'setupAgentMode', 'auto');
  state = installer.applyOnboardingChoice(state, 'modelSource', 'small local setup model');
  state = installer.applyOnboardingChoice(state, 'authMethod', 'local gateway session');
  state = installer.applyOnboardingChoice(state, 'setupAgentProvisioning', installer.buildAutoProvisioningPlan(state));
  state = installer.applyOnboardingChoice(state, 'gatewayConfig', installer.defaultGatewayConfig(state));

  const summary = installer.buildReviewSummary('new-user', { title: 'Install new default path instance', displayLabel: 'New install target' }, state);
  assert.equal(summary.installStyle, 'recommended');
  assert.equal(summary.dockerEnabled, false);
  assert.equal(summary.installRoot, '/srv/resonantos');
  assert.equal(summary.workspacePath, '/srv/resonantos/workspace');
  assert.equal(summary.gatewayPort, '18820');
  assert.equal(summary.setupAgentMode, 'auto');
  assert.equal(summary.dashboardUrl, 'http://127.0.0.1:18820/dashboard');
  assert.equal(summary.installReady, true);
});
