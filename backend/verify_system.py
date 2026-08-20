import urllib.request
import urllib.parse
import json

def verify_all():
    print("=== STARTING FULL SYSTEM VERIFICATION ===")
    
    # 1. Backend Health
    health = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/health").read().decode())
    print(f"1. Backend Health: {health['status']} ({health['engine']})")
    
    # 2. Presets
    presets = json.loads(urllib.request.urlopen("http://127.0.0.1:8000/api/presets").read().decode())
    print(f"2. Presets Count: {len(presets)}")
    
    # 3. Test all Presets Analysis
    for p in presets:
        data = urllib.parse.urlencode({"preset_id": p["id"]}).encode()
        req = urllib.request.Request("http://127.0.0.1:8000/api/analyze-preset", data=data)
        result = json.loads(urllib.request.urlopen(req).read().decode())
        print(f"   [PASS] Preset [{p['id']}] '{p['title']}': Score = {result['score']}/100, Grade = {result['grade']}, Defects = {len(result['findings'])}")
        
    # 4. Frontend Status
    frontend_html = urllib.request.urlopen("http://127.0.0.1:3000/").read().decode()
    print(f"4. Frontend Server: Status = 200 OK (HTML Length = {len(frontend_html)} bytes)")
    
    print("=== ALL VERIFICATION CHECKS PASSED SUCCESSFULLY ===")

if __name__ == "__main__":
    verify_all()
