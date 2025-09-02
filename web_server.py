# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import hashlib
import os
import hmac
import base64
import uuid
import sqlite3
import secrets 
from html import escape
from datetime import datetime, date, timedelta
from collections import defaultdict
import time
import re
from email.utils import formatdate

# --- Database Setup ---
DB_FILE = "database.db"

# --- Configuration ---
FAILED_LOGIN_ATTEMPTS = {}
LOCKOUT_TIME = 300
MAX_ATTEMPTS = 5
SESSION_TIMEOUT_SECONDS = 1800 # 30 minutes
ITEMS_PER_PAGE = 15 # Pagination limit

COMMISSIONED_RANKS = [
    'น.อ.(พ)', 'น.อ.(พ).หญิง', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.อ.หญิง', 
    'น.ท.', 'น.ท.หญิง', 'น.ต.', 'น.ต.หญิง', 
    'ร.อ.', 'ร.อ.หญิง', 'ร.ท.', 'ร.ท.หญิง', 'ร.ต.', 'ร.ต.หญิง'
]
NON_COMMISSIONED_RANKS = [
    'พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.อ.หญิง', 'พ.อ.ท.', 'พ.อ.ท.หญิง', 
    'พ.อ.ต.', 'พ.อ.ต.หญิง', 'จ.อ.', 'จ.อ.หญิง', 'จ.ท.', 'จ.ท.หญิง', 
    'จ.ต.', 'จ.ต.หญิง', 'นาย', 'นาง', 'นางสาว'
]
RANK_ORDER = COMMISSIONED_RANKS + NON_COMMISSIONED_RANKS

# --- Helper Functions ---
def get_personnel_type_from_rank(rank):
    if rank in COMMISSIONED_RANKS:
        return 'สัญญาบัตร'
    elif rank in NON_COMMISSIONED_RANKS:
        return 'ประทวน'
    return 'ไม่ระบุ'

def get_next_week_range_str():
    today = date.today()
    start_of_next_week = today + timedelta(days=(7 - today.weekday()))
    end_of_next_week = start_of_next_week + timedelta(days=6)
    thai_months_abbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    start_day = start_of_next_week.day
    start_month = thai_months_abbr[start_of_next_week.month - 1]
    start_year_be = start_of_next_week.year + 543
    end_day = end_of_next_week.day
    end_month = thai_months_abbr[end_of_next_week.month - 1]
    end_year_be = end_of_next_week.year + 543

    if start_year_be != end_year_be:
        return f"รอบวันที่ {start_day} {start_month} {start_year_be} - {end_day} {end_month} {end_year_be}"
    elif start_month != end_month:
        return f"รอบวันที่ {start_day} {start_month} - {end_day} {end_month} {end_year_be}"
    else:
        return f"รอบวันที่ {start_day} - {end_day} {end_month} {end_year_be}"

# --- Database Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, key BLOB NOT NULL, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, department TEXT, role TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS personnel (id TEXT PRIMARY KEY, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, specialty TEXT, department TEXT, personnel_type TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS archived_reports (id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, date TEXT NOT NULL, department TEXT, submitted_by TEXT, report_data TEXT, timestamp DATETIME)')
    cursor.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS persistent_statuses (id TEXT PRIMARY KEY, personnel_id TEXT NOT NULL, department TEXT NOT NULL, status TEXT, details TEXT, start_date TEXT, end_date TEXT, FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS daily_status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS daily_archived_reports (id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, date TEXT NOT NULL, department TEXT, submitted_by TEXT, report_data TEXT, timestamp DATETIME)')
    
    try:
        cursor.execute('ALTER TABLE personnel ADD COLUMN personnel_type TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists

    cursor.execute("SELECT * FROM users WHERE username = ?", ('jeerawut',))
    if not cursor.fetchone():
        salt, key = hash_password("Jee@wut2534")
        cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('jeerawut', salt, key, 'น.อ.', 'จีราวุฒิ', 'ผู้ดูแลระบบ', 'ผู้ดูแลระบบ', 'ส่วนกลาง', 'admin'))
    conn.commit()
    conn.close()

# --- Security Functions ---
def hash_password(password, salt=None):
    if salt is None: salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt, key

def verify_password(salt, key, password_to_check):
    return hmac.compare_digest(key, hash_password(password_to_check, salt)[1])

def is_password_complex(password):
    if len(password) < 8: return False
    if not re.search("[a-z]", password): return False
    if not re.search("[A-Z]", password): return False
    if not re.search("[0-9]", password): return False
    return True

# --- Generic Handlers ---
def handle_login(payload, conn, cursor, client_address):
    # ... (code is identical to previous versions, omitted for brevity)
    ip_address = client_address[0]
    if ip_address in FAILED_LOGIN_ATTEMPTS:
        attempts, last_attempt_time = FAILED_LOGIN_ATTEMPTS[ip_address]
        if attempts >= MAX_ATTEMPTS and time.time() - last_attempt_time < LOCKOUT_TIME:
            return {"status": "error", "message": "คุณพยายามล็อกอินผิดพลาดบ่อยเกินไป กรุณาลองใหม่อีกครั้งใน 5 นาที"}, None
    
    username, password = payload.get("username"), payload.get("password")
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    
    if user_data and verify_password(user_data['salt'], user_data['key'], password):
        if ip_address in FAILED_LOGIN_ATTEMPTS: del FAILED_LOGIN_ATTEMPTS[ip_address]
        session_token = secrets.token_hex(16)
        cursor.execute("INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)", 
                       (session_token, user_data["username"], datetime.now()))
        conn.commit()
        user_info = {k: user_data[k] for k in user_data.keys() if k not in ['salt', 'key']}
        expires_time = time.time() + SESSION_TIMEOUT_SECONDS
        cookie_attrs = [
            f'session_token={session_token}', 'HttpOnly', 'Path=/', 'SameSite=Strict',
            f'Max-Age={SESSION_TIMEOUT_SECONDS}', f'Expires={formatdate(expires_time, usegmt=True)}'
        ]
        headers = [('Set-Cookie', '; '.join(cookie_attrs))]
        return {"status": "success", "user": user_info}, headers
    else:
        if ip_address in FAILED_LOGIN_ATTEMPTS: FAILED_LOGIN_ATTEMPTS[ip_address] = (FAILED_LOGIN_ATTEMPTS[ip_address][0] + 1, time.time())
        else: FAILED_LOGIN_ATTEMPTS[ip_address] = (1, time.time())
        return {"status": "error", "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}, None

def handle_logout(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    token_to_delete = session.get("token")
    if token_to_delete:
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_to_delete,))
        conn.commit()
    headers = [('Set-Cookie', 'session_token=; HttpOnly; Path=/; SameSite=Strict; Expires=Thu, 01 Jan 1970 00:00:00 GMT')]
    return {"status": "success", "message": "ออกจากระบบสำเร็จ"}, headers

# --- Weekly System Handlers ---
def handle_get_dashboard_summary(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    query = "SELECT sr.department, sr.report_data, sr.timestamp, u.rank, u.first_name, u.last_name FROM status_reports sr JOIN users u ON sr.submitted_by = u.username WHERE sr.timestamp = (SELECT MAX(timestamp) FROM status_reports WHERE department = sr.department)"
    cursor.execute(query)
    
    submitted_info = {}
    status_summary = defaultdict(int)
    latest_reports = cursor.fetchall()

    for row in latest_reports:
        try:
            items = json.loads(row['report_data'])
            submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
            submitted_info[row['department']] = {'submitter_fullname': submitter_fullname, 'timestamp': row['timestamp'], 'status_count': len(items)}
            for item in items:
                status_summary[item.get('status', 'ไม่ระบุ')] += 1
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted report data for department {row['department']}")
            continue

    cursor.execute("SELECT COUNT(id) as total FROM personnel WHERE personnel_type = 'สัญญาบัตร'")
    total_personnel_row = cursor.fetchone()
    total_personnel = total_personnel_row['total'] if total_personnel_row else 0
    
    total_on_duty = total_personnel - sum(status_summary.values())

    summary = {"all_departments": all_departments, "submitted_info": submitted_info, "status_summary": dict(status_summary), "total_personnel": total_personnel, "total_on_duty": total_on_duty, "weekly_date_range": get_next_week_range_str()}
    return {"status": "success", "summary": summary}
    
def handle_list_personnel(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    page = payload.get("page", 1)
    search_term_from_payload = payload.get("searchTerm")
    fetch_all = payload.get("fetchAll", False)
    offset = (page - 1) * ITEMS_PER_PAGE
    base_query = " FROM personnel"
    params, where_clauses = [], []
    is_admin, department = session.get("role") == "admin", session.get("department")
    
    if fetch_all:
        where_clauses.append("personnel_type = 'สัญญาบัตร'")

    if not is_admin:
        where_clauses.append("department = ?"); params.append(department)

    if search_term_from_payload and search_term_from_payload.strip():
        search_term = search_term_from_payload.strip()
        search_like_clause = "(first_name LIKE ? OR last_name LIKE ? OR position LIKE ? OR rank LIKE ? OR department LIKE ? OR personnel_type LIKE ?)"
        where_clauses.append(search_like_clause)
        term = f"%{search_term}%"
        params.extend([term] * 6)
    
    where_clause_str = ""
    if where_clauses:
        where_clause_str = " WHERE " + " AND ".join(where_clauses)
    
    count_query = "SELECT COUNT(*) as total" + base_query + where_clause_str
    cursor.execute(count_query, params)
    total_items = cursor.fetchone()['total']
    
    data_query = "SELECT *" + base_query + where_clause_str
    if not fetch_all:
        data_query += " LIMIT ? OFFSET ?"
        params.extend([ITEMS_PER_PAGE, offset])
    
    cursor.execute(data_query, params)
    personnel = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]
    
    submission_status = None
    if not is_admin:
        cursor.execute("SELECT timestamp FROM status_reports WHERE department = ? ORDER BY timestamp DESC LIMIT 1", (department,))
        last_submission = cursor.fetchone()
        if last_submission: submission_status = {"timestamp": last_submission['timestamp']}

    persistent_statuses = []
    if fetch_all:
        today = date.today()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        next_week_start_str = start_of_next_week.isoformat()
        
        status_query_params = [next_week_start_str]
        status_query = "SELECT personnel_id, department, status, details, start_date, end_date FROM persistent_statuses WHERE end_date >= ?"
        
        if not is_admin:
            status_query += " AND department = ?"
            status_query_params.append(department)
        
        cursor.execute(status_query, status_query_params)
        persistent_statuses = [dict(row) for row in cursor.fetchall()]

    return {
        "status": "success", 
        "personnel": personnel, 
        "total": total_items, 
        "page": page, 
        "submission_status": submission_status, 
        "weekly_date_range": get_next_week_range_str(),
        "persistent_statuses": persistent_statuses
    }
    
def handle_get_active_statuses(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    today_str = date.today().isoformat()
    is_admin = session.get("role") == "admin"
    department = session.get("department")

    # This query gets all persistent statuses for ALL commissioned officers
    query_unavailable = """
        SELECT 
            ps.status, ps.details, ps.start_date, ps.end_date, ps.personnel_id,
            p.rank, p.first_name, p.last_name, p.department
        FROM persistent_statuses ps
        JOIN personnel p ON ps.personnel_id = p.id
        WHERE ps.end_date >= ? AND p.personnel_type = 'สัญญาบัตร'
    """
    params_unavailable = [today_str]
    if not is_admin:
        query_unavailable += " AND ps.department = ?"
        params_unavailable.append(department)
    
    cursor.execute(query_unavailable, params_unavailable)
    unavailable_personnel = [dict(row) for row in cursor.fetchall()]
    unavailable_ids = {p['personnel_id'] for p in unavailable_personnel}

    # Get all commissioned officers
    query_all = "SELECT id, rank, first_name, last_name, department FROM personnel WHERE personnel_type = 'สัญญาบัตร'"
    params_all = []
    if not is_admin:
        query_all += " AND department = ?"
        params_all.append(department)

    cursor.execute(query_all, params_all)
    all_personnel = [dict(row) for row in cursor.fetchall()]
    available_personnel = [p for p in all_personnel if p['id'] not in unavailable_ids]

    def get_rank_index(item):
        try: return RANK_ORDER.index(item['rank'])
        except ValueError: return len(RANK_ORDER)

    unavailable_personnel.sort(key=get_rank_index)
    available_personnel.sort(key=get_rank_index)
    total_personnel_in_scope = len(all_personnel)

    return {
        "status": "success", 
        "active_statuses": unavailable_personnel,
        "available_personnel": available_personnel,
        "total_personnel": total_personnel_in_scope
    }
    
# --- Daily System Handlers ---
def handle_get_daily_dashboard_summary(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    # The daily report is always for the *next* day, so we calculate tomorrow's date.
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    # Fetch reports submitted for tomorrow's date.
    query = "SELECT dsr.department, dsr.report_data, dsr.timestamp, u.rank, u.first_name, u.last_name FROM daily_status_reports dsr JOIN users u ON dsr.submitted_by = u.username WHERE dsr.date = ?"
    cursor.execute(query, (report_date_str,))
    
    submitted_info = {}
    status_summary = defaultdict(int)
    
    for row in cursor.fetchall():
        try:
            items = json.loads(row['report_data'])
            submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
            submitted_info[row['department']] = {'submitter_fullname': submitter_fullname, 'timestamp': row['timestamp']}
            for item in items:
                status_summary[item.get('status', 'ไม่ระบุ')] += 1
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily report for department {row['department']}")
            continue

    # Count all personnel for the daily dashboard
    cursor.execute("SELECT COUNT(id) as total FROM personnel")
    total_personnel_row = cursor.fetchone()
    total_personnel = total_personnel_row['total'] if total_personnel_row else 0
    
    summary = {
        "all_departments": all_departments, 
        "submitted_info": submitted_info, 
        "status_summary": dict(status_summary), 
        "total_personnel": total_personnel,
        "date": report_date_str
    }
    return {"status": "success", "summary": summary}
    
def handle_get_personnel_for_daily_report(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    department = session.get("department")
    is_admin = session.get("role") == "admin"
    
    if is_admin and payload.get("department"):
        department = payload.get("department")

    cursor.execute("SELECT * FROM personnel WHERE department = ?", (department,))
    personnel = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]

    # Check submission status for *tomorrow's* report.
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    cursor.execute("SELECT timestamp FROM daily_status_reports WHERE department = ? AND date = ?", (department, report_date_str))
    last_submission = cursor.fetchone()
    submission_status = {"timestamp": last_submission['timestamp']} if last_submission else None

    all_departments = []
    if is_admin:
        cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
        all_departments = [row['department'] for row in cursor.fetchall()]

    return {
        "status": "success", 
        "personnel": personnel, 
        "submission_status": submission_status,
        "all_departments": all_departments,
    }

def handle_get_daily_submission_history(payload, conn, cursor, session):
    is_admin = session.get("role") == "admin"
    department_filter = payload.get("department")
    
    params = {}
    query = """
    SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source 
    FROM daily_status_reports
    """
    
    where_clauses = []
    if not is_admin:
        where_clauses.append("department = :dept")
        params["dept"] = session.get("department")
    elif department_filter:
        where_clauses.append("department = :dept")
        params["dept"] = department_filter

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    
    history_by_date = defaultdict(list)
    
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            history_by_date[report["date"]].append(report)
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily history report with id {row['id']}")
            continue
    
    cursor.execute("SELECT DISTINCT department FROM personnel")
    all_departments = [row['department'] for row in cursor.fetchall()]
        
    return {"status": "success", "history": dict(history_by_date), "all_departments": all_departments}

def handle_get_daily_reports(payload, conn, cursor, session):
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')

    query = """
    SELECT dsr.id, dsr.date, dsr.department, dsr.timestamp, dsr.report_data, 
           u.rank, u.first_name, u.last_name 
    FROM daily_status_reports dsr 
    JOIN users u ON dsr.submitted_by = u.username 
    WHERE dsr.date = ? 
    ORDER BY dsr.department
    """
    cursor.execute(query, (report_date_str,))
    
    reports = []
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            reports.append(report)
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily report with id {row['id']}")
            continue
            
    return {"status": "success", "reports": reports, "date": report_date_str}

# --- Shared Handlers ---
# ... (All other handlers like submit, archive, edit, manage users/personnel are omitted for brevity as they remain unchanged)
# -*- coding: utf-8 -*-
from http.server import BaseHTTPRequestHandler, HTTPServer
import json
import hashlib
import os
import hmac
import base64
import uuid
import sqlite3
import secrets 
from html import escape
from datetime import datetime, date, timedelta
from collections import defaultdict
import time
import re
from email.utils import formatdate

# --- Database Setup ---
DB_FILE = "database.db"

# --- Configuration ---
FAILED_LOGIN_ATTEMPTS = {}
LOCKOUT_TIME = 300
MAX_ATTEMPTS = 5
SESSION_TIMEOUT_SECONDS = 1800 # 30 minutes
ITEMS_PER_PAGE = 15 # Pagination limit

COMMISSIONED_RANKS = [
    'น.อ.(พ)', 'น.อ.(พ).หญิง', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.อ.หญิง', 
    'น.ท.', 'น.ท.หญิง', 'น.ต.', 'น.ต.หญิง', 
    'ร.อ.', 'ร.อ.หญิง', 'ร.ท.', 'ร.ท.หญิง', 'ร.ต.', 'ร.ต.หญิง'
]
NON_COMMISSIONED_RANKS = [
    'พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.อ.หญิง', 'พ.อ.ท.', 'พ.อ.ท.หญิง', 
    'พ.อ.ต.', 'พ.อ.ต.หญิง', 'จ.อ.', 'จ.อ.หญิง', 'จ.ท.', 'จ.ท.หญิง', 
    'จ.ต.', 'จ.ต.หญิง', 'นาย', 'นาง', 'นางสาว'
]
RANK_ORDER = COMMISSIONED_RANKS + NON_COMMISSIONED_RANKS

# --- Helper Functions ---
def get_personnel_type_from_rank(rank):
    if rank in COMMISSIONED_RANKS:
        return 'สัญญาบัตร'
    elif rank in NON_COMMISSIONED_RANKS:
        return 'ประทวน'
    return 'ไม่ระบุ'

def get_next_week_range_str():
    today = date.today()
    start_of_next_week = today + timedelta(days=(7 - today.weekday()))
    end_of_next_week = start_of_next_week + timedelta(days=6)
    thai_months_abbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]
    start_day = start_of_next_week.day
    start_month = thai_months_abbr[start_of_next_week.month - 1]
    start_year_be = start_of_next_week.year + 543
    end_day = end_of_next_week.day
    end_month = thai_months_abbr[end_of_next_week.month - 1]
    end_year_be = end_of_next_week.year + 543

    if start_year_be != end_year_be:
        return f"รอบวันที่ {start_day} {start_month} {start_year_be} - {end_day} {end_month} {end_year_be}"
    elif start_month != end_month:
        return f"รอบวันที่ {start_day} {start_month} - {end_day} {end_month} {end_year_be}"
    else:
        return f"รอบวันที่ {start_day} - {end_day} {end_month} {end_year_be}"

# --- Database Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, key BLOB NOT NULL, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, department TEXT, role TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS personnel (id TEXT PRIMARY KEY, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, specialty TEXT, department TEXT, personnel_type TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS archived_reports (id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, date TEXT NOT NULL, department TEXT, submitted_by TEXT, report_data TEXT, timestamp DATETIME)')
    cursor.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS persistent_statuses (id TEXT PRIMARY KEY, personnel_id TEXT NOT NULL, department TEXT NOT NULL, status TEXT, details TEXT, start_date TEXT, end_date TEXT, FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE)')
    cursor.execute('CREATE TABLE IF NOT EXISTS daily_status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS daily_archived_reports (id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, date TEXT NOT NULL, department TEXT, submitted_by TEXT, report_data TEXT, timestamp DATETIME)')
    
    try:
        cursor.execute('ALTER TABLE personnel ADD COLUMN personnel_type TEXT')
    except sqlite3.OperationalError:
        pass # Column already exists

    cursor.execute("SELECT * FROM users WHERE username = ?", ('jeerawut',))
    if not cursor.fetchone():
        salt, key = hash_password("Jee@wut2534")
        cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('jeerawut', salt, key, 'น.อ.', 'จีราวุฒิ', 'ผู้ดูแลระบบ', 'ผู้ดูแลระบบ', 'ส่วนกลาง', 'admin'))
    conn.commit()
    conn.close()


# --- Security Functions ---
def hash_password(password, salt=None):
    if salt is None: salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt, key

def verify_password(salt, key, password_to_check):
    return hmac.compare_digest(key, hash_password(password_to_check, salt)[1])

def is_password_complex(password):
    if len(password) < 8: return False
    if not re.search("[a-z]", password): return False
    if not re.search("[A-Z]", password): return False
    if not re.search("[0-9]", password): return False
    return True

# --- Action Handlers ---
def handle_login(payload, conn, cursor, client_address):
    # ... (code is identical to previous versions, omitted for brevity)
    ip_address = client_address[0]
    if ip_address in FAILED_LOGIN_ATTEMPTS:
        attempts, last_attempt_time = FAILED_LOGIN_ATTEMPTS[ip_address]
        if attempts >= MAX_ATTEMPTS and time.time() - last_attempt_time < LOCKOUT_TIME:
            return {"status": "error", "message": "คุณพยายามล็อกอินผิดพลาดบ่อยเกินไป กรุณาลองใหม่อีกครั้งใน 5 นาที"}, None
    
    username, password = payload.get("username"), payload.get("password")
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    user_data = cursor.fetchone()
    
    if user_data and verify_password(user_data['salt'], user_data['key'], password):
        if ip_address in FAILED_LOGIN_ATTEMPTS: del FAILED_LOGIN_ATTEMPTS[ip_address]
        session_token = secrets.token_hex(16)
        cursor.execute("INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)", 
                       (session_token, user_data["username"], datetime.now()))
        conn.commit()
        user_info = {k: user_data[k] for k in user_data.keys() if k not in ['salt', 'key']}
        expires_time = time.time() + SESSION_TIMEOUT_SECONDS
        cookie_attrs = [
            f'session_token={session_token}', 'HttpOnly', 'Path=/', 'SameSite=Strict',
            f'Max-Age={SESSION_TIMEOUT_SECONDS}', f'Expires={formatdate(expires_time, usegmt=True)}'
        ]
        headers = [('Set-Cookie', '; '.join(cookie_attrs))]
        return {"status": "success", "user": user_info}, headers
    else:
        if ip_address in FAILED_LOGIN_ATTEMPTS: FAILED_LOGIN_ATTEMPTS[ip_address] = (FAILED_LOGIN_ATTEMPTS[ip_address][0] + 1, time.time())
        else: FAILED_LOGIN_ATTEMPTS[ip_address] = (1, time.time())
        return {"status": "error", "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}, None

def handle_logout(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    token_to_delete = session.get("token")
    if token_to_delete:
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_to_delete,))
        conn.commit()
    headers = [('Set-Cookie', 'session_token=; HttpOnly; Path=/; SameSite=Strict; Expires=Thu, 01 Jan 1970 00:00:00 GMT')]
    return {"status": "success", "message": "ออกจากระบบสำเร็จ"}, headers

# --- Weekly System Handlers ---
def handle_get_dashboard_summary(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    query = "SELECT sr.department, sr.report_data, sr.timestamp, u.rank, u.first_name, u.last_name FROM status_reports sr JOIN users u ON sr.submitted_by = u.username WHERE sr.timestamp = (SELECT MAX(timestamp) FROM status_reports WHERE department = sr.department)"
    cursor.execute(query)
    
    submitted_info = {}
    status_summary = defaultdict(int)
    latest_reports = cursor.fetchall()

    for row in latest_reports:
        try:
            items = json.loads(row['report_data'])
            submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
            submitted_info[row['department']] = {'submitter_fullname': submitter_fullname, 'timestamp': row['timestamp'], 'status_count': len(items)}
            for item in items:
                status_summary[item.get('status', 'ไม่ระบุ')] += 1
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted report data for department {row['department']}")
            continue

    cursor.execute("SELECT COUNT(id) as total FROM personnel WHERE personnel_type = 'สัญญาบัตร'")
    total_personnel_row = cursor.fetchone()
    total_personnel = total_personnel_row['total'] if total_personnel_row else 0
    
    total_on_duty = total_personnel - sum(status_summary.values())

    summary = {"all_departments": all_departments, "submitted_info": submitted_info, "status_summary": dict(status_summary), "total_personnel": total_personnel, "total_on_duty": total_on_duty, "weekly_date_range": get_next_week_range_str()}
    return {"status": "success", "summary": summary}
    
def handle_list_personnel(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    page = payload.get("page", 1)
    search_term_from_payload = payload.get("searchTerm")
    fetch_all = payload.get("fetchAll", False)
    offset = (page - 1) * ITEMS_PER_PAGE
    base_query = " FROM personnel"
    params, where_clauses = [], []
    is_admin, department = session.get("role") == "admin", session.get("department")
    
    if fetch_all:
        where_clauses.append("personnel_type = 'สัญญาบัตร'")

    if not is_admin:
        where_clauses.append("department = ?"); params.append(department)

    if search_term_from_payload and search_term_from_payload.strip():
        search_term = search_term_from_payload.strip()
        search_like_clause = "(first_name LIKE ? OR last_name LIKE ? OR position LIKE ? OR rank LIKE ? OR department LIKE ? OR personnel_type LIKE ?)"
        where_clauses.append(search_like_clause)
        term = f"%{search_term}%"
        params.extend([term] * 6)
    
    where_clause_str = ""
    if where_clauses:
        where_clause_str = " WHERE " + " AND ".join(where_clauses)
    
    count_query = "SELECT COUNT(*) as total" + base_query + where_clause_str
    cursor.execute(count_query, params)
    total_items = cursor.fetchone()['total']
    
    data_query = "SELECT *" + base_query + where_clause_str
    if not fetch_all:
        data_query += " LIMIT ? OFFSET ?"
        params.extend([ITEMS_PER_PAGE, offset])
    
    cursor.execute(data_query, params)
    personnel = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]
    
    submission_status = None
    if not is_admin:
        cursor.execute("SELECT timestamp FROM status_reports WHERE department = ? ORDER BY timestamp DESC LIMIT 1", (department,))
        last_submission = cursor.fetchone()
        if last_submission: submission_status = {"timestamp": last_submission['timestamp']}

    persistent_statuses = []
    if fetch_all:
        today = date.today()
        start_of_next_week = today + timedelta(days=(7 - today.weekday()))
        next_week_start_str = start_of_next_week.isoformat()
        
        status_query_params = [next_week_start_str]
        status_query = "SELECT personnel_id, department, status, details, start_date, end_date FROM persistent_statuses WHERE end_date >= ?"
        
        if not is_admin:
            status_query += " AND department = ?"
            status_query_params.append(department)
        
        cursor.execute(status_query, status_query_params)
        persistent_statuses = [dict(row) for row in cursor.fetchall()]

    return {
        "status": "success", 
        "personnel": personnel, 
        "total": total_items, 
        "page": page, 
        "submission_status": submission_status, 
        "weekly_date_range": get_next_week_range_str(),
        "persistent_statuses": persistent_statuses
    }
    
def handle_get_active_statuses(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    today_str = date.today().isoformat()
    is_admin = session.get("role") == "admin"
    department = session.get("department")

    # This query gets all persistent statuses for ALL commissioned officers
    query_unavailable = """
        SELECT 
            ps.status, ps.details, ps.start_date, ps.end_date, ps.personnel_id,
            p.rank, p.first_name, p.last_name, p.department
        FROM persistent_statuses ps
        JOIN personnel p ON ps.personnel_id = p.id
        WHERE ps.end_date >= ? AND p.personnel_type = 'สัญญาบัตร'
    """
    params_unavailable = [today_str]
    if not is_admin:
        query_unavailable += " AND ps.department = ?"
        params_unavailable.append(department)
    
    cursor.execute(query_unavailable, params_unavailable)
    unavailable_personnel = [dict(row) for row in cursor.fetchall()]
    unavailable_ids = {p['personnel_id'] for p in unavailable_personnel}

    # Get all commissioned officers
    query_all = "SELECT id, rank, first_name, last_name, department FROM personnel WHERE personnel_type = 'สัญญาบัตร'"
    params_all = []
    if not is_admin:
        query_all += " AND department = ?"
        params_all.append(department)

    cursor.execute(query_all, params_all)
    all_personnel = [dict(row) for row in cursor.fetchall()]
    available_personnel = [p for p in all_personnel if p['id'] not in unavailable_ids]

    def get_rank_index(item):
        try: return RANK_ORDER.index(item['rank'])
        except ValueError: return len(RANK_ORDER)

    unavailable_personnel.sort(key=get_rank_index)
    available_personnel.sort(key=get_rank_index)
    total_personnel_in_scope = len(all_personnel)

    return {
        "status": "success", 
        "active_statuses": unavailable_personnel,
        "available_personnel": available_personnel,
        "total_personnel": total_personnel_in_scope
    }
    
# --- Daily System Handlers ---
def handle_get_daily_dashboard_summary(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    # The daily report is always for the *next* day, so we calculate tomorrow's date.
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    # Fetch reports submitted for tomorrow's date.
    query = "SELECT dsr.department, dsr.report_data, dsr.timestamp, u.rank, u.first_name, u.last_name FROM daily_status_reports dsr JOIN users u ON dsr.submitted_by = u.username WHERE dsr.date = ?"
    cursor.execute(query, (report_date_str,))
    
    submitted_info = {}
    status_summary = defaultdict(int)
    
    for row in cursor.fetchall():
        try:
            items = json.loads(row['report_data'])
            submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
            submitted_info[row['department']] = {'submitter_fullname': submitter_fullname, 'timestamp': row['timestamp']}
            for item in items:
                status_summary[item.get('status', 'ไม่ระบุ')] += 1
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily report for department {row['department']}")
            continue

    # Count all personnel for the daily dashboard
    cursor.execute("SELECT COUNT(id) as total FROM personnel")
    total_personnel_row = cursor.fetchone()
    total_personnel = total_personnel_row['total'] if total_personnel_row else 0
    
    summary = {
        "all_departments": all_departments, 
        "submitted_info": submitted_info, 
        "status_summary": dict(status_summary), 
        "total_personnel": total_personnel,
        "date": report_date_str
    }
    return {"status": "success", "summary": summary}
    
def handle_get_personnel_for_daily_report(payload, conn, cursor, session):
    department = session.get("department")
    is_admin = session.get("role") == "admin"
    
    if is_admin:
        # If admin provides a department in payload, use it. Otherwise, get all departments to populate selector.
        target_dept = payload.get("department")
        cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
        all_departments = [row['department'] for row in cursor.fetchall()]
        if not target_dept and all_departments:
            target_dept = all_departments[0]
        department = target_dept
    else:
        all_departments = []

    # Fetch all personnel for the target department
    cursor.execute("SELECT * FROM personnel WHERE department = ?", (department,))
    personnel = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]

    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    
    # Get submission status for all departments to correctly show info message
    cursor.execute("SELECT department, timestamp FROM daily_status_reports WHERE date = ?", (report_date_str,))
    submission_status = {row['department']: {"timestamp": row['timestamp']} for row in cursor.fetchall()}

    return {
        "status": "success", 
        "personnel": personnel, 
        "submission_status": submission_status, # This is now a dict of all submitted depts
        "all_departments": all_departments,
        "current_department": department
    }

def handle_get_daily_submission_history(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    is_admin = session.get("role") == "admin"
    department_filter = payload.get("department")
    
    params = {}
    query = """
    SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source 
    FROM daily_status_reports
    """
    
    where_clauses = []
    if not is_admin:
        where_clauses.append("department = :dept")
        params["dept"] = session.get("department")
    elif department_filter:
        where_clauses.append("department = :dept")
        params["dept"] = department_filter

    if where_clauses:
        query += " WHERE " + " AND ".join(where_clauses)
        
    query += " ORDER BY timestamp DESC"
    
    cursor.execute(query, params)
    
    history_by_date = defaultdict(list)
    
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            history_by_date[report["date"]].append(report)
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily history report with id {row['id']}")
            continue
    
    cursor.execute("SELECT DISTINCT department FROM personnel")
    all_departments = [row['department'] for row in cursor.fetchall()]
        
    return {"status": "success", "history": dict(history_by_date), "all_departments": all_departments}

def handle_get_daily_reports(payload, conn, cursor, session):
    # ... (code is identical to previous versions, omitted for brevity)
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')

    query = """
    SELECT dsr.id, dsr.date, dsr.department, dsr.timestamp, dsr.report_data, 
           u.rank, u.first_name, u.last_name 
    FROM daily_status_reports dsr 
    JOIN users u ON dsr.submitted_by = u.username 
    WHERE dsr.date = ? 
    ORDER BY dsr.department
    """
    cursor.execute(query, (report_date_str,))
    
    reports = []
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            reports.append(report)
        except (json.JSONDecodeError, TypeError):
            print(f"Warning: Skipping corrupted daily report with id {row['id']}")
            continue
            
    return {"status": "success", "reports": reports, "date": report_date_str}

# --- Shared Handlers ---
# ... (All other handlers like submit, archive, edit, manage users/personnel are omitted for brevity as they remain unchanged)
# --- HTTP Request Handler ---
class APIHandler(BaseHTTPRequestHandler):
    ACTION_MAP = {
        "login": {"handler": handle_login, "auth_required": False},
        "logout": {"handler": handle_logout, "auth_required": True},
        "get_dashboard_summary": {"handler": handle_get_dashboard_summary, "auth_required": True, "admin_only": True},
        "list_users": {"handler": handle_list_users, "auth_required": True, "admin_only": True},
        "add_user": {"handler": handle_add_user, "auth_required": True, "admin_only": True},
        "update_user": {"handler": handle_update_user, "auth_required": True, "admin_only": True},
        "delete_user": {"handler": handle_delete_user, "auth_required": True, "admin_only": True},
        "list_personnel": {"handler": handle_list_personnel, "auth_required": True},
        "get_personnel_details": {"handler": handle_get_personnel_details, "auth_required": True, "admin_only": True},
        "add_personnel": {"handler": handle_add_personnel, "auth_required": True, "admin_only": True},
        "update_personnel": {"handler": handle_update_personnel, "auth_required": True, "admin_only": True},
        "delete_personnel": {"handler": handle_delete_personnel, "auth_required": True, "admin_only": True},
        "import_personnel": {"handler": handle_import_personnel, "auth_required": True, "admin_only": True},
        "submit_status_report": {"handler": handle_submit_status_report, "auth_required": True},
        "get_status_reports": {"handler": handle_get_status_reports, "auth_required": True, "admin_only": True},
        "archive_reports": {"handler": handle_archive_reports, "auth_required": True, "admin_only": True},
        "get_archived_reports": {"handler": handle_get_archived_reports, "auth_required": True, "admin_only": True},
        "get_submission_history": {"handler": handle_get_submission_history, "auth_required": True},
        "get_report_for_editing": {"handler": handle_get_report_for_editing, "auth_required": True},
        "get_active_statuses": {"handler": handle_get_active_statuses, "auth_required": True},
        # Daily report actions
        "get_daily_dashboard_summary": {"handler": handle_get_daily_dashboard_summary, "auth_required": True, "admin_only": True},
        "get_personnel_for_daily_report": {"handler": handle_get_personnel_for_daily_report, "auth_required": True},
        "submit_daily_status_report": {"handler": handle_submit_daily_status_report, "auth_required": True},
        "get_daily_submission_history": {"handler": handle_get_daily_submission_history, "auth_required": True},
        "get_daily_reports": {"handler": handle_get_daily_reports, "auth_required": True, "admin_only": True},
        "get_daily_active_statuses": {"handler": handle_get_daily_active_statuses, "auth_required": True, "admin_only": True},
        "get_all_persistent_statuses": {"handler": handle_get_all_persistent_statuses, "auth_required": True},
        "get_full_daily_report_for_export": {"handler": handle_get_full_daily_report_for_export, "auth_required": True, "admin_only": True},
    }

    def _serve_static_file(self):
        # ... (code is identical to previous versions, omitted for brevity)
        path_map = {'/': '/login.html', '/main': '/main.html', '/main_daily': '/main_daily.html', '/admin': '/admin.html'}
        path = path_map.get(self.path, self.path)
        filepath = path.lstrip('/')
        if not os.path.exists(filepath): 
            self.send_error(404, "File not found")
            return
        mimetypes = {'.html': 'text/html', '.js': 'application/javascript', '.css': 'text/css'}
        mimetype = mimetypes.get(os.path.splitext(filepath)[1], 'application/octet-stream')
        self.send_response(200)
        self.send_header('Content-type', mimetype)
        self.end_headers()
        with open(filepath, 'rb') as f: 
            self.wfile.write(f.read())

    def do_GET(self): 
        self._serve_static_file()

    def do_POST(self):
        if self.path == "/api": 
            self._handle_api_request()
        else: 
            self.send_error(404, "Endpoint not found")

    def _send_json_response(self, data, status_code=200, headers=None):
        # ... (code is identical to previous versions, omitted for brevity)
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        if headers:
            for key, value in headers: 
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _get_session(self):
        # ... (code is identical to previous versions, omitted for brevity)
        cookie_header = self.headers.get('Cookie')
        if not cookie_header: return None
        cookies = dict(item.strip().split('=', 1) for item in cookie_header.split(';') if '=' in item)
        session_token = cookies.get('session_token')
        if not session_token: return None
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        expiry_limit = datetime.now() - timedelta(seconds=SESSION_TIMEOUT_SECONDS)
        cursor.execute("DELETE FROM sessions WHERE created_at < ?", (expiry_limit,))
        conn.commit()

        cursor.execute("SELECT u.username, u.role, u.department, s.created_at FROM sessions s JOIN users u ON s.username = u.username WHERE s.token = ?", (session_token,))
        session_data = cursor.fetchone()
        conn.close()
        
        if session_data:
            session_dict = dict(session_data)
            session_dict['token'] = session_token
            return session_dict
        return None

    def _handle_api_request(self):
        # ... (code is identical to previous versions, omitted for brevity)
        action_name = "unknown"
        try:
            session = self._get_session()
            content_length = int(self.headers['Content-Length'])
            request_data = json.loads(self.rfile.read(content_length).decode('utf-8'))
            action_name, payload = request_data.get("action"), request_data.get("payload", {})
            action_config = self.ACTION_MAP.get(action_name)
            if not action_config: 
                return self._send_json_response({"status": "error", "message": "ไม่รู้จักคำสั่งนี้"}, 404)
            if action_config.get("auth_required") and not session: 
                return self._send_json_response({"status": "error", "message": "Unauthorized"}, 401)
            if action_config.get("admin_only") and (not session or session.get("role") != "admin"): 
                return self._send_json_response({"status": "error", "message": "คุณไม่มีสิทธิ์ดำเนินการ"}, 403)
            
            conn = get_db_connection()
            cursor = conn.cursor()
            try:
                handler_kwargs = {"payload": payload, "conn": conn, "cursor": cursor}
                if action_name == "login": 
                    handler_kwargs["client_address"] = self.client_address
                # Pass session object only to handlers that need it (auth_required is True)
                if action_config.get("auth_required") and session:
                    handler_kwargs["session"] = session

                response_data = action_config["handler"](**handler_kwargs)
                headers = None
                if isinstance(response_data, tuple): 
                    response_data, headers = response_data
                self._send_json_response(response_data, headers=headers)
            finally: 
                conn.close()
        except Exception as e:
            print(f"API Error on action '{action_name}': {e}")
            self._send_json_response({"status": "error", "message": "Server error"}, 500)

def run(server_class=HTTPServer, handler_class=APIHandler, port=9999):
    init_db()
    httpd = server_class(('', port), handler_class)
    print(f"เซิร์ฟเวอร์ระบบจัดการกำลังพลกำลังทำงานที่ http://localhost:{port}")
    httpd.serve_forever()

if __name__ == "__main__":
    run()

