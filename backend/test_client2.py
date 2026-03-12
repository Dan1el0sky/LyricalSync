import requests

url = "http://127.0.0.1:8000/api/process"
data = {
    "video_id": "Vhh5MuZXnKU", # Dreams Pt 2
    "title": "Dreams, Pt. 2",
    "artist": "Matthew Mayer"
}
print("Starting request...")
res = requests.post(url, json=data)
print("Status:", res.status_code)
try:
    print(res.json())
except:
    print(res.text)
