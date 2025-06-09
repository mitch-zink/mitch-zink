#!/bin/bash

# ==============================================================================
# RESET GIT BRANCH TO SINGLE COMMIT
# ==============================================================================
#
# DESCRIPTION:
#   This script removes all commit history from a git branch and creates a new 
#   single commit containing all the current content. This is useful for cleaning 
#   up messy commit history or starting fresh while preserving all your work.
#
# WHAT IT DOES:
#   1. Creates a new orphan branch with no history
#   2. Adds all current files to a single new commit
#   3. Replaces the target branch with this new single-commit branch
#
# HOW TO RUN:
#   ./reset-to-latest-commit.sh              # Interactive mode - shows branch list
#   ./reset-to-latest-commit.sh <branch>     # Direct mode - resets specified branch
#   ./reset-to-latest-commit.sh -c           # Current branch mode
#   
#   Examples:
#   ./reset-to-latest-commit.sh main         # Reset main branch
#   ./reset-to-latest-commit.sh feature-xyz  # Reset feature-xyz branch
#   ./reset-to-latest-commit.sh -c           # Reset current branch
#
# SAFETY FEATURES:
#   - Requires explicit confirmation before proceeding
#   - Shows what will be removed before proceeding
#
# WARNING: NO BACKUP IS CREATED - HISTORY WILL BE PERMANENTLY DESTROYED
#
# WARNING: 
#   This is a destructive operation that rewrites history. If you've already
#   pushed this branch to a remote, you'll need to force push after running
#   this script.
#
# ==============================================================================

# Color codes for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${YELLOW}WARNING: This script will remove all commits except the latest from a branch.${NC}"
echo -e "${YELLOW}This is a destructive operation that cannot be easily undone.${NC}"
echo ""

# Handle branch selection
if [ "$1" == "-c" ]; then
    # Use current branch
    TARGET_BRANCH=$(git rev-parse --abbrev-ref HEAD)
    echo -e "Using current branch: ${GREEN}${TARGET_BRANCH}${NC}"
elif [ -n "$1" ]; then
    # Use provided branch name
    TARGET_BRANCH="$1"
    # Check if branch exists
    if ! git show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
        echo -e "${RED}Error: Branch '$TARGET_BRANCH' does not exist.${NC}"
        exit 1
    fi
    echo -e "Target branch: ${GREEN}${TARGET_BRANCH}${NC}"
else
    # Interactive mode - show branch list
    echo -e "${GREEN}Available branches:${NC}"
    echo ""
    
    # Get all local branches
    branches=($(git branch | sed 's/\*//g' | sed 's/^ *//g'))
    
    # Display branches with numbers
    for i in "${!branches[@]}"; do
        if [ "${branches[$i]}" == "$(git rev-parse --abbrev-ref HEAD)" ]; then
            echo -e "  $((i+1))) ${GREEN}${branches[$i]}${NC} (current)"
        else
            echo -e "  $((i+1))) ${branches[$i]}"
        fi
    done
    
    echo ""
    echo -e "${YELLOW}Enter branch number or branch name:${NC}"
    read -p "> " BRANCH_SELECTION
    
    # Check if input is a number
    if [[ "$BRANCH_SELECTION" =~ ^[0-9]+$ ]]; then
        # User entered a number
        idx=$((BRANCH_SELECTION - 1))
        if [ $idx -ge 0 ] && [ $idx -lt ${#branches[@]} ]; then
            TARGET_BRANCH="${branches[$idx]}"
        else
            echo -e "${RED}Invalid selection.${NC}"
            exit 1
        fi
    else
        # User entered a branch name
        TARGET_BRANCH="$BRANCH_SELECTION"
        # Check if branch exists
        if ! git show-ref --verify --quiet "refs/heads/$TARGET_BRANCH"; then
            echo -e "${RED}Error: Branch '$TARGET_BRANCH' does not exist.${NC}"
            exit 1
        fi
    fi
    
    echo ""
    echo -e "Selected branch: ${GREEN}${TARGET_BRANCH}${NC}"
fi

# Store current branch to return to it later
ORIGINAL_BRANCH=$(git rev-parse --abbrev-ref HEAD)

# Switch to target branch if different
if [ "$TARGET_BRANCH" != "$ORIGINAL_BRANCH" ]; then
    echo -e "Switching to branch ${GREEN}${TARGET_BRANCH}${NC}..."
    git checkout "$TARGET_BRANCH" > /dev/null 2>&1
fi

# Get latest commit hash
LATEST_COMMIT=$(git rev-parse HEAD)
echo -e "Latest commit: ${GREEN}${LATEST_COMMIT}${NC}"

# Show current commit count
COMMIT_COUNT=$(git rev-list --count HEAD)
echo -e "Total commits on this branch: ${GREEN}${COMMIT_COUNT}${NC}"

if [ "$COMMIT_COUNT" -eq 1 ]; then
    echo -e "${GREEN}This branch already has only one commit. Nothing to do.${NC}"
    exit 0
fi

echo ""
echo -e "${RED}This will remove $(($COMMIT_COUNT - 1)) commits!${NC}"
echo ""

# Confirmation prompt
read -p "Are you sure you want to proceed? Type 'yes' to continue: " CONFIRM

if [ "$CONFIRM" != "yes" ]; then
    echo -e "${YELLOW}Operation cancelled.${NC}"
    exit 0
fi

# No backup needed - we're destroying history intentionally

echo ""
echo -e "${YELLOW}Resetting branch to only the latest commit...${NC}"

# Option 1: Using git reset --soft to preserve changes
# This creates a new root commit with all the current content
git checkout --orphan temp-branch
git add -A
# Create a simple commit message
git commit -m "Updates"

# Force update the original branch
git branch -D "$TARGET_BRANCH"
git branch -m "$TARGET_BRANCH"

echo ""
echo -e "${GREEN}Successfully reset ${TARGET_BRANCH} to only contain the latest commit!${NC}"
echo -e "${RED}All previous history has been permanently destroyed.${NC}"

# Return to original branch if different
if [ "$TARGET_BRANCH" != "$ORIGINAL_BRANCH" ]; then
    echo ""
    echo -e "Returning to original branch ${GREEN}${ORIGINAL_BRANCH}${NC}..."
    git checkout "$ORIGINAL_BRANCH" > /dev/null 2>&1
fi

echo ""
echo -e "${YELLOW}To push this change to remote, you'll need to force push:${NC}"
echo -e "  git push --force origin ${TARGET_BRANCH}"