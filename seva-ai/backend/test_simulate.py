import requests

res = requests.post("http://localhost:8000/api/v1/reports/simulate/voice", json={"text": "There is a lot of stagnant water causing kids to have cholera"})
print("STATUS:", res.status_code)
print("BODY:", res.text)
