#!/usr/bin/env python3
"""
Test script to verify the custom handler is working correctly
"""
import sys
import os

# Add /app to path
sys.path.insert(0, '/app')

def test_handler():
    print("=== Testing Custom Handler ===")
    
    # Test 1: Check if handler module can be imported
    try:
        import handler
        print("✅ Successfully imported handler module")
        print(f"   Handler file: {handler.__file__}")
    except ImportError as e:
        print(f"❌ Failed to import handler module: {e}")
        return False
    
    # Test 2: Check if handler function exists
    if hasattr(handler, 'handler'):
        print("✅ Handler function found")
    else:
        print("❌ Handler function not found")
        return False
    
    # Test 3: Test handler with mock job
    try:
        mock_job = {
            "id": "test-job-123",
            "input": {"test": "data"}
        }
        
        print("🧪 Testing handler with mock job...")
        result = handler.handler(mock_job)
        
        print(f"✅ Handler executed successfully")
        print(f"   Result type: {type(result)}")
        print(f"   Result keys: {list(result.keys()) if isinstance(result, dict) else 'Not a dict'}")
        
        # Check if metadata was added
        if isinstance(result, dict):
            if 'worker_metadata' in result:
                print("✅ Worker metadata found in result")
            elif 'output' in result and isinstance(result['output'], dict) and 'worker_metadata' in result['output']:
                print("✅ Worker metadata found in output")
            else:
                print("⚠️  Worker metadata not found in result")
        
        return True
        
    except Exception as e:
        print(f"❌ Handler execution failed: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    success = test_handler()
    sys.exit(0 if success else 1)
