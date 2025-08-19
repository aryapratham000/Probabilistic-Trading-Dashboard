import requests
from config import PROJECTX_USERNAME, PROJECTX_API_KEY, PROJECTX_BASE_URL

token = None
headers = {"Content-Type": "application/json"}

def authenticate():
    global token, headers
    url = f"{PROJECTX_BASE_URL}/api/Auth/loginKey"
    payload = {
        "userName": PROJECTX_USERNAME,
        "apiKey": PROJECTX_API_KEY
    }

    try:
        response = requests.post(url, json=payload, headers=headers)
        response.raise_for_status()
        data = response.json()

        if data.get("success"):
            token = data["token"]
            headers["Authorization"] = f"Bearer {token}"
            print("✅ Authentication successful")
            return token   
        else:
            raise Exception("❌ Authentication failed: " + str(data))

    except Exception as e:
        print("❌ Error during authentication:", e)
        raise

def get_headers():
    return headers

