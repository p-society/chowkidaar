from db.platforms.leetcode import get_leetcode_recent_submissions
from db.platforms.codeforces import get_codeforces_recent_submissions
from db.db import save_cp_log, delete_cp_log, register_user, connect_to_database
from utils.parse_message import extract_user_info, extract_user_lc_cf_id, extract_day_number, is_registration_message
import json
import os

# Load questions configuration
QUESTIONS_FILE = os.path.join(os.path.dirname(__file__), "questions.json")
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
        sub_question_id=str(sub.get('problem').get('contestId'))+sub.get('problem').get('index')
        if str(sub_question_id) == str(question_id) and sub.get('verdict')=='OK':
            return True
    return False

def process_submissions(msg: str):
    """
    Process user submissions from a message.
    Handles both registration and daily log formats.
    
    Args:
        msg (str): The message containing user information and submissions
        
    Returns:
        dict: Status of submission processing with details
    """
    # Extract basic information
    user_id, name = extract_user_info(msg)
    platform_ids = extract_user_lc_cf_id(msg)
    
    # Validate basic data
    if not user_id:
        return {"error": "Could not extract user ID"}
    if not name:
        return {"error": "Could not extract user name"}
    
    # Check if this is a registration message
    if is_registration_message(msg):
        if not platform_ids['lc'] or not platform_ids['cf']:
            return {"error": "Could not extract platform IDs"}
            
        # Register/update user
        success = register_user(user_id, name, platform_ids['lc'], platform_ids['cf'])
        if not success:
            return {"error": "Failed to register user"}
            
        return {
            "status": "success",
            "message": "User registered successfully",
            "user_id": user_id,
            "name": name,
            "lc_handle": platform_ids['lc'],
            "cf_handle": platform_ids['cf']
        }
    
    # Handle daily log format
    day = extract_day_number(msg)
    if not day:
        return {"error": "Could not extract day number"}
    
    # Get questions for the day
    day_questions = questions.get(str(day))
    if not day_questions:
        return {"error": f"No questions found for day {day}"}
    
    # Get user's handles from database
    conn = connect_to_database()
    if not conn:
        return {"error": "Could not connect to database"}
        
    try:
        with conn.cursor() as cur:
            cur.execute('''
                SELECT lc_handle, cf_handle 
                FROM student_list_2024 
                WHERE stu_id = %s
            ''', (user_id,))
            result = cur.fetchone()
            
            if not result:
                return {"error": "User not registered. Please register first using the registration format."}
                
            lc_handle, cf_handle = result
            
            if not lc_handle or not cf_handle:
                return {"error": "User's LeetCode or CodeForces handle not found. Please register first."}
    
        # Get submissions using stored handles
        lc_submissions = get_leetcode_recent_submissions(lc_handle)
        cf_submissions = get_codeforces_recent_submissions(cf_handle)
        
        # Validate submissions
        if isinstance(lc_submissions, dict) and 'error' in lc_submissions:
            return {"error": f"LeetCode error: {lc_submissions['message']}"}
        if isinstance(cf_submissions, dict) and 'error' in cf_submissions:
            return {"error": f"CodeForces error: {cf_submissions['message']}"}
        
        # Check submissions against questions
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
        
        # Update database
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
            "name": name
        }
        
    except Exception as e:
        return {"error": f"Error processing submissions: {str(e)}"}
    finally:
        if conn:
            conn.close()

def cpLogs(studentId, usernameCF, usernameLC, realName, day):
    """
    Legacy function for backward compatibility.
    Use process_submissions() for new code.
    """
    leetcodeSubmission = get_leetcode_recent_submissions(usernameLC)
    codeforcesSubmission = get_codeforces_recent_submissions(usernameCF)
    questionOfDay = questions[str(day)]
    save_cp_log(studentId, questionOfDay, realName, leetcodeSubmission, codeforcesSubmission, day)
