#!/bin/bash

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Function to fetch latest version from PyPI
get_pypi_version() {
    # Try to fetch the latest version from PyPI using API
    local version=$(curl -s https://pypi.org/pypi/pragma-sdk/json | grep -o '"version":"[^"]*"' | cut -d'"' -f4)

    if [ -z "$version" ]; then
        echo "Error: Could not fetch version from PyPI"
        exit 1
    fi

    echo "$version"
}

# Function to extract version from __init__.py files
get_local_version() {
    local file="$1"
    if [ -f "$file" ]; then
        version=$(grep -o "__version__[[:space:]]*=[[:space:]]*[\"'][^\"']*[\"']" "$file" | cut -d'"' -f2 | cut -d"'" -f2)
        echo "$version"
    fi
}

# Function to compare versions
version_gt() {
    test "$(printf '%s\n' "$@" | sort -V | head -n 1)" != "$1";
}

# Function to bump version
bump_version() {
    local current_version="$1"
    local bump_type="$2"

    IFS='.' read -r major minor patch <<< "$current_version"

    case "$bump_type" in
        "major")
            major=$((major + 1))
            minor=0
            patch=0
            ;;
        "minor")
            minor=$((minor + 1))
            patch=0
            ;;
        "patch")
            patch=$((patch + 1))
            ;;
        *)
            echo "Invalid bump type. Use: major, minor, or patch"
            exit 1
            ;;
    esac

    echo "${major}.${minor}.${patch}"
}

# Main script
echo -e "${YELLOW}Fetching latest version from PyPI...${NC}"
PYPI_VERSION=$(get_pypi_version)
echo -e "PyPI version: ${GREEN}${PYPI_VERSION}${NC}"

# Define the project directories to check
PROJECT_DIRS=(
    "pragma-sdk"
    "pragma-utils"
    "price-pusher"
    "checkpointer"
    "vrf-listener"
    "lp-pricer"
)

# Find all __init__.py files while excluding .venv directories
echo -e "\n${YELLOW}Checking local versions...${NC}"
files_to_update=()
versions_to_update=()
has_different_versions=false

for dir in "${PROJECT_DIRS[@]}"; do
    if [ -d "$dir" ]; then
        while IFS= read -r init_file; do
            if [ ! -z "$init_file" ]; then
                LOCAL_VERSION=$(get_local_version "$init_file")
                if [ ! -z "$LOCAL_VERSION" ]; then
                    echo -e "File: ${init_file}"
                    echo -e "Local version: ${GREEN}${LOCAL_VERSION}${NC}"

                    files_to_update+=("$init_file")
                    versions_to_update+=("$LOCAL_VERSION")

                    if [ "$LOCAL_VERSION" != "$PYPI_VERSION" ]; then
                        has_different_versions=true
                    fi
                fi
            fi
        done < <(find "$dir" -type d -name ".venv" -prune -o -type f -name "__init__.py" -print)
    fi
done

if [ ${#files_to_update[@]} -eq 0 ]; then
    echo -e "\n${RED}No __init__.py files found with version information!${NC}"
    exit 1
fi

if $has_different_versions; then
    echo -e "\n${YELLOW}Some versions differ from PyPI version ${PYPI_VERSION}${NC}"
else
    echo -e "\n${GREEN}All versions match PyPI version ${PYPI_VERSION}${NC}"
fi

# Ask if user wants to bump version
read -p "Would you like to bump the version? (y/n): " bump_answer

if [ "$bump_answer" != "y" ]; then
    echo -e "${YELLOW}No version changes will be made.${NC}"
    exit 0
fi

# Ask for version bump type
echo -e "\n${YELLOW}Choose bump type:${NC}"
echo "1) major"
echo "2) minor"
echo "3) patch"
echo "4) custom version"
read -p "Enter choice (1-4): " bump_choice

case $bump_choice in
    1) NEW_VERSION=$(bump_version "$PYPI_VERSION" "major");;
    2) NEW_VERSION=$(bump_version "$PYPI_VERSION" "minor");;
    3) NEW_VERSION=$(bump_version "$PYPI_VERSION" "patch");;
    4)
        read -p "Enter custom version (x.y.z format): " custom_version
        if [[ $custom_version =~ ^[0-9]+\.[0-9]+\.[0-9]+$ ]]; then
            NEW_VERSION="$custom_version"
        else
            echo -e "${RED}Invalid version format${NC}"
            exit 1
        fi
        ;;
    *)
        echo -e "${RED}Invalid choice${NC}"
        exit 1
        ;;
esac

echo -e "\n${YELLOW}New version will be: ${GREEN}${NEW_VERSION}${NC}"
read -p "Proceed with update? (y/n): " confirm

if [ "$confirm" != "y" ]; then
    echo -e "${YELLOW}Update cancelled${NC}"
    exit 0
fi

# Update files
for i in "${!files_to_update[@]}"; do
    file="${files_to_update[$i]}"
    current_version="${versions_to_update[$i]}"

    echo -e "\nUpdating ${file}..."

    # Create a temporary file for sed operations
    temp_file=$(mktemp)

    if grep -q "__version__ = \"${current_version}\"" "$file"; then
        # Double quotes version
        sed "s/^__version__[[:space:]]*=[[:space:]]*\"${current_version}\"/__version__ = \"${NEW_VERSION}\"/" "$file" > "$temp_file"
    elif grep -q "__version__ = '${current_version}'" "$file"; then
        # Single quotes version
        sed "s/^__version__[[:space:]]*=[[:space:]]*'${current_version}'/__version__ = '${NEW_VERSION}'/" "$file" > "$temp_file"
    fi

    # Check if sed operation was successful
    if [ $? -eq 0 ] && [ -s "$temp_file" ]; then
        # Replace original file with updated content
        mv "$temp_file" "$file"
        echo -e "${GREEN}Successfully updated ${file}${NC}"
    else
        rm -f "$temp_file"
        echo -e "${RED}Failed to update ${file}${NC}"
    fi
done

echo -e "\n${GREEN}Version update complete!${NC}"
