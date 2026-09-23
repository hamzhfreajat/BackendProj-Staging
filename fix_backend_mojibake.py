import sys

def fix_mojibake_file(filepath):
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()
    
    lines = content.split('\n')
    fixed_lines = []
    changed_count = 0
    
    for line in lines:
        if 'Ø' in line or 'Ù' in line or '?' in line:
            # Let's fix cp1252 to utf-8 mojibake
            try:
                # encode back to bytes
                b = line.encode('cp1252', errors='replace')
                # decode as utf-8
                fixed = b.decode('utf-8', errors='replace')
                
                # If there are literal '?' in prompt, let's just let it be or replace it with something
                if fixed != line:
                    fixed_lines.append(fixed)
                    changed_count += 1
                else:
                    fixed_lines.append(line)
            except Exception as e:
                fixed_lines.append(line)
        else:
            fixed_lines.append(line)
            
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write('\n'.join(fixed_lines))
    print(f"Fixed {changed_count} lines in {filepath}")

fix_mojibake_file(r'D:\open\classifieds-app-staging-backend\smart_search_router.py')
