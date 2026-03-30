#!/usr/bin/env python3
"""
Setup script for Colab environment
Run this to install dependencies and verify the setup
"""

import subprocess
import sys
import os


def run_command(cmd, description):
    print(f"\n{'='*60}")
    print(f"{description}")
    print(f"{'='*60}")
    result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
    print(result.stdout)
    if result.stderr:
        print("STDERR:", result.stderr)
    return result.returncode == 0


def main():
    print("Colab DentalCare Account Manager - Setup")
    print("=" * 60)
    
    # Update package lists
    run_command("apt-get update -qq", "Updating package lists")
    
    # Install system dependencies
    run_command(
        "apt-get install -y -qq fonts-liberation libasound2 libatk-bridge2.0-0 "
        "libatk1.0-0 libcups2 libdrm2 libgbm1 libgtk-3-0 libnspr4 libnss3 "
        "libx11-xcb1 libxcomposite1 libxdamage1 libxrandr2 xdg-utils",
        "Installing system dependencies"
    )
    
    # Install Python packages
    print("\n" + "="*60)
    print("Installing Python packages...")
    print("="*60)
    
    packages = [
        "playwright>=1.40.0",
        "requests>=2.31.0",
        "urllib3>=2.0.0",
    ]
    
    for pkg in packages:
        run_command(f"pip install -q {pkg}", f"Installing {pkg}")
    
    # Install Playwright browsers
    print("\n" + "="*60)
    print("Installing Playwright Chromium...")
    print("="*60)
    run_command("playwright install chromium", "Installing Chromium browser")
    
    print("\n" + "="*60)
    print("Setup Complete!")
    print("="*60)
    print("\nYou can now run: python run.py")
    print("\nFor Colab notebook, upload run_colab.ipynb to Google Colab")


if __name__ == "__main__":
    main()
