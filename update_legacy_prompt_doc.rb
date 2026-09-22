require 'cgi'

path = File.join(__dir__, '.legacy_docx_work', 'word', 'document.xml')
xml = File.read(path)
old_text = 'Return {{answer:string, certainty:confirmed|favored|suspicious|indeterminate|negative|pending|insufficient_information, citations:[U ids]}}. Answer only the asked report question.'
paragraphs = [
  "Answer the user's specific question about the uploaded patient document.",
  'Determine what clinical information the user is asking for. This may include diagnosis, pathology, tumor location, tumor size, lymph nodes, metastasis, staging, biomarkers, molecular findings, imaging findings, treatment, pending tests, negative findings, or any other information documented in the uploaded evidence.',
  'Answer only the question asked. Do not summarize the complete report unless the user requests a complete report explanation.',
  'Use only U evidence for patient-specific facts. Never use external R evidence to create a patient-specific fact.',
  'If the requested information is not documented in the uploaded evidence, clearly state that it is not documented and use certainty insufficient_information.',
  'Preserve the exact clinical meaning of the evidence, including confirmed, negative, suspicious, favored, indeterminate, and pending findings. Do not infer missing information. Do not convert suspicious or uncertain findings into confirmed findings.',
  'Do not assign a final cancer stage unless the final stage is explicitly documented in U evidence.',
  'Every patient-specific claim must be supported by valid U citations.',
  'Return exactly: {{"answer":"string","certainty":"confirmed|favored|suspicious|indeterminate|negative|pending|insufficient_information","citations":["U ids"]}}',
]
replacement = paragraphs.map do |text|
  %(<w:p><w:pPr><w:pStyle w:val="Normal" /></w:pPr><w:r><w:t>#{CGI.escapeHTML(text)}</w:t></w:r></w:p>)
end.join
old_paragraph = %(<w:p><w:pPr><w:pStyle w:val="Normal" /></w:pPr><w:r><w:t>#{CGI.escapeHTML(old_text)}</w:t></w:r></w:p>)
abort 'Focused contract paragraph was not found' unless xml.include?(old_paragraph)
xml.sub!(old_paragraph, replacement)
File.write(path, xml)
