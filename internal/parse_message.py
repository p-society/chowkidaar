import re
import time
from internal.dfa import IdentityAutomata

def extract_user_info(msg: str):
    machine = IdentityAutomata()
    msg = msg.lower()
    tokens = msg.split()
    potentialIds = [word for word in tokens if word[0] =='b']

    for k in potentialIds:
        if machine.is_accepted(k[1:]):
            name = msg.split("\n\n")[0].strip("\n")[0]
            id_location = msg.find(k)
            name = msg[:id_location].split()
        
            return name[0]+" "+ name[1],k
    return None,None

messages = [
    '''
    B422056
    Day 25:
    Continued learning elastic beanstalk and cloud functions
    Started working on a project using React-RTK with B122103
    solved some leetcode problem
    ''',
    '''
    B122126
    Day 25:
    Solved leetcode problems. Continued working on the app.
    ''',
    '''
    ID B122085 
    Day 22

    solved some questions in GFG Root to leaf paths , reverse level order traversal, k distance from root, nodes at odd level, sum of longest path from root to leaf.
    solved sort a linklist by bubble sort algorithm.
    solved some questions on string largest odd number in a string and reverse words in a string.
    ''',
    ""
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
    user_id, name = extract_user_info(msg)
    if user_id and name:
        print(f"ID: {user_id}")
        print(f"Name: {name}")
        print("-----")