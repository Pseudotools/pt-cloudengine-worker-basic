#!/bin/bash
# Runtime diagnostic script to check handler status

echo "================================================"
echo "🔍 HANDLER DIAGNOSTIC CHECK"
echo "================================================"

echo "📁 Checking /app directory contents:"
ls -la /app/

echo ""
echo "🐍 Checking Python handler module:"
if [ -f "/app/handler.py" ]; then
    echo "✅ handler.py exists"
    echo "📄 First 10 lines of handler.py:"
    head -10 /app/handler.py
else
    echo "❌ handler.py not found"
fi

echo ""
echo "🧪 Testing handler import:"
python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    import handler
    print('✅ Successfully imported handler module')
    print(f'   Handler file: {handler.__file__}')
    if hasattr(handler, 'handler'):
        print('✅ Handler function found')
    else:
        print('❌ Handler function not found')
except Exception as e:
    print(f'❌ Failed to import handler: {e}')
"

echo ""
echo "🔍 Checking for rp_handler:"
python3 -c "
import sys
sys.path.insert(0, '/app')
try:
    import rp_handler
    print('✅ rp_handler module found')
    print(f'   rp_handler file: {rp_handler.__file__}')
except Exception as e:
    print(f'❌ rp_handler not found: {e}')
"

echo "================================================"
