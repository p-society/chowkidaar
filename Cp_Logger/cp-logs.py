from platforms.leetcode import get_leetcode_recent_submissions
from platforms.codeforces import get_codeforces_recent_submissions
from database_service.mark_data import delete_db
from database_service.mark_data import mark_db
import json
import os
with open(os.path.join(os.path.dirname(__file__), "questions.json"), "r") as file:
    questions = json.load(file)

def cpLogs(studentId,usernameCF,usernameLC,realName,day):
    leetcodeSubmission=get_leetcode_recent_submissions(usernameLC)
    codeforcesSubmission=get_codeforces_recent_submissions(usernameCF)
    questionOfDay=questions[day]
    print(questionOfDay)
    mark_db(studentId,questionOfDay,realName,leetcodeSubmission,codeforcesSubmission,day)
