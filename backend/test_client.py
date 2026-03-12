import requests

url = "http://127.0.0.1:8000/api/process"
data = {
    "video_id": "H5v3kku4y6Q", # "As It Was"
    "title": "As It Was",
    "artist": "Harry Styles"
}
print("Starting request...")
res = requests.post(url, json=data)
print("Status:", res.status_code)
try:
    print(res.json())
except:
    print(res.text)
