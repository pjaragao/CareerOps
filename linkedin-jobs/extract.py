import re

with open('web.py', 'r', encoding='utf-8') as f:
    web = f.read()

chat_html = web.split('CHAT_TEMPLATE = """\n')[1].split('"""')[0]
index_html = web.split('HTML_TEMPLATE = """\n')[1].split('"""')[0]

with open('templates/chat.html', 'w', encoding='utf-8') as f:
    f.write(chat_html)

css = re.search(r'<style>(.*)</style>', index_html, re.DOTALL).group(1)
js = re.search(r'<script>(.*)</script>', index_html, re.DOTALL).group(1)

with open('static/css/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

with open('static/js/app.js', 'w', encoding='utf-8') as f:
    f.write(js)

index_html = re.sub(r'<style>.*</style>', '<link rel=\"stylesheet\" href=\"{{ url_for(\'static\', filename=\'css/style.css\') }}\">', index_html, flags=re.DOTALL)
index_html = re.sub(r'<script>.*</script>', '<script src=\"{{ url_for(\'static\', filename=\'js/app.js\') }}\"></script>', index_html, flags=re.DOTALL)

with open('templates/index.html', 'w', encoding='utf-8') as f:
    f.write(index_html)
