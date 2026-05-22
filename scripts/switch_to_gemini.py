import urllib.request
import json
import sys

VAPI_KEY = "3a2e87a1-6100-42d2-b805-376dfae6cf99"
HEADERS = {"Authorization": f"Bearer {VAPI_KEY}", "Content-Type": "application/json"}


def vapi(method, path, body=None):
    url = f"https://api.vapi.ai{path}"
    data = json.dumps(body).encode() if body else None
    req = urllib.request.Request(url, data=data, headers=HEADERS, method=method)
    with urllib.request.urlopen(req, timeout=15) as r:
        return json.loads(r.read())


assistants = vapi("GET", "/assistant")
asst_list = assistants if isinstance(assistants, list) else assistants.get("data", [])
nova = next((a for a in asst_list if "Nova" in a.get("name", "")), None)

if not nova:
    print("ERROR: No Nova assistant found")
    sys.exit(1)

print(f"Found: {nova['name']} ({nova['id']})")
old_model = nova.get("model", {})

result = vapi("PATCH", f"/assistant/{nova['id']}", {
    "model": {
        "provider": "google",
        "model": "gemini-2.0-flash",
        "systemPrompt": old_model.get("systemPrompt", ""),
        "temperature": 0.7,
        "tools": old_model.get("tools", []),
    }
})

new_model = result.get("model", {})
print(f"Model: {new_model.get('provider')} / {new_model.get('model')}")
print("Assistant updated successfully!")
