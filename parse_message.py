import re

def extract_user_info(msg: str):
    # Search for the user ID pattern
    match = re.search(r'\bB\d{6}\b', msg)
    if match:
        user_id = match.group()
        print("user_id = ",user_id)
        # Find the position of the user ID in the message
        id_pos = msg.find(user_id)
        
        # Extract the name from the beginning of the message up to the user ID
        name = msg[:id_pos].strip()
        print("name_ = ",name)
        return user_id, name
    
    return None, None

# Example messages
messages = [
    '''
    Soubhik Gon
    B422056
    Day 25:
    Continued learning elastic beanstalk and cloud functions
    Started working on a project using React-RTK 
    solved some leetcode problem
    ''',
    '''
    Samarth Thaker
    B122126
    Day 25:
    Solved leetcode problems. Continued working on the app.
    ''',
    '''
    Pruthiraj panda
    ID B122085 
    Day 22

    solved some questions in GFG Root to leaf paths , reverse level order traversal, k distance from root, nodes at odd level, sum of longest path from root to leaf.
    solved sort a linklist by bubble sort algorithm.
    solved some questions on string largest odd number in a string and reverse words in a string.
    ''',
    '''
    Sarthak Mishra
    ID : B122100
    Day 25:
    • Completed learning javascript
    • Solved leetcode problems based on sliding window
    '''
]

for msg in messages:
    user_id, name = extract_user_info(msg)
    if user_id and name:
        print("User ID:", user_id)
        print("Name:", name)
        print("------")
