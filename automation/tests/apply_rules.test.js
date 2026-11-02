// node --test automation/tests/apply_rules.test.js
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const context = {};
context.globalThis = context;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../extension/apply_rules.js'), 'utf8'), context);
const { stepClear } = context.careeropsApplyRules;

test('a step with nothing left goes on', () => {
    assert.strictEqual(stepClear({ filled: 3, pending: 0, toConfirm: 0 }), true);
    assert.strictEqual(stepClear({ filled: 0, pending: 0 }), true);
});

test('an AI salary suggestion nobody confirmed stops the submit', () => {
    assert.strictEqual(stepClear({ filled: 3, pending: 0, toConfirm: 1 }), false);
});

test('an unanswered field stops it', () => {
    assert.strictEqual(stepClear({ filled: 3, pending: 1, toConfirm: 0 }), false);
});

test('a step that failed to fill stops it', () => {
    assert.strictEqual(stepClear(null), false);
    assert.strictEqual(stepClear(undefined), false);
});
