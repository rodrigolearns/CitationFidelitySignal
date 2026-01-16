"""
NeoWorkflow 5 - Phase A Prompt: Per-Reference Deep Analysis

This prompt analyzes ALL citations (suspicious + supporting) to a SINGLE reference paper.
Goal: Understand patterns of use/misuse and provide specific impact statement for this reference.
"""

from typing import List, Dict


def format_phase_a_prompt(
    citing_paper_text: str,
    ref_paper_text: str,
    suspicious_contexts: List[Dict],
    supporting_contexts: List[Dict]
) -> str:
    """
    Format Phase A prompt for analyzing one reference paper's usage.
    
    Args:
        citing_paper_text: Full XML text of citing paper
        ref_paper_text: Full XML text of reference paper
        suspicious_contexts: Suspicious citation contexts to this reference
        supporting_contexts: Supporting citation contexts to this reference
    
    Returns:
        Formatted prompt string
    """
    
    # Format suspicious citations
    suspicious_section = ""
    if suspicious_contexts:
        suspicious_section = "### SUSPICIOUS CITATIONS\n\n"
        for i, ctx in enumerate(suspicious_contexts, 1):
            suspicious_section += f"""
**Citation {i}:**
- Location: {ctx.get('section_name', 'Unknown')}
- In-text format: {ctx.get('in_text_citation', 'N/A')}
- Classification: {ctx.get('classification', 'UNKNOWN')}
- Reasoning: {ctx.get('reasoning', 'No reasoning provided')}

Context (4-sentence window):
{ctx.get('context_text', 'No context available')}

---
"""
    else:
        suspicious_section = "### SUSPICIOUS CITATIONS\n\nNone.\n\n"
    
    # Format supporting citations
    supporting_section = ""
    if supporting_contexts:
        supporting_section = "### SUPPORTING CITATIONS\n\n"
        for i, ctx in enumerate(supporting_contexts, 1):
            supporting_section += f"""
**Citation {i}:**
- Location: {ctx.get('section_name', 'Unknown')}
- In-text format: {ctx.get('in_text_citation', 'N/A')}

Context (4-sentence window):
{ctx.get('context_text', 'No context available')}

---
"""
    else:
        supporting_section = "### SUPPORTING CITATIONS\n\nNone.\n\n"
    
    # Build full prompt
    prompt = f"""# NeoWorkflow 5 - Phase A: Reference-Specific Deep Analysis

You are analyzing how a CITING PAPER uses/misuses a single REFERENCE PAPER across all mentions.

## YOUR TASK

Analyze ALL citations (suspicious + supporting) to understand:
1. **What the reference paper actually says** (read it carefully)
2. **How the citing paper uses it** (across all mentions)
3. **Patterns of misuse**: cherry-picking, misunderstanding, ignoring context, over-extrapolation
4. **Specific consequences**: What parts of the citing paper's argument are weakened?

## CITATION DATA

Total suspicious: {len(suspicious_contexts)}
Total supporting: {len(supporting_contexts)}

{suspicious_section}

{supporting_section}

## REFERENCE PAPER (What it actually says)

<reference_paper>
{ref_paper_text[:30000]}  <!-- Truncated for token limits -->
</reference_paper>

## CITING PAPER (How they use it)

<citing_paper>
{citing_paper_text[:30000]}  <!-- Truncated for token limits -->
</citing_paper>

## OUTPUT FORMAT

Provide your analysis as JSON:

```json
{{
  "color_rating": "CRITICAL_CONCERN|MODERATE_CONCERN|MINOR_CONCERN|FALSE_ALARM",
  "impact_statement": "One-sentence summary of the impact of misciting THIS reference",
  "specific_issues": [
    "Issue 1: What was misunderstood/cherry-picked",
    "Issue 2: What was ignored",
    "Issue 3: What was over-extrapolated"
  ],
  "consequences": "Paragraph explaining what parts of the citing paper are affected and how",
  "sections_affected": ["Introduction", "Discussion"],
  "pattern_analysis": {{
    "cherry_picking": "Yes/No - explanation",
    "context_ignoring": "Yes/No - explanation",
    "over_extrapolation": "Yes/No - explanation",
    "misunderstanding": "Yes/No - explanation"
  }}
}}
```

## CLASSIFICATION GUIDE

- **CRITICAL_CONCERN**: Critical misuse - undermines major claims or conclusions
- **MODERATE_CONCERN**: Significant misuse - affects multiple arguments or key sections
- **MINOR_CONCERN**: Minor misuse - isolated issues, paper still mostly valid
- **FALSE_ALARM**: Proper usage - no significant issues detected

## CRITICAL INSTRUCTIONS

1. **Be specific**: Don't say "misrepresented findings" - say exactly WHAT was misrepresented and HOW
2. **Use evidence**: Quote from both papers to support your assessment
3. **Focus on consequences**: What parts of the citing paper cannot be trusted because of this?
4. **Consider supporting citations too**: Do they contradict the suspicious ones? Are they also problematic?
5. **Be actionable**: A reviewer should know exactly what to check

Now analyze this reference's usage and provide your JSON response.
"""
    
    return prompt
