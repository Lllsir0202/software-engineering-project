#!/bin/bash

# Python environment initialization script
# Supports Conda virtual environment or direct pip installation
# Prefers python3.7, falls back to python3 or python

set -e

echo "Python Environment Initialization Tool"
echo "Select an initialization method:"
echo "1. Create a Conda virtual environment (recommended)"
echo "2. Install packages directly using pip (without creating an environment)"
read -p "Enter your choice (1 or 2, default is 1): " choice

REQUIRED_PACKAGES="flask flask-mail flask-cors email-validator matplotlib openmeteo-requests requests-cache retry-requests flask_sqlalchemy pymysql flask_migrate openpyxl"
CONDA_REQUIRED_PACKAGES="flask email-validator matplotlib pandas openpyxl"
CONDA_REQUIRED_PIP_PACKAGES="flask-mail flask-cors openmeteo-requests requests-cache retry-requests flask_sqlalchemy pymysql flask_migrate"
ENV_NAME="soft_engineering"   # Default Conda environment name. You can change it as you like.

# pip method
if [[ "$choice" == "2" ]]; then
    echo "Installing packages directly using pip (no virtual environment will be created)..."

    if command -v python3.12 &> /dev/null; then
        PYTHON_BIN=$(command -v python3.12)
        echo "Using python3.12: $PYTHON_BIN"
    elif command -v python3 &> /dev/null; then
        PYTHON_BIN=$(command -v python3)
        echo "Using default python3: $PYTHON_BIN"
    elif command -v python &> /dev/null; then
        PYTHON_BIN=$(command -v python)
        echo "Using python: $PYTHON_BIN"
    else
        echo "Python not found. Please install Python first."
        exit 1
    fi

    $PYTHON_BIN -m pip install --upgrade pip
    $PYTHON_BIN -m pip install $REQUIRED_PACKAGES

    echo "Package installation completed."

    echo "USE_CONDA=0" >> env.mk
    PYTHON_PATH=$(command -v python3 || command -v python)
    echo "PYTHON_BIN=$PYTHON_PATH" >> env.mk
# conda method
else
    if ! command -v conda &> /dev/null; then
        echo "Conda not found. Please install Anaconda or Miniconda first."
        exit 1
    fi

    # 检查环境是否已存在
    if conda info --envs | grep -q "^$ENV_NAME[[:space:]]"; then
        echo "Conda environment '$ENV_NAME' already exists. Skipping creation..."
    else
        echo "Creating Conda virtual environment: $ENV_NAME (Python 3.12)..."
        conda create -y -n $ENV_NAME python=3.12
    fi

    echo "Initializing Conda..."
    # conda init

    echo "Installing required packages into '$ENV_NAME'..."
    echo "Installing conda packages..."
    conda run -n $ENV_NAME conda install -y $CONDA_REQUIRED_PACKAGES
    echo "Installing pip packages..."
    conda run -n $ENV_NAME pip install $CONDA_REQUIRED_PIP_PACKAGES

    echo "Conda environment setup and package installation completed."
    echo "To activate the environment later, run:"
    echo "  conda activate $ENV_NAME"
    # 输出 Makefile 可用的变量文件
    echo "ENV_NAME=$ENV_NAME" > env.mk
    echo "USE_CONDA=1" >> env.mk
fi
