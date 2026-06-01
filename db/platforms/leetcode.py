import requests

HEADERS = {
    "Content-Type": "application/json",
    "User-Agent": "Mozilla/5.0"
}

def get_leetcode_data(username):
    query = {
        "operationName": "fullUserData",
        "variables": {"username": username},
        "query": """
        query fullUserData($username: String!) {
          matchedUser(username: $username) {
            username
            profile {
              realName
            }
            submitStats {
              acSubmissionNum {
                count
                difficulty
              }
            }
          }
          recentAcSubmissionList(username: $username) {
            id
            title
            titleSlug
            timestamp
          }
          userContestRanking(username: $username) {
            rating
            globalRanking
            totalParticipants
            attendedContestsCount
          }
        }
        """
    }

    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json=query,
            headers=HEADERS
        )
        response.raise_for_status()
        resp_json = response.json()
        
        if "errors" in resp_json:
            err_msg = resp_json["errors"][0].get("message", "Unknown GraphQL error")
            if "does not exist" in err_msg.lower():
                return {"error": "User Not Found", "message": f"LeetCode profile '{username}' does not exist or is private."}
            return {"error": "GraphQL Error", "message": err_msg}

        data = resp_json.get("data")
        if not data:
            return {"error": "No Data", "message": f"No data returned for '{username}'. Profile may be private."}

        matched_user = data.get("matchedUser")
        if matched_user is None:
            return {"error": "User Not Found", "message": f"LeetCode profile '{username}' does not exist or is private."}

        submissions = data.get("recentAcSubmissionList") or []
        contest = data.get("userContestRanking") or {}

        result = {
            "username": username,
            "realName": matched_user.get("profile", {}).get("realName", ""),
            "submitStats": {
                "total": matched_user["submitStats"]["acSubmissionNum"][0]["count"],
                "easy": matched_user["submitStats"]["acSubmissionNum"][1]["count"],
                "medium": matched_user["submitStats"]["acSubmissionNum"][2]["count"],
                "hard": matched_user["submitStats"]["acSubmissionNum"][3]["count"]
            },
            "recentSubmissions": submissions,
            "ratingInfo": contest
        }

        return result

    except requests.RequestException as e:
        print("Error fetching data:", str(e))
        return {"error": "Unable to Fetch Data", "message": str(e)}


def get_leetcode_recent_submissions(username):
    query = {
        "operationName": "recentAcSubmissions",
        "variables": {"username": username},
        "query": """
        query recentAcSubmissions($username: String!) {
            recentAcSubmissionList(username: $username) {
              id
              title
              titleSlug
              timestamp
            }
        }
        """
    }

    try:
        response = requests.post(
            "https://leetcode.com/graphql",
            json=query,
            headers=HEADERS
        )
        response.raise_for_status()
        resp_json = response.json()
        
        if "errors" in resp_json:
            err_msg = resp_json["errors"][0].get("message", "Unknown GraphQL error")
            if "does not exist" in err_msg.lower():
                return {"error": "User Not Found", "message": f"LeetCode profile '{username}' does not exist or is private."}
            return {"error": "GraphQL Error", "message": err_msg}

        data = resp_json.get("data", {})
        if data is None:
            return {"error": "Private Profile", "message": f"LeetCode profile '{username}' might be private."}
            
        submissions = data.get("recentAcSubmissionList")

        if submissions is None:
            return {"error": "Private Profile", "message": f"LeetCode profile '{username}' might be private."}

        return submissions

    except requests.RequestException as e:
        print("Error fetching recent submissions:", str(e))
        return {"error": "Unable to Fetch Data", "message": str(e)}
