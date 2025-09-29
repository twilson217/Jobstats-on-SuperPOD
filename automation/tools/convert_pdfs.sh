#!/bin/bash

# PDF to Text Conversion Script for BCM Documentation
# This script converts all PDFs in bcm-documentation/ to text files

set -e

# Create output directory for text files
TEXT_DIR="/root/jobstat/bcm-documentation-text"
mkdir -p "$TEXT_DIR"

echo "PDF to Text Converter for BCM Documentation"
echo "============================================="

# Check if pdftotext is available
if ! command -v pdftotext &> /dev/null; then
    echo "pdftotext not found. Installing poppler-utils..."
    apt update
    apt install -y poppler-utils
fi

# Convert each PDF to text
echo "Converting PDFs to text format..."

for pdf_file in /root/jobstat/bcm-documentation/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file" .pdf)
        text_file="$TEXT_DIR/${filename}.txt"
        
        echo "Converting: $pdf_file -> $text_file"
        pdftotext "$pdf_file" "$text_file"
        
        # Check if conversion was successful
        if [ -s "$text_file" ]; then
            echo "✓ Successfully converted $filename"
        else
            echo "✗ Failed to convert $filename (empty file)"
        fi
    fi
done

echo ""
echo "Conversion complete! Text files are available in: $TEXT_DIR"
echo ""
echo "Converted files:"
ls -la "$TEXT_DIR"
