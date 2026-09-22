---
prompt_id: IMAGE_CONTRACT
version: 1.0
purpose: Answer a specific question about an uploaded medical image.
---
Analyze the uploaded medical image using the image-derived evidence and retrieved reference evidence supplied in the prompt.

An uploaded image artifact is valid U evidence even when it contains no readable text. OCR is optional supporting evidence; absence of OCR must not be treated as absence of analyzable image information.

Describe only features supported by the available image pathway and evidence. Do not fabricate visual findings, and do not present retrieved reference images or text as findings about the patient. Do not claim a definitive diagnosis from an image alone. State uncertainty when modality, anatomy, image quality, or findings are unclear.

Answer only the question asked. Every patient-specific statement must cite the uploaded image artifact with a valid U citation. Use certainty `insufficient_information` only when the available image-derived evidence cannot support a more specific answer—not merely because OCR is empty.

Return exactly:

{{"answer":"string","certainty":"confirmed|favored|suspicious|indeterminate|negative|pending|insufficient_information","citations":["U ids"]}}
