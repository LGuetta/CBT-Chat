"""
CBT Chat Assistant - FastAPI Backend
Main application entry point.
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from config.settings import get_settings
from api.routes import chat, therapist, admin

settings = get_settings()

# Create FastAPI app
app = FastAPI(
    title="CBT Chat Assistant API",
    description="Backend API for CBT-aligned chat assistant for adults",
    version="0.1.0",
    debug=settings.debug
)

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Health check endpoint
@app.get("/")
async def root():
    """Root endpoint - health check."""
    return {
        "status": "healthy",
        "service": "CBT Chat Assistant API",
        "version": "0.1.0",
        "environment": settings.environment
    }


@app.get("/health")
async def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "database": "connected",  # TODO: Add actual DB health check
        "llm_services": {
            "primary": settings.primary_llm,
            "risk_detection": settings.risk_detection_llm
        }
    }


# Include routers
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(therapist.router, prefix="/api/therapist", tags=["therapist"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])


# Global exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Handle all unhandled exceptions."""
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal server error",
            "message": str(exc) if settings.debug else "An error occurred",
            "type": type(exc).__name__
        }
    )


if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.debug
    )
