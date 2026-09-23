with open('arabic_utils.py', 'rb') as f:
    text = f.read().decode('utf-8')

# The corruption is literally ??? in the file, because earlier we saw it in the commit!
# Wait! In git show HEAD it had '???'!
# Someone committed '???' to github!
# So I must replace '???' with 'الف' !

text = text.replace("'???' in text or '???' in text", "'الف' in text or 'ألف' in text")
text = text.replace("'?????' in text", "'مليون' in text")

with open('arabic_utils.py', 'wb') as f:
    f.write(text.encode('utf-8'))
