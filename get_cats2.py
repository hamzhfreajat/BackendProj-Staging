import urllib.request, json, ssl
ctx = ssl.create_default_context()
ctx.check_hostname = False
ctx.verify_mode = ssl.CERT_NONE
req = urllib.request.Request('https://staging.sooq-com.com/api/categories/tree', headers={'User-Agent': 'Mozilla'})
try:
    with urllib.request.urlopen(req, context=ctx) as response:
        cats = json.loads(response.read().decode('utf-8'))
        def print_cats(clist, indent=''):
            for c in clist:
                lname = c['name']
                if '201' in str(c['id']) or '301' in str(c['id']) or '2'==str(c['id']) or '3'==str(c['id']):
                    print(indent + str(c['id']) + ": " + lname)
                if 'children' in c and c['children']:
                    print_cats(c['children'], indent + '  ')
        print_cats(cats)
exception as e:
    print(e)