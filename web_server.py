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
    elif rank in ['นาย', 'นาง', 'นางสาว']:
        # This is a simplification; you might need a more robust way to distinguish civilians
        return 'พลเรือน' 
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
    token_to_delete = session.get("token")
    if token_to_delete:
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_to_delete,))
        conn.commit()
    headers = [('Set-Cookie', 'session_token=; HttpOnly; Path=/; SameSite=Strict; Expires=Thu, 01 Jan 1970 00:00:00 GMT')]
    return {"status": "success", "message": "ออกจากระบบสำเร็จ"}, headers

def handle_list_users(payload, conn, cursor, session):
    page = payload.get("page", 1)
    search_term_from_payload = payload.get("searchTerm")
    offset = (page - 1) * ITEMS_PER_PAGE
    base_query = " FROM users"
    params, where_clauses = [], []
    
    if search_term_from_payload and search_term_from_payload.strip():
        search_term = search_term_from_payload.strip()
        search_like_clause = "(username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR position LIKE ? OR rank LIKE ? OR department LIKE ?)"
        where_clauses.append(search_like_clause)
        term = f"%{search_term}%"
        params.extend([term] * 6)
    
    where_clause_str = ""
    if where_clauses:
        where_clause_str = " WHERE " + " AND ".join(where_clauses)
    
    count_query = "SELECT COUNT(*) as total" + base_query + where_clause_str
    cursor.execute(count_query, params)
    total_items = cursor.fetchone()['total']
    
    data_query = "SELECT username, rank, first_name, last_name, position, department, role" + base_query + where_clause_str + " LIMIT ? OFFSET ?"
    params.extend([ITEMS_PER_PAGE, offset])
    cursor.execute(data_query, params)
    users = [dict(row) for row in cursor.fetchall()]
    return {"status": "success", "users": users, "total": total_items, "page": page}

def handle_add_user(payload, conn, cursor, session):
    data = payload.get("data", {})
    username, password, rank, first_name, last_name, position, department, role = (data.get(k) for k in ["username", "password", "rank", "first_name", "last_name", "position", "department", "role"])
    
    if not all([username, password, rank, first_name, last_name, position, department, role]):
        return {"status": "error", "message": "กรุณากรอกข้อมูลให้ครบทุกช่อง"}
    
    if not is_password_complex(password):
        return {"status": "error", "message": "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร และประกอบด้วยตัวพิมพ์เล็ก, พิมพ์ใหญ่, และตัวเลข"}

    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    if cursor.fetchone():
        return {"status": "error", "message": f"ชื่อผู้ใช้ '{username}' มีอยู่ในระบบแล้ว"}
        
    salt, key = hash_password(password)
    cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (username, salt, key, rank, first_name, last_name, position, department, role))
    conn.commit()
    return {"status": "success", "message": "เพิ่มผู้ใช้ใหม่สำเร็จ"}

def handle_update_user(payload, conn, cursor, session):
    data = payload.get("data", {})
    username, password, rank, first_name, last_name, position, department, role = (data.get(k) for k in ["username", "password", "rank", "first_name", "last_name", "position", "department", "role"])

    if not all([username, rank, first_name, last_name, position, department, role]):
        return {"status": "error", "message": "กรุณากรอกข้อมูลให้ครบทุกช่อง"}

    if password:
        if not is_password_complex(password):
            return {"status": "error", "message": "รหัสผ่านใหม่ต้องมีความยาวอย่างน้อย 8 ตัวอักษร และประกอบด้วยตัวพิมพ์เล็ก, พิมพ์ใหญ่, และตัวเลข"}
        salt, key = hash_password(password)
        cursor.execute("UPDATE users SET salt = ?, key = ?, rank = ?, first_name = ?, last_name = ?, position = ?, department = ?, role = ? WHERE username = ?",
                       (salt, key, rank, first_name, last_name, position, department, role, username))
    else:
        cursor.execute("UPDATE users SET rank = ?, first_name = ?, last_name = ?, position = ?, department = ?, role = ? WHERE username = ?",
                       (rank, first_name, last_name, position, department, role, username))
    conn.commit()
    return {"status": "success", "message": "อัปเดตข้อมูลผู้ใช้สำเร็จ"}

def handle_delete_user(payload, conn, cursor, session):
    username = payload.get("username")
    if not username:
        return {"status": "error", "message": "ไม่พบชื่อผู้ใช้ที่ต้องการลบ"}
    if username == 'jeerawut':
        return {"status": "error", "message": "ไม่สามารถลบผู้ดูแลระบบหลักได้"}
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    return {"status": "success", "message": f"ลบผู้ใช้ '{username}' สำเร็จ"}

# --- Weekly System Handlers ---
def handle_get_dashboard_summary(payload, conn, cursor, session):
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
    today_str = date.today().isoformat()
    is_admin = session.get("role") == "admin"
    department = session.get("department")

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
    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
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
    is_admin = session.get("role") == "admin"
    department = session.get("department")

    if is_admin:
        cursor.execute("SELECT * FROM personnel")
    else:
        cursor.execute("SELECT * FROM personnel WHERE department = ?", (department,))
    
    personnel = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]
    
    all_departments = []
    if is_admin:
        cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
        all_departments = [row['department'] for row in cursor.fetchall()]

    report_date = datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)
    report_date_str = report_date.strftime('%Y-%m-%d')
    cursor.execute("SELECT department, timestamp FROM daily_status_reports WHERE date = ?", (report_date_str,))
    submission_status = {row['department']: {"timestamp": row['timestamp']} for row in cursor.fetchall()}

    persistent_statuses = []
    status_query = "SELECT personnel_id, department, status, details, start_date, end_date FROM persistent_statuses WHERE end_date >= ?"
    params_status = [report_date_str]

    if not is_admin:
        status_query += " AND department = ?"
        params_status.append(department)

    cursor.execute(status_query, params_status)
    persistent_statuses = [dict(row) for row in cursor.fetchall()]

    return {
        "status": "success", 
        "personnel": personnel, 
        "submission_status": submission_status,
        "all_departments": all_departments,
        "persistent_statuses": persistent_statuses
    }

def handle_get_daily_submission_history(payload, conn, cursor, session):
    is_admin = session.get("role") == "admin"
    department = session.get("department")

    query = """
    SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source 
    FROM daily_status_reports
    UNION ALL
    SELECT id, date, submitted_by, department, timestamp, report_data, 'archived' as source 
    FROM daily_archived_reports
    """
    
    if not is_admin:
        final_query = f"SELECT * FROM ({query}) AS combined WHERE department = ? ORDER BY timestamp DESC"
        params_for_query = [department]
    else:
        final_query = f"SELECT * FROM ({query}) AS combined ORDER BY timestamp DESC"
        params_for_query = []

    cursor.execute(final_query, params_for_query)
    history_rows = cursor.fetchall()

    history_by_year_month = defaultdict(lambda: defaultdict(list))
    all_departments = []

    if is_admin:
        cursor.execute("SELECT DISTINCT department FROM personnel")
        all_departments = [row['department'] for row in cursor.fetchall()]

    for row in history_rows:
        report = dict(row)
        try:
            report_date = datetime.strptime(report["date"], '%Y-%m-%d')
            year, month = str(report_date.year), str(report_date.month)
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            history_by_year_month[year][month].append(report)
        except (json.JSONDecodeError, TypeError, ValueError) as e:
            print(f"Warning: Skipping corrupted daily history report with id {row['id']}. Error: {e}")
            continue
            
    return {"status": "success", "history": dict(history_by_year_month), "all_departments": all_departments}


def handle_get_daily_report_for_editing(payload, conn, cursor, session):
    report_id = payload.get("id")
    if not report_id:
        return {"status": "error", "message": "ไม่พบ ID ของรายงาน"}

    cursor.execute("SELECT * FROM daily_status_reports WHERE id = ?", (report_id,))
    report_data = cursor.fetchone()

    if not report_data:
        return {"status": "error", "message": "ไม่พบรายงานที่ต้องการแก้ไข"}

    report = dict(report_data)
    try:
        report["items"] = json.loads(report["report_data"])
        del report["report_data"]
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "message": "ไม่สามารถอ่านข้อมูลรายงานได้"}

    return {"status": "success", "report": report}

def handle_get_all_persistent_statuses(payload, conn, cursor, session):
    today_str = date.today().isoformat()
    
    query_unavailable = """
        SELECT 
            ps.status, ps.details, ps.start_date, ps.end_date, ps.personnel_id,
            p.rank, p.first_name, p.last_name, p.department
        FROM persistent_statuses ps
        JOIN personnel p ON ps.personnel_id = p.id
        WHERE ps.end_date >= ?
    """
    cursor.execute(query_unavailable, [today_str])
    unavailable_personnel = [dict(row) for row in cursor.fetchall()]
    unavailable_ids = {p['personnel_id'] for p in unavailable_personnel}

    cursor.execute("SELECT id, rank, first_name, last_name, department FROM personnel")
    all_personnel = [dict(row) for row in cursor.fetchall()]
    available_personnel = [p for p in all_personnel if p['id'] not in unavailable_ids]
    
    def get_rank_index(item):
        try: return RANK_ORDER.index(item['rank'])
        except ValueError: return len(RANK_ORDER)

    unavailable_personnel.sort(key=get_rank_index)
    available_personnel.sort(key=get_rank_index)
    
    return {
        "status": "success",
        "active_statuses": unavailable_personnel,
        "available_personnel": available_personnel,
        "total_personnel": len(all_personnel)
    }

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

def handle_archive_daily_reports(payload, conn, cursor, session):
    report_date_str = payload.get("date")
    if not report_date_str:
        return {"status": "error", "message": "ไม่พบวันที่ของรายงานที่จะเก็บ"}

    try:
        report_date = datetime.strptime(report_date_str, '%Y-%m-%d').date()
    except ValueError:
        return {"status": "error", "message": "รูปแบบวันที่ไม่ถูกต้อง"}

    cursor.execute("SELECT * FROM daily_status_reports WHERE date = ?", (report_date_str,))
    reports_to_archive = cursor.fetchall()

    if not reports_to_archive:
        return {"status": "error", "message": "ไม่พบรายงานสำหรับวันที่ที่ระบุให้เก็บ"}

    for report_row in reports_to_archive:
        report = dict(report_row)
        archive_id = str(uuid.uuid4())
        year, month = report_date.year, report_date.month

        cursor.execute("""
            INSERT INTO daily_archived_reports 
            (id, year, month, date, department, submitted_by, report_data, timestamp) 
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            archive_id,
            year,
            month,
            report['date'],
            report['department'],
            report['submitted_by'],
            report['report_data'],
            report['timestamp']
        ))

    # Also clear persistent statuses for the archived reports
    all_personnel_ids_in_archived_reports = []
    for report_row in reports_to_archive:
        try:
            items = json.loads(report_row['report_data'])
            for item in items:
                all_personnel_ids_in_archived_reports.append(item['personnel_id'])
        except:
            continue
    
    if all_personnel_ids_in_archived_reports:
        # Prevents SQL error on empty list
        placeholders = ','.join('?' for _ in all_personnel_ids_in_archived_reports)
        cursor.execute(f"DELETE FROM persistent_statuses WHERE personnel_id IN ({placeholders})", all_personnel_ids_in_archived_reports)

    cursor.execute("DELETE FROM daily_status_reports WHERE date = ?", (report_date_str,))
    
    conn.commit()
    return {"status": "success", "message": f"เก็บรายงานประจำวันที่ {report_date_str} สำเร็จ"}

# --- Shared Handlers ---
def handle_submit_status_report(payload, conn, cursor, session):
    report_data = payload.get("report")
    if not report_data or not isinstance(report_data.get("items"), list):
        return {"status": "error", "message": "ข้อมูลรายงานไม่ถูกต้อง"}

    report_id = report_data.get("id") or str(uuid.uuid4())
    submitted_by = session.get("username")
    department = report_data.get("department")
    timestamp = datetime.now()
    report_items_json = json.dumps(report_data["items"])
    date_str = timestamp.strftime('%Y-%m-%d')

    cursor.execute("SELECT id FROM status_reports WHERE id = ?", (report_id,))
    existing = cursor.fetchone()

    personnel_ids_in_report = {item['personnel_id'] for item in report_data.get("items", [])}
    if personnel_ids_in_report:
        cursor.execute("DELETE FROM persistent_statuses WHERE department = ? AND personnel_id NOT IN ({seq})".format(seq=','.join(['?']*len(personnel_ids_in_report))), [department] + list(personnel_ids_in_report))

    for item in report_data.get("items", []):
        cursor.execute("REPLACE INTO persistent_statuses (id, personnel_id, department, status, details, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (str(uuid.uuid4()), item['personnel_id'], department, item['status'], item.get('details'), item.get('start_date'), item.get('end_date')))

    if existing:
        cursor.execute("UPDATE status_reports SET submitted_by = ?, timestamp = ?, report_data = ? WHERE id = ?",
                       (submitted_by, timestamp, report_items_json, report_id))
    else:
        cursor.execute("INSERT INTO status_reports (id, date, submitted_by, department, timestamp, report_data) VALUES (?, ?, ?, ?, ?, ?)",
                       (report_id, date_str, submitted_by, department, timestamp, report_items_json))
    
    conn.commit()
    return {"status": "success", "message": "ส่งรายงานสำเร็จ"}

def handle_archive_reports(payload, conn, cursor, session):
    reports = payload.get("reports")
    if not reports:
        return {"status": "error", "message": "ไม่มีข้อมูลที่จะเก็บ"}
    
    user = f"{session.get('rank')} {session.get('first_name')} {session.get('last_name')}"
    archive_date = date.today()
    year, month = archive_date.year, archive_date.month
    
    for report in reports:
        report_id = str(uuid.uuid4())
        department = report.get('department')
        timestamp = report.get('timestamp')
        report_data = json.dumps(report.get('items', []))
        cursor.execute("INSERT INTO archived_reports (id, year, month, date, department, submitted_by, report_data, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (report_id, year, month, archive_date.isoformat(), department, user, report_data, timestamp))
    
    cursor.execute("DELETE FROM status_reports")
    cursor.execute("DELETE FROM persistent_statuses")
    conn.commit()
    return {"status": "success", "message": "เก็บและล้างข้อมูลรายงานปัจจุบันสำเร็จ"}

def handle_get_archived_reports(payload, conn, cursor, session):
    cursor.execute("SELECT year, month, date, department, submitted_by, report_data, timestamp FROM archived_reports ORDER BY timestamp DESC")
    archives_by_year_month = defaultdict(lambda: defaultdict(list))
    
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report_date = datetime.fromisoformat(report["date"])
            year, month = str(report_date.year), str(report_date.month)
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            archives_by_year_month[year][month].append(report)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
    
    return {"status": "success", "archives": dict(archives_by_year_month)}

def handle_get_submission_history(payload, conn, cursor, session):
    is_admin = session.get("role") == "admin"
    department = session.get("department")
    
    query = """
    SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source FROM status_reports
    UNION ALL
    SELECT id, date, submitted_by, department, timestamp, report_data, 'archived' as source FROM archived_reports
    """
    params = []
    
    if not is_admin:
        query = query.replace("UNION ALL", "WHERE department = ? UNION ALL").replace("FROM archived_reports", "FROM archived_reports WHERE department = ?")
        params.extend([department, department])

    query += " ORDER BY timestamp DESC"
    cursor.execute(query, params)
    
    history_by_year_month = defaultdict(lambda: defaultdict(list))
    
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report_date = datetime.strptime(report["date"], '%Y-%m-%d')
            year, month = str(report_date.year), str(report_date.month)
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            history_by_year_month[year][month].append(report)
        except (json.JSONDecodeError, TypeError, ValueError):
            continue
            
    return {"status": "success", "history": dict(history_by_year_month)}

def handle_get_report_for_editing(payload, conn, cursor, session):
    report_id = payload.get("id")
    if not report_id:
        return {"status": "error", "message": "ไม่พบ ID ของรายงาน"}

    cursor.execute("SELECT * FROM status_reports WHERE id = ?", (report_id,))
    report_data = cursor.fetchone()

    if not report_data:
        return {"status": "error", "message": "ไม่พบรายงานที่ต้องการแก้ไข"}

    report = dict(report_data)
    try:
        report["items"] = json.loads(report["report_data"])
        del report["report_data"]
    except (json.JSONDecodeError, TypeError):
        return {"status": "error", "message": "ไม่สามารถอ่านข้อมูลรายงานได้"}

    return {"status": "success", "report": report}

def handle_get_status_reports(payload, conn, cursor, session):
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE personnel_type = 'สัญญาบัตร'")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    query = """
    SELECT sr.id, sr.date, sr.department, sr.timestamp, sr.report_data, 
           u.rank, u.first_name, u.last_name 
    FROM status_reports sr 
    JOIN users u ON sr.submitted_by = u.username 
    ORDER BY sr.department
    """
    cursor.execute(query)
    
    reports = []
    submitted_departments = []
    for row in cursor.fetchall():
        report = dict(row)
        try:
            report["items"] = json.loads(report["report_data"])
            del report["report_data"]
            reports.append(report)
            submitted_departments.append(report['department'])
        except (json.JSONDecodeError, TypeError):
            continue
            
    return {"status": "success", "reports": reports, "weekly_date_range": get_next_week_range_str(), "all_departments": all_departments, "submitted_departments": submitted_departments}
    
def handle_submit_daily_status_report(payload, conn, cursor, session):
    report_data = payload.get("report")
    if not report_data or not isinstance(report_data.get("items"), list):
        return {"status": "error", "message": "ข้อมูลรายงานไม่ถูกต้อง"}
        
    report_id = report_data.get("id") or str(uuid.uuid4())
    submitted_by = session.get("username")
    department = report_data.get("department")
    timestamp = datetime.now()
    report_items_json = json.dumps(report_data["items"])
    
    # Determine the date for the report
    if editing_report_data := report_data.get("id"):
        cursor.execute("SELECT date FROM daily_status_reports WHERE id = ?", (editing_report_data,))
        existing_report = cursor.fetchone()
        date_str = existing_report['date'] if existing_report else (datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)).strftime('%Y-%m-%d')
    else:
        date_str = (datetime.utcnow() + timedelta(hours=7) + timedelta(days=1)).strftime('%Y-%m-%d')

    
    cursor.execute("SELECT id FROM daily_status_reports WHERE id = ?", (report_id,))
    existing = cursor.fetchone()

    # Handle persistent statuses for daily reports
    personnel_ids_in_report = {item['personnel_id'] for item in report_data.get("items", [])}
    if personnel_ids_in_report:
        cursor.execute("DELETE FROM persistent_statuses WHERE department = ? AND personnel_id NOT IN ({seq})".format(seq=','.join(['?']*len(personnel_ids_in_report))), [department] + list(personnel_ids_in_report))

    for item in report_data.get("items", []):
        cursor.execute("REPLACE INTO persistent_statuses (id, personnel_id, department, status, details, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (str(uuid.uuid4()), item['personnel_id'], department, item['status'], item.get('details'), item.get('start_date'), item.get('end_date')))


    if existing:
        cursor.execute("UPDATE daily_status_reports SET submitted_by = ?, timestamp = ?, report_data = ? WHERE id = ?",
                       (submitted_by, timestamp, report_items_json, report_id))
    else:
        cursor.execute("INSERT INTO daily_status_reports (id, date, submitted_by, department, timestamp, report_data) VALUES (?, ?, ?, ?, ?, ?)",
                       (report_id, date_str, submitted_by, department, timestamp, report_items_json))
    
    conn.commit()
    return {"status": "success", "message": "ส่งรายงานประจำวันสำเร็จ"}

# --- Personnel Management ---
def handle_get_personnel_details(payload, conn, cursor, session):
    person_id = payload.get("id")
    cursor.execute("SELECT * FROM personnel WHERE id = ?", (person_id,))
    personnel = cursor.fetchone()
    if personnel:
        return {"status": "success", "personnel": dict(personnel)}
    return {"status": "error", "message": "ไม่พบข้อมูล"}

def handle_add_personnel(payload, conn, cursor, session):
    data = payload.get("data", {})
    person_id = str(uuid.uuid4())
    data['id'] = person_id
    if 'personnel_type' not in data or not data['personnel_type']:
        data['personnel_type'] = get_personnel_type_from_rank(data.get('rank'))
        
    columns = ['id', 'rank', 'first_name', 'last_name', 'position', 'specialty', 'department', 'personnel_type']
    values = [data.get(col) for col in columns]
    cursor.execute(f"INSERT INTO personnel ({', '.join(columns)}) VALUES ({', '.join(['?']*len(columns))})", values)
    conn.commit()
    return {"status": "success", "message": "เพิ่มข้อมูลกำลังพลสำเร็จ"}

def handle_update_personnel(payload, conn, cursor, session):
    data = payload.get("data", {})
    person_id = data.get("id")
    if not person_id:
        return {"status": "error", "message": "ไม่พบ ID"}
    
    if 'personnel_type' not in data or not data['personnel_type']:
        data['personnel_type'] = get_personnel_type_from_rank(data.get('rank'))
        
    columns = ['rank', 'first_name', 'last_name', 'position', 'specialty', 'department', 'personnel_type']
    values = [data.get(col) for col in columns]
    set_clause = ", ".join([f"{col} = ?" for col in columns])
    values.append(person_id)
    cursor.execute(f"UPDATE personnel SET {set_clause} WHERE id = ?", values)
    conn.commit()
    return {"status": "success", "message": "อัปเดตข้อมูลสำเร็จ"}

def handle_delete_personnel(payload, conn, cursor, session):
    person_id = payload.get("id")
    cursor.execute("DELETE FROM personnel WHERE id = ?", (person_id,))
    conn.commit()
    return {"status": "success", "message": "ลบข้อมูลสำเร็จ"}

def handle_import_personnel(payload, conn, cursor, session):
    personnel_data = payload.get("personnel", [])
    added_count, updated_count, error_count = 0, 0, 0
    errors = []

    for idx, p in enumerate(personnel_data, 1):
        try:
            rank = p.get('ยศ-คำนำหน้า')
            first_name = p.get('ชื่อ')
            last_name = p.get('นามสกุล')
            personnel_type = p.get('ประเภท') or get_personnel_type_from_rank(rank)
            
            if not all([rank, first_name, last_name]):
                errors.append(f"แถวที่ {idx}: ข้อมูลไม่ครบถ้วน")
                error_count += 1
                continue

            cursor.execute("SELECT id FROM personnel WHERE rank = ? AND first_name = ? AND last_name = ?", (rank, first_name, last_name))
            existing = cursor.fetchone()
            
            columns = ['rank', 'first_name', 'last_name', 'position', 'specialty', 'department', 'personnel_type']
            values = [p.get(k_th, p.get(k_en, '')) for k_th, k_en in [('ยศ-คำนำหน้า', 'rank'), ('ชื่อ', 'first_name'), ('นามสกุล', 'last_name'), ('ตำแหน่ง', 'position'), ('เหล่า', 'specialty'), ('แผนก', 'department')]]
            values.append(personnel_type)

            if existing:
                person_id = existing['id']
                set_clause = ", ".join([f"{col} = ?" for col in columns])
                cursor.execute(f"UPDATE personnel SET {set_clause} WHERE id = ?", values + [person_id])
                updated_count += 1
            else:
                person_id = str(uuid.uuid4())
                cursor.execute(f"INSERT INTO personnel (id, {', '.join(columns)}) VALUES (?, {', '.join(['?']*len(columns))})", [person_id] + values)
                added_count += 1
        except Exception as e:
            error_count += 1
            errors.append(f"แถวที่ {idx}: {e}")

    conn.commit()
    message = f"นำเข้าสำเร็จ: เพิ่ม {added_count} รายการ, อัปเดต {updated_count} รายการ."
    if error_count > 0:
        message += f" พบข้อผิดพลาด {error_count} รายการ: {'; '.join(errors[:3])}" # Show first 3 errors
    
    return {"status": "success" if error_count == 0 else "warning", "message": message}


# --- HTTP Request Handler ---
class APIHandler(BaseHTTPRequestHandler):
    ACTION_MAP = {
        "login": {"handler": handle_login, "auth_required": False},
        "logout": {"handler": handle_logout, "auth_required": True},
        # Admin User/Personnel Management
        "list_users": {"handler": handle_list_users, "auth_required": True, "admin_only": True},
        "add_user": {"handler": handle_add_user, "auth_required": True, "admin_only": True},
        "update_user": {"handler": handle_update_user, "auth_required": True, "admin_only": True},
        "delete_user": {"handler": handle_delete_user, "auth_required": True, "admin_only": True},
        "get_personnel_details": {"handler": handle_get_personnel_details, "auth_required": True, "admin_only": True},
        "add_personnel": {"handler": handle_add_personnel, "auth_required": True, "admin_only": True},
        "update_personnel": {"handler": handle_update_personnel, "auth_required": True, "admin_only": True},
        "delete_personnel": {"handler": handle_delete_personnel, "auth_required": True, "admin_only": True},
        "import_personnel": {"handler": handle_import_personnel, "auth_required": True, "admin_only": True},
        # Weekly System
        "get_dashboard_summary": {"handler": handle_get_dashboard_summary, "auth_required": True, "admin_only": True},
        "list_personnel": {"handler": handle_list_personnel, "auth_required": True},
        "submit_status_report": {"handler": handle_submit_status_report, "auth_required": True},
        "get_status_reports": {"handler": handle_get_status_reports, "auth_required": True, "admin_only": True},
        "archive_reports": {"handler": handle_archive_reports, "auth_required": True, "admin_only": True},
        "get_archived_reports": {"handler": handle_get_archived_reports, "auth_required": True, "admin_only": True},
        "get_submission_history": {"handler": handle_get_submission_history, "auth_required": True},
        "get_report_for_editing": {"handler": handle_get_report_for_editing, "auth_required": True},
        "get_active_statuses": {"handler": handle_get_active_statuses, "auth_required": True},
        # Daily System
        "get_daily_dashboard_summary": {"handler": handle_get_daily_dashboard_summary, "auth_required": True, "admin_only": True},
        "get_personnel_for_daily_report": {"handler": handle_get_personnel_for_daily_report, "auth_required": True},
        "submit_daily_status_report": {"handler": handle_submit_daily_status_report, "auth_required": True},
        "get_daily_submission_history": {"handler": handle_get_daily_submission_history, "auth_required": True},
        "get_daily_report_for_editing": {"handler": handle_get_daily_report_for_editing, "auth_required": True},
        "get_all_persistent_statuses": {"handler": handle_get_all_persistent_statuses, "auth_required": True},
        "get_daily_reports": {"handler": handle_get_daily_reports, "auth_required": True, "admin_only": True},
        "archive_daily_reports": {"handler": handle_archive_daily_reports, "auth_required": True, "admin_only": True},
    }

    def _serve_static_file(self):
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
        self.send_response(status_code)
        self.send_header('Content-type', 'application/json')
        if headers:
            for key, value in headers: 
                self.send_header(key, value)
        self.end_headers()
        self.wfile.write(json.dumps(data).encode('utf-8'))

    def _get_session(self):
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

