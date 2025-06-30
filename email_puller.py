
import os.path
import sqlite3
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# --- Configuration ---
SCOPES = ['https://mail.google.com/']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'
DB_PATH = 'emails.db'

# --- Database ---
def initialize_database():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS emails (
            id TEXT PRIMARY KEY,
            thread_id TEXT,
            sender_name TEXT,
            sender_email TEXT,
            subject TEXT,
            received_on INTEGER,
            is_read INTEGER DEFAULT 0,
            is_personal INTEGER DEFAULT 0,
            is_social INTEGER DEFAULT 0,
            is_promotions INTEGER DEFAULT 0,
            is_updates INTEGER DEFAULT 0,
            is_forums INTEGER DEFAULT 0,
            is_important INTEGER DEFAULT 0,
            is_starred INTEGER DEFAULT 0,
            is_trash INTEGER DEFAULT 0,
            is_spam INTEGER DEFAULT 0,
            is_inbox INTEGER DEFAULT 0,
            is_replied INTEGER DEFAULT 0
        )
    ''')
    conn.commit()
    return conn

def insert_email(conn, email):
    cursor = conn.cursor()
    payload = email.get('payload', {})
    headers = payload.get('headers', [])
    
    sender = next((h['value'] for h in headers if h['name'] == 'From'), '')
    sender_email = sender
    sender_name = ''
    if '<' in sender and '>' in sender:
        sender_email = sender.split('<')[1].split('>')[0]
        sender_name = sender.split('<')[0].strip()
    
    subject = next((h['value'] for h in headers if h['name'] == 'Subject'), '')

    is_read = 0 if 'UNREAD' in email.get('labelIds', []) else 1
    labels = email.get('labelIds', [])
    is_personal = 1 if 'CATEGORY_PERSONAL' in labels else 0
    is_social = 1 if 'CATEGORY_SOCIAL' in labels else 0
    is_promotions = 1 if 'CATEGORY_PROMOTIONS' in labels else 0
    is_updates = 1 if 'CATEGORY_UPDATES' in labels else 0
    is_forums = 1 if 'CATEGORY_FORUMS' in labels else 0
    is_important = 1 if 'IMPORTANT' in labels else 0
    is_starred = 1 if 'STARRED' in labels else 0
    is_trash = 1 if 'TRASH' in labels else 0
    is_spam = 1 if 'SPAM' in labels else 0
    is_inbox = 1 if 'INBOX' in labels else 0
    is_replied = 1 if 'SENT' in labels else 0

    cursor.execute(
        'INSERT OR IGNORE INTO emails (id, thread_id, sender_name, sender_email, subject, received_on, is_read, is_personal, is_social, is_promotions, is_updates, is_forums, is_important, is_starred, is_trash, is_spam, is_inbox, is_replied) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)',
        (email['id'], email['threadId'], sender_name, sender_email, subject, email['internalDate'], is_read, is_personal, is_social, is_promotions, is_updates, is_forums, is_important, is_starred, is_trash, is_spam, is_inbox, is_replied)
    )

# --- Google API ---
def get_credentials():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return creds

def list_emails(service, conn):
    page_token = None
    email_count = 0
    while True:
        results = service.users().messages().list(userId='me', pageToken=page_token).execute()
        messages = results.get('messages', [])
        if not messages:
            print('No more emails found.')
            break

        for message in messages:
            msg = service.users().messages().get(userId='me', id=message['id'], format='full').execute()
            insert_email(conn, msg)
            email_count += 1
        
        page_token = results.get('nextPageToken')
        if not page_token:
            break
        print(f"Fetched {email_count} emails...")

    print(f"Finished fetching emails. Total: {email_count}")
    conn.commit()

# --- Main Execution ---
def main():
    try:
        print('Initializing database...')
        conn = initialize_database()
        print('Database initialized.')

        print('Authorizing with Google...')
        creds = get_credentials()
        service = build('gmail', 'v1', credentials=creds)
        print('Authorization successful.')

        print('Fetching emails from Gmail...')
        list_emails(service, conn)
        print('Email fetching complete.')

    except Exception as e:
        print(f'An error occurred: {e}')
    finally:
        if 'conn' in locals() and conn:
            conn.close()

if __name__ == '__main__':
    main()
