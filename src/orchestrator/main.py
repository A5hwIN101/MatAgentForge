# Purpose: Integrate StateGraph into FastAPI endpoints
# ============================================================================

from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.middleware.cors import CORSMiddleware
import json
import asyncio
from typing import AsyncGenerator

from src.orchestrator.pipeline_graph import get_pipeline_graph, visualize_graph
from src.orchestrator.pipeline_state import create_initial_state


# ===== FASTAPI APP SETUP =====

app = FastAPI(
    title="MatAgent-Forge API",
    description="AI-powered materials science discovery platform",
    version="1.0.0"
)

# ===== CORS CONFIGURATION =====
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins (change to specific domains in production)
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ===== ENDPOINTS =====

@app.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns:
        {"status": "healthy"}
    """
    return {"status": "healthy"}


@app.get("/debug/graph-structure")
async def debug_graph_structure():
    """
    Debug endpoint: Print the graph structure.
    
    Returns:
        {"status": "printed to console"}
    """
    visualize_graph()
    return {"status": "Graph structure printed to console"}


@app.post("/api/analyze")
async def analyze_material(request: dict):
    """
    Main analysis endpoint.
    
    Analyzes a material using the StateGraph pipeline.
    Streams markdown output to the client.
    
    Request body:
        {
            "material_name": "NaCl"  # Material formula
        }
    
    Returns:
        StreamingResponse with markdown formatted analysis
    """
    
    # ===== VALIDATE INPUT =====
    material_name = request.get("material_name", "").strip()
    
    if not material_name:
        raise HTTPException(
            status_code=400,
            detail="material_name is required in request body"
        )
    
    # ===== RUN PIPELINE & STREAM OUTPUT =====
    async def stream_analysis() -> AsyncGenerator[str, None]:
        """
        Run the pipeline and stream output line by line.
        """
        try:
            # Get compiled graph
            graph = get_pipeline_graph()
            
            # Initialize state
            initial_state = create_initial_state(material_name)
            
            # Stream: Pipeline starting
            yield "# Material Analysis: " + material_name + "\n\n"
            yield "**Status:** Processing...\n\n"
            
            # Run the graph (this is async and awaits each node)
            print(f"\n[API] Starting pipeline for: {material_name}")
            final_state = await graph.ainvoke(initial_state)
            
            # Extract the formatted output
            formatted_output = final_state.get("formatted_output", "")
            pipeline_status = final_state.get("pipeline_status", "unknown")
            
            # Stream: Replace processing status with actual status
            if pipeline_status == "success":
                yield "**Status:** ✓ Complete\n\n"
            else:
                yield "**Status:** ⚠ Completed with errors\n\n"
            
            # Stream: The full formatted output
            yield formatted_output
            
            print(f"[API] Pipeline complete - Status: {pipeline_status}")
        
        except Exception as e:
            # Stream error message
            print(f"[API] Pipeline exception: {e}")
            yield f"\n\n# Error\n\nAn unexpected error occurred:\n\n```\n{str(e)}\n```"
    
    # Return streaming response
    return StreamingResponse(
        stream_analysis(),
        media_type="text/plain"
    )


@app.post("/api/analyze-debug")
async def analyze_material_debug(request: dict):
    """
    Debug endpoint: Same as /api/analyze but prints full state at each step.
    
    Useful for understanding what's happening in the pipeline.
    """
    
    material_name = request.get("material_name", "").strip()
    
    if not material_name:
        raise HTTPException(
            status_code=400,
            detail="material_name is required in request body"
        )
    
    async def stream_debug() -> AsyncGenerator[str, None]:
        try:
            graph = get_pipeline_graph()
            initial_state = create_initial_state(material_name)
            
            yield f"DEBUG: Starting pipeline for {material_name}\n\n"
            yield "INITIAL STATE:\n"
            yield json.dumps(initial_state, indent=2, default=str) + "\n\n"
            
            # Run graph with streaming
            final_state = await graph.ainvoke(initial_state)
            
            yield "\n\nFINAL STATE:\n"
            yield json.dumps(final_state, indent=2, default=str) + "\n\n"
            
            yield "\nFORMATTED OUTPUT:\n"
            yield final_state.get("formatted_output", "No output") + "\n"
        
        except Exception as e:
            yield f"ERROR: {str(e)}\n"
    
    return StreamingResponse(
        stream_debug(),
        media_type="text/plain"
    )

@app.post("/api/feedback")
async def submit_feedback(request: dict):
    """
    Feedback collection endpoint.
    
    Accepts user thumbs up/down + optional comment.
    Logs to data/feedback.json
    """
    import os
    from datetime import datetime
    
    material_name = request.get("material_name", "").strip()
    thumbs_up = request.get("thumbs_up")
    comment = request.get("comment", "")
    
    if not material_name or thumbs_up is None:
        raise HTTPException(
            status_code=400,
            detail="material_name and thumbs_up are required"
        )
    
    feedback_entry = {
        "timestamp": datetime.now().isoformat(),
        "material_name": material_name,
        "thumbs_up": thumbs_up,
        "comment": comment
    }
    
    # Ensure data dir exists
    os.makedirs("data", exist_ok=True)
    
    # Append to feedback.json
    feedback_file = "data/feedback.json"
    feedback_list = []
    
    if os.path.exists(feedback_file):
        with open(feedback_file, "r") as f:
            feedback_list = json.load(f)
    
    feedback_list.append(feedback_entry)
    
    with open(feedback_file, "w") as f:
        json.dump(feedback_list, f, indent=2)
    
    print(f"[Feedback] Recorded: {material_name} - thumbs_up={thumbs_up}")
    
    return {"status": "success", "message": "Feedback recorded"}

@app.get("/docs")
async def get_docs():
    """
    API documentation endpoint.
    
    FastAPI auto-generates this, but this shows how to customize.
    """
    return {
        "endpoints": {
            "POST /api/analyze": "Main analysis endpoint (streams markdown)",
            "POST /api/analyze-debug": "Debug version (shows state at each step)",
            "GET /health": "Health check",
            "GET /debug/graph-structure": "Print graph structure to console"
        }
    }


# ===== STARTUP/SHUTDOWN EVENTS =====

@app.on_event("startup")
async def startup_event():
    """
    Initialize on startup.
    """
    print("\n" + "="*60)
    print("MatAgent-Forge API Starting Up")
    print("="*60)
    
    # Pre-compile the graph
    print("[Startup] Pre-compiling pipeline graph...")
    graph = get_pipeline_graph()
    print("[Startup] ✓ Graph pre-compiled and ready")
    
    # Print structure for debugging
    visualize_graph()
    
    print("[Startup] ✓ API ready to accept requests")
    print(f"[Startup] Available at: http://localhost:8000")
    print(f"[Startup] Docs at: http://localhost:8000/docs")
    print("="*60 + "\n")


@app.on_event("shutdown")
async def shutdown_event():
    """
    Cleanup on shutdown.
    """
    print("\n[Shutdown] MatAgent-Forge API shutting down...")


# ===== MAIN ENTRY POINT =====

if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        app,
        host="0.0.0.0",
        port=8000,
        reload=True
    )