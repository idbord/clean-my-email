
from flask import Flask, render_template, request, jsonify
import sqlite3
import pandas as pd
import json
import os
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

app = Flask(__name__)

# --- Configuration ---
SCOPES = ['https://mail.google.com/']
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'
DB_PATH = 'emails.db'

def get_db_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def get_gmail_service():
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
    return build('gmail', 'v1', credentials=creds)

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/data')
def get_data():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT * FROM emails WHERE is_replied = 0 ORDER BY received_on DESC;", conn)
    conn.close()

    df['received_on'] = pd.to_datetime(df['received_on'], unit='ms')

    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    sender_email = request.args.get('sender_email')
    exclude_starred = request.args.get('exclude_starred', 'false').lower() == 'true'
    exclude_important = request.args.get('exclude_important', 'false').lower() == 'true'
    exclude_personal = request.args.get('exclude_personal', 'false').lower() == 'true'
    exclude_read = request.args.get('exclude_read', 'false').lower() == 'true'

    if start_date:
        df = df[df['received_on'] >= pd.to_datetime(start_date)]
    if end_date:
        df = df[df['received_on'] <= pd.to_datetime(end_date)]
    if sender_email and sender_email != 'all':
        df = df[df['sender_email'] == sender_email]
    if exclude_starred:
        df = df[df['is_starred'] == 0]
    if exclude_important:
        df = df[df['is_important'] == 0]
    if exclude_personal:
        df = df[df['is_personal'] == 0]
    if exclude_read:
        df = df[df['is_read'] == 0]

    # Sort by date and calculate cumulative sum for emails received
    emails_received_cumulative = df.groupby(df['received_on'].dt.date).size().reset_index(name='count')
    emails_received_cumulative['cumulative_count'] = emails_received_cumulative['count'].cumsum()

    emails_per_sender = df['sender_email'].value_counts().reset_index()
    emails_per_sender.columns = ['sender_email', 'count']

    # Convert received_on to milliseconds for JSON serialization after calculations
    df['received_on'] = df['received_on'].astype('int64').astype(int)

    chart_data = {
        'emails_received': {
            'labels': emails_received_cumulative['received_on'].astype(str).tolist(),
            'data': emails_received_cumulative['cumulative_count'].tolist()
        },
        'emails_per_sender': {
            'labels': emails_per_sender['sender_email'].tolist(),
            'data': emails_per_sender['count'].tolist()
        },
        'emails': df.to_dict(orient='records') # Add raw email data
    }

    return json.dumps(chart_data)

@app.route('/senders')
def get_senders():
    conn = get_db_connection()
    df = pd.read_sql_query("SELECT DISTINCT sender_email FROM emails", conn)
    conn.close()
    return json.dumps(df['sender_email'].tolist())

@app.route('/emails')
def get_emails():
    conn = get_db_connection()
    emails = conn.execute('SELECT * FROM emails ORDER BY received_on DESC').fetchall()
    conn.close()
    return jsonify([dict(row) for row in emails])

@app.route('/delete_emails', methods=['POST'])
def delete_emails():
    data = request.get_json()
    email_ids = data.get('ids', [])
    excluded_ids = data.get('excluded_ids', [])
    action = data.get('action', 'delete') # 'delete' or 'mark_read'

    # Filter out excluded_ids from email_ids
    email_ids_to_process = [id for id in email_ids if id not in excluded_ids]

    if not email_ids_to_process:
        return jsonify({'error': 'No email IDs provided for processing'}), 400

    try:
        service = get_gmail_service()
        if action == 'delete':
            service.users().messages().batchDelete(
                userId='me',
                body={
                    'ids': email_ids_to_process
                }
            ).execute()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM emails WHERE id IN ({', '.join('?' * len(email_ids_to_process))})", email_ids_to_process)
            conn.commit()
            conn.close()
            return jsonify({'message': f'{len(email_ids_to_process)} emails deleted successfully'})
        elif action == 'mark_read':
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': email_ids_to_process,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"UPDATE emails SET is_read = 1 WHERE id IN ({', '.join('?' * len(email_ids_to_process))})", email_ids_to_process)
            conn.commit()
            conn.close()
            return jsonify({'message': f'{len(email_ids_to_process)} emails marked as read successfully'})
        else:
            return jsonify({'error': 'Invalid action specified'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_filtered_emails', methods=['POST'])
def delete_filtered_emails():
    data = request.get_json()
    start_date = data.get('start_date')
    end_date = data.get('end_date')
    sender_email = data.get('sender_email')
    exclude_starred = data.get('exclude_starred', False)
    exclude_important = data.get('exclude_important', False)
    exclude_personal = data.get('exclude_personal', False)
    exclude_read = data.get('exclude_read', False)

    conn = get_db_connection()
    query = "SELECT id FROM emails WHERE 1=1"
    params = []

    if start_date:
        query += " AND received_on >= ?"
        params.append(pd.to_datetime(start_date).value // 10**6) # Convert to milliseconds
    if end_date:
        query += " AND received_on <= ?"
        params.append(pd.to_datetime(end_date).value // 10**6) # Convert to milliseconds
    if sender_email and sender_email != 'all':
        query += " AND sender_email = ?"
        params.append(sender_email)
    if exclude_starred:
        query += " AND is_starred = 0"
    if exclude_important:
        query += " AND is_important = 0"
    if exclude_personal:
        query += " AND is_personal = 0"
    if exclude_read:
        query += " AND is_read = 0"

    email_ids = [row['id'] for row in conn.execute(query, params).fetchall()]
    conn.close()

    if not email_ids:
        return jsonify({'message': 'No emails found matching the criteria'})

    try:
        service = get_gmail_service()
        action = request.get_json().get('action', 'delete') # 'delete' or 'mark_read'

        if action == 'delete':
            service.users().messages().batchDelete(
                userId='me',
                body={
                    'ids': email_ids
                }
            ).execute()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"DELETE FROM emails WHERE id IN ({', '.join('?' * len(email_ids))})", email_ids)
            conn.commit()
            conn.close()

            return jsonify({'message': f'{len(email_ids)} emails deleted successfully'})
        elif action == 'mark_read':
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': email_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute(f"UPDATE emails SET is_read = 1 WHERE id IN ({', '.join('?' * len(email_ids))})", email_ids)
            conn.commit()
            conn.close()
            return jsonify({'message': f'{len(email_ids)} emails marked as read successfully'})
        else:
            return jsonify({'error': 'Invalid action specified'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/delete_by_sender', methods=['POST'])
def delete_by_sender():
    data = request.get_json()
    sender_email = data.get('sender_email')

    if not sender_email:
        return jsonify({'error': 'No sender email provided'}), 400

    try:
        conn = get_db_connection()
        email_ids = [row['id'] for row in conn.execute('SELECT id FROM emails WHERE sender_email = ?', (sender_email,)).fetchall()]
        conn.close()

        if not email_ids:
            return jsonify({'message': 'No emails found for this sender'})

        service = get_gmail_service()
        action = request.get_json().get('action', 'delete') # 'delete' or 'mark_read'

        if action == 'delete':
            service.users().messages().batchDelete(
                userId='me',
                body={
                    'ids': email_ids
                }
            ).execute()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('DELETE FROM emails WHERE sender_email = ?', (sender_email,))
            conn.commit()
            conn.close()

            return jsonify({'message': f'All emails from {sender_email} deleted successfully'})
        elif action == 'mark_read':
            service.users().messages().batchModify(
                userId='me',
                body={
                    'ids': email_ids,
                    'removeLabelIds': ['UNREAD']
                }
            ).execute()

            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('UPDATE emails SET is_read = 1 WHERE sender_email = ?', (sender_email,))
            conn.commit()
            conn.close()
        else:
            return jsonify({'error': 'Invalid action specified'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)
