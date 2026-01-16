"""FastAPI backend for eLife Citation Qualification Viewer."""
import sys
from pathlib import Path

# Add project root to Python path
project_root = Path(__file__).parent.parent.parent
sys.path.insert(0, str(project_root))

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from neo4j_client import Neo4jClient

# Import workflow components at startup (so .env is loaded before any requests)
from elife_graph_builder.impact_assessment import ImpactAssessmentWorkflow
from elife_graph_builder.config import Config

# Global Neo4j client
neo4j_client = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifecycle manager for FastAPI app."""
    global neo4j_client
    # Startup
    neo4j_client = Neo4jClient()
    yield
    # Shutdown
    if neo4j_client:
        neo4j_client.close()


app = FastAPI(
    title="eLife Citation Qualification API",
    description="API for viewing citation qualification data",
    version="1.0.0",
    lifespan=lifespan
)

# CORS middleware for React frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:3001", "http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "eLife Citation Qualification API",
        "docs": "/docs"
    }


@app.get("/api/stats")
async def get_stats():
    """Get overall statistics."""
    try:
        stats = neo4j_client.get_stats()
        return stats
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/citations")
async def get_citations():
    """
    Get list of all qualified citations.
    
    Returns:
        List of citations with source/target metadata.
    """
    try:
        citations = neo4j_client.get_qualified_citations()
        return {
            "count": len(citations),
            "citations": citations
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/citations/{source_id}/{target_id}")
async def get_citation_detail(source_id: str, target_id: str):
    """
    Get detailed citation data including contexts and evidence.
    
    Args:
        source_id: Source article ID
        target_id: Target article ID
        
    Returns:
        Detailed citation data with contexts and evidence segments.
    """
    try:
        citation = neo4j_client.get_citation_detail(source_id, target_id)
        
        if not citation:
            raise HTTPException(
                status_code=404, 
                detail=f"Citation not found: {source_id} → {target_id}"
            )
        
        return citation
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/problematic-papers")
async def get_problematic_papers():
    """
    Get list of papers with multiple problematic citations (repeat offenders).
    
    Returns:
        List of papers with counts of problematic citations, sorted by severity.
    """
    try:
        papers = neo4j_client.get_problematic_papers()
        return papers
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/problematic-paper/{article_id}")
async def get_problematic_paper_detail(article_id: str):
    """
    Get detailed information about a problematic paper.
    
    Args:
        article_id: Article ID of the problematic citing paper
    
    Returns:
        Paper metadata, all citations, and Workflow 5 impact analysis (if available)
    """
    try:
        paper_data = neo4j_client.get_problematic_paper_detail(article_id)
        
        if not paper_data:
            raise HTTPException(status_code=404, detail=f"Paper not found: {article_id}")
        
        return paper_data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/api/problematic-paper/{article_id}/analyze")
async def analyze_problematic_paper(article_id: str):
    """
    Trigger Workflow 5: Impact Assessment for a problematic paper.
    
    This is a long-running operation (~2-3 minutes with DeepSeek batching) that performs:
    - Phase A: Citation Analysis - Deep reading of full papers
    - Phase B: Synthesis & Reporting - Pattern detection and comprehensive report
    
    Args:
        article_id: Article ID to analyze
    
    Returns:
        Complete impact analysis with classification and report
    """
    try:
        import aiohttp
        
        # Check if any version of the XML exists
        samples_dir = Config.SAMPLES_DIR
        xml_found = False
        
        print(f"🔍 Checking for cached XML for article {article_id}...")
        
        # Check for versioned XMLs (elife-XXXXX-v1.xml, etc.)
        for version in [6, 5, 4, 3, 2, 1]:
            versioned_xml = samples_dir / f"elife-{article_id}-v{version}.xml"
            if versioned_xml.exists():
                # Create copy to expected name
                expected_xml = samples_dir / f"elife-{article_id}.xml"
                if not expected_xml.exists():
                    import shutil
                    shutil.copy(versioned_xml, expected_xml)
                    print(f"✅ Using cached v{version}")
                xml_found = True
                break
        
        # If no XML exists, download it
        if not xml_found:
            expected_xml = samples_dir / f"elife-{article_id}.xml"
            if not expected_xml.exists():
                print(f"📥 Downloading from GitHub...")
                
                # Try versions v6, v5, v4, v3, v2, v1
                downloaded = False
                for version in [6, 5, 4, 3, 2, 1]:
                    url = f"https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles/elife-{article_id}-v{version}.xml"
                    print(f"  Trying v{version}...")
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                                if response.status == 200:
                                    content = await response.read()
                                    
                                    # Check if XML has body content (basic validation)
                                    content_str = content.decode('utf-8', errors='ignore')
                                    if '<body>' in content_str or '<back>' in content_str:
                                        # Save the XML
                                        samples_dir.mkdir(parents=True, exist_ok=True)
                                        expected_xml.write_bytes(content)
                                        print(f"✅ Downloaded v{version} successfully")
                                        downloaded = True
                                        break
                                    else:
                                        print(f"  v{version} has no body content, trying next version...")
                                elif response.status == 404:
                                    print(f"  v{version} not found (404)")
                                else:
                                    print(f"  v{version} returned HTTP {response.status}")
                    except Exception as e:
                        print(f"  v{version} error: {e}")
                        continue
                
                if not downloaded:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Could not download XML for article {article_id}. Please check that the article exists on GitHub."
                    )
        
        print(f"🎯 Starting Workflow 5 analysis...")
        
        # Create workflow
        pipeline = ImpactAssessmentWorkflow(use_batch_api=True)
        
        # Run analysis in thread pool to avoid blocking the async event loop
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        print(f"📖 Phase A: Deep reading citations...")
        
        # Execute the blocking call in a thread pool
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(pool, pipeline.analyze_paper, article_id)
        
        print(f"✅ Analysis complete!")
        
        return {
            "success": True,
            "article_id": article_id,
            "classification": result.overall_classification,
            "analysis": result.dict()
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("=" * 80)
        print("❌ WORKFLOW 5 ERROR:")
        print(error_detail)
        print("=" * 80)
        
        # Include detailed error message from the exception
        error_msg = str(e)
        if not error_msg or len(error_msg) < 50:
            # If error message is too short, include the full traceback
            error_msg = f"{str(e)}\n\nFull trace: {error_detail[-500:]}"
        
        raise HTTPException(status_code=500, detail=f"Analysis failed: {error_msg}")


@app.post("/api/problematic-paper/{article_id}/neo-analyze")
async def neo_analyze_problematic_paper(article_id: str):
    """
    Trigger NEO Workflow 5: Reference-Centric Impact Assessment.
    
    This is a long-running operation that performs:
    - Phase A: Per-reference deep analysis (groups citations by reference paper)
    - Phase B: Cumulative assessment and synthesis
    
    Args:
        article_id: Article ID to analyze
    
    Returns:
        NEO impact analysis with classification and per-reference reports
    """
    try:
        import aiohttp
        import json
        from pathlib import Path
        
        # Import NeoImpactAnalyzer
        from elife_graph_builder.analyzers.neo_impact_analyzer import NeoImpactAnalyzer
        
        # Check if XML exists (same logic as regular workflow 5)
        samples_dir = Config.SAMPLES_DIR
        xml_found = False
        
        print(f"🔍 [NEO] Checking for cached XML for article {article_id}...")
        
        # Check for versioned XMLs
        for version in [6, 5, 4, 3, 2, 1]:
            versioned_xml = samples_dir / f"elife-{article_id}-v{version}.xml"
            if versioned_xml.exists():
                expected_xml = samples_dir / f"elife-{article_id}.xml"
                if not expected_xml.exists():
                    import shutil
                    shutil.copy(versioned_xml, expected_xml)
                    print(f"✅ [NEO] Using cached v{version}")
                xml_found = True
                break
        
        # Download if needed
        if not xml_found:
            expected_xml = samples_dir / f"elife-{article_id}.xml"
            if not expected_xml.exists():
                print(f"📥 [NEO] Downloading from GitHub...")
                
                downloaded = False
                for version in [6, 5, 4, 3, 2, 1]:
                    url = f"https://raw.githubusercontent.com/elifesciences/elife-article-xml/master/articles/elife-{article_id}-v{version}.xml"
                    print(f"  Trying v{version}...")
                    
                    try:
                        async with aiohttp.ClientSession() as session:
                            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                                if response.status == 200:
                                    content = await response.read()
                                    content_str = content.decode('utf-8', errors='ignore')
                                    if '<body>' in content_str or '<back>' in content_str:
                                        samples_dir.mkdir(parents=True, exist_ok=True)
                                        expected_xml.write_bytes(content)
                                        print(f"✅ [NEO] Downloaded v{version} successfully")
                                        downloaded = True
                                        break
                                elif response.status == 404:
                                    print(f"  v{version} not found (404)")
                                else:
                                    print(f"  v{version} returned HTTP {response.status}")
                    except Exception as e:
                        print(f"  v{version} error: {e}")
                        continue
                
                if not downloaded:
                    raise HTTPException(
                        status_code=404,
                        detail=f"Could not download XML for article {article_id}"
                    )
        
        # Fetch citation contexts from Neo4j
        print(f"📊 [NEO] Fetching citation contexts...")
        contexts = []
        
        with neo4j_client.driver.session() as session:
            result = session.run("""
                MATCH (source:Article {article_id: $article_id})-[c:CITES]->(target:Article)
                WHERE c.citation_contexts_json IS NOT NULL
                RETURN target.article_id as target_id,
                       target.title as target_title,
                       target.authors as target_authors,
                       target.pub_year as target_year,
                       c.citation_contexts_json as contexts_json,
                       c.qualified as is_suspicious
            """, article_id=article_id)
            
            for record in result:
                contexts_data = json.loads(record['contexts_json']) if record['contexts_json'] else []
                
                for ctx_data in contexts_data:
                    classification_info = ctx_data.get('classification', {})
                    if isinstance(classification_info, dict):
                        classification_category = classification_info.get('category', 'UNKNOWN')
                        classification_reasoning = classification_info.get('justification', '')
                    else:
                        classification_category = 'UNKNOWN'
                        classification_reasoning = ''
                    
                    # Map to concern levels
                    if classification_category in ['CONTRADICT', 'MISQUOTE']:
                        mapped_classification = 'HIGH_CONCERN'
                    elif classification_category in ['NOT_SUBSTANTIATE', 'OVERSIMPLIFY']:
                        mapped_classification = 'MODERATE_CONCERN'
                    elif classification_category == 'LEGITIMATE':
                        mapped_classification = 'FALSE_ALARM'
                    else:
                        mapped_classification = 'MINOR_CONCERN'
                    
                    context = {
                        'citing_article_id': article_id,
                        'target_article_id': record['target_id'],
                        'section_name': ctx_data.get('section_name', 'Unknown'),
                        'context_text': ctx_data.get('context_text', ''),
                        'in_text_citation': ctx_data.get('in_text_citation', ''),
                        'target_authors': record['target_authors'] or [],
                        'target_year': record['target_year'],
                        'classification': mapped_classification,
                        'reasoning': classification_reasoning,
                        'evidence_passages': ctx_data.get('evidence_passages', [])
                    }
                    contexts.append(context)
        
        print(f"📊 [NEO] Found {len(contexts)} citation contexts")
        
        if not contexts:
            raise HTTPException(
                status_code=400,
                detail="No citation contexts found for this paper"
            )
        
        # Run NEO analysis
        print(f"🎯 [NEO] Starting reference-centric analysis...")
        
        xml_path = samples_dir / f"elife-{article_id}.xml"
        analyzer = NeoImpactAnalyzer(provider='deepseek', model='deepseek-reasoner')
        
        # Run in thread pool to avoid blocking
        import asyncio
        from concurrent.futures import ThreadPoolExecutor
        
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            result = await loop.run_in_executor(
                pool,
                analyzer.run_neo_analysis,
                article_id,
                xml_path,
                contexts
            )
        
        # Save to Neo4j
        print(f"💾 [NEO] Saving results...")
        success = neo4j_client.save_neo_impact_analysis(article_id, result)
        
        if not success:
            raise HTTPException(status_code=500, detail="Failed to save NEO analysis")
        
        print(f"✅ [NEO] Analysis complete!")
        
        return {
            "success": True,
            "article_id": article_id,
            "classification": result['synthesis'].get('overall_classification', 'UNKNOWN'),
            "analysis": result
        }
        
    except HTTPException:
        raise
    except Exception as e:
        import traceback
        error_detail = traceback.format_exc()
        print("=" * 80)
        print("❌ NEO WORKFLOW 5 ERROR:")
        print(error_detail)
        print("=" * 80)
        
        error_msg = str(e)
        if not error_msg or len(error_msg) < 50:
            error_msg = f"{str(e)}\n\nFull trace: {error_detail[-500:]}"
        
        raise HTTPException(status_code=500, detail=f"NEO Analysis failed: {error_msg}")


@app.put("/api/problematic-paper/{article_id}/neo-notes")
async def update_neo_reviewer_notes(article_id: str, notes: dict):
    """
    Update reviewer notes for NEO analysis.
    
    Args:
        article_id: Article ID
        notes: dict with 'notes' field containing reviewer notes text
    
    Returns:
        Success status
    """
    try:
        notes_text = notes.get('notes', '')
        success = neo4j_client.update_neo_reviewer_notes(article_id, notes_text)
        
        if not success:
            raise HTTPException(status_code=404, detail="Paper not found")
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/citations/{source_id}/{target_id}/review-status")
async def update_review_status(source_id: str, target_id: str, reviewed: bool):
    """
    Update manual review status for a citation.
    
    Args:
        source_id: Source article ID
        target_id: Target article ID
        reviewed: Whether citation has been manually reviewed
    """
    try:
        success = neo4j_client.update_review_status(source_id, target_id, reviewed)
        
        if not success:
            raise HTTPException(status_code=404, detail="Citation not found")
        
        return {"success": True, "reviewed": reviewed}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/citations/{source_id}/{target_id}/classification")
async def update_user_classification(
    source_id: str, 
    target_id: str,
    instance_id: int,
    classification: str
):
    """
    Update user's classification override for a specific context.
    
    Args:
        source_id: Source article ID
        target_id: Target article ID
        instance_id: Context instance ID
        classification: User's classification
    """
    try:
        success = neo4j_client.update_user_classification(
            source_id, target_id, instance_id, classification
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Citation context not found")
        
        return {"success": True, "classification": classification}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.put("/api/citations/{source_id}/{target_id}/comment")
async def update_user_comment(
    source_id: str,
    target_id: str,
    instance_id: int,
    comment: str
):
    """
    Update user's comment for a specific context.
    
    Args:
        source_id: Source article ID
        target_id: Target article ID
        instance_id: Context instance ID
        comment: User's comment
    """
    try:
        success = neo4j_client.update_user_comment(
            source_id, target_id, instance_id, comment
        )
        
        if not success:
            raise HTTPException(status_code=404, detail="Citation context not found")
        
        return {"success": True}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
