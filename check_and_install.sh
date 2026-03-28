#!/bin/bash

# 1. Check if virtual environment folder "venv" exists. If not, create it.
if [ ! -d "venv" ]; then
    echo "Creating virtual environment 'venv'..."
    python3 -m venv venv
else
    echo "Virtual environment 'venv' already exists."
fi

# 2. Activate the virtual environment
echo "Activating virtual environment..."
source venv/bin/activate

# 3. Check and install packages
packages=(
    "flask"
    "flask-cors"
    "python-dotenv"
    "requests"
    "notion-client"
    "youtube-transcript-api"
    "PyMuPDF"
    "beautifulsoup4"
    "lxml"
)

echo "Checking packages..."
for pkg in "${packages[@]}"; do
    if pip show "$pkg" > /dev/null 2>&1; then
        echo "✓ $pkg is already installed."
    else
        echo "⬇️ Installing $pkg..."
        pip install "$pkg"
    fi
done

# 4. Save output to requirements.txt
echo "Saving dependencies to backend/requirements.txt..."
pip freeze > backend/requirements.txt

# Also updating root requirements.txt to maintain project structure consistency
pip freeze > requirements.txt

# 5. Final completion message
echo ""
echo "All done! Run: source venv/bin/activate"
