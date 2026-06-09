from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).parent))

from src.extractor import ResumeExtractor

# Test with your PDF file
pdf_path = "Al Architect Resume.pdf"

if Path(pdf_path).exists():
    print(f"Testing extraction for: {pdf_path}")
    extractor = ResumeExtractor()
    try:
        text = extractor.extract(pdf_path)
        print(f"\n✅ Success! Extracted {len(text)} characters")
        print("\n--- First 500 characters ---")
        print(text[:500])
        print("--- End ---")
    except Exception as e:
        print(f"❌ Error: {e}")
else:
    print(f"❌ File not found: {pdf_path}")
    print(f"Current directory: {Path.cwd()}")
    print("Files in current directory:")
    for f in Path.cwd().iterdir():
        if f.suffix.lower() == '.pdf':
            print(f"  - {f.name}")