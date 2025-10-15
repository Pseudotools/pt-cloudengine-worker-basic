#!/usr/bin/env python3
"""
Startup script that integrates our custom handler with the base image.
This script ensures our execution metadata handler is used instead of the base handler.
"""

import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def main():
    """Main startup function that sets up our custom handler."""
    
    logger.info("🚀 Starting Pseudotools ComfyUI Worker with Custom Handler")
    
    # Verify our custom handler exists
    handler_path = "/app/handler.py"
    if not os.path.exists(handler_path):
        logger.error(f"❌ Custom handler not found at {handler_path}")
        logger.info("Falling back to base image handler...")
        # Fall back to base image startup
        os.execv("/start.sh", ["/start.sh"])
        return
    
    logger.info(f"✅ Custom handler found at {handler_path}")
    
    # Set up environment to use our handler
    os.environ["RUNPOD_HANDLER_PATH"] = handler_path
    
    # Import and start our custom handler with RunPod serverless
    try:
        logger.info("🔧 Starting RunPod serverless with custom handler...")
        
        # Import runpod and our handler
        import runpod
        sys.path.insert(0, "/app")
        from handler import handler as custom_handler
        
        logger.info("✅ Custom handler imported successfully")
        logger.info("🚀 Starting RunPod serverless worker...")
        
        # Start the serverless worker with our custom handler
        runpod.serverless.start({"handler": custom_handler})
        
    except ImportError as e:
        logger.error(f"❌ Failed to import runpod or custom handler: {e}")
        logger.info("Falling back to base image handler...")
        os.execv("/start.sh", ["/start.sh"])
    except Exception as e:
        logger.error(f"❌ Failed to start custom handler: {e}")
        logger.info("Falling back to base image handler...")
        os.execv("/start.sh", ["/start.sh"])

if __name__ == "__main__":
    main()
