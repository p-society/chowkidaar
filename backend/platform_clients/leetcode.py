import requests
from typing import Dict, List

HEADERS = {"Content-Type": "application/json", "User-Agent": "Mozilla/5.0"}


def get_leetcode_data(username: str) -> Dict | None:
    """
    Fetch full user profile, submission stats, recent accepted submissions,
    and contest rating information for a given LeetCode username.

    Args:
        username (str): LeetCode username to query.

    Returns:
        dict: A dictionary containing user data, including:
            - 'username': str
            - 'realName': str (from profile)
            - 'submitStats': dict with total, easy, medium, hard AC counts
            - 'recentSubmissions': list of recent AC submissions
            - 'ratingInfo': contest rating and ranking info
        or
        None: If no data is returned (e.g. due to profile privacy settings)

    Raises:
        None: All exceptions are caught and handled internally.
    """
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
        """,
    }

    try:
        response = requests.post(
            "https://leetcode.com/graphql", json=query, headers=HEADERS
        )
        response.raise_for_status()
        data = response.json().get("data")

        if not data:
            print("No data returned (possible profile privacy settings).")
            return

        matched_user = data.get("matchedUser", {})
        submissions = data.get("recentAcSubmissionList", [])
        contest = data.get("userContestRanking", {})

        result = {
            "username": username,
            "realName": matched_user.get("profile", {}).get("realName", ""),
            "submitStats": {
                "total": matched_user["submitStats"]["acSubmissionNum"][0]["count"],
                "easy": matched_user["submitStats"]["acSubmissionNum"][1]["count"],
                "medium": matched_user["submitStats"]["acSubmissionNum"][2]["count"],
                "hard": matched_user["submitStats"]["acSubmissionNum"][3]["count"],
            },
            "recentSubmissions": submissions,
            "ratingInfo": contest,
        }

        return result

    except requests.RequestException as e:
        print("Error fetching data:", str(e))
        return {"error": "Unable to Fetch Data", "message": str(e)}


def get_leetcode_recent_submissions(username: str) -> List[Dict]:
    """
    Fetch a list of recent accepted submissions for a given LeetCode username.

    Args:
        username (str): LeetCode username to query.

    Returns:
        list: A list of dictionaries containing recent accepted submissions, each with:
            - 'id': str
            - 'title': str
            - 'titleSlug': str
            - 'timestamp': str
        or
        dict: An error dictionary if the request fails:
            - 'error': str
            - 'message': str (detailed exception message)

    Raises:
        None: All exceptions are caught and handled internally.
    """
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
        """,
    }

    try:
        response = requests.post(
            "https://leetcode.com/graphql", json=query, headers=HEADERS
        )
        response.raise_for_status()
        data = response.json().get("data", {})
        submissions = data.get("recentAcSubmissionList", [])

        if not submissions:
            print("No recent accepted submissions found or profile is private.")
            return []

        return submissions

    except requests.RequestException as e:
        print("Error fetching recent submissions:", str(e))
        return {"error": "Unable to Fetch Data", "message": str(e)}
