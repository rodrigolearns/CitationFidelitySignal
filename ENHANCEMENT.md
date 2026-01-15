# Enhancement & Improvement Roadmap

This document tracks planned improvements and enhancements for the Citation Fidelity Signal system.

---

## 🎯 Priority Improvements

### 1. **Enhanced Metadata Extraction** 🔬 [HIGH PRIORITY]

**Status**: Development plan complete, backup created, ready for implementation

**Problem**: Current extraction only captures basic section names, often resulting in subsections (e.g., "Formation of sediments associated with H. naledi") instead of main sections. ~70% of citations show as "Unknown" section after normalization.

**Solution**: Extract 5+ additional metadata fields from JATS XML:

1. **section_type** - From XML `@sec-type` attribute (`intro`, `results`, `materials|methods`, `discussion`)
   - More reliable than text-based detection
   - Standardized across eLife articles

2. **section_depth** - Nesting level (0=top, 1=nested once, etc.)
   - Captures whether citation is in main section or subsection
   - Helps identify context specificity

3. **subsection_title** - Specific subsection heading (before normalization)
   - Preserves fine-grained context ("Statistical Analysis" vs "Cell Culture")
   - Useful for qualitative review and pattern detection

4. **context_type** - Where citation appears: `figure_caption`, `table_caption`, `prose`, `list_item`
   - Helps distinguish METHODOLOGICAL citations (in Methods, near tables/figures)
   - Identifies BACKGROUND citations (in Introduction prose)
   - Flags EVIDENCE citations (in Results prose)

5. **position_in_section** - 0.0-1.0 relative position (0=first paragraph, 1=last)
   - Early citations often establish background/context
   - Late citations typically support conclusions
   - Helps detect "drive-by" citations vs substantive references

6. **reference_metadata** - DOI, PMID, publication type (journal/book/software), journal name
   - Enable retraction checking via external databases
   - Distinguish peer-reviewed articles from software/datasets
   - Cross-reference with other citation databases
   - Track citation of preprints vs published work

**Expected Improvements**:
- Section accuracy: 30% → 95%+
- Richer LLM context for better classification
- Better pattern detection in Workflow 5 impact analysis
- Retraction checking capability

**Implementation Plan**: See `METADATA_ENHANCEMENT_PLAN.md`
- Estimated: 8-9 hours development + testing
- Requires reprocessing of all papers (but preserves existing classifications)
- Backup of current run saved at: `backups/run_1_baseline_20260115_224903/`

---

### 2. **Workflow 2: Classification Granularity** 🎯

**Problem**: Most citations are classified as `NOT_SUBSTANTIATE`, limiting analytical value and making it difficult to distinguish between different types of citation issues.

**Solutions**:
- [ ] Expand classification schema with more specific categories:
  - `INCOMPLETE_SUPPORT` - Reference partially supports the claim but lacks key details
  - `OVERSTATED_CLAIM` - Citing paper extrapolates beyond what reference actually shows
  - `CONTEXT_MISMATCH` - Reference discusses the topic but in a different context
  - `METHODOLOGICAL_MISMATCH` - Reference uses different methods/conditions
  - `CHERRY_PICKED` - Citing paper selects favorable results while ignoring contradictory findings
  - `MISSING_CAVEATS` - Citing paper omits important limitations/qualifications from reference
- [ ] Refine LLM prompts to guide more nuanced classification
- [ ] Add confidence thresholds to prevent over-classification into generic categories
- [ ] Include examples of each category in prompts to improve LLM accuracy

---

### 3. **In-Text Citation Display** 📝

**Problem**: Citations displayed as "Citation #1", "Citation #2" makes analysis difficult, especially when papers cite the same reference multiple times.

**Solutions**:
- [ ] Display citations using proper in-text format throughout UI:
  - **Problematic Papers List**: Show "Smith et al., 2020" instead of "Citation #1"
  - **Phase A Assessments**: Use author-year format for each citation instance
  - **Citation Details**: Include formatted citation in headers
- [ ] Backend: Extract and store in-text citation format during parsing:
  - Parse `<xref>` tags to extract citation text
  - Generate author-year format from reference metadata
  - Store as `in_text_citation` field in Neo4j
- [ ] Frontend: Update display logic to use formatted citations
- [ ] Add tooltip showing full reference when hovering over in-text citation

**Status**: Partially implemented - `in_text_citation` field added to model, needs full integration

---

### 4. **User Annotations & Notes** 💬

**Problem**: Notes/comments in early workflows (Workflow 2-3) are not useful; manual review should focus on problematic papers after Workflow 5.

**Solutions**:
- [ ] Remove note-taking features from Workflow 2/3 citation lists
- [ ] Add comprehensive annotation system to Problematic Paper Detail page:
  - Per-citation notes visible in context
  - Paper-level notes for overall assessment
  - Severity override capability (upgrade/downgrade High/Moderate/Low)
  - Flag for "requires expert review"
  - Link to related citations within same paper
- [ ] Store annotations in Neo4j with timestamp and user tracking
- [ ] Export annotations with Workflow 5 reports for external review

---

### 5. **Phase A: Citation Impact Assessment Depth** 🔬

**Problem**: Phase A assessments often conclude "discussion questionable, but results valid" without analyzing whether the citing paper's methodology, assumptions, or arguments actually depend on the miscited reference.

**Solutions**:
- [ ] Refine Phase A prompt to trace citation dependencies:
  - **Methodological Dependencies**: "Did the citing paper justify their methods based on this reference?"
  - **Assumption Dependencies**: "Does the citing paper's rationale rely on claims from this reference?"
  - **Interpretive Dependencies**: "Are the citing paper's conclusions drawn by building on this reference?"
  - **Data Dependencies**: "Does the citing paper compare their results against this reference's data?"
- [ ] Add structured impact analysis fields:
  - `affects_methods`: Boolean + explanation
  - `affects_assumptions`: Boolean + explanation
  - `affects_interpretation`: Boolean + explanation
  - `undermined_claims`: List of specific claims/arguments put into question
- [ ] Update Phase B synthesis to aggregate these dependency impacts:
  - Clearly state which specific arguments/claims are undermined
  - Avoid generic statements like "results remain valid"
  - Provide evidence-based assessment of what can/cannot be trusted

**Example Output**: 
> "The citing paper's choice of treatment protocol (Methods, para 3) was justified by claiming that Reference X demonstrated 70% efficacy. However, Reference X does not report this efficacy rate. This undermines the methodological rationale, though the experimental execution itself remains sound. Readers should question why this specific protocol was chosen over alternatives."

---

### 6. **Problematic Paper Analysis: Enhanced Citation Context** 📊

**Problem**: Problematic citations list lacks sufficient context for meaningful analysis.

**Solutions**:
- [ ] Add to each citation entry:
  - **In-text citation format** (e.g., "Smith et al., 2020")
  - **Section location** (Introduction/Methods/Results/Discussion)
  - **Paragraph number** within section
  - **Citation role** (background, methodological justification, comparative data, etc.)
  - **Severity indicator** (High/Moderate/Low impact badge)
  - **Quick summary** (1-sentence explanation of the issue)
- [ ] Group citations by:
  - Reference paper (show all instances of citing same paper)
  - Section (Introduction citations vs. Methods citations)
  - Severity (High impact citations first)
- [ ] Add filtering and sorting options
- [ ] Include "View in context" link to see full paragraph

---

### 7. **Classification Schema Refinement** 🏷️

**Current Issue**: Over-reliance on generic categories reduces system utility.

**Action Items**:
- [ ] Conduct classification distribution analysis on processed corpus
- [ ] Identify patterns in miscategorized citations through manual review
- [ ] A/B test alternative prompt formulations
- [ ] Add few-shot examples to prompts for edge cases
- [ ] Implement confidence calibration for borderline classifications
- [ ] Consider hierarchical classification (primary + secondary tags)

---

## 📊 Planned Analytics

### Dashboard Metrics
- [ ] **Total Citation Count**: Number of eLife→eLife citations discovered
- [ ] **Classification Distribution**: Breakdown by category (SUPPORT, CONTRADICT, etc.)
- [ ] **Manual Review Statistics**: Percentage of citations manually reviewed
- [ ] **Agreement Analysis**: LLM vs. human reviewer alignment rates
- [ ] **Citation Propagation Maps**: Visualize how miscitations spread through networks

### Section Analysis
- [ ] **Section Distribution**: Where problematic citations occur most (Introduction vs Methods vs Results)
- [ ] **Context Type Distribution**: Figure captions vs prose vs tables
- [ ] **Position Analysis**: Early vs late section citations
- [ ] **Reference Type Analysis**: Journal articles vs books vs software

---

## 🚀 Expansion Goals

### Multi-Publisher Support
- [ ] **PubMed**: Integrate with PubMed API for broader coverage
- [ ] **arXiv**: Add preprint analysis capability
- [ ] **bioRxiv/medRxiv**: Track citation quality in preprints
- [ ] **PDF Processing**: Handle papers without structured XML using Grobid or similar

### User Features
- [ ] **User Submission Portal**: Allow researchers to submit their DOI/PDF
- [ ] **Automated Citation Discovery**: Find all papers citing a given work
- [ ] **Citation Quality Dashboard**: Show citation health for any paper
- [ ] **API Service**: Programmatic access to citation assessments
- [ ] **Citation Propagation Analysis**: Track how errors spread through citation chains
- [ ] **Email Alerts**: Notify when papers citing your work are analyzed

### Integration Features
- [ ] **Retraction Watch**: Cross-check citations against retracted papers database
- [ ] **ORCID Integration**: Connect to researcher profiles
- [ ] **Publisher Integration**: API for journal editors to check submissions
- [ ] **Reference Manager Integration**: Plugins for Zotero, Mendeley, EndNote

---

## 🔬 Research Questions

These questions can be answered once we have a larger corpus analyzed:

- **How common are low-fidelity citations in scientific literature?**
  - Current data: ~30.6% of citations have some issues in eLife corpus
  - Need broader sampling across fields and publishers

- **Do certain fields or topics have higher rates of miscitation?**
  - Analyze by subject categories
  - Compare methodology-heavy vs theory-heavy fields

- **Can we predict which citations are likely to be problematic?**
  - Machine learning on citation patterns
  - Risk scoring based on citation context

- **How do miscitations propagate through citation networks?**
  - Graph analysis of citation chains
  - Identify papers that spread errors vs correct them

- **What interventions can improve citation accuracy?**
  - Author tools showing real-time citation quality
  - Reviewer checklists for citation verification
  - Journal policies requiring citation justification

---

## 🛠️ Technical Improvements

### Performance Optimization
- [ ] Cache frequently accessed reference texts
- [ ] Batch LLM API calls more efficiently
- [ ] Optimize Neo4j queries for large graphs
- [ ] Implement progressive loading in frontend
- [ ] Add background job processing for long workflows

### Code Quality
- [ ] Increase test coverage to >80%
- [ ] Add integration tests for full workflows
- [ ] Implement CI/CD pipeline
- [ ] Add code documentation generation
- [ ] Refactor common patterns into utilities

### Infrastructure
- [ ] Add Redis for caching and job queues
- [ ] Implement rate limiting and backpressure
- [ ] Add monitoring and logging dashboards
- [ ] Set up error tracking (Sentry or similar)
- [ ] Add database backup automation

---

## 📅 Implementation Priority

### Phase 1: Critical Improvements (Next 2-4 weeks)
1. ✅ Metadata extraction enhancement (8-9 hours) - **READY TO START**
2. Section-based citation grouping in UI (2-3 hours)
3. Reference metadata display and retraction checking (3-4 hours)

### Phase 2: User Experience (4-6 weeks)
1. In-text citation display throughout UI (4-5 hours)
2. Enhanced Problematic Paper context view (6-8 hours)
3. User annotations system (8-10 hours)
4. Citation impact dependency analysis (Phase A refinement) (6-8 hours)

### Phase 3: Analytics & Expansion (6-8 weeks)
1. Classification schema refinement (10-15 hours)
2. Dashboard metrics and visualizations (12-15 hours)
3. Multi-publisher support planning and POC (20-25 hours)

---

## 🔄 Status Tracking

**Current Focus**: Metadata extraction enhancement
- ✅ Backup created: `backups/run_1_baseline_20260115_224903/`
- ✅ Development plan complete: `METADATA_ENHANCEMENT_PLAN.md`
- ⬜ Phase 1: Update models
- ⬜ Phase 2: Enhanced XML extraction
- ⬜ Phase 3: Reference metadata parser
- ⬜ Phase 4: Integration & testing
- ⬜ Phase 5: Reprocess & compare

**Next Up**: 
- Complete metadata extraction implementation
- Reprocess 1000 papers with enhanced metadata
- Compare LLM outputs before/after improvements

---

## 💡 Ideas for Future Exploration

### Advanced Features
- **Citation Quality Score**: Single metric (0-100) summarizing citation health
- **Author Dashboard**: Personal view of how your work is being cited
- **Citation Correction Suggestions**: AI-generated alternative phrasings
- **Collaborative Review**: Multi-user annotation and discussion threads
- **Citation Network Visualization**: Interactive graph showing citation propagation
- **Temporal Analysis**: How citation patterns change over time
- **Peer Comparison**: How paper's citation quality compares to field average

### AI Model Improvements
- **Fine-tuning**: Train domain-specific models on human-verified examples
- **Ensemble Methods**: Combine multiple LLMs for higher accuracy
- **Active Learning**: Prioritize uncertain citations for human review
- **Explainable AI**: Better visualization of why citations were flagged
- **Multi-modal Analysis**: Incorporate figures, tables, and equations

---

**Last Updated**: January 15, 2026
**Status**: Active development - Priority on metadata extraction
