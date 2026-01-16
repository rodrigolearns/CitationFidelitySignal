"""
NeoWorkflow 5 - Phase B Prompt: Synthesis & Cumulative Assessment

This prompt synthesizes all per-reference analyses into a cumulative assessment.
Goal: List accumulated caveats and combined impact (not vague trust ratings).
"""

from typing import Dict, List


def format_phase_b_prompt(
    citing_paper_metadata: Dict,
    reference_analyses: List[Dict]
) -> str:
    """
    Format Phase B prompt for synthesizing cumulative impact.
    
    Args:
        citing_paper_metadata: Title, authors, etc. of citing paper
        reference_analyses: List of Phase A results (one per reference)
    
    Returns:
        Formatted prompt string
    """
    
    # Format reference summaries
    ref_summaries = ""
    for i, ref in enumerate(reference_analyses, 1):
        color = ref.get('color_rating', 'UNKNOWN')
        ref_id = ref.get('reference_paper_id', 'unknown')
        impact = ref.get('impact_statement', 'No statement')
        issues = ref.get('specific_issues', [])
        consequences = ref.get('consequences', 'No consequences listed')
        
        ref_summaries += f"""
## Reference {i}: {ref_id}

**Color Rating**: {color}

**Impact Statement**: {impact}

**Specific Issues**:
"""
        for issue in issues:
            ref_summaries += f"- {issue}\n"
        
        ref_summaries += f"""
**Consequences**: {consequences}

**Sections Affected**: {', '.join(ref.get('sections_affected', []))}

---
"""
    
    # Build full prompt
    prompt = f"""# NeoWorkflow 5 - Phase B: Cumulative Impact Synthesis

You have received detailed analyses of how a citing paper uses/misuses EACH of its reference papers.

Now synthesize these into a cumulative assessment focusing on **what is wrong**, not vague trust ratings.

## CITING PAPER

- **Title**: {citing_paper_metadata.get('title', 'Unknown')}
- **Article ID**: {citing_paper_metadata.get('article_id', 'Unknown')}
- **Authors**: {', '.join(citing_paper_metadata.get('authors', [])[:3])} et al.

## PER-REFERENCE ANALYSES

{ref_summaries}

## YOUR TASK

Synthesize all reference-specific issues into a cumulative assessment that answers:

1. **What accumulated caveats exist?** (All issues combined)
2. **Which sections have problems?** (Group issues by section)
3. **What should reviewers check?** (Specific, actionable)
4. **What should readers know?** (Clear warnings/limitations)

## OUTPUT FORMAT

Provide your synthesis as JSON:

```json
{{
  "overall_classification": "CRITICAL_CONCERN|MODERATE_CONCERN|MINOR_CONCERN|FALSE_ALARM",
  "accumulated_caveats": [
    "Caveat 1: Misrepresented X in Introduction",
    "Caveat 2: Cherry-picked Y in Discussion",
    "Caveat 3: Ignored Z throughout"
  ],
  "sections_with_issues": {{
    "Introduction": [
      "Issue 1 from Ref A",
      "Issue 2 from Ref B"
    ],
    "Discussion": [
      "Issue 3 from Ref A",
      "Issue 4 from Ref C"
    ]
  }},
  "recommendations_for_reviewers": [
    "Verify claim X by checking original Ref A, page Y",
    "Compare citing paper's interpretation of Z with Ref B's actual conclusions",
    "Request additional evidence for claim W, as Ref C doesn't support it"
  ],
  "recommendations_for_readers": [
    "Be cautious of claims in Discussion about X - they may over-extrapolate from sources",
    "Cross-reference any claims about Y with the original papers",
    "The Introduction's framing may not reflect the full context from cited literature"
  ],
  "executive_summary": "Clear, specific paragraph explaining what's wrong and what the consequences are. NO VAGUE TRUST RATINGS. Focus on concrete issues and their impacts."
}}
```

## OVERALL CLASSIFICATION GUIDE

Aggregate the individual reference classifications:
- **CRITICAL_CONCERN**: Multiple references critically misused OR one reference that undermines core claims
- **MODERATE_CONCERN**: Multiple references significantly misused OR consistent pattern of cherry-picking
- **MINOR_CONCERN**: Isolated issues across references, paper mostly valid but has caveats
- **FALSE_ALARM**: No significant cumulative issues

## CRITICAL INSTRUCTIONS

1. **Be specific**: List concrete issues, not vague concerns
2. **Group by section**: Show which parts of the paper have problems
3. **Make it actionable**: Reviewers and readers should know exactly what to do
4. **Avoid vague language**: Don't say "may be problematic" - say what IS problematic and why
5. **Focus on consequences**: What can/cannot be trusted?

## SYNTHESIS STRATEGY

1. Read all reference analyses
2. Identify common patterns (e.g., cherry-picking throughout Discussion)
3. Group issues by paper section
4. Assess cumulative severity
5. Provide specific, actionable recommendations

Now synthesize the cumulative impact and provide your JSON response.
"""
    
    return prompt
