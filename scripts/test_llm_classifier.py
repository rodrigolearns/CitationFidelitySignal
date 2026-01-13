#!/usr/bin/env python3
"""
Quick test of LLM classifier on a mock citation.

Usage:
    python scripts/test_llm_classifier.py
"""

from elife_graph_builder.classifiers import LLMClassifier
from elife_graph_builder.models import CitationContext, EvidenceSegment

# Mock data for testing
mock_context = CitationContext(
    instance_id=1,
    source_article_id="12345",
    target_article_id="67890",
    ref_id="bib10",
    section="Introduction",
    sentence_before_2="Previous research has explored various mechanisms.",
    sentence_before_1="Several studies have investigated this phenomenon.",
    citation_sentence="Recent work demonstrated that CRISPR editing efficiency varies across cell types (Zhang et al., 2019).",
    sentence_after_1="This heterogeneity must be considered in therapeutic applications.",
    context_text="Previous research has explored various mechanisms. Several studies have investigated this phenomenon. Recent work demonstrated that CRISPR editing efficiency varies across cell types (Zhang et al., 2019). This heterogeneity must be considered in therapeutic applications.",
    evidence_segments=[
        EvidenceSegment(
            section="Results",
            text="We observed substantial variation in editing efficiency across cell types. Primary T cells exhibited editing rates of 23-31%, while HEK293T cells showed 67-82% efficiency (p<0.001).",
            similarity_score=0.89,
            retrieval_method="hybrid"
        ),
        EvidenceSegment(
            section="Discussion",
            text="Our findings indicate that CRISPR-Cas9 efficiency is highly cell-type dependent. Primary cells showed consistently lower editing rates compared to immortalized lines.",
            similarity_score=0.76,
            retrieval_method="hybrid"
        ),
        EvidenceSegment(
            section="Methods",
            text="CRISPR-Cas9 editing was performed using standard protocols with guide RNAs targeting the AAVS1 safe harbor locus.",
            similarity_score=0.63,
            retrieval_method="hybrid"
        )
    ]
)

def main():
    print("="*70)
    print("🧪 Testing LLM Classifier")
    print("="*70)
    print()
    
    try:
        # Initialize classifier
        print("Initializing LLM classifier...")
        classifier = LLMClassifier()
        print(f"✅ Using model: {classifier.model}")
        print()
        
        # Classify the mock context
        print("Classifying mock citation context...")
        print(f"Context: {mock_context.context_text[:100]}...")
        print()
        
        classification = classifier.classify_context(
            citation_format="Zhang L et al. (2019)",
            context=mock_context,
            reference_article_id="67890"
        )
        
        print("="*70)
        print("✅ CLASSIFICATION RESULT")
        print("="*70)
        print(f"Classification: {classification.classification}")
        print(f"Confidence: {classification.confidence:.2f}")
        print(f"Justification: {classification.justification}")
        print(f"Tokens used: {classification.tokens_used}")
        print(f"Model: {classification.model_used}")
        print()
        
        # Calculate cost
        if classification.tokens_used:
            # GPT-5 Mini pricing: $0.25 input, $2.00 output per million
            # Rough estimate: 80% input, 20% output
            input_tokens = int(classification.tokens_used * 0.8)
            output_tokens = int(classification.tokens_used * 0.2)
            cost = (input_tokens * 0.25 / 1_000_000) + (output_tokens * 2.00 / 1_000_000)
            print(f"💰 Estimated cost: ${cost:.6f}")
            print(f"   (For 1000 citations: ${cost * 1000:.2f})")
        
        print()
        print("✅ Test complete!")
        
    except Exception as e:
        print(f"❌ Error: {e}")
        print()
        print("Make sure you have:")
        print("1. Created .env file with OPENAI_API_KEY")
        print("2. Installed openai: pip install openai")
        return 1
    
    return 0


if __name__ == "__main__":
    exit(main())
