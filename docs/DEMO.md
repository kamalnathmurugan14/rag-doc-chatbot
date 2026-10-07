# 5-step demo script
1. **Index** – start backend + frontend, open Chat, click **Index** and watch the progress bar; run it again → nothing is re-embedded (incremental).
2. **Ask** – "How many days of annual leave do employees get?" – answer streams with `[1]` chips; click a chip to open the exact chunk with neighbouring text and page.
3. **Scope & follow-up** – tick the `hr/` folder in the explorer, ask "what about carry-over?" – the header shows the rewritten standalone query.
4. **Debug & honesty** – press **Debug**: retrieved chunks with scores, timings, final prompt. Ask something unrelated → *"I could not find this in your documents."* Open `injection_test.txt` questions to show the injection defence.
5. **Evaluate** – Evaluation page → run a sweep over chunk sizes 300/600 and top-k 3/5 → compare hit-rate and MRR; toggle LLM judge for answer scores.
