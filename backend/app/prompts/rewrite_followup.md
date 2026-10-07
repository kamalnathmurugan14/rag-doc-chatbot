# Task
Rewrite the user's latest question into a single, standalone question that can be understood without the conversation. Resolve pronouns and references ("it", "the second one", "what about 2023?") using the history. Do not answer the question.

# Rules
- Keep the original language and all names, numbers and dates.
- If the question is already standalone, return it unchanged.
- Output ONLY the rewritten question, nothing else.

# Conversation
{% for m in history %}{{ m.role }}: {{ m.content }}
{% endfor %}
# Latest question
{{ question }}

# Standalone question
