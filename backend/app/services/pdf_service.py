import requests
import re
import os
from app.core.config import settings

class PDFService:
    @staticmethod
    def _markdown_to_html(md: str) -> str:
        """Simple markdown to HTML converter for professional resumes."""
        # Remove markdown code fences if present
        md = re.sub(r'^```(?:markdown)?\n?', '', md, flags=re.MULTILINE)
        md = re.sub(r'```$', '', md, flags=re.MULTILINE)
        md = md.strip()

        lines = md.split('\n')
        html_lines = []
        in_list = False

        def inline(text: str) -> str:
            text = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
            text = re.sub(r'\*(.+?)\*', r'<em>\1</em>', text)
            text = re.sub(r'\[(.+?)\]\((.+?)\)', r'<a href="\2">\1</a>', text)
            return text

        for line in lines:
            stripped = line.strip()
            if not stripped:
                if in_list:
                    html_lines.append('</ul>')
                    in_list = False
                continue

            if stripped in ['---', '***', '___']:
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append('<hr>')
                continue

            if stripped.startswith('# '):
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<h1>{inline(stripped[2:])}</h1>')
            elif stripped.startswith('## '):
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<h2>{inline(stripped[3:])}</h2>')
            elif stripped.startswith('### '):
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<h3>{inline(stripped[4:])}</h3>')
            elif re.match(r'^[-*+] ', stripped):
                if not in_list:
                    html_lines.append('<ul>')
                    in_list = True
                html_lines.append(f'<li>{inline(stripped[2:])}</li>')
            else:
                if in_list: html_lines.append('</ul>'); in_list = False
                html_lines.append(f'<p>{inline(stripped)}</p>')

        if in_list: html_lines.append('</ul>')
        return '\n'.join(html_lines)

    @staticmethod
    def generate_pdf(markdown_content: str, filename: str) -> bytes:
        html_content = PDFService._markdown_to_html(markdown_content)
        
        styled_html = f'''<!DOCTYPE html>
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
    background-color: #f2f2f2;
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
  p {{ margin: 4px 0; text-align: justify; }}
  ul {{ margin: 4px 0 4px 18px; padding: 0; }}
  li {{ margin: 2px 0; padding-left: 2px; }}
  hr {{ border: none; border-top: 1px solid #ccc; margin: 10px 0; }}
  strong {{ font-weight: 600; }}
  a {{ color: #333; text-decoration: none; }}
  @media print {{ body {{ padding: 0.4in 0.5in; }} h2 {{ break-after: avoid; }} }}
</style>
</head>
<body>
{html_content}
</body>
</html>'''
        
        url = f"{settings.GOTENBERG_URL}/forms/chromium/convert/html"
        files = {
            "index.html": ("index.html", styled_html.encode("utf-8"), "text/html"),
        }
        
        try:
            response = requests.post(url, files=files, timeout=30)
            if response.status_code == 200:
                return response.content
            else:
                raise Exception(f"Gotenberg error: {response.status_code}")
        except Exception as e:
            print(f"Error calling Gotenberg: {e}")
            raise
