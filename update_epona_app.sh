#!/bin/bash

# Stop the epona service
sudo systemctl stop epona

echo "Epona service stopped. Updating app..."

# Update the app and print git output to the console
git pull origin main

echo "Epona app updated successfully. Restarting service..."

# Restart the epona service
sudo systemctl start epona

