import re
import time

def extract_user_info(msg: str):
    t1 = time.time()
    match = re.search(r'\bB\d{6}\b', msg)
    t2 = time.time()
    search_time = t2 - t1
    
    if match:
        user_id = match.group()
        
        t3 = time.time()
        id_pos = msg.find(user_id)
        name = msg[:id_pos].strip().split("\n")[0]
        t4 = time.time()
        process_time = t4 - t3
        
        return user_id, name, search_time, process_time
    
    return None, None, None, None

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
    ID - B122100
    Day 25:
    • Completed learning javascript
    • Solved leetcode problems based on sliding window
    ''',
    '''
    Binashak Mohanty
    B122038
    Day 15 :
    Learnt about working of sensors and their applications.
    Started working on a Scanner app.
    ''',
    '''Aurojyoti Das 
B422017
Day 24:
. Continued studying html
. Solved 2 question on gfg
    '''
]

for msg in messages:
    user_id, name, search_time, process_time = extract_user_info(msg)
    if user_id and name:
        print(f"ID: {user_id}")
        print(f"Name: {name}")
        print(f"Search Time: {search_time}")
        print(f"Process Time: {process_time}")
        print("-----")
