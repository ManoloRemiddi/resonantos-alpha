// Test shield layer modules
const layers = [
  './layers/layer_1_destructive',
  './layers/layer_1_5_delegation',
  './layers/layer_2_coherence',
  './layers/layer_3_direct_coding',
  './layers/layer_4_context_isolation',
  './layers/layer_5_research',
  './layers/layer_6_behavioral',
  './layers/layer_7_external',
  './layers/layer_8_compaction',
  './layers/layer_9_researcher',
  './layers/layer_10_network',
  './layers/layer_11_sensitive',
  './layers/layer_12_git_push',
  './layers/layer_13_atomic_rebuild',
  './layers/layer_14_autonomous',
];

let pass = 0, fail = 0;
for (const l of layers) {
  try {
    const m = require(l);
    if (typeof m.check === 'function') {
      console.log(`PASS: ${l}`);
      pass++;
    } else {
      console.log(`FAIL: ${l} — no check() function`);
      fail++;
    }
  } catch(e) {
    console.log(`FAIL: ${l} — ${e.message}`);
    fail++;
  }
}

console.log(`\n${pass}/${pass+fail} layer modules exported check() correctly.`);
process.exit(fail > 0 ? 1 : 0);
