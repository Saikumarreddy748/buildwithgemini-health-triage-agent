# My agent: health-triage-agent
One-liner: A conversational health assistant that collects current symptoms, health conditions, and medical history to suggest potential conditions, recommend medical specialist domains, and provide first-aid / OTC medicine guidance for common mild ailments.

Tool coverage:
- Memory: User's medical history, current health conditions, allergies, and ongoing medications
- Tools:
  - `diagnose_symptoms`: Triage symptoms, suggest possible health conditions, and recommend appropriate doctor specialist domains (e.g. ENT, Pulmonologist, Dermatologist, General Practitioner)
  - `recommend_first_aid_and_otc`: Provide OTC medication and first-aid recommendations for common mild issues (cough, cold, general fever, minor kitchen cuts)
- Catalog/UI: Triage summary cards, specialist recommendations, and first-aid care tables (A2UI)
- Image gen: Visual diagrams for first-aid wound dressing or care instructions
- Sandbox: BMI or dosage calculations based on patient metrics

Recommended for every project: memory, storage, tools, image generation, A2UI
Agent-specific / stretch: code sandbox for dosage / health metric calculations
