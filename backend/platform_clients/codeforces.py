import requests


def get_codeforces_recent_submissions(username, count=25):
    try:
        url = f"https://codeforces.com/api/user.status?handle={username}&from=1&count={count}"
        response = requests.get(url)
        response.raise_for_status()  # Raise exception for HTTP errors
        return response.json().get("result")  # Contains 'status' and 'result'
    except requests.RequestException as err:
        return {"error": "Unable to Fetch Data", "message": str(err)}
