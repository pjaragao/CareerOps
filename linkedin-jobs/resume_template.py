"""
Resume HTML template — professional styling for PDF output via Gotenberg.
"""


def markdown_to_html(md: str) -> str:
    """
    Convert simple markdown to HTML.
    Handles: h1-h3, bold, italic, lists, horizontal rules, paragraphs.
    """
    import re

    # Remove markdown code fences if present
    md = re.sub(r'^```(?:markdown)?\n?', '', md, flags=re.MULTILINE)
    md = re.sub(r'```$', '', md, flags=re.MULTILINE)
    md = md.strip()

    lines = md.split('\n')
    html_lines = []
    in_list = False

    for line in lines:
        stripped = line.strip()

        # Horizontal rule
        if stripped == '---' or stripped == '***' or stripped == '___':
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append('<hr>')
            continue

        # Headers
        if stripped.startswith('### '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h3>{_inline(stripped[4:])}</h3>')
            continue
        if stripped.startswith('## '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h2>{_inline(stripped[3:])}</h2>')
            continue
        if stripped.startswith('# '):
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            html_lines.append(f'<h1>{_inline(stripped[2:])}</h1>')
            continue

        # List items
        if re.match(r'^[-*+] ', stripped):
            if not in_list:
                html_lines.append('<ul>')
                in_list = True
            html_lines.append(f'<li>{_inline(stripped[2:])}</li>')
            continue

        # Empty line
        if not stripped:
            if in_list:
                html_lines.append('</ul>')
                in_list = False
            continue

        # Regular paragraph
        if in_list:
            html_lines.append('</ul>')
            in_list = False
        html_lines.append(f'<p>{_inline(stripped)}</p>')

    if in_list:
        html_lines.append('</ul>')

    return '\n'.join(html_lines)


def _inline(text: str) -> str:
    """Process inline markdown: bold, italic, links."""
    import re
    # Bold
    text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
    # Italic
    text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
    # Links
    text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
    return text


def wrap_in_template(html_content: str) -> str:
    """Wrap HTML content in a full HTML document with professional resume styling."""
    return f'''<!DOCTYPE html>
<html>
<head>
<meta charset="UTF-8">
<style>
  @import url("https://fonts.googleapis.com/css2?family=Open+Sans:wght@400;600;700&display=swap");
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  body {{
    font-family: "Open Sans", Arial, sans-serif;
    font-size: 10.5pt;
    line-height: 1.4;
    color: #333;
    max-width: 8.5in;
    margin: 0 auto;
    padding: 0.5in 0.6in;
  }}
  h1 {{
    font-size: 20pt;
    font-weight: 700;
    text-align: center;
    color: #1a1a1a;
    margin-bottom: 4px;
  }}
  h2 {{
    font-size: 11pt;
    font-weight: 700;
    text-transform: uppercase;
    letter-spacing: 0.5px;
    color: #1a1a1a;
    background-color: #e8e8e8;
    padding: 5px 8px;
    margin: 14px 0 8px 0;
    border-left: 3px solid #555;
  }}
  h3 {{
    font-size: 10.5pt;
    font-weight: 600;
    color: #222;
    margin: 8px 0 4px 0;
  }}
  p {{
    margin: 4px 0;
    text-align: justify;
  }}
  ul {{
    margin: 4px 0 4px 18px;
    padding: 0;
  }}
  li {{
    margin: 2px 0;
    padding-left: 2px;
  }}
  hr {{
    border: none;
    border-top: 1px solid #ccc;
    margin: 10px 0;
  }}
  strong {{
    font-weight: 600;
  }}
  a {{
    color: #333;
    text-decoration: none;
  }}
  @media print {{
    body {{ padding: 0.4in 0.5in; }}
    h2 {{ break-after: avoid; }}
  }}
</style>
</head>
<body>
{html_content}
</body>
</html>'''
