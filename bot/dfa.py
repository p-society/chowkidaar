class IdentityAutomata:
    def __init__(self) -> None:
        self.states = {'q0','q1','q2','q3','q4','q5','q6','q7','qx'}
        self.alphabet = {'B',0,1,2,3,4,5,6,7,8,9}
        self.transitions = {
            'q0':{
                'B':'qx',
                '0':'qx',
                '1':'q1',
                '2':'q1',
                '3':'q1',
                '4':'q1',
                '5':'q1',
                '6':'qx',
                '7':'qx',
                '8':'qx',
                '9':'qx',
            },
            'q1':{
                'B':'qx',
                '0':'qx',
                '1':'q2',
                '2':'q4',
                '3':'qx',
                '4':'qx',
                '5':'qx',
                '6':'qx',
                '7':'qx',
                '8':'qx',
                '9':'qx',
            },
            'q2':{
                'B':'qx',
                '0':'q3',
                '1':'q3',
                '2':'q3',
                '3':'q3',
                '4':'q3',
                '5':'q3',
                '6':'q3',
                '7':'q3',
                '8':'q3',
                '9':'q3',
            },
            'q4':{
                'B':'qx',
                '0':'q3',
                '1':'q3',
                '2':'q3',
                '3':'q3',
                '4':'qx',
                '5':'qx',
                '6':'qx',
                '7':'qx',
                '8':'qx',
                '9':'qx',
            },
            'q3': {
                'B':'qx',
                '0':'q5',
                '1':'q5',
                '2':'qx',
                '3':'qx',
                '4':'qx',
                '5':'qx',
                '6':'qx',
                '7':'qx',
                '8':'qx',
                '9':'qx',                
            },
            'q5':{
                'B':'qx',
                '0':'q6',
                '1':'q6',
                '2':'q6',
                '3':'q6',
                '4':'q6',
                '5':'q6',
                '6':'q6',
                '7':'q6',
                '8':'q6',
                '9':'q6',
            },
            'q6':{
                'B':'qx',
                '0':'q7',
                '1':'q7',
                '2':'q7',
                '3':'q7',
                '4':'q7',
                '5':'q7',
                '6':'q7',
                '7':'q7',
                '8':'q7',
                '9':'q7',
            },
            'q7':{
                'B':'qx',
                '0':'qx',
                '1':'qx',
                '2':'qx',
                '3':'qx',
                '4':'qx',
                '5':'qx',
                '6':'qx',
                '7':'qx',
                '8':'qx',
                '9':'qx',                
            }
        }
        self.initial_state = 'q0' # ->q0
        self.final_states = {'q7'} 
        
    def transition_state(self,state,symbol):
            if state in self.transitions and symbol in self.transitions[state]:
                return self.transitions[state][symbol]
            return None
        
    def is_accepted(self,string):
            current_state = self.initial_state
            for symbol in string:
                current_state = self.transition_state(current_state,symbol)
                if current_state == None:
                    return False
            return current_state in self.final_states