**Product Requirements Document (PRD): Citation Fidelity Microservice**

---

**Product Title:** Citation Fidelity Verification Microservice

**Author:** [Your Name]

**Created:** [Date]

**Overview:**
This microservice provides an API to evaluate the fidelity of in-text citations within a scholarly paper. Users submit a "central paper" (under review) and all "cited papers" (referenced sources). The service returns a detailed citation-by-citation analysis, assessing whether each citation accurately reflects its source, classifying potential misrepresentations using a fine-grained schema, and generating a visualization-ready JSON payload.

---

### **Goals:**

* Detect citation inaccuracies using LLM-based evaluation.
* Return citation context, matching reference content, and classification.
* Provide data for downstream visualization.
* Work fully offline (no paper fetching); user supplies all PDFs or text.

---

### **User Stories:**

1. As a researcher, I want to check if the citations in my draft are accurate.
2. As a journal editor, I want to identify misrepresented or unsupported references.
3. As a reviewer, I want to quickly audit claims against referenced content.

---

### **Core Features:**

#### 1. **API Endpoint**

* `POST /analyze`

  * Input: JSON or multipart form-data

    * `central_paper`: full text or PDF
    * `cited_papers`: list of papers (full text or PDFs) keyed by reference ID
  * Output: JSON response with analysis for each in-text citation:

    * `citation_id`
    * `citation_context`: 1-4 sentence window
    * `matched_chunks`: array of evidence segments from cited paper
    * `classification`: label from schema
    * `justification`: LLM rationale
    * `confidence` (optional)
    * `risk_level`: green/yellow/red based on severity

#### 2. **Citation Context Extraction**

* Extract in-text citations and capture ±1–2 sentence window.
* Handle numeric (`[12]`) and author-year (`(Smith et al., 2020)`) styles.

#### 3. **Reference Chunking & Indexing**

* Split each cited paper into paragraphs or fixed-size text blocks.
* Compute embeddings (e.g., SciBERT) for semantic similarity.
* Optional: create BM25 index for lexical match.

#### 4. **Evidence Retrieval**

* Retrieve top-K relevant chunks using hybrid search (semantic + lexical).
* Cutoff `K` is configurable via settings.

#### 5. **LLM-Based Classification**

* Inputs: `citation_context`, `evidence_chunks`
* Output: category from schema with justification
* Categories (priority order):

  * `ACCURATE`
  * `CONTRADICT`
  * `NOT_SUBSTANTIATE`
  * `IRRELEVANT`
  * `OVERSIMPLIFY`
  * `MISQUOTE`
  * `INDIRECT`
  * `ETIQUETTE`
* Apply highest-priority label if multiple apply.

#### 6. **Visualization Output**

* Include metadata for display:

  * Matched evidence text
  * Classification badge (label + color code)
  * Risk score color (green/yellow/red)
  * Processing time/logging info
  * Summary stats: total citations, distribution of labels

---

### **Settings & Configuration:**

* `max_evidence_chunks`: default 3
* `llm_model`: model identifier or API key source
* `schema_version`: allows updates to category definitions
* `use_bm25`: toggle for keyword-based fallback

---

### **Non-Goals:**

* No automatic paper downloading (user must supply text)
* No document OCR (assumes text or well-parsed PDFs)
* No web UI in this PRD (but outputs are frontend-friendly)

---

### **Acceptance Criteria:**

* Input: user submits a central paper and cited sources.
* Output: JSON contains accurate citation contexts, relevant evidence, and correct classification.
* Each citation gets a color-coded risk label.
* Service processes average-length paper (<30 refs) in under 2 minutes.

---

### **Nice-to-Haves (Future Extensions):**

* Async processing for large jobs
* Multi-language support
* PDF visual overlay
* UI dashboard (not part of core PRD)

---

### **Dependencies:**

* PyMuPDF / PDFPlumber for PDF parsing
* SentenceTransformers / SciBERT for embeddings
* BM25 (e.g., Whoosh) for lexical search
* OpenAI / HuggingFace API for LLM classification

---

### **Security & Privacy:**

* No persistent storage by default
* Option to disable logging for sensitive data
* Does not access external databases or APIs
