"""
Workflow 5 - Phase B: Synthesis & Reporting Prompt

Focuses on assessing whether miscitations affect paper validity using
qualitative criteria based on centrality and dependence.
"""

PHASE_B_SYSTEM_PROMPT = """You are a senior scientific integrity analyst writing a comprehensive impact assessment. Your role is to determine whether citation issues affect a paper's scientific validity.

CORE PHILOSOPHY:
- We know the citations are problematic (Workflow 2 confirmed this)
- Your job: Assess whether these issues MATTER for the paper's validity
- Focus on CENTRALITY and DEPENDENCE, not count
- One critical miscitation > Ten peripheral miscitations

Your report will guide researchers and reviewers in deciding:
- Can this paper's conclusions be trusted?
- Which specific findings are affected?
- What actions should be taken?

Be thorough, objective, and specific. Use qualitative criteria, not arbitrary thresholds."""


PHASE_B_USER_PROMPT_TEMPLATE = """You have completed detailed impact analysis of {num_citations} problematic citations. Now synthesize your findings into a comprehensive assessment of how these issues affect the paper's scientific validity.

# PAPER BEING ANALYZED
**Title:** {paper_title}
**Authors:** {paper_authors}
**DOI:** {paper_doi}
**Total Citations in Paper:** {total_citations}
**Problematic Citations Analyzed:** {problematic_count}

---

# CITATION IMPACT ANALYSES FROM PHASE A

{phase_a_analyses}

---

# YOUR TASK: DETERMINE IMPACT ON SCIENTIFIC VALIDITY

## STEP 1: IDENTIFY THE PAPER'S MAIN CONTRIBUTION

Before assessing impact, identify what this paper's PRIMARY contribution is:

### Where to Look:
1. **Abstract's final sentence** (usually states main conclusion)
2. **Paper title** (often states key finding)
3. **Discussion paragraph 1** (restates main finding)

### Claim Hierarchy:
- **TIER 1 (PRIMARY):** The main conclusion in abstract
- **TIER 2 (SECONDARY):** Supporting findings in Results
- **TIER 3 (BACKGROUND):** Context in Introduction

**Focus 80% of your analysis on citations supporting TIER 1 claims.**

---

## STEP 2: MAP CITATIONS TO CLAIMS

For each MAIN CLAIM in Results/Discussion:
1. State the claim (quote from paper)
2. Which problematic citations support it?
3. Does the paper have its OWN data supporting this claim?
4. Could the claim stand without these citations?

**Centrality Test:**
> "If I removed this miscitation, would the paper's main conclusion still be valid?"
> - NO → HIGH impact
> - YES → Lower impact

---

## STEP 3: PATTERN ANALYSIS

### A. Section Distribution
Count where miscitations appear:
- Introduction: X
- Methods: X  
- Results: X
- Discussion: X

**Key question:** Are problems concentrated in high-stakes sections (Results/Discussion) or low-stakes (Introduction)?

### B. Relationship Patterns (Brief Context Only)
- Self-citations: {self_citation_count} of {total_problematic}
- Same-institution: {same_inst_count} of {total_problematic}

**Note:** Mention briefly as possible context for patterns. Focus on IMPACT, not motivation.

**Only elaborate if:** Pattern is systematic (e.g., all self-citations overstate findings) AND affects validity.

---

## STEP 4: OVERALL CLASSIFICATION

Choose ONE classification using QUALITATIVE criteria:

**🔴 CRITICAL_CONCERN** - Use when:

The paper's **primary stated finding** (in abstract/conclusion) **depends on** miscited evidence AND:
- The paper's OWN data doesn't adequately support the conclusion, OR
- The methodology is based on a miscited protocol/data source

**Decision criteria:**
- Does the PRIMARY claim from the abstract depend on problematic citations?
- Could the claim stand on the paper's own data alone?
- Are there other valid citations that support it?

**Examples:**
- Paper claims "X causes Y" (abstract) but only citation supporting causation is miscited, and paper's own data only shows correlation → CRITICAL
- Paper's methodology claims to use "validated protocol from Smith 2020" but Smith doesn't describe this → CRITICAL

**🟠 MODERATE_CONCERN** - Use when:

Miscitations affect **interpretation or discussion** but:
- Paper's own experimental DATA is valid and well-executed
- PRIMARY finding is supported by paper's own work
- SECONDARY claims or interpretations are affected

**Decision criteria:**
- Own data supports main finding?
- But discussion/interpretation relies on miscited references?

**Examples:**
- Paper's experiments show X (solid data), but Discussion claims "explains Y (Smith 2020)" when Smith found opposite
- Secondary mechanistic interpretation affected, but primary observation stands

**🟡 MINOR_CONCERN** - Use when:

All problematic citations are:
- In Introduction (background only)
- Not referenced in Results/Discussion
- Not part of paper's contribution

**Decision criteria:**
- Could you delete the Introduction entirely and the findings would still be valid?
- Are miscitations purely context-setting, not claim-supporting?

**⚪ FALSE_ALARM** - Use when:

After deep reading, most flagged citations are actually:
- Acceptable METHODOLOGICAL citations (Workflow 2 misunderstood type)
- Reasonable paraphrases within scientific norms
- Not genuinely problematic

**Decision criteria:**
- After reading original texts, are these citations actually OK?
- Was Workflow 2 too strict or misunderstood citation types?

---

## STEP 5: GENERATE REPORT

Write a comprehensive assessment with these REQUIRED elements:

### 1. OPENING CLASSIFICATION (1 sentence)
State classification and single most critical reason.

**Template:**
"This paper is classified as [LEVEL] because [most critical issue in 15 words or less]."

### 2. MOST DAMAGING ISSUE (100-150 words)
Focus on the ONE most problematic citation that has highest impact.

**Must include:**
- What the citing paper claims (direct quote with location)
- What the reference actually says (direct quote with location)
- Why this matters for the paper's validity
- Whether paper's own data compensates

**Example structure:**
"The paper's central claim, stated in the abstract as '[quote],' depends critically on [Reference X]. In [Section] paragraph [N], the authors state: '[full quote from citing paper].' However, [Reference X]'s actual conclusion (Discussion, para [N]) states: '[quote from reference].' This miscitation is critical because [impact on validity]. The authors' own data [does/does not] provide alternative support for this claim."

### 3. SECTION DISTRIBUTION & PATTERNS (50-75 words)
Describe where problems appear and any systematic patterns.

**Required:**
- Numbers: X in Introduction, Y in Results, Z in Discussion
- Assessment: Are problems in high-stakes or low-stakes sections?
- Relationship patterns: Mention ONLY if helps explain validity impact

**Template:**
"The {num_citations} problematic citations are distributed: [breakdown by section]. [If critical: 'Significantly, X citations in Results/Discussion directly support main claims.' OR if minor: 'All citations appear in Introduction as background context only.'] [If relevant: Brief note on self-citation pattern as possible explanation, not accusation.]"

### 4. VALIDITY ASSESSMENT (75-100 words)
Answer directly: Can readers trust this paper?

**Must address:**
- Which findings can be trusted vs questioned?
- What's based on solid experimental data vs miscited references?
- Specific guidance for readers

**Template:**
"The paper's [primary/secondary] findings [can/cannot] be trusted because [specific reason based on dependence analysis]. Readers should [specific action: trust the experimental data but question the interpretation / be skeptical of the main conclusion / etc.]. The authors' own [data/methods/analysis] [is/is not] sound, but [the interpretation/conclusion/methodology] relies on miscited sources."

---

## TOTAL SYNTHESIS LENGTH: 250-350 words
- Opening: ~25 words
- Most damaging issue: 100-150 words  
- Pattern: 50-75 words
- Validity: 75-100 words

---

## OUTPUT FORMAT

Return JSON:

```json
{{
  "pattern_analysis": {{
    "section_distribution": {{"Introduction": 2, "Methods": 0, "Results": 4, "Discussion": 5}},
    
    "claim_impact_map": [
      {{
        "claim_text": "Direct quote of claim from abstract or results",
        "claim_tier": "PRIMARY" | "SECONDARY" | "BACKGROUND",
        "section": "Results",
        "paragraph_number": 8,
        "supporting_citation_ids": [1, 3, 7],
        "problematic_citation_ids": [1, 3],
        "status": "UNDERMINED" | "WEAKENED" | "UNAFFECTED" | "INDEPENDENT",
        "explanation": "How miscitations affect this specific claim"
      }}
    ],
    
    "relationship_patterns": {{
      "total_self_citations": 3,
      "total_same_institution": 2,
      "brief_note": "Only if relevant: Brief context about patterns"
    }},
    
    "severity_assessment": {{
      "high_impact_citations": [1, 3],
      "moderate_impact_citations": [2, 5, 7],
      "low_impact_citations": [4, 6, 8, 9, 10, 11],
      "rationale": "Explanation of why these groupings"
    }}
  }},
  
  "overall_classification": "CRITICAL_CONCERN" | "MODERATE_CONCERN" | "MINOR_CONCERN" | "FALSE_ALARM",
  
  "executive_summary": "3-4 sentence summary of classification and key finding",
  
  "detailed_report": "250-350 word assessment following the required 4-part structure above (opening + most damaging + pattern + validity)",
  
  "recommendations": {{
    "for_reviewers": "Specific actions reviewers/editors should take",
    "for_readers": "What readers should trust vs question"
  }}
}}
```

---

**REMEMBER:**
- This is about IMPACT on validity, not about counting errors
- Focus on which FINDINGS are affected, not just listing problems
- Use the centrality test: "Would removing this change the conclusion?"
- Quote extensively from both papers
- Be specific about which claims are undermined vs which remain valid
"""


def format_phase_b_prompt(
    paper_metadata: dict,
    phase_a_assessments: list,
    problematic_citations_contexts: list
) -> tuple:
    """
    Format Phase B synthesis prompt with Phase A results.
    
    Args:
        paper_metadata: Dict with title, authors, doi, total_citations
        phase_a_assessments: List of CitationAssessment objects
        problematic_citations_contexts: List of EnrichedCitationContext objects
    
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Format Phase A analyses
    phase_a_text = ""
    for i, assessment in enumerate(phase_a_assessments, 1):
        # Extract data safely
        impact = assessment.impact_assessment if hasattr(assessment, 'impact_assessment') else 'UNKNOWN'
        role = assessment.citation_role if hasattr(assessment, 'citation_role') else {}
        validity = assessment.validity_impact if hasattr(assessment, 'validity_impact') else {}
        
        phase_a_text += f"""## Citation {i} - Impact Analysis

**Impact Level:** {impact}
**Citation Role:** {role.get('type', 'UNKNOWN')} - {role.get('centrality', 'UNKNOWN')}
**Affects Main Finding:** {validity.get('affects_main_finding', 'Unknown')}

**Citing Paper Claim:**
Section: {assessment.citing_paper_claim.get('section', 'Unknown')}
> {assessment.citing_paper_claim.get('specific_claim', '')[:300]}

**Reference Evidence Summary:**
{assessment.reference_paper_evidence.get('summary', '')[:300]}

**Validity Impact:**
{validity.get('explanation', '')[:400]}

**Centrality Test:** {validity.get('centrality_test', 'Not provided')}

---

"""
    
    # Count self-citations and same-institution
    self_citation_count = sum(1 for ctx in problematic_citations_contexts if ctx.get('is_self_citation'))
    same_inst_count = sum(1 for ctx in problematic_citations_contexts if ctx.get('is_same_institution'))
    
    user_prompt = PHASE_B_USER_PROMPT_TEMPLATE.format(
        num_citations=len(phase_a_assessments),
        paper_title=paper_metadata.get('title', 'Unknown'),
        paper_authors=', '.join(paper_metadata.get('authors', [])[:5]),
        paper_doi=paper_metadata.get('doi', 'Unknown'),
        total_citations=paper_metadata.get('total_citations', '?'),
        problematic_count=len(phase_a_assessments),
        phase_a_analyses=phase_a_text,
        self_citation_count=self_citation_count,
        total_problematic=len(phase_a_assessments),
        same_inst_count=same_inst_count
    )
    
    return PHASE_B_SYSTEM_PROMPT, user_prompt
