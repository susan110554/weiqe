import urllib.request, json

base = 'http://127.0.0.1:8000'

# Login
req = urllib.request.Request(base+'/api/auth/login',
    data=json.dumps({'token':'admin-token'}).encode(),
    headers={'Content-Type':'application/json'})
jwt = json.loads(urllib.request.urlopen(req, timeout=5).read())['access_token']
print(f"[AUTH] JWT OK\n")

results = []
endpoints = [
    ('GET', '/health', None),
    ('GET', '/api/dashboard/stats', None),
    ('GET', '/api/cases', None),
    ('GET', '/api/users', None),
    ('GET', '/api/admins', None),
    ('GET', '/api/audit-logs', None),
    ('GET', '/api/blacklist', None),
    ('GET', '/api/fee-config', None),
    ('GET', '/api/agents', None),
    ('GET', '/api/system-config', None),
    ('GET', '/api/templates', None),
    ('GET', '/api/messages', None),
    ('GET', '/api/broadcasts', None),
    ('GET', '/api/pdf-templates', None),
]

for method, ep, body in endpoints:
    req = urllib.request.Request(base+ep, headers={'Authorization':'Bearer '+jwt})
    try:
        r = urllib.request.urlopen(req, timeout=5)
        d = json.loads(r.read())
        keys = list(d.keys()) if isinstance(d, dict) else type(d).__name__
        status = '✅'
        detail = str(keys)[:55]
    except Exception as e:
        code = e.code if hasattr(e, 'code') else '?'
        status = f'❌ {code}'
        detail = ''
    print(f"  {status}  {ep:35s}  {detail}")
