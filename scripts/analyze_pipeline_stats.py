#!/usr/bin/env python3
"""
Analyze overall pipeline statistics and generate summary report.

Part of Sprint 10: Data Analysis & Quality Assessment
"""

import sys
import json
from pathlib import Path
from collections import Counter, defaultdict
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent.parent))

from elife_graph_builder.graph.neo4j_importer import StreamingNeo4jImporter
from elife_graph_builder.config import Config


def get_pipeline_stats(neo4j):
    """Get comprehensive statistics from all pipeline stages."""
    
    stats = {}
    
    with neo4j.driver.session() as session:
        # Part 1: Citation Graph
        result = session.run('MATCH (a:Article) RETURN count(a) as total')
        stats['total_articles'] = result.single()['total']
        
        result = session.run('MATCH ()-[c:CITES]->() RETURN count(c) as total')
        stats['total_citations'] = result.single()['total']
        
        result = session.run('''
            MATCH (a:Article)-[:CITES]->()
            RETURN count(DISTINCT a) as total
        ''')
        stats['citing_articles'] = result.single()['total']
        
        result = session.run('''
            MATCH (a:Article)<-[:CITES]-()
            WHERE NOT (a)-[:CITES]->()
            RETURN count(DISTINCT a) as total
        ''')
        stats['referenced_only_articles'] = result.single()['total']
        
        # Part 2: Qualification & Classification
        result = session.run('''
            MATCH ()-[c:CITES]->()
            WHERE c.qualified = true
            RETURN count(c) as total
        ''')
        stats['qualified_citations'] = result.single()['total']
        
        # Get all contexts (parse JSON in Python)
        result = session.run('''
            MATCH ()-[c:CITES]->()
            WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
            RETURN c.citation_contexts_json as contexts_json
        ''')
        
        classification_dist = Counter()
        citation_type_dist = Counter()
        confidence_scores = []
        total_contexts = 0
        
        for record in result:
            contexts = json.loads(record['contexts_json'])
            total_contexts += len(contexts)
            
            for context in contexts:
                if context.get('classification'):
                    classif = context['classification']
                    if isinstance(classif, dict):
                        if classif.get('category'):
                            classification_dist[classif['category']] += 1
                        if classif.get('citation_type'):
                            citation_type_dist[classif['citation_type']] += 1
                        if classif.get('confidence'):
                            confidence_scores.append(classif['confidence'])
        
        stats['total_contexts'] = total_contexts
        
        stats['classification_distribution'] = dict(classification_dist)
        stats['citation_type_distribution'] = dict(citation_type_dist)
        stats['avg_confidence'] = sum(confidence_scores) / len(confidence_scores) if confidence_scores else 0
        
        # Part 3: Second-Round Determination (parse JSON in Python)
        result = session.run('''
            MATCH ()-[c:CITES]->()
            WHERE c.qualified = true AND c.citation_contexts_json IS NOT NULL
            RETURN c.citation_contexts_json as contexts_json
        ''')
        
        determination_dist = Counter()
        recommendation_dist = Counter()
        second_round_categories = Counter()
        
        for record in result:
            contexts = json.loads(record['contexts_json'])
            for context in contexts:
                if context.get('second_round'):
                    sr = context['second_round']
                    if sr.get('determination'):
                        determination_dist[sr['determination']] += 1
                    if sr.get('recommendation'):
                        recommendation_dist[sr['recommendation']] += 1
                    if sr.get('category'):
                        second_round_categories[sr['category']] += 1
        
        stats['determination_distribution'] = dict(determination_dist)
        stats['recommendation_distribution'] = dict(recommendation_dist)
        stats['second_round_categories'] = dict(second_round_categories)
        stats['second_round_total'] = sum(determination_dist.values())
    
    return stats


def print_report(stats):
    """Print formatted statistics report."""
    
    print("\n" + "="*70)
    print("CITATION FIDELITY ANALYSIS - PIPELINE STATISTICS")
    print("="*70)
    print(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("="*70)
    
    # Part 1
    print("\n📊 PART 1: CITATION GRAPH")
    print("-" * 70)
    print(f"  Total Articles: {stats['total_articles']:,}")
    print(f"  Total Citations: {stats['total_citations']:,}")
    print(f"  Citing Articles: {stats['citing_articles']:,}")
    print(f"  Referenced-Only Articles: {stats['referenced_only_articles']:,}")
    
    # Part 2a
    print("\n📊 PART 2A: EVIDENCE EXTRACTION")
    print("-" * 70)
    print(f"  Qualified Citations: {stats['qualified_citations']:,}")
    print(f"  Citation Contexts: {stats['total_contexts']:,}")
    print(f"  Avg Contexts per Citation: {stats['total_contexts'] / stats['qualified_citations']:.2f}")
    
    # Part 2b
    print("\n📊 PART 2B: INITIAL CLASSIFICATION")
    print("-" * 70)
    print(f"  Average Confidence: {stats['avg_confidence']:.2%}")
    print("\n  Classification Distribution:")
    for category, count in sorted(stats['classification_distribution'].items(), 
                                   key=lambda x: x[1], reverse=True):
        pct = count / stats['total_contexts'] * 100
        bar = "█" * int(pct / 2)
        print(f"    {category:20s}: {count:4d} ({pct:5.1f}%) {bar}")
    
    print("\n  Citation Type Distribution:")
    for ctype, count in sorted(stats['citation_type_distribution'].items(), 
                               key=lambda x: x[1], reverse=True):
        pct = count / stats['total_contexts'] * 100
        bar = "█" * int(pct / 2)
        print(f"    {ctype:20s}: {count:4d} ({pct:5.1f}%) {bar}")
    
    # Part 3
    if stats['second_round_total'] > 0:
        print("\n📊 PART 3: FINAL DETERMINATION (SECOND-ROUND)")
        print("-" * 70)
        print(f"  Total Second-Round Reviews: {stats['second_round_total']:,}")
        
        print("\n  Determination:")
        for det, count in stats['determination_distribution'].items():
            pct = count / stats['second_round_total'] * 100
            print(f"    {det:20s}: {count:4d} ({pct:5.1f}%)")
        
        print("\n  Recommendation:")
        for rec, count in stats['recommendation_distribution'].items():
            pct = count / stats['second_round_total'] * 100
            print(f"    {rec:20s}: {count:4d} ({pct:5.1f}%)")
        
        print("\n  Final Categories (After Second Round):")
        for category, count in sorted(stats['second_round_categories'].items(), 
                                       key=lambda x: x[1], reverse=True):
            pct = count / stats['second_round_total'] * 100
            print(f"    {category:20s}: {count:4d} ({pct:5.1f}%)")
    else:
        print("\n📊 PART 3: FINAL DETERMINATION")
        print("-" * 70)
        print("  No second-round reviews conducted yet.")
    
    # Summary
    print("\n📈 KEY METRICS")
    print("-" * 70)
    total_classified = sum(stats['classification_distribution'].values())
    problematic = sum(stats['classification_distribution'].get(cat, 0) 
                     for cat in ['NOT_SUBSTANTIATE', 'CONTRADICT', 'OVERSIMPLIFY', 'MISQUOTE'])
    problematic_pct = problematic / total_classified * 100 if total_classified > 0 else 0
    
    print(f"  Citation Fidelity Rate: {100 - problematic_pct:.1f}%")
    print(f"  Problematic Citations: {problematic} / {total_classified} ({problematic_pct:.1f}%)")
    
    if stats['second_round_total'] > 0:
        confirmed = stats['determination_distribution'].get('CONFIRMED', 0)
        corrected = stats['determination_distribution'].get('CORRECTED', 0)
        false_positive_rate = corrected / stats['second_round_total'] * 100
        print(f"  False Positive Rate: {false_positive_rate:.1f}% ({corrected} / {stats['second_round_total']})")
    
    print("\n" + "="*70)


def save_stats_json(stats, output_path):
    """Save statistics to JSON file."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        json.dump(stats, f, indent=2)
    print(f"\n💾 Statistics saved to: {output_path}")


def main():
    print("Connecting to Neo4j...")
    neo4j = StreamingNeo4jImporter(Config.NEO4J_URI, Config.NEO4J_USER, Config.NEO4J_PASSWORD)
    
    try:
        print("Analyzing pipeline statistics...")
        stats = get_pipeline_stats(neo4j)
        
        print_report(stats)
        
        # Save to JSON
        output_path = Path(__file__).parent.parent / 'data' / 'analysis' / 'pipeline_stats.json'
        save_stats_json(stats, output_path)
        
    finally:
        neo4j.close()


if __name__ == '__main__':
    main()
