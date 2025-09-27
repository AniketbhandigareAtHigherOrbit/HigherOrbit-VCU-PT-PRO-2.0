#!/bin/bash
echo "Pulling latest changes from GitHub..."

# go to project directory
cd ~/VCU-PT-PRO-2.0 || exit

# make sure env is activated
source ~/H-orbit/bin/activate

# pull changes
git fetch origin
git pull origin main

echo "? Project updated successfully!"
