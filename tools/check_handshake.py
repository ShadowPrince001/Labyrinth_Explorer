import urllib.request

url = 'http://127.0.0.1:5000/socket.io/?EIO=4&transport=polling'
req = urllib.request.Request(url)
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print('status', r.status)
        data = r.read().decode('utf-8', errors='replace')
        print('body:', data[:1000])
except Exception as e:
    print('error', e)
