const assert = require('node:assert/strict');
const { readFileSync } = require('node:fs');
const { runInNewContext } = require('node:vm');
const { test } = require('node:test');

test('logout bypasses validation; contributions still require valid fields and an empty honeypot', () => {
    let submit;
    let valid = false;
    let website = '';
    const form = {
        addEventListener: (_, handler) => { submit = handler; },
        checkValidity: () => valid,
        reportValidity: () => {},
    };
    const document = {
        querySelectorAll: () => [],
        querySelector: () => null,
        getElementById: (id) => {
            if (id === 'crosswordForm') return form;
            if (id === 'website') return { value: website };
            return null;
        },
    };
    runInNewContext(readFileSync(`${__dirname}/static/js/app.js`, 'utf8'), { document });
    for (const [formNoValidate, fieldsValid, honeypot, expectedBlocked] of [
        [true, false, '', false],
        [true, false, 'autofilled', false],
        [false, false, '', true],
        [false, true, '', false],
        [false, true, 'spam', true],
    ]) {
        valid = fieldsValid;
        website = honeypot;
        let blocked = false;
        submit({ submitter: { formNoValidate }, preventDefault: () => { blocked = true; } });
        assert.equal(blocked, expectedBlocked);
    }
});
