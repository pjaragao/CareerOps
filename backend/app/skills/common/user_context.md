{% set knowledge_file = 'knowledge/user_data.md' %}
{% try %}
    {% include knowledge_file %}
{% catch %}
    <!-- No additional user context available -->
{% endtry %}
