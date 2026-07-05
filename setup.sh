#!/bin/bash
echo "Creating virtual environment..."
uv venv

echo "Installing libraries..."
uv pip install -r requirements.txt

echo ""
echo "Setup complete. You can now start the app with ./run.sh"
