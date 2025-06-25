#!/bin/bash

OS=$(uname)

if [[ "$OS" == "Linux" ]]; then
    echo "Installing MySQL(Linux)..."
    sudo apt update
    sudo apt install mysql-server -y
    sudo service mysql start

elif [[ "$OS" == "Darwin" ]]; then
    echo "Installing MySQL(macOS)..."
    brew install mysql
    brew services start mysql

else
    echo "Unsupported OS:$OS,Please install MySQL manually."
    exit 1
fi
