import requests

OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

#OLLAMA_URL = "http://127.0.0.1:11434/api/generate"

def query_ollama(prompt, model="llama3.1"):
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False
    }
    res = requests.post(OLLAMA_URL, json=payload)
    res.raise_for_status()
    return res.json()["response"]
