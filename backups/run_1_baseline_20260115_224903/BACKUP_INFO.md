# Baseline Processing Run - Backup

**Date:** $(date)
**Git Commit:** $(git rev-parse HEAD 2>/dev/null || echo "N/A")

## What This Backup Contains

### Processed Data
- Neo4j graph database with ~662 citing papers
- ~861 qualified eLife→eLife citation relationships
- Citation contexts extracted from XMLs
- Workflow 2: Rapid screening classifications
- Workflow 3: Deep verification results
- Workflow 5: Impact assessments for problematic papers

### Known Issues in This Run
1. **Section extraction**: Used subsection titles instead of main sections
   - Results: Many citations marked as "Unknown" section
   - Impact: Workflow 5 severity tables incomplete
   
2. **Missing metadata**: Did not capture:
   - Section type attributes from XML
   - Citation context type (figure caption vs prose)
   - Reference metadata (DOI, PMID, publication type)
   - Section depth and position information

### Data Quality
- LLM classifications: High quality (DeepSeek Chat + Reasoner)
- Section normalization: ~30% accurate (many "Unknown")
- Evidence retrieval: Working well
- Impact analysis: Complete for 10 problematic papers

## Purpose
This backup preserves the baseline processing to enable:
1. Comparison of LLM executive summaries before/after metadata improvements
2. Analysis of how better metadata affects classification accuracy
3. Rollback point if new processing encounters issues

## Restore Instructions
To restore this backup:
```bash
# Stop current Neo4j
docker-compose down

# Restore database files
# (specific commands depend on backup method used)

# Restart
docker-compose up -d
```
