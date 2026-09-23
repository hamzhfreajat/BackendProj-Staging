import csv
import sys

md_path = 'C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/ai_batch_md.md'
csv_path = 'C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/extracted_filters_report.csv'

with open(md_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

with open(csv_path, 'w', encoding='utf-8-sig', newline='') as f:
    writer = csv.writer(f)
    for line in lines:
        line = line.strip()
        if not line or line.startswith('|---'):
            continue
        
        # Remove leading and trailing |
        if line.startswith('|'):
            line = line[1:]
        if line.endswith('|'):
            line = line[:-1]
            
        row = [col.strip() for col in line.split('|')]
        writer.writerow(row)
