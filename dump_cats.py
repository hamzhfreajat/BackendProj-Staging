import extraction_constants

with open('cats.txt', 'w', encoding='utf-8') as f:
    for line in extraction_constants.REAL_ESTATE_CATEGORIES.split('\n'):
        if line.strip() and 'ID:' in line:
            f.write(line.strip() + '\n')
