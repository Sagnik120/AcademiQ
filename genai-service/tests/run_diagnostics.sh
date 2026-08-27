#!/bin/bash

cd "$(dirname "$0")"

echo "======================================"
echo "🏃‍♂️ Running GenAI Service Diagnostics"
echo "======================================"

echo ""
echo "--- Testing /grade ---"
python test_grading.py

echo ""
echo "--- Testing /generate-questions ---"
python test_generation.py

echo ""
echo "--- Testing /extract-pdf ---"
python test_pdf.py

echo ""
echo "--- Testing E2E Pipeline ---"
python test_pipeline.py

echo "======================================"
echo "🏁 Diagnostics Complete"
echo "======================================"
