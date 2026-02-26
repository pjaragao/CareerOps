import re

with open('web.py', 'r', encoding='utf-8') as f:
    web = f.read()

web = web.replace('from flask import Flask, render_template_string, jsonify, request, send_from_directory', 'from flask import Flask, render_template, jsonify, request, send_from_directory')

web = re.sub(r'CHAT_TEMPLATE = \"\"\"(.*?)\"\"\"', '# CHAT_TEMPLATE moved to templates/chat.html', web, flags=re.DOTALL)
web = re.sub(r'HTML_TEMPLATE = \"\"\"(.*?)\"\"\"', '# HTML_TEMPLATE moved to templates/index.html', web, flags=re.DOTALL)

web = web.replace('return render_template_string(HTML_TEMPLATE)', 'return render_template(\"index.html\")')

old_chat = '''    html = CHAT_TEMPLATE.replace(\"{{ job_id }}\", str(job[\"id\"]))\n    html = html.replace(\"{{ job_title }}\", job.get(\"job_title\", \"Unknown\"))\n    html = html.replace(\"{{ company }}\", job.get(\"company\", \"Unknown\"))\n    return render_template_string(html)'''

new_chat = '''    return render_template(\n        \"chat.html\",\n        job_id=job[\"id\"],\n        job_title=job.get(\"job_title\", \"Unknown\"),\n        company=job.get(\"company\", \"Unknown\")\n    )'''

web = web.replace(old_chat, new_chat)

with open('web.py', 'w', encoding='utf-8') as f:
    f.write(web)
