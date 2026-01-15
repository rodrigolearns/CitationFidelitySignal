# Citation Fidelity Signal
**Detecting and Evaluating Citation Accuracy in Scientific Literature Using LLM-Powered Analysis**

---

## 🎯 The Problem: Citation Misrepresentation

Scientific research builds upon prior work through citations. However, citations are not always accurate—papers may be **miscited, oversimplified, taken out of context, or misrepresented**. These low-fidelity citations can:

- Distort the scientific record
- Propagate misinformation through citation chains
- Misrepresent researchers' work and findings
- Undermine the credibility of scientific literature

Traditionally, verifying citation accuracy required manual review of both the citing paper and the referenced work—a time-consuming process that doesn't scale.

---

## 💡 The Solution: LLM-Powered Citation Verification

With modern Large Language Models (LLMs), we can now **automatically evaluate citation fidelity at scale**. This project enables researchers to:

- ✅ **Check citations of their own work** to ensure accurate representation
- ✅ **Identify potentially problematic citations** that may misrepresent findings
- ✅ **Track citation propagation** through research networks
- ✅ **Review flagged citations** through an intuitive web interface

---

## 🔬 Current Implementation: eLife Proof-of-Concept

This project demonstrates citation fidelity analysis using **eLife articles** as a closed-loop test case. We chose eLife because:

- High-quality JATS XML format with structured metadata
- Open access via GitHub repository
- Well-documented API for article retrieval
- Strong citation network within eLife publications

### Current Scope

The system processes recent eLife articles through a multi-stage pipeline:

**Initial Scan (1,000 papers)**
- Scanned 1,000 most recently published eLife articles (March 2025 - January 2026)
- Time: ~5 minutes (API scan)

**↓ Workflow 1: Graph Construction & Qualification**
- **Input**: 1,000 papers scanned
- **Output**: 
  - 658 citing papers (cite other eLife papers)
  - 1,463 referenced papers (cited by others)
  - 1,692 citation relationships
  - 1,688 qualified citations (with evidence retrieved)
- **Time**: ~5 min (XML download) + ~15 sec (graph build) + ~11 min (qualification)

**↓ Workflow 2: Rapid Citation Screening**
- **Input**: 1,688 qualified citations
- **Output**: 1,678 citations classified
  - ✅ **SUPPORT**: 2,920 contexts (67.7%) - Citations are accurate
  - ⚠️ **Suspicious**: 1,394 contexts (32.3%) across 461 papers
    - NOT_SUBSTANTIATE: 1,245 contexts (28.9%)
    - IRRELEVANT: 74 contexts (1.7%)
    - CONTRADICT: 41 contexts (1.0%)
    - OVERSIMPLIFY: 34 contexts (0.8%)
- **Time**: ~8 minutes (parallel processing)
- **Result**: **461 papers with suspicious citations** identified for deeper review

**↓ Workflow 3: Deep Verification** (of suspicious citations)
- **Input**: 461 papers with 861 suspicious citation relationships (1,394 contexts)
- **Processing**: 569 citations with suspicious contexts verified (524 processed, 45 skipped)
- **Output**: 757 contexts analyzed with enhanced evidence (abstract + 15 segments)
  - ✅ **Corrected to Support**: 248 contexts (32.8%) - False positives from first round
  - ⚠️ **Confirmed Suspicious**: 509 contexts (67.2%) - First-round was correct
- **Time**: ~29.5 minutes (parallel processing with DeepSeek-Reasoner)
- **Key Insight**: Second-round verification corrected ~33% of first-round false positives

**↓ Workflow 4: Quality Analytics**
- **Input**: All classified citations and verification results
- **Output**: Comprehensive statistical analysis
  - Overall citation fidelity rate: **69.4%**
  - Problematic citations: 1,320 / 4,314 contexts (30.6%)
  - False positive rate from first round: 32.4% (248 corrected out of 765 verified)
  - Most common issues: NOT_SUBSTANTIATE (64.3%), SUPPORT after correction (22.5%)
  - Recommendations: 40% NEEDS_REVIEW, 37.5% MISREPRESENTATION, 22.5% ACCURATE
- **Time**: ~1 second
- **Result**: Statistics saved to `data/analysis/pipeline_stats.json`

**↓ Workflow 5: Impact Assessment**
- **Input**: Select problematic papers for deep analysis (on-demand or batch)
- **Processing**: Deep analysis with full paper context using DeepSeek-Reasoner
  - Tested on top 10 most problematic papers (10-52 suspicious citations each)
  - Uses "thinking" mode for thorough analysis
- **Output**: Detailed impact classifications
  - 8 papers: MODERATE_CONCERN
  - 2 papers: MINOR_CONCERN  
  - Detailed report showing citation-level analysis and patterns
- **Time**: ~3.5 minutes per paper average (8-35 minutes depending on complexity)
  - Simple papers (10-15 citations): ~8-10 minutes
  - Complex papers (50+ citations): ~35 minutes
  - Parallel processing: 5 papers concurrently
- **Note**: Much slower than Workflows 2-3 due to full context analysis (by design)

**Final Dataset:**
- 2,100 total papers in citation network
- 1,692 citation relationships analyzed
- 1,678 citations classified in first round
- 757 suspicious contexts verified in second round
- 509 confirmed problematic contexts (after deep verification)
- 461 papers with confirmed issues flagged for manual review
- All data stored in Neo4j graph database for network analysis

### Future Vision
Eventually, this will become a **user-facing service** where researchers can:
1. Submit their paper's PDF or DOI
2. Automatically retrieve all papers citing their work
3. Review citation quality assessments
4. Identify and address misrepresentations

---

## 🏗️ System Architecture

The Citation Fidelity Signal system consists of five interconnected workflows:

### **Workflow 1: Graph Construction & Evidence Retrieval**

This workflow discovers citation relationships and retrieves supporting evidence from source papers.

**What It Does:**
1. **Citation Discovery**: Identifies eLife papers that cite other eLife papers
2. **Context Extraction**: Extracts 4-sentence windows around each in-text citation
   - 2 sentences before the citation
   - The sentence containing the citation
   - 1 sentence after the citation
3. **Evidence Retrieval**: Finds relevant passages from the referenced paper using **hybrid retrieval**:
   - **BM25**: Keyword-based search to narrow down candidates (top 20 paragraphs)
   - **Semantic Embeddings**: Sentence-transformer models to find semantically similar passages (top 3-5)
   - **Why chunks?** For efficiency—we don't need to send entire papers to the LLM, only the most relevant passages
4. **Graph Storage**: Stores citation network in **Neo4j** for:
   - Easy traversal of citation chains
   - Analysis of citation propagation
   - Detection of recurring miscitations across multiple papers

**Technologies:** JATS XML parsing | Hybrid retrieval (BM25 + semantic embeddings) | Neo4j graph database | Parallel processing for scale

---

### **Workflow 2: Rapid Citation Screening**

This workflow uses LLMs to perform fast initial screening of all citations to identify potentially problematic ones.

**What It Does:**
1. **Rapid LLM Screening**: For each citation context + evidence pair:
   - Sends the citation context (how the citing paper uses the reference)
   - Sends the evidence segments (relevant passages from the referenced paper)
   - Uses DeepSeek Chat or GPT-4o-mini for fast classification

2. **Classification Categories** (as defined in the LLM prompt):
   - **SUPPORT** - Evidence supports the citation claim (displayed in green)
   - **CONTRADICT** - Evidence contradicts the citation
   - **NOT_SUBSTANTIATE** - Evidence doesn't support the specific claim
   - **OVERSIMPLIFY** - Citation oversimplifies nuanced findings
   - **IRRELEVANT** - Evidence unrelated to citation
   - **MISQUOTE** - Citation misquotes or misattributes findings
   - **INDIRECT** - Citation treats secondary source as primary
   - **ETIQUETTE** - Courtesy citation without substantive support
   
   **Note:** In the web interface, SUPPORT classifications are shown in green. All other categories are color-coded based on the LLM's confidence score (high confidence = red, medium = orange, low = yellow) to help prioritize manual review.

3. **Data Storage**: Results are stored in the Neo4j graph on citation relationships, including:
   - Classification category and confidence
   - LLM's reasoning
   - Evidence used for evaluation
   - Support for manual review and overrides

4. **Manual Review Interface**: Web application for researchers to:
   - Browse all analyzed citations
   - Filter by classification (show only suspicious citations)
   - View side-by-side: citation context vs. reference evidence
   - Override LLM classification if needed
   - Add comments for further investigation
   - Mark citations as manually reviewed

**How It Works:**

The screener understands that different types of citations require different evaluation criteria:

- **Data Source Citations** ("We analyzed datasets from Smith 2020, Jones 2021..."): Verifies the reference actually provided the data, not whether it discusses the research question
- **Finding Citations** ("Studies show X causes Y (Smith 2020)"): Checks whether the reference supports the claim and identifies oversimplifications
- **Background Citations**: Confirms the reference explored the topic
- **Attribution Citations**: Verifies correct attribution of discoveries

This type-aware approach dramatically reduces false positives - preventing the system from incorrectly flagging valid data source citations as unsupported.

**Technologies:** DeepSeek Chat (or GPT-4o-mini) for rapid screening | Hybrid retrieval | React + Material-UI web interface

---

### **Workflow 3: Deep Citation Verification**

For citations flagged as potentially problematic in Workflow 2, this workflow performs an in-depth verification with expanded evidence to confirm or correct the initial screening.

**What It Does:**
1. **Selective Processing**: Only re-evaluates citations classified as:
   - CONTRADICT
   - NOT_SUBSTANTIATE
   - OVERSIMPLIFY
   - IRRELEVANT
   - MISQUOTE
   
   (SUPPORT citations are already verified; INDIRECT and ETIQUETTE are lower priority)

2. **Deeper Evidence Gathering**:
   - Retrieves the full abstract for complete context
   - Expands from 5 to 15 evidence segments for comprehensive analysis
   - **Smart Section Targeting**: Automatically focuses on the right parts of the reference paper:
     - Data source citations → Methods and Results sections
     - Finding citations → Results and Discussion sections
     - Background citations → Abstract and Introduction
   - Quality checks ensure evidence is relevant and non-contradictory

3. **In-Depth Re-Analysis**:
   - Uses a more capable AI model (DeepSeek Reasoner or GPT-4o) for higher accuracy
   - Reviews the initial screening with significantly more evidence
   - Re-checks the citation type to catch mistakes (e.g., data sources flagged as unsupported claims)
   - Follows a systematic evaluation process: abstract → methods → results → discussion → consistency
   - Either confirms or corrects the initial classification
   - Provides both technical analysis and plain-language explanations

4. **Clear Results for Researchers**: Each verification provides:
   - **Plain-language summary** of what was found
   - **Key evidence** that supports the assessment
   - **Recommendation** - whether the citation is accurate, needs review, or is a misrepresentation
   - **Detailed analysis** for those who want to dig deeper

5. **Results Storage**: Deep verifications are added to the graph, preserving both initial screening and deep verification assessments for comparison. This allows researchers to see the progression of analysis and understand when classifications were corrected.

6. **Thorough Coverage**:
   - Checks every place where a paper cites the reference (not just the first mention)
   - Each citation context gets independent verification
   - Helps identify inconsistent or contradictory citation patterns

**Why This Matters:** Workflow 3 focuses intensive analysis only on suspicious citations, dramatically reducing false positives while keeping costs reasonable.

**Technologies:** DeepSeek Reasoner (thinking mode) or GPT-4o | Enhanced evidence retrieval | Type-aware analysis

---

### **Workflow 4: Quality Analytics & Problem Detection**

After all citations have been processed and verified, this workflow performs comprehensive analysis to identify patterns and problematic papers.

**What It Does:**
1. **Pipeline Statistics**: Generates comprehensive metrics about:
   - Total articles and citations processed
   - Classification distribution (SUPPORT, NOT_SUBSTANTIATE, etc.)
   - Citation type distribution (CONCEPTUAL, METHODOLOGICAL, etc.)
   - Second-round verification outcomes (CONFIRMED vs. CORRECTED)
   - Overall citation fidelity rate
   - False positive rate

2. **Problematic Papers Identification**: Detects "repeat offenders":
   - Papers with ≥2 problematic citations (NOT_SUBSTANTIATE, CONTRADICT, MISQUOTE)
   - Ranks by severity (number of problematic citations)
   - Displays in web interface for easy access

3. **Quality Metrics**:
   - Overall citation fidelity rate across the corpus
   - Second-round verification accuracy
   - Evidence quality distribution

**Output:**
- JSON file with detailed statistics (`data/analysis/pipeline_stats.json`)
- "Problematic Papers" table in web interface showing top offenders
- Console report with visual charts and key findings

**Why This Matters:** Identifies systematic issues and helps researchers understand citation patterns. Highlights papers that may require deeper investigation or author notification. Automatically runs after Workflow 3.

**Technologies:** Neo4j graph queries | Python data analysis | React data visualization

---

### **Workflow 5: Impact Assessment & Reporting**

For papers identified as "repeat offenders" in Workflow 4 (≥2 problematic citations), this workflow performs comprehensive impact analysis to assess how miscitations affect the paper's scientific validity.

**What It Does:**

**Phase A: Citation Analysis**
- Deep reading of full paper texts (citing paper + all referenced papers)
- Assessment of each miscitation's validity and impact on paper conclusions
- Identification of whether miscitations are central to findings or peripheral
- Detailed quotes and evidence from both papers to support assessment
- Uses DeepSeek Chat for cost-optimized deep reading (~$0.07 per paper vs $0.42 with GPT-5.2)

**Phase B: Synthesis & Reporting**
- Pattern detection across all problematic citations
- Assessment of cumulative impact on paper validity
- Classification: MINOR_ISSUES, MODERATE_CONCERNS, or MAJOR_PROBLEMS
- Comprehensive report with:
  - Executive summary for quick understanding
  - Detailed analysis of each citation's impact
  - Section-by-section breakdown (Introduction, Methods, Results, Discussion)
  - Strategic recommendations for reviewers, readers, and authors
- Uses DeepSeek Reasoner (thinking mode) for sophisticated analysis (~$0.01 per paper vs $0.12 with GPT-5.2)

**Why This Matters:** Provides human-readable, actionable insights for researchers, reviewers, and editors. Distinguishes between minor writing issues and problems that genuinely affect scientific validity. **87% cheaper than GPT-5.2** while maintaining quality.

**Technologies:** DeepSeek Chat & Reasoner | Full-text analysis | Pattern synthesis | Strategic assessment

---

## 📊 Data Flow

```
eLife Papers (GitHub)
        ↓
   [Download & Parse]
        ↓
   Workflow 1: Graph Construction & Evidence Retrieval
        ├─→ Extract Citations → Build Neo4j Graph
        ├─→ Extract Contexts (4-sentence windows)
        └─→ Retrieve Evidence (BM25 + Semantic, 5 segments)
        ↓
   Workflow 2: Rapid Citation Screening (DeepSeek Chat)
        ├─→ Quick LLM classification of all citations
        └─→ Store results in Neo4j
        ↓
        ├─→ [SUPPORT] → Ready for Review
        │
        └─→ [Suspicious: CONTRADICT, NOT_SUBSTANTIATE, etc.]
                ↓
           Workflow 3: Deep Citation Verification (DeepSeek Reasoner)
                ├─→ Enhanced Evidence Retrieval (15 segments + abstract)
                ├─→ In-depth re-analysis with type-aware logic
                └─→ Store verified results in Neo4j
                ↓
           Workflow 4: Quality Analytics & Problem Detection
                ├─→ Generate pipeline statistics
                ├─→ Identify problematic papers (≥2 issues)
                └─→ Display in web interface
                ↓
           Workflow 5: Impact Assessment & Reporting (for problematic papers)
                ├─→ Phase A: Citation Analysis (full text reading)
                ├─→ Phase B: Synthesis & Reporting (pattern detection)
                └─→ Generate comprehensive impact report
                ↓
   Web Interface (Manual Review + Analytics Dashboard + Impact Reports)
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.9+
- Node.js 16+
- Docker (for Neo4j)
- OpenAI API key

### Installation

1. **Clone the repository**
   ```bash
   git clone <repo-url>
   cd CitationFidelitySignal
   ```

2. **Set up Python environment**
   ```bash
   pip install -r requirements.txt
   python3 setup.py develop
   ```

3. **Configure environment**
   ```bash
   cp env.example .env
   # Edit .env and add your OpenAI API key:
   # OPENAI_API_KEY=sk-...
   # OPENAI_MODEL=gpt-4o-mini
   ```

4. **Start Neo4j database**
   ```bash
   docker-compose up -d
   ```
   - Access Neo4j Browser: http://localhost:7474
   - Username: `neo4j`
   - Password: `elifecitations2024`

5. **Run the complete workflow**
   ```bash
   # Workflow 1: Graph Construction (10 papers for testing)
   python3 scripts/1_graph_construction.py --limit 10
   # → Automatically cleans up XMLs for articles without eLife citations

   # Workflow 2: Rapid Citation Screening (DeepSeek Chat)
   python3 scripts/2_rapid_screening.py --batch-size 10

   # Workflow 3: Deep Citation Verification (DeepSeek Reasoner)
   python3 scripts/3_deep_verification.py --batch-size 5
   # → Automatically cleans up ALL remaining XMLs after completion
   # → Automatically runs Workflow 4: Quality Analytics
   
   # Workflow 4: Quality Analytics (runs automatically after Workflow 3)
   python3 scripts/4_quality_analytics.py
   
   # Workflow 5: Impact Assessment (for problematic papers)
   python3 scripts/5_impact_assessment.py <article_id>
   # Example: python3 scripts/5_impact_assessment.py 84538
   ```

   **Note on XML Storage:**
   - **Default behavior**: All XMLs are kept after processing (useful for debugging and re-analysis)
   - **Workflow 4**: Automatically runs after Workflow 3 to generate statistics and identify problematic papers
   - To enable XML cleanup (delete files to save space), use `--enable-cleanup` flag on Workflow 1 or 3

6. **Start the web interface**
   ```bash
   # Terminal 1: Start backend
   cd web_interface/backend
   python3 main.py

   # Terminal 2: Start frontend
   cd web_interface/frontend
   npm install
   npm run dev
   ```

7. **View results**
   - Open http://localhost:3000
   - Browse classified citations
   - Filter by classification category
   - Review suspicious citations

---

## 📁 Project Structure

```
CitationFidelitySignal/
├── elife_graph_builder/           # Core workflow modules
│   ├── classifiers/                # LLM-based screening & verification
│   │   ├── llm_classifier.py       # Workflow 2: Rapid screening
│   │   ├── second_round_classifier.py  # Workflow 3: Deep verification
│   │   └── deep_reading_analyzer.py    # Workflow 5 Phase A: Citation analysis
│   ├── analyzers/                  # Pattern analysis & synthesis
│   │   └── impact_analyzer.py      # Workflow 5 Phase B: Synthesis
│   ├── data_ingestion/             # Article downloading
│   ├── extractors/                 # Context extraction
│   ├── graph/                      # Neo4j integration
│   ├── matchers/                   # Citation matching
│   ├── parsers/                    # JATS XML parsing
│   ├── retrievers/                 # Evidence retrieval (BM25 + Semantic)
│   ├── prompts/                    # LLM prompts for each workflow
│   ├── models.py                   # Data models
│   ├── graph_construction.py       # Workflow 1: Graph building
│   ├── evidence_retrieval.py       # Workflow 1: Evidence retrieval
│   ├── deep_verification.py        # Workflow 3: Deep verification
│   └── impact_assessment.py        # Workflow 5: Impact assessment
├── scripts/                        # Executable workflow scripts
│   ├── 1_graph_construction.py     # Workflow 1: Graph construction
│   ├── 2_rapid_screening.py        # Workflow 2: Rapid screening
│   ├── 3_deep_verification.py      # Workflow 3: Deep verification
│   ├── 4_quality_analytics.py      # Workflow 4: Quality analytics
│   ├── 5_impact_assessment.py      # Workflow 5: Impact assessment
│   ├── clear_neo4j.py              # Reset database
│   └── clear_evidence.py           # Clear evidence data
├── web_interface/                  # Manual review interface
│   ├── backend/                    # FastAPI server
│   └── frontend/                   # React + Material-UI
├── data/                           # Downloaded articles + cache
├── tests/                          # Unit tests
└── docs/                           # Sprint documentation
```

---

## 📈 Current Status & Metrics

### Workflow Capabilities
- ✅ **Article Import**: Downloads and parses eLife JATS XML
- ✅ **Citation Discovery**: Identifies eLife→eLife citations
- ✅ **Context Extraction**: 4-sentence windows around in-text citations
- ✅ **Evidence Retrieval**: Hybrid BM25 + semantic search (min 3 segments per context)
- ✅ **Rapid Screening**: DeepSeek Chat for fast classification
- ✅ **Deep Verification**: DeepSeek Reasoner for in-depth analysis
- ✅ **Impact Assessment**: Full paper analysis for problematic citations
- ✅ **Manual Review**: Web interface with filtering and annotation

### Performance
- Processes 50-100 articles per minute
- Retrieves 3-5 high-quality evidence segments per citation
- Successfully classifies ~95% of citations
- Cost-effective at ~$0.002 per citation

---

## 🔮 Future Developments

### Priority Improvements

#### 1. **Workflow 2: Classification Granularity** 🎯
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

#### 2. **In-Text Citation Display** 📝
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

#### 3. **User Annotations & Notes** 💬
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

#### 4. **Phase A: Citation Impact Assessment Depth** 🔬
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

#### 5. **Problematic Paper Analysis: Enhanced Citation Context** 📊
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

#### 6. **Classification Schema Refinement** 🏷️
**Current Issue**: Over-reliance on generic categories reduces system utility.

**Action Items**:
- [ ] Conduct classification distribution analysis on processed corpus
- [ ] Identify patterns in miscategorized citations through manual review
- [ ] A/B test alternative prompt formulations
- [ ] Add few-shot examples to prompts for edge cases
- [ ] Implement confidence calibration for borderline classifications
- [ ] Consider hierarchical classification (primary + secondary tags)

---

## 🔮 Future Work

This project is a proof-of-concept with significant room for growth:

### Planned Analytics
- [ ] **Total Citation Count**: Number of eLife→eLife citations discovered
- [ ] **Classification Distribution**: Breakdown by category (SUPPORT, CONTRADICT, etc.)
- [ ] **Manual Review Statistics**: Percentage of citations manually reviewed
- [ ] **Agreement Analysis**: LLM vs. human reviewer alignment rates
- [ ] **Citation Propagation Maps**: Visualize how miscitations spread through networks

### Expansion Goals
- [ ] **Multi-Publisher Support**: Extend beyond eLife to PubMed, arXiv, bioRxiv
- [ ] **PDF Processing**: Handle papers without structured XML
- [ ] **User Submission Portal**: Allow researchers to submit their DOI/PDF
- [ ] **Automated Citation Discovery**: Find all papers citing a given work
- [ ] **Citation Quality Dashboard**: Show citation health for any paper
- [ ] **API Service**: Programmatic access to citation assessments
- [ ] **Citation Propagation Analysis**: Track how errors spread through citation chains

### Research Questions
- **How common are low-fidelity citations in scientific literature?**
- **Do certain fields or topics have higher rates of miscitation?**
- **Can we predict which citations are likely to be problematic?**
- **How do miscitations propagate through citation networks?**
- **What interventions can improve citation accuracy?**

---

## 🤝 Contributing

This is a research project exploring the potential of LLMs for citation verification. Contributions are welcome!

Areas for contribution:
- Improving evidence retrieval algorithms
- Enhancing LLM prompt design
- Adding support for new publishers/formats
- Building better visualization tools
- Testing on diverse paper collections

---

## 📄 License

**Creative Commons Attribution-NonCommercial 4.0 International (CC BY-NC 4.0)**

This project is free to use for:
- ✅ Academic research
- ✅ Personal projects
- ✅ Non-profit organizations
- ✅ Educational purposes

**Commercial use requires a separate license.** If you wish to use this system commercially or monetize it in any way, please contact the creator for licensing terms.

For the full license text, see: https://creativecommons.org/licenses/by-nc/4.0/

---

## 📚 Citation

If you use this work in your research, please cite:

```
Rosas-Bertolini, Rodrigo (2026). Citation Fidelity Signal: 
Detecting and Evaluating Citation Accuracy in Scientific Literature 
Using LLM-Powered Analysis. GitHub repository.
```

---

## 🙏 Acknowledgments

- **eLife Sciences** for providing open-access articles and structured data
- **OpenAI** for GPT-4o-mini API access
- **Neo4j** for graph database capabilities
- **Sentence Transformers** for semantic embedding models

---

## 📧 Contact

**Rodrigo Rosas-Bertolini**  
Creator & Lead Developer

📧 For commercial licensing inquiries, collaborations, or questions:  
🔗 LinkedIn: [www.linkedin.com/in/rodrigo-rosas-bertolini-6a0743111](https://www.linkedin.com/in/rodrigo-rosas-bertolini-6a0743111)

---

**Built with the goal of improving citation accuracy and scientific integrity through automated, scalable analysis.**
