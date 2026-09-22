# Oncology prompt registry

Markdown files under this directory are the only active runtime prompt source. Each file has `prompt_id`, `version`, and `purpose` metadata followed by its template body. Python requests prompts by stable ID through `backend/app/langchain/prompt_store.py`; clinical prompt prose must not be embedded in pipeline or route code.

The former Word prompt library is retained in `legacy/` for reference only and is never loaded at runtime.

All specific patient-report questions use the single `FOCUSED_CONTRACT`, regardless of whether the question concerns pathology, biomarkers, lymph nodes, imaging, staging evidence, treatment, medications, or another documented detail. Retired keyword-specific prompts are preserved as `.txt` files under `legacy/retired_question_prompts/`; the Markdown registry does not load them.

Safety-critical controls remain in Python, including response/schema validation, citation-ID rejection, patient identity boundaries, emergency routing, file/access validation, and formal-stage authorization. Prompt wording reinforces those controls but cannot disable them.
