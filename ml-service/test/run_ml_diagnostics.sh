#!/bin/bash

# Ensure we are in the ml-service directory
SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )"
cd "$SCRIPT_DIR/.."

echo "======================================"
echo "🏃‍♂️ Running ML Service Diagnostics"
echo "======================================"

# Determine pytest executable
if [ -d "../.venv" ]; then
    PYTEST="../.venv/bin/pytest"
else
    PYTEST="pytest"
fi

export PYTHONPATH=.

# Run Face Detection tests
echo ""
echo "--- Testing Face Detection (MediaPipe) ---"
$PYTEST test/test_face_detection.py -v
if [ $? -ne 0 ]; then
    echo "❌ Face Detection tests failed!"
    exit 1
fi

# Run Pose Estimation tests
echo ""
echo "--- Testing Pose Estimation (ONNX) ---"
$PYTEST test/test_pose_estimation.py -v
if [ $? -ne 0 ]; then
    echo "❌ Pose Estimation tests failed!"
    exit 1
fi

# Run API Endpoints tests
echo ""
echo "--- Testing FastAPI Endpoints ---"
$PYTEST test/test_api.py -v
if [ $? -ne 0 ]; then
    echo "❌ API Endpoints tests failed!"
    exit 1
fi

echo ""
echo "======================================"
echo "✅ All Diagnostics Passed Successfully!"
echo "======================================"
