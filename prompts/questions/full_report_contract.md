---
prompt_id: FULL_REPORT_CONTRACT
version: 1.0
purpose: Define the canonical complete report response contract.
---
Return exactly this canonical JSON shape and no other fields: {{"headline":string,"plain_language_summary":string,"case_complexity":{{"level":"low|moderate|high|insufficient_information","reason":string,"citations":["U1"]}},"evidence_support":{{"level":"Moderate|Limited|Insufficient","explanation":string}},"key_findings":[{{"title":string,"result":string,"meaning":string,"certainty":"confirmed|favored|suspicious|indeterminate|negative|pending|insufficient_information","importance":"critical|high|supporting","citations":["U1"]}}],"staging":{{"documented_components":[string],"unresolved_components":[string],"final_stage":string|null,"can_assign_final_stage":boolean,"explanation":string,"citations":["U1"]}},"limitations":[string],"medical_terms":[{{"term":string,"definition":string}}],"safety_notice":string}}. Do not duplicate findings. Never calculate stage. A final stage may appear only if directly documented in U evidence or application-authorized.
