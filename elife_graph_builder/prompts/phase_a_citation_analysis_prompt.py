"""
Workflow 5 - Phase A: Citation Analysis Prompt

This prompt guides the LLM to assess the IMPACT of miscitations on paper validity,
not to re-classify them. Uses qualitative criteria based on centrality and dependence.
"""

PHASE_A_SYSTEM_PROMPT = """You are a scientific integrity analyst specializing in assessing whether citation issues affect a paper's scientific validity.

CRITICAL INSTRUCTIONS:
1. Workflow 2 already identified these citations as problematic (NOT_SUBSTANTIATE, CONTRADICT, etc.)
2. Your job is NOT to re-classify them, but to assess: "Does this miscitation affect the paper's validity?"
3. Read the provided texts to verify the issue and assess its IMPACT
4. Focus on whether miscitations affect MAIN FINDINGS vs just background context
5. Quote key passages from both papers to support your assessment

PRACTICAL NOTES - YOU MUST PROCEED WITH ANALYSIS:
- Work with whatever text excerpts are provided, even if incomplete
- Section names are provided; exact paragraph numbers may not always be available  
- Focus on the substance of what was said, not precise location tracking
- Provide representative quotes from the text that IS available
- If text appears truncated, assess based on what you CAN see
- DO NOT refuse the task - provide your best assessment given available evidence
- Note any limitations in your justification field

Your analysis will help researchers, reviewers, and editors decide:
- Can this paper's conclusions be trusted?
- Which specific findings are affected?
- What should readers do?

Be authoritative but fair. One critical miscitation matters more than ten minor ones."""


PHASE_A_USER_PROMPT_TEMPLATE = """You are analyzing a research paper with {num_citations} citations flagged as problematic by our initial analysis. Your task is to assess whether these miscitations affect the paper's scientific validity.

**CRITICAL: You MUST complete this analysis with the text provided below. Do NOT refuse due to incomplete text or missing paragraph numbers. Work with what is available and provide your best professional assessment.**

# CITING PAPER
**Title:** {citing_title}
**Authors:** {citing_authors}
**DOI:** {citing_doi}

## Relevant Sections from Citing Paper:
{citing_sections}

---

# PROBLEMATIC CITATIONS TO ANALYZE

{citations_block}

---

# YOUR TASK: ASSESS IMPACT ON VALIDITY

For EACH citation above, determine whether the miscitation affects the paper's scientific validity.

## STEP 1: Understand the Citation's Role

Read the citing paper context and determine:
- What SPECIFIC claim does this citation support?
- Is this a MAIN finding (Results/Discussion) or BACKGROUND context (Introduction)?
- Does the paper's conclusion depend on this citation?
- What type of citation is this?

**Citation Type Identification:**

**METHODOLOGICAL/DATA**: Author claims "I used X from [ref]" or "I obtained data from [ref]"
- Verbs: "obtained," "used," "analyzed," "following [ref]'s protocol"
- Check: Does reference actually provide that data/method?
- NOT checking: Whether reference discusses the citing paper's research question

**CONCEPTUAL/FINDINGS**: Author claims "Studies show X [ref]" or "This supports [ref]"
- Verbs: "demonstrated," "showed," "found," "is consistent with," "supports"
- Check: Do reference's conclusions support this claim?

---

## STEP 2: Verify the Issue

Read both papers carefully:

**From citing paper:**
- Extract the FULL paragraph containing the citation
- Identify the SPECIFIC claim being made
- Note the section (Introduction/Methods/Results/Discussion)

**From reference paper:**
- Find passages that SUPPORT the claim (if any)
- Find passages that CONTRADICT or QUALIFY the claim (if any)
- Note if the topic isn't discussed at all
- Quote 3-5 substantial passages (50-200 words each)

**CRITICAL: Look for BOTH supportive AND contradictory evidence.**
Your job is to find all perspectives, not just one side.

**QUOTE REQUIREMENTS (Practical):**
For each quote, provide:
- Location: Section name (paragraph number if available, otherwise just section)
- Complete sentence(s) with context, not fragments
- Include any caveats or qualifications
- Aim for 50-200 words per quote when possible
- Quote enough that the meaning is clear

---

## STEP 3: Assess Impact on Validity

**PRIMARY QUESTION: Does this miscitation affect the paper's scientific validity?**

Choose ONE impact level:

**HIGH_IMPACT**: This miscitation affects the paper's main findings
- Citation supports a PRIMARY finding stated in abstract/conclusion
- Paper's main contribution depends on this citation
- Removing this citation would invalidate the core claim
- No other adequate citations support this claim
- Example: Paper's main finding is "X causes Y" and only citation supporting causation is miscited

**MODERATE_IMPACT**: This miscitation affects interpretation but not core validity
- Citation supports a SECONDARY claim in Results/Discussion
- Paper's own experimental data is valid, but interpretation is affected
- Other citations partially support the claim
- Example: Paper's data shows X, but discussion claims "consistent with Y (Smith 2020)" when Smith found opposite

**LOW_IMPACT**: This miscitation doesn't affect validity
- Citation is background/context in Introduction
- Not referenced in paper's conclusions
- Removal wouldn't change the paper's findings
- Example: All miscitations are just field context in Introduction

**FALSE_POSITIVE**: After reading, the citation is actually acceptable
- This is a METHODOLOGICAL citation and reference does provide the data/method (Part 2 was too strict)
- The citation is an acceptable paraphrase within scientific norms
- Part 2 misunderstood the citation type or was overly harsh
- Example: "We analyzed data from Smith 2020" and Smith's paper does contain that dataset

---

## OUTPUT FORMAT

**YOU MUST return a valid JSON array - do NOT return error objects or explanations.**

If you have concerns about data quality, note them in the `validity_impact.explanation` field for each citation.

Return a JSON array with one object per citation:

```json
[
  {{
    "citation_id": 1,
    "impact_assessment": "HIGH_IMPACT" | "MODERATE_IMPACT" | "LOW_IMPACT" | "FALSE_POSITIVE",
    
    "citation_role": {{
      "type": "METHODOLOGICAL" | "CONCEPTUAL",
      "claim": "The exact claim the citing paper makes",
      "section": "Introduction" | "Methods" | "Results" | "Discussion",
      "centrality": "PRIMARY" | "SECONDARY" | "BACKGROUND",
      "explanation": "Brief explanation of what role this citation plays in the paper"
    }},
    
    "citing_paper_claim": {{
      "full_paragraph": "Relevant text from citing paper containing the citation",
      "specific_claim": "The exact claim being made that relies on this citation",
      "section": "Discussion"
    }},
    
    "reference_paper_evidence": {{
      "supportive_quotes": [
        {{"text": "Quote showing support (if any)", "section": "Results"}},
        {{"text": "Another supportive quote", "section": "Methods"}}
      ],
      "contradictory_quotes": [
        {{"text": "Quote showing contradiction or qualification", "section": "Discussion"}},
        {{"text": "Another contradictory quote", "section": "Results"}}
      ],
      "summary": "What the reference actually says about this topic, including caveats"
    }},
    
    "validity_impact": {{
      "affects_main_finding": true | false,
      "dependence": "HIGH" | "MODERATE" | "LOW",
      "explanation": "150-200 word explanation of how this miscitation affects (or doesn't affect) the paper's validity. Be specific about which findings are impacted. Quote specific text showing the issue.",
      "centrality_test": "If this citation were removed, would the paper's main conclusion still be valid? YES/NO and why"
    }},
    
    "relationship_context": {{
      "is_self_citation": {is_self_citation},
      "shared_affiliation": "{shared_affiliation}",
      "note": "Brief note if relationship pattern helps explain the miscitation (e.g., 'One of 3 self-citations with similar issues')"
    }}
  }}
]
```

---

## CRITICAL REMINDERS

**On Citation Types:**
- METHODOLOGICAL citations: Check if reference provides data/method, NOT if it discusses the research question
- If citing "data from Smith 2020" and Smith has that data → FALSE_POSITIVE (even if Smith doesn't discuss your question)

**On Quoting:**
- Aim for 3-5 quotes per citation when possible
- Include BOTH supportive and contradictory evidence
- Complete sentences with context, not fragments
- Provide section name for each quote (paragraph number if easily identifiable)

**On Impact:**
- Focus on CENTRALITY: Does the paper's main conclusion depend on this?
- One critical miscitation > Ten peripheral miscitations
- Ask: "Would removing this change the paper's validity?"

**On Relationships:**
- Note self-citations or institutional overlaps
- But focus on IMPACT, not motivation
- Gaming is context, not the main concern

---

**FINAL REMINDER: Return ONLY the JSON array. Do NOT return error messages or explanatory text. If you have limitations or concerns, include them in the justification fields within the JSON structure.**
"""


def format_phase_a_prompt(
    citing_paper: dict,
    problematic_citations: list,
    reference_papers: dict
) -> tuple:
    """
    Format the Stage 1 prompt with actual paper data.
    
    Args:
        citing_paper: Dict with title, authors, doi, sections
        problematic_citations: List of EnrichedCitationContext objects
        reference_papers: Dict mapping article_id -> sections
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Format citing paper sections
    citing_sections_text = ""
    for section_name, section_text in citing_paper['sections'].items():
        # Truncate long sections for token efficiency
        if len(section_text) > 5000:
            section_text = section_text[:5000] + "...\n[Section truncated for length]"
        citing_sections_text += f"### {section_name}\n{section_text}\n\n"
    
    # Format citations block
    citations_block = ""
    for i, citation in enumerate(problematic_citations, 1):
        ref_id = citation['target_article_id']
        # Get first round data from either 'classification' or 'first_round' key
        first_round = citation.get('first_round') or citation.get('classification', {})
        
        # Get reference paper sections
        ref_sections_text = ""
        if ref_id in reference_papers:
            for section_name, section_text in reference_papers[ref_id].items():
                if len(section_text) > 3000:
                    section_text = section_text[:3000] + "...\n[Section truncated]"
                ref_sections_text += f"#### {section_name}\n{section_text}\n\n"
        
        citations_block += f"""## Citation {i}

**Previous Analysis (Part 2):** {first_round.get('category', 'UNKNOWN')} (Confidence: {first_round.get('confidence', 0):.0%})
**Citation Type Detected:** {first_round.get('citation_type', 'UNKNOWN')}
**Why Flagged:** {first_round.get('justification', 'Not provided')[:250]}...

**Reference Paper:** eLife.{ref_id}
**Title:** {reference_papers.get(ref_id, {}).get('title', 'Unknown')}

**Citation Location in Citing Paper:**
- Section: {citation.get('section', 'Unknown')}
- Paragraph #{citation.get('paragraph_number', '?')}

**Citation Context (Full Paragraph):**
{citation.get('full_paragraph', '')[:800]}...

**Surrounding Context (2 paragraphs before/after):**
{citation.get('surrounding_context', '')[:1200]}...

---

**Reference Paper Sections (Read These Carefully):**
{ref_sections_text}

---

**Relationship Context:**
- Self-citation: {'Yes' if citation.get('is_self_citation', False) else 'No'}
- Same institution: {'Yes' if citation.get('is_same_institution', False) else 'No'}
- Shared authors: {', '.join(citation.get('shared_authors', [])) or 'None'}
- Shared affiliations: {', '.join(citation.get('shared_affiliations', [])) or 'None'}

**Note:** Relationship context may help explain patterns but focus on IMPACT, not motivation.

---

"""
    
    user_prompt = PHASE_A_USER_PROMPT_TEMPLATE.format(
        num_citations=len(problematic_citations),
        citing_title=citing_paper.get('title', 'Unknown'),
        citing_authors=', '.join(citing_paper.get('authors', [])[:5]),
        citing_doi=citing_paper.get('doi', 'Unknown'),
        citing_sections=citing_sections_text,
        citations_block=citations_block,
        is_self_citation="true/false",  # Placeholder, actual value in citations_block
        shared_affiliation="if any"  # Placeholder, actual value in citations_block
    )
    
    return PHASE_A_SYSTEM_PROMPT, user_prompt
