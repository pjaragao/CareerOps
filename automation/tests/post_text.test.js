// node --test automation/tests/post_text.test.js
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');
const vm = require('node:vm');

const context = {};
context.globalThis = context;
vm.runInNewContext(fs.readFileSync(path.join(__dirname, '../../extension/post_text.js'), 'utf8'), context);
const { cardText } = context.careeropsPostText;

const WHO = { name: 'Bruno Adam', headline: 'VDC | BIM coordinator | Open Source Developer' };
const HEAD = 'Feed post\n\nBruno Adam\n\n \n • 3rd+\n\nVDC | BIM coordinator | Open Source Developer\n\n1d\n\nFollow\n\n';
const POST = 'Contractors work with IFC every day. Versioning is missing.\n\nHowever, design changes are very difficult to track across all the weekly deliveries.\n\nThis article is the part 1 of a series.\n\nI am working on diff and git processes for IFC.\n\nThis work could not be done without my colleagues.';
const LINES = POST.split('\n').filter(Boolean);
const TITLE = "We exchange models weekly — IFC can't tell us what changed";

test('the author credit under a document card does not erase the post (text from the real card)', () => {
    const card = `${HEAD}${POST}\n… more\n\n${TITLE}\n\nBruno Adam\n\n42\n14\n2\n\u200b\n`;
    assert.strictEqual(cardText(card, WHO).body, [...LINES, TITLE].join('\n'));
});

test('"…" and "more" on lines of their own are the end of the text, not the header', () => {
    const card = `${HEAD}${LINES[0]}\n…\nmore\n\n${TITLE}\n\nBruno Adam\n\n42\n14\n2`;
    assert.strictEqual(cardText(card, WHO).body, [LINES[0], TITLE].join('\n'));
});

test('a "…" alone is the card menu', () => {
    const card = `Bruno Adam\n${WHO.headline}\n1d\n…\n${POST}`;
    assert.strictEqual(cardText(card, WHO).body, LINES.join('\n'));
});

test('the actor block goes when no time line closes the header', () => {
    const card = `Feed post\nBruno Adam\n${WHO.headline}\n1,234 followers\n${POST}`;
    assert.strictEqual(cardText(card, WHO).body, LINES.join('\n'));
});

test('social context above the author goes with the actor block', () => {
    const card = `Mats Romblad likes this\nBruno Adam\n${WHO.headline}\n${POST}`;
    assert.strictEqual(cardText(card, WHO).body, LINES.join('\n'));
});

test('the author named in the middle of the text keeps what is around it', () => {
    const card = `${HEAD}Thanks to\nBruno Adam\nfor the article on IFC`;
    assert.strictEqual(cardText(card, WHO).body, 'Thanks to\nBruno Adam\nfor the article on IFC');
});

test('reactions and comments are the tail, not the text', () => {
    const { body, tail } = cardText(`${HEAD}${POST}\n42 reactions\n3 comments\nMost relevant`, WHO);
    assert.strictEqual(body, LINES.join('\n'));
    assert.strictEqual(tail, '\n42 reactions\n3 comments\nMost relevant');
});

test('a carousel leaves neither its title nor its page count', () => {
    assert.strictEqual(cardText(`${HEAD}${LINES[0]}\nMy carousel\n8 pages`, WHO).body, LINES[0]);
});

test('a post with no known author still loses the header', () => {
    assert.strictEqual(cardText(`${HEAD}${POST}`, null).body, LINES.join('\n'));
});

test('a bulleted list stays in the text', () => {
    const body = 'Three lessons from this project:\n• Scope first\n• Then budget\n• Then people\nWhat would you add?';
    assert.strictEqual(cardText(`${HEAD}${body}`, WHO).body, body);
});

test('lines of the post that start like a header stay in the text', () => {
    for (const line of ['Following the launch, we hired ten people.', 'Follow the money on this one.', '3 d printing saved us a week.', '5 a 10 dias de obra a menos.', '2 years of work went into it.']) {
        const body = `We closed the round today.\n${line}\nMore details soon.`;
        assert.strictEqual(cardText(`${HEAD}${body}`, WHO).body, body);
    }
});

test('the header formats seen on LinkedIn still go', () => {
    for (const head of ['1d', '2d • Edited', '2yr', '2yr • Edited','1w •', '3 h ago', '1mo • Visible to anyone', '• 3rd+', '• 3rd+ • Follow', '• Follow', '• You', 'Follow', '+ Follow', 'Following', 'Seguindo', 'Bruno Adam • 2nd', 'Promoted', 'Feed post', 'Publicação no feed']) {
        assert.strictEqual(cardText(`Bruno Adam\n${WHO.headline}\n${head}\n${POST}`, WHO).body, LINES.join('\n'), head);
    }
});

test('a repost keeps nothing of the header above the time line (text from a real card)', () => {
    const who = { name: 'Márcia Doring PMP, PSM-I, VDC', headline: 'Engenharia Digital e Gestão de Projetos' };
    const card = `Feed post\nPaulo Jose Aragao Junior reposted this\n${who.name}\n• Following\n${who.headline}\nVisit my website\n2yr • Edited\n${POST}`;
    assert.strictEqual(cardText(card, who).body, LINES.join('\n'));
});

test('a repost with a comment keeps the comment and the post, without the second header (real card)', () => {
    const comment = 'What happened in 3 years?\nIt was incredible to look back.\nI am proud of these years.';
    const original = 'Denmark is looking for talent.\nHere are the reasons.';
    const card = `Feed post\nBruno Adam\n• 3rd+\n${WHO.headline}\n7mo\nFollow\n${comment}\n… more\nDorthe Kingo Vesterlund\n• 3rd+\nProject Manager / Special Consultant\n7mo • Edited\nFollow\n${original}\n42\n14`;
    assert.strictEqual(cardText(card, WHO).body, `${comment}\n${original}`);
});

test('a short comment on a repost is not taken for the header', () => {
    const card = `Feed post\nBruno Adam\n• 2nd\n${WHO.headline}\n1d\nMy own take: this changes how we bid.\nJoão Silva\n• 3rd+\nArchitect\n3d\nOriginal post text about bidding.`;
    assert.strictEqual(cardText(card, WHO).body, 'My own take: this changes how we bid.\nOriginal post text about bidding.');
});

test('a repost with no comment leaves only the post (real card)', () => {
    const who = { name: 'Paulo Jose Aragao Junior', headline: 'Consultor Independente' };
    const card = `Feed post\n${who.name}\n• You\n${who.headline}\n3yr\nGustavo Machado Costa\n• 1st\nEngenheiro na MPB Engenharia\n3yr\n${POST}\n42\n14`;
    assert.strictEqual(cardText(card, who).body, LINES.join('\n'));
});

test('a repost of a company post loses the company header', () => {
    const card = `Feed post\nBruno Adam\n• 2nd\n${WHO.headline}\n1d\nGood read.\nAutodesk University\n58,910 followers\n1w\nFollow\n${POST}`;
    assert.strictEqual(cardText(card, WHO).body, `Good read.\n${LINES.join('\n')}`);
});

test('a comment shown below the counters is not a second header (real card)', () => {
    const who = { name: 'Santiago Nestares', headline: 'Co-Founder at DualEntry' };
    const card = `Feed post\nRon Morris commented on this\n${who.name}\n• Following\n${who.headline}\nBook an appointment\n5d • Edited\n${POST}\n… more\n25\n12\nRon Morris\n• 1st\nAI Advisor to CFOs\n5d\nThis is consistent with what I see.`;
    assert.ok(cardText(card, who).body.startsWith(LINES.join('\n')));
});

test('what comes below the action bar is the tail, not the text (real card)', () => {
    const who = { name: 'Santiago Nestares', headline: 'Co-Founder at DualEntry' };
    const shown = 'Ron Morris\n• 1st\nAI Advisor to CFOs\n5d\nThis is consistent with what I see.';
    const card = `Feed post\nRon Morris commented on this\n${who.name}\n• Following\n${who.headline}\nBook an appointment\n5d • Edited\n${POST}\n… more\n25\n12\n\u200b\n\u200b\n${shown}`;
    const { body, tail } = cardText(card, who);
    assert.strictEqual(body, LINES.join('\n'));
    assert.strictEqual(tail, shown);
});

test('an action bar with no counters still ends the text', () => {
    const { body, tail } = cardText(`${HEAD}${POST}\n\u200b\n\u200b\n\u200b\nRon Morris\nNice post.`, WHO);
    assert.strictEqual(body, LINES.join('\n'));
    assert.strictEqual(tail, 'Ron Morris\nNice post.');
});

test('a line with only a number stays in the text', () => {
    const body = 'What changed in\n2024\nand what comes next.';
    assert.strictEqual(cardText(`${HEAD}${body}\n42\n14\n\u200b\n`, WHO).body, body);
});

test('the document viewer leaves nothing behind (real card)', () => {
    const viewer = 'My guide to BIM\n5 pages\nWant to view more? Unlock the full document\n1 / 5\n1\nUnlock full document';
    assert.strictEqual(cardText(`${HEAD}${LINES[0]}\n${viewer}\n12\n\u200b\n\u200b\n\u200b\n`, WHO).body, LINES[0]);
});

test('the document preview counter goes, the line above it stays (real card)', () => {
    const body = 'Rich-world interest bills have passed $2tn a year.\nMore in interest than on defence';
    assert.strictEqual(cardText(`${HEAD}${body}\nPreview 4 of 22 pages\n12\n\u200b\n`, WHO).body, body);
});

test('the text alone has nothing to strip', () => {
    assert.strictEqual(cardText(POST, WHO).body, LINES.join('\n'));
});
