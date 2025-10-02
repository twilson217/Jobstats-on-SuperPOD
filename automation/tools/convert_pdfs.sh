#!/bin/bash

# PDF to Text Conversion Script
# This script converts all PDFs in a specified directory to text files

set -e

# Function to display usage
usage() {
    echo "Usage: $0 <input_directory> <output_directory>"
    echo ""
    echo "Arguments:"
    echo "  input_directory   Directory containing PDF files to convert"
    echo "  output_directory  Directory where text files will be saved"
    echo ""
    echo "Example:"
    echo "  $0 /path/to/pdfs /path/to/output"
    echo ""
    exit 1
}

# Check if correct number of arguments provided
if [ $# -ne 2 ]; then
    echo "Error: Incorrect number of arguments"
    echo ""
    usage
fi

# Get input and output directories from arguments
INPUT_DIR="$1"
OUTPUT_DIR="$2"

# Validate input directory exists
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory '$INPUT_DIR' does not exist"
    exit 1
fi

# Create output directory if it doesn't exist
mkdir -p "$OUTPUT_DIR"

echo "PDF to Text Converter"
echo "====================="
echo "Input directory:  $INPUT_DIR"
echo "Output directory: $OUTPUT_DIR"
echo ""

# Check if pdftotext is available
if ! command -v pdftotext &> /dev/null; then
    echo "pdftotext not found. Installing poppler-utils..."
    apt update
    apt install -y poppler-utils
fi

# Check if there are any PDF files in the input directory
pdf_count=$(find "$INPUT_DIR" -maxdepth 1 -name "*.pdf" -type f | wc -l)
if [ $pdf_count -eq 0 ]; then
    echo "No PDF files found in '$INPUT_DIR'"
    exit 1
fi

echo "Found $pdf_count PDF file(s) to convert"
echo "Converting PDFs to text format..."
echo ""

# Convert each PDF to text
converted_count=0
failed_count=0

for pdf_file in "$INPUT_DIR"/*.pdf; do
    if [ -f "$pdf_file" ]; then
        filename=$(basename "$pdf_file" .pdf)
        text_file="$OUTPUT_DIR/${filename}.txt"
        
        echo "Converting: $(basename "$pdf_file") -> ${filename}.txt"
        
        if pdftotext "$pdf_file" "$text_file" 2>/dev/null; then
            # Check if conversion was successful and file has content
            if [ -s "$text_file" ]; then
                echo "✓ Successfully converted $filename"
                converted_count=$((converted_count + 1))
            else
                echo "✗ Failed to convert $filename (empty file)"
                failed_count=$((failed_count + 1))
            fi
        else
            echo "✗ Failed to convert $filename (pdftotext error)"
            failed_count=$((failed_count + 1))
        fi
        echo ""
    fi
done

echo "Conversion Summary:"
echo "=================="
echo "Successfully converted: $converted_count files"
echo "Failed conversions: $failed_count files"
echo "Output directory: $OUTPUT_DIR"
echo ""

if [ $converted_count -gt 0 ]; then
    echo "Converted files:"
    ls -la "$OUTPUT_DIR"/*.txt 2>/dev/null || echo "No text files found in output directory"
fi
