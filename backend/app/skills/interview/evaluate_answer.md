Evaluate the candidate's answer to the following interview question.

{% include 'common/critical_rules.md' %}
{% include 'common/output_format.md' %}

Question: {{ question }}
Answer: {{ answer }}

Return JSON:
{
    "score": 0-10,
    "feedback": "strengths and weaknesses",
    "improved_answer": "a better way to answer the same question",
    "tips": ["tip1", "tip2"]
}
