#!/bin/bash

# 1. Check if virtual environment exists
if [ ! -d "venv" ]; then
  echo "Error: Virtual environment 'venv' not found! Please run check_and_install.sh first."
  exit 1
fi

# 2. Activate the virtual environment
source venv/bin/activate

# 3. List of Google Calendar libraries to install
PACKAGES=(
  "google-auth"
  "google-auth-oauthlib"
  "google-auth-httplib2"
  "google-api-python-client"
)

# Install loop
for pkg in "${PACKAGES[@]}"; do
  if pip show "$pkg" > /dev/null 2>&1; then
    echo "✓ $pkg is already installed."
  else
    echo "Installing $pkg..."
    pip install "$pkg"
  fi
done

# 4. Update backend/requirements.txt
echo "Updating requirements.txt..."
pip freeze > backend/requirements.txt

# 5. Success message
echo "Google Calendar libraries ready!"
