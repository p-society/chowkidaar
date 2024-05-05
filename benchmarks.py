import time
from dfa import IdentityAutomata

def benchmark_dfa(dfa, strings):
    total_time = 0
    for string in strings:
        start_time = time.time()
        is_accepted = dfa.is_accepted(string)
        end_time = time.time()
        total_time += end_time - start_time
        print(f"String '{string}' accepted: {is_accepted}")
    average_time_per_string = total_time / len(strings)
    print(f"Average time per string: {average_time_per_string} seconds")

# Example usage:
strings_to_test = ['429056', '1234567890', '422019'] * 100000
benchmark_dfa(IdentityAutomata(), strings_to_test)