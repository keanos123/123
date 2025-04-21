import requests

def upload_file_to_gofile(file_path, api_key):
    url = "https://upload.gofile.io/uploadFile"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(file_path, 'rb') as f:
        files = {'file': (file_path, f)}
        response = requests.post(url, files=files, headers=headers)
    if response.status_code == 200:
        result = response.json()
        try:
            return result['data']['downloadPage']
        except Exception as e:
            return None
    else:
        return None
