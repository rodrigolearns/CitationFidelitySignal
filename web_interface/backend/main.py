"""FastAPI backend for eLife Citation Qualification Viewer."""
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from neo4j_client import Neo4jClient

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
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
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
