import re

def extract_user_info(msg: str):
    """
    Extract user ID and name from a message.
    
    Args:
        msg (str): The message string containing user information
        
    Returns:
        tuple: (user_id, name) if found, (None, None) otherwise
    """
    name = msg.split('\n')[0].strip()[5:]
    
    # Extract name (first line)
    msg = msg.lower()
    
    # Extract user ID - look for both formats
    # Format 1: "ID: B123456" or "ID - B123456"
    # Format 2: "B123456" directly
    id_patterns = [
        r'id:\s*([bB]\d+)',  # Format 1 with colon
        r'id\s*-\s*([bB]\d+)',  # Format 1 with dash
        r'([bB]\d+)'  # Format 2 direct ID
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, msg)
        if match:
            college_id = match.group(1)
            return college_id, name
                
    return None, None

def extract_user_lc_cf_id(msg: str):
    """
    Extract LeetCode and CodeForces IDs from a message string.
    Args:
        msg (str): The message string containing user information
    Returns:
        dict: A dictionary containing 'lc' and 'cf' keys with their respective IDs
    """
    # msg = msg.lower()
    
    result = {'lc': None, 'cf': None}
    
    # Look for both formats
    # Format 1: "LC: username" or "LC - username"
    # Format 2: "lc-username"
    lc_patterns = [
        r'(?i)lc:\s*(\w+)',
        r'(?i)lc\s*-\s*(\w+)',
        r'(?i)lc-(\w+)'
    ]
    
    cf_patterns = [
        r'(?i)cf:\s*(\w+)',
        r'(?i)cf\s*-\s*(\w+)',
        r'(?i)cf-(\w+)'
    ]
    
    for pattern in lc_patterns:
        match = re.search(pattern, msg)
        if match:
            result['lc'] = match.group(1)
            break
            
    for pattern in cf_patterns:
        match = re.search(pattern, msg)
        if match:
            result['cf'] = match.group(1)
            break
            
    return result

def extract_day_number(msg: str) -> int:
    """
    Extract the day number from a message string.
    Args:
        msg (str): The message string containing day information
    Returns:
        int: The day number if found, None otherwise
    """
    msg = msg.lower()
    tokens = msg.split()
    
    for i, token in enumerate(tokens):
        if token == 'day' and i + 1 < len(tokens):
            # Try to extract number from next token
            next_token = tokens[i + 1]
            # Remove any trailing punctuation
            next_token = next_token.rstrip(':.')
            try:
                return int(next_token)
            except ValueError:
                continue
    return None

def is_registration_message(msg: str) -> bool:
    """
    Check if a message is a registration message.
    A registration message must contain both LC and CF handles.
    
    Args:
        msg (str): The message to check
        
    Returns:
        bool: True if it's a registration message, False otherwise
    """
    platform_ids = extract_user_lc_cf_id(msg)
    return platform_ids['lc'] is not None and platform_ids['cf'] is not None

# Test messages
messages = [
    '''
    Soubhik Gon
    B422056
    lc-testingID
    cf-testingID
    Day 25:
    Continued learning elastic beanstalk and cloud functions
    Started working on a project using React-RTK 
    solved some leetcode problem
    ''',
    '''
    Samarth Thaker
    B122126
    lc-testingID
    cf-testingID
    Day 25:
    Solved leetcode problems. Continued working on the app.
    ''',
    '''
    Pruthiraj panda
    ID B122085 
    lc-testingID
    cf-testingID
    Day 22

    solved some questions in GFG Root to leaf paths , reverse level order traversal, k distance from root, nodes at odd level, sum of longest path from root to leaf.
    solved sort a linklist by bubble sort algorithm.
    solved some questions on string largest odd number in a string and reverse words in a string.
    ''',
    '''
    Sarthak Mishra
    ID - B122100
    lc-testingID
    cf-testingID
    Day 25:
    • Completed learning javascript
    • Solved leetcode problems based on sliding window
    ''',
    '''
    Binashak Mohanty
    B122038
    lc-testingID
    cf-testingID
    Day 15 :
    Learnt about working of sensors and their applications.
    Started working on a Scanner app.
    ''',
    '''Aurojyoti Das 
    B422017
    lc-testingID
    cf-testingID
    Day 24:
    . Continued studying html
    . Solved 2 question on gfg
    '''
]

if __name__ == "__main__":
    for msg in messages:
        user_id, name = extract_user_info(msg)
        if user_id and name:
            print(f"ID: {user_id}")
            print(f"Name: {name}")
            print("-----")
