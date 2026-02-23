import re

with open('scraper.py', 'r', encoding='utf-8') as f:
    content = f.read()

# Find the hiring_elements = page.evaluate block
# It starts with "hiring_elements = page.evaluate" and ends with the matching """) or []"
start_marker = '                hiring_elements = page.evaluate("""() =>'
end_marker = '                }""") or []'

start_idx = content.find(start_marker)
end_idx = content.find(end_marker, start_idx)

if start_idx == -1:
    print("ERROR: Could not find start marker")
    exit(1)
if end_idx == -1:
    print("ERROR: Could not find end marker")
    exit(1)

end_idx += len(end_marker)

print(f"Found block at chars {start_idx}-{end_idx}")
print(f"Block length: {end_idx - start_idx}")

new_block = '''                hiring_elements = page.evaluate(r\"\"\"() => {
                    const keywords = ['Meet the hiring team', 'Conhe\u00e7a a equipe de contrata\u00e7\u00e3o'];
                    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
                    while (walker.nextNode()) {
                        const txt = walker.currentNode.textContent.trim();
                        if (keywords.includes(txt)) {
                            let el = walker.currentNode.parentElement;
                            for (let i = 0; i < 3; i++) {
                                if (el.parentElement) el = el.parentElement;
                            }
                            const links = Array.from(el.querySelectorAll('a[href*="/in/"]'));
                            const results = [];
                            const noise = ['View profile', 'Ver perfil', 'Message', 'Mensagem',
                                           'People you can reach out to', 'Fale com',
                                           'Meet the hiring team', 'Conhe\u00e7a a equipe'];
                            
                            for (const a of links) {
                                const url = a.href.split('?')[0];
                                if (!url.includes('/in/')) continue;
                                
                                let name = a.innerText.trim().split('\\n')[0].trim();
                                noise.forEach(n => { name = name.replace(n, ''); });
                                name = name.trim();
                                if (!name || name.length < 2) continue;
                                if (noise.some(n => name.toLowerCase().includes(n.toLowerCase()))) continue;
                                
                                let title = '';
                                let card = a.closest('div[class]');
                                if (card && card.parentElement && card.parentElement !== el) {
                                    card = card.parentElement;
                                }
                                if (card) {
                                    const cardLines = card.innerText.split('\\n')
                                        .map(l => l.trim()).filter(l => l.length > 0);
                                    const nameIdx = cardLines.findIndex(l => l.includes(name));
                                    if (nameIdx >= 0) {
                                        for (let i = nameIdx + 1; i < cardLines.length; i++) {
                                            const line = cardLines[i];
                                            if (noise.some(n => line.includes(n))) continue;
                                            if (line === name) continue;
                                            // Skip connection degree indicators
                                            if (/^\\u2022\\s*\\d+(st|nd|rd|th)/i.test(line)) continue;
                                            if (/^\\d+(st|nd|rd|th)$/i.test(line)) continue;
                                            // If line starts with bullet, strip it for the title
                                            if (/^\\u2022\\s/.test(line)) { title = line.replace(/^\\u2022\\s*/, ''); break; }
                                            title = line;
                                            break;
                                        }
                                    }
                                }
                                results.push({ name, title, url });
                            }
                            return results;
                        }
                    }
                    return [];
                }\"\"\") or []'''

content = content[:start_idx] + new_block + content[end_idx:]

with open('scraper.py', 'w', encoding='utf-8') as f:
    f.write(content)

print("Done! Block replaced successfully.")
