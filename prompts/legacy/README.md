# Legacy oncology prompts

This directory is reference-only and is not loaded by the runtime prompt registry.

- `oncology_ai_prompts.docx` is the editable legacy Word prompt library.
- `retired_question_prompts/` preserves the former keyword-specific prompt files as `.txt` files.

The active system uses one `FOCUSED_CONTRACT` for every specific uploaded patient-report question. The retired files must not be renamed to `.md` inside `prompts/`, because the recursive prompt loader would treat them as active runtime prompts.
