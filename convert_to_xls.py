import csv
import sys

csv_path = 'C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/extracted_filters_report.csv'
xls_path = 'C:/Users/hfraijat/.gemini/antigravity/brain/696fb396-0dce-4ae5-a16f-7a3bb2cd2761/extracted_filters_report.xls'

html = '''<html xmlns:o="urn:schemas-microsoft-com:office:office" xmlns:x="urn:schemas-microsoft-com:office:excel" xmlns="http://www.w3.org/TR/REC-html40">
<head><meta http-equiv="Content-type" content="text/html;charset=utf-8" /></head><body><table border="1">'''

with open(csv_path, 'r', encoding='utf-8-sig') as f:
    reader = csv.reader(f)
    for row in reader:
        html += "<tr>" + "".join(f"<td>{col}</td>" for col in row) + "</tr>\n"

html += "</table></body></html>"

with open(xls_path, 'w', encoding='utf-8') as f:
    f.write(html)
