# Citation Fidelity Signal

> **Detecting and Evaluating Citation Accuracy in Scientific Literature Using LLM-Powered Analysis**

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
- **Input**: eLife articles that cite other eLife articles
- **Output**: Citation fidelity assessments with evidence and LLM evaluations
- **Storage**: Neo4j graph database for network traversal and analysis

### Future Vision
Eventually, this will become a **user-facing service** where researchers can:
1. Submit their paper's PDF or DOI
2. Automatically retrieve all papers citing their work
3. Review citation quality assessments
4. Identify and address misrepresentations

---

## 🏗️ System Architecture

The system is composed of two main pipelines:

### **Part 1: Citation Graph & Evidence Extraction Pipeline**

This pipeline discovers citation relationships and retrieves supporting evidence from source papers.

**What It Does:**
1. **Citation Discovery**: Identifies eLife papers that cite other eLife papers
2. **Context Extraction**: Extracts 4-sentence windows around each in-text citation
   - 2 sentences before the citation
   - The sentence containing the citation
   - 1 sentence after the citation
3. **Evidence Retrieval**: Finds relevant passages from the referenced paper using **hybrid retrieval**:
   - **Stage 1 (BM25)**: Keyword-based search to narrow down candidates (top 20 paragraphs)
   - **Stage 2 (Semantic Embeddings)**: Sentence-transformer models to find semantically similar passages (top 3-5)
   - **Why chunks?** For efficiency—we don't need to send entire papers to the LLM, only the most relevant passages
4. **Graph Storage**: Stores citation network in **Neo4j** for:
   - Easy traversal of citation chains
   - Analysis of citation propagation
   - Detection of recurring miscitations across multiple papers

**Key Technologies:**
- **JATS XML Parser**: Extracts metadata, references, and in-text citations
- **Hybrid Retriever**: BM25 (keyword) + Sentence Transformers (semantic)
- **Neo4j Graph Database**: Stores articles as nodes, citations as edges
- **Async/Parallel Processing**: Handles large-scale data efficiently

---

### **Part 2: Citation Fidelity Evaluation System**

This pipeline uses LLMs to assess whether citations accurately represent the referenced work.

**What It Does:**
1. **LLM Classification**: For each citation context + evidence pair:
   - Sends the citation context (how the citing paper uses the reference)
   - Sends the evidence segments (relevant passages from the referenced paper)
   - Uses GPT-4o-mini to classify the citation fidelity

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

3. **Data Storage**: Stores classification results in Neo4j on `CITES` relationship edges:
   ```json
   {
     "citation_contexts": [
       {
         "instance_id": 1,
         "context_text": "...",
         "section": "Introduction",
         "evidence_segments": [...],
         "classification": {
           "category": "SUPPORT",
           "confidence": 0.92,
           "justification": "...",
           "classified_at": "2026-01-13T...",
           "manually_reviewed": false,
           "user_classification": null,
           "user_comment": null
         }
       }
     ]
   }
   ```

4. **Manual Review Interface**: Web application for researchers to:
   - Browse all analyzed citations
   - Filter by classification (show only suspicious citations)
   - View side-by-side: citation context vs. reference evidence
   - Override LLM classification if needed
   - Add comments for further investigation
   - Mark citations as manually reviewed

**LLM Prompt Design:**

The system uses a carefully crafted prompt (see `elife_graph_builder/classifiers/llm_classifier.py`) that:
- Explains the evaluation task clearly
- Provides the citation context from the citing paper
- Includes 3 evidence segments from the reference paper (with similarity scores)
- Lists all classification categories with detailed definitions
- Includes an example classification (OVERSIMPLIFY case)
- Requests structured JSON output with category, confidence, and justification

**Key Technologies:**
- **OpenAI GPT-4o-mini**: Cost-effective, reliable LLM for classification
- **Prompt Engineering**: Structured prompts with examples for consistent results
- **React + Material-UI**: Professional web interface
- **FastAPI**: Backend API for data access

---

## 📊 Data Flow

```
eLife Papers (GitHub)
        ↓
   [Download & Parse]
        ↓
   Extract Citations → Build Neo4j Graph (Articles + CITES edges)
        ↓
   Extract Contexts (4-sentence windows)
        ↓
   Retrieve Evidence (BM25 + Semantic)
        ↓
   Store on CITES edges
        ↓
   LLM Classification (GPT-4o-mini)
        ↓
   Store Results in Neo4j
        ↓
   Web Interface (Manual Review)
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

5. **Run the full pipeline**
   ```bash
   # Step 1: Import articles and build citation graph (10 papers for testing)
   python3 scripts/run_streaming_pipeline.py --limit 10

   # Step 2: Extract contexts and retrieve evidence
   python3 scripts/continue_qualification.py --batch-size 10

   # Step 3: Classify citations with LLM
   python3 scripts/classify_citations.py --batch-size 10
   ```

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
├── elife_graph_builder/           # Core pipeline modules
│   ├── classifiers/                # LLM-based classification
│   │   └── llm_classifier.py       # GPT-4o-mini integration + prompt
│   ├── data_ingestion/             # Article downloading
│   ├── extractors/                 # Context extraction
│   ├── graph/                      # Neo4j integration
│   ├── matchers/                   # Citation matching
│   ├── parsers/                    # JATS XML parsing
│   ├── retrievers/                 # Evidence retrieval (BM25 + Semantic)
│   ├── models.py                   # Data models
│   ├── streaming_pipeline.py       # Part 1: Graph building
│   └── qualification_pipeline.py   # Part 1: Context + Evidence
├── scripts/                        # Executable scripts
│   ├── run_streaming_pipeline.py   # Import articles
│   ├── continue_qualification.py   # Add contexts/evidence
│   ├── classify_citations.py       # LLM classification
│   └── clear_neo4j.py              # Reset database
├── web_interface/                  # Manual review interface
│   ├── backend/                    # FastAPI server
│   └── frontend/                   # React + Material-UI
├── data/                           # Downloaded articles + cache
├── tests/                          # Unit tests
└── docs/                           # Sprint documentation
```

---

## 📈 Current Status & Metrics

### Pipeline Capabilities
- ✅ **Article Import**: Downloads and parses eLife JATS XML
- ✅ **Citation Discovery**: Identifies eLife→eLife citations
- ✅ **Context Extraction**: 4-sentence windows around in-text citations
- ✅ **Evidence Retrieval**: Hybrid BM25 + semantic search (min 3 segments per context)
- ✅ **LLM Classification**: GPT-4o-mini with structured prompts
- ✅ **Manual Review**: Web interface with filtering and annotation

### Performance Metrics
- **Processing Speed**: ~50-100 articles/minute (depends on API limits)
- **Evidence Quality**: 3-5 evidence segments per citation context
- **LLM Success Rate**: ~95% (with GPT-4o-mini and truncated evidence)
- **Cost**: ~$0.002 per citation classification

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

[Add your license here]

---

## 📚 Citation

If you use this work in your research, please cite:

```
[Add citation format]
```

---

## 🙏 Acknowledgments

- **eLife Sciences** for providing open-access articles and structured data
- **OpenAI** for GPT-4o-mini API access
- **Neo4j** for graph database capabilities
- **Sentence Transformers** for semantic embedding models

---

## 📧 Contact

[Add contact information]

---

**Built with the goal of improving citation accuracy and scientific integrity through automated, scalable analysis.**
