from prometheus_client import Counter, Gauge, start_http_server

# Discord metrics
message_new_attempts_total = Counter('discord_messages_new_attempts_total', 'Total number of new messages received')
message_new_edits_total = Counter('discord_messages_new_edit_attempts_total', 'Total number of patch request received')

messages_sent_total = Counter('discord_messages_sent_total', 'Total number of messages saved in DB')
messages_edited_total = Counter('discord_messages_edited_total', 'Total number of messages patched in DB')
messages_deleted_total = Counter('discord_messages_deleted_total', 'Total number of messages deleted in DB')

errors_encountered_total = Counter('errors_encountered_total', 'Total Errors Encountered during bot\'s processing of messages')

def start_metrics_server(port: int = 8000):
    start_http_server(port)
