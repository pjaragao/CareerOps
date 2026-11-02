// CareerOps — a post's text out of the text of its whole card. Separate from linkedin_assist.js so it can be tested alone.
(() => {
    const CUT = /\n(add a comment|adicionar um coment[aá]rio|most relevant|mais relevantes|\d[\d.,]*\s*(reactions?|rea[cç][oõ]es|comments?|coment[aá]rios)\b|like\ncomment|gostei\ncomentar)/i;
    const SOCIAL = /\b(likes?|loves?|celebrates?|supports?|finds?|commented|reposted|follows?|curtiu|gostou|comentou|republicou|celebrou|apoiou|amou|achou)\b/i;
    const AGE = String.raw`\d+\s*(s|m|min|h|d|w|sem|mo|yrs?|y|a)\b`;
    const DEGREE = String.raw`(1st|2nd|3rd\+?|1º|2º|3º\+?)`;
    const FOLLOW = '(following|seguindo|follow|seguir)';
    // whole lines only: a line of the post can start with a bullet, "Following…" or "3 d printing…"
    const HEADER = new RegExp(String.raw`^(${AGE}\s*(ago|atrás)?\s*(•.*)?|\+?\s*${FOLLOW}|…|\.\.\.|•\s*(${DEGREE}|${FOLLOW}|you|voc[eê]|author|autor|edited|editado|promoted|promovido|${AGE})(\s*•.*)?|.*•\s*${DEGREE}|promoted|promovido|edited|editado|feed post|publicação no feed)$`, 'i');
    const TIME = new RegExp(String.raw`^(•\s*)?${AGE}\s*(ago|atrás)?\s*(•.*)?$`, 'i');
    const BADGE = new RegExp(String.raw`^(•\s*(${DEGREE}|${FOLLOW}|you|voc[eê])(\s*•.*)?|.*•\s*${DEGREE}|[\d.,]+\s*(followers|seguidores))$`, 'i');
    const COUNTER = /^[\d.,]+$/;
    // the action bar in the card's text: its counters, if any, then a line of zero-width characters. Below it, comments.
    const BAR = /\n([\d.,]+[ \t]*\n\s*)*[\u200b-\u200d\ufeff]+([ \t]*\n\s*[\u200b-\u200d\ufeff]+)*[ \t]*(?=\n|$)/;
    const LEFTOVER = /^([\d\s/.,]+|\d+\s*(pages?|páginas?)|unlock full document|want to view more\b.*)$/i;

    // A repost has a second header, the original author's (name, badge, headline, time), between the text of whoever
    // reposted and the post. The counters end the search: below them, the same lines are someone's comment.
    function secondHeader(lines, from) {
        for (let t = from; t < lines.length && !COUNTER.test(lines[t]); t++) {
            if (!TIME.test(lines[t])) continue;
            for (let b = Math.max(from, t - 4); b < t; b++) {
                if (!BADGE.test(lines[b])) continue;
                const start = /^[•\d]/.test(lines[b]) ? b - 1 : b;   // "Name • 2nd" has the name on the same line
                if (start < from) continue;
                let end = t;
                while (end + 1 < lines.length && HEADER.test(lines[end + 1])) end++;
                return { start, end };
            }
        }
        return null;
    }

    // who = { name, headline } of the post's author, or null. Returns the text and what comes after it (reactions, comments).
    function cardText(card, who) {
        let text = card;
        let tail = '';
        const bar = text.match(BAR);
        if (bar) { tail = text.slice(bar.index + bar[0].length).trim(); text = text.slice(0, bar.index); }
        const m = text.match(CUT);
        if (m) { tail = text.slice(m.index); text = text.slice(0, m.index); }
        // a "…" alone is the card's menu, but followed by "more" it is the end of a cut-off text: not the header
        text = text.replace(/\n\s*(…|\.\.\.)\s*\n\s*(see more|ver mais|more|mais)\s*(?=\n|$)/gi, '\n');
        let lines = text.split('\n').map((l) => l.replace(/[\u200b-\u200d\ufeff]/g, '').trim()).filter((l) => l && !/^(show translation|ver tradução|traduzir|see translation|preview \d+ of \d+ pages?)$/i.test(l));
        // out first: the search below takes the last header line it sees, and that would erase the reposter's text
        const repost = secondHeader(lines, lines.slice(0, 8).findIndex((l) => TIME.test(l)) + 1 || lines.length);
        if (repost) lines = [...lines.slice(0, repost.start), ...lines.slice(repost.end + 1)];
        let last = -1;
        lines.slice(0, 8).forEach((l, k) => { if (HEADER.test(l)) last = k; });
        if (last >= 0) lines = lines.slice(last + 1);
        lines = lines.map((l) => l.replace(/\s*…\s*(see more|ver mais|more|mais)$/i, '')).filter((l) => l && !HEADER.test(l));
        // the actor block (name, headline, followers) goes before the text: below the text, the name is the credit of a
        // document or article card, and what comes before it is the post
        if (who) {
            const i = lines.slice(0, 8).indexOf(who.name);
            if (i >= 0 && lines.slice(0, i).every((l) => l.length < 160 && SOCIAL.test(l))) {
                lines = lines.slice(i + 1).filter((l, k) => !(k < 3 && (l === who.headline || /^[\d.,]+\s*(followers|seguidores)$/i.test(l))));
            }
        }
        // carousel/counter leftovers at the end, then that credit (the card's title stays: it says what the post is about)
        while (lines.length && LEFTOVER.test(lines[lines.length - 1])) {
            if (/pages?|páginas?/i.test(lines.pop()) && lines.length) lines.pop();   // "Title / 8 pages": drop the title too
        }
        if (who && lines[lines.length - 1] === who.name) lines.pop();
        return { body: lines.join('\n'), tail };
    }

    globalThis.careeropsPostText = { cardText, SOCIAL };
})();
