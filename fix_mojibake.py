import sys

def fix_file(filepath):
    with open(filepath, "rb") as f:
        content = f.read()
    
    text = content.decode("utf-8")
    
    try:
        fixed_text = text.encode("cp1252").decode("utf-8")
        with open(filepath, "wb") as f:
            f.write(fixed_text.encode("utf-8"))
        print("Fixed successfully!")
    except Exception as e:
        print("Error during cp1252 fix:", e)
        # Maybe it's not purely cp1252, let's try a custom replacement just for the ????? parts if needed
        # But wait, python's cp1252 might throw an error if there are characters not in cp1252.

fix_file("D:\\open\\classifieds-app-staging-backend\\smart_search_router.py")
