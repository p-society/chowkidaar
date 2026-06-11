from db.platforms.leetcode import get_leetcode_recent_submissions
from db.platforms.codeforces import get_codeforces_recent_submissions
from db.db import save_cp_log, connect_to_database, delete_cp_log
import json
import os

QUESTIONS_FILE = os.path.join(os.path.dirname(os.path.dirname(__file__)), "configs", "questions.json")
with open(QUESTIONS_FILE, "r") as file:
    questions = json.load(file)

def check_lc(question_id, leetcode_submissions):
    """Check if a LeetCode question is solved"""
    for sub in leetcode_submissions:
        if str(sub.get("titleSlug")) == str(question_id):
            return True
    return False

def check_cf(question_id, codeforces_submissions):
    """Check if a CodeForces question is solved"""
    for sub in codeforces_submissions:
        sub_question_id = str(sub.get('problem').get('contestId')) + sub.get('problem').get('index')
        if str(sub_question_id) == str(question_id) and sub.get('verdict') == 'OK':
            return True
    return False

def process_slash_submission(user_id: str, day: int):
    """
    Process user submissions for a specific day using their student ID.
    """
    day_questions = questions.get(str(day))
    if not day_questions:
        return {"error": f"No questions found for day {day}"}
    
    conn = connect_to_database(purpose="Lookup Student Handles")
    if not conn:
        return {"error": "Could not connect to database"}
        
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT name, lc_handle, cf_handle 
                FROM student_list_2024 
                WHERE stu_id = %s
            ''', (user_id,))
            result = cur.fetchone()
            
            if not result:
                return {"error": "User not registered. Please register first using `/register`."}
                
            name, lc_handle, cf_handle = result
            
            if not lc_handle or not cf_handle:
                return {"error": "User's LeetCode or CodeForces handle not found. Please register first using `/register`."}
    except Exception as e:
        return {"error": f"Error fetching student: {str(e)}"}
    finally:
        conn.close()
    
    # Get submissions using stored handles
    lc_submissions = get_leetcode_recent_submissions(lc_handle)
    
    # Get CF submissions
    try:
        cf_submissions = get_codeforces_recent_submissions(cf_handle)
    except Exception:
        cf_submissions = {}
        
    # Determine which platforms failed
    lc_failed = isinstance(lc_submissions, dict) and 'error' in lc_submissions
    cf_failed = isinstance(cf_submissions, dict) and 'error' in cf_submissions

    if lc_failed and cf_failed:
        return {
            "queue_required": True,
            "failed_platform": "both",
            "error_message": f"LeetCode: {lc_submissions['message']}; CodeForces: {cf_submissions['message']}",
            "user_id": user_id,
            "name": name,
        }
    if lc_failed:
        return {
            "queue_required": True,
            "failed_platform": "leetcode",
            "error_message": lc_submissions['message'],
            "user_id": user_id,
            "name": name,
        }
    if cf_failed:
        return {
            "queue_required": True,
            "failed_platform": "codeforces",
            "error_message": cf_submissions['message'],
            "user_id": user_id,
            "name": name,
        }
    
    solved = []
    for idx, q in enumerate(day_questions):
        if q.startswith("LC"):
            question_id = q[3:]
            if check_lc(question_id, lc_submissions):
                solved.append(question_id)
        elif q.startswith("CF"):
            question_id = q[3:]
            if check_cf(question_id, cf_submissions):
                solved.append(question_id)
    
    try:
        save_cp_log(user_id, name, solved, day)
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    
    return {
        "status": "success",
        "solved_questions": solved,
        "total_questions": len(day_questions),
        "day": day,
        "user_id": user_id,
        "name": name,
        "day_questions": day_questions
    }

def get_user_status(user_id: str, day: int):
    """
    Get the status of a user's submissions for a given day without updating it.
    """
    day_questions = questions.get(str(day))
    if not day_questions:
        return {"error": f"No questions found for day {day}"}
        
    conn = connect_to_database(purpose="Fetch User CP Status")
    if not conn:
        return {"error": "Could not connect to database"}
        
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT q1, q2, q3 
                FROM student_list_2024 
                WHERE stu_id = %s
            ''', (user_id,))
            result = cur.fetchone()
            
            if not result:
                return {"error": "User not registered. Please register first."}
                
            q1, q2, q3 = result
            
            solved_questions = []
            if str(day) in (q1 or []): solved_questions.append(day_questions[0] if len(day_questions) > 0 else "")
            if str(day) in (q2 or []): solved_questions.append(day_questions[1] if len(day_questions) > 1 else "")
            if str(day) in (q3 or []): solved_questions.append(day_questions[2] if len(day_questions) > 2 else "")
            
            # Remove empty strings
            solved_questions = [q for q in solved_questions if q]
            
            return {
                "status": "success",
                "solved_questions": solved_questions,
                "total_questions": len(day_questions),
                "day_questions": day_questions
            }
    except Exception as e:
        return {"error": f"Database error: {str(e)}"}
    finally:
        if conn:
            conn.close()
