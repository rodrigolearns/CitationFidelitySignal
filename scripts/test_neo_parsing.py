#!/usr/bin/env python3
"""
Quick test to see what LLM actually returns and why parsing fails.
"""

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.analyzers.neo_impact_analyzer import NeoImpactAnalyzer

# Initialize analyzer
analyzer = NeoImpactAnalyzer(provider='deepseek', model='deepseek-reasoner')

# Create a minimal test prompt
test_prompt = """# Test Prompt

Please return this exact JSON:

```json
{
  "color_rating": "MODERATE_CONCERN",
  "impact_statement": "Test statement",
  "specific_issues": ["Issue 1", "Issue 2"],
  "consequences": "Test consequences",
  "sections_affected": ["Introduction"],
  "pattern_analysis": {
    "cherry_picking": "No",
    "context_ignoring": "No",
    "over_extrapolation": "No",
    "misunderstanding": "No"
  }
}
```

Return ONLY the JSON above, nothing else.
"""

print("=" * 80)
print("Testing LLM Response and Parsing")
print("=" * 80)
print()

# Call LLM
print("Calling LLM...")
response = analyzer._call_llm(test_prompt)

print(f"\nResponse length: {len(response)} characters")
print("\nFull response:")
print("-" * 80)
print(response)
print("-" * 80)
print()

# Test parsing
print("Testing parsing...")
test_contexts = [{}]  # Dummy
parsed = analyzer._parse_phase_a_response(response, "test_ref", test_contexts, [])

print("\nParsed result:")
print("color_rating:", parsed.get('color_rating'))
print("impact_statement length:", len(str(parsed.get('impact_statement', ''))))
print("specific_issues:", parsed.get('specific_issues'))
print()

if parsed.get('color_rating') == 'MODERATE_CONCERN':
    print("✅ Parsing SUCCESSFUL!")
else:
    print("❌ Parsing FAILED - fell back to template")
