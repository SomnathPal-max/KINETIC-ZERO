import urllib.request
import json
import time

t0 = time.time()
print("Sending test request to Ollama...")
payload = {
    "model": "llama3.2:latest",
    "prompt": "Respond with JSON only: {\"category\": \"health\" or \"finance\", \"confidence\": 0.95}",
    "format": "json",
    "stream": False
}
req = urllib.request.Request(
    "http://127.0.0.1:11434/api/generate",
    data=json.dumps(payload).encode("utf-8"),
    headers={"Content-Type": "application/json"}
)
try:
    with urllib.request.urlopen(req, timeout=60.0) as resp:
        data = json.loads(resp.read().decode("utf-8"))
        print(f"Success in {time.time()-t0:.2f}s:")
        print("Response:", data.get("response"))
except Exception as e:
    print(f"Failed in {time.time()-t0:.2f}s: {e}")
