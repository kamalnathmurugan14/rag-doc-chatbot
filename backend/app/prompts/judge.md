# Task
You are grading an answer from a question-answering system.

# Inputs
Question: {{ question }}
Reference answer: {{ expected }}
Retrieved context:
{{ context }}

System answer: {{ answer }}

# Grading
- "correctness": 0 = wrong or missing, 1 = partly correct, 2 = fully correct compared with the reference answer.
- "faithfulness": 0 = contains claims not supported by the retrieved context, 1 = mostly supported, 2 = fully supported by the context.

# Output
Return ONLY JSON like {"correctness": 2, "faithfulness": 2}
