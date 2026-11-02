// CareerOps — when an Auto Apply step may go on by itself. Separate from linkedin_assist.js so it can be tested alone.
(() => {
    // result of fillStep: `pending` fields are left for you, `toConfirm` hold an AI suggestion nobody confirmed
    const stepClear = (result) => !!result && !result.pending && !result.toConfirm;
    globalThis.careeropsApplyRules = { stepClear };
})();
