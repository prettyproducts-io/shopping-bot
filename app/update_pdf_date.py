import requests

url = 'http://epona.eqbay.co/update_pdf_date'  # Adjust the URL to your Flask server URL
data = {'new_date': 'Jun 28, 2024'}
response = requests.post(url, json=data)
print(response.json())