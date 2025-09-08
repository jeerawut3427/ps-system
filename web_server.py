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
from urllib.parse import urlparse

# --- Database Setup ---
DB_FILE = "database.db"

# --- Configuration ---
FAILED_LOGIN_ATTEMPTS = {}
LOCKOUT_TIME = 300
MAX_ATTEMPTS = 5
SESSION_TIMEOUT_SECONDS = 1800 # 30 minutes
ITEMS_PER_PAGE = 15 # Pagination limit

RANK_ORDER = [
    'น.อ.(พ)', 'น.อ.(พ).หญิง', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.อ.หญิง',
    'น.ท.', 'น.ท.หญิง', 'น.ต.', 'น.ต.หญิง',
    'ร.อ.', 'ร.อ.หญิง', 'ร.ท.', 'ร.ท.หญิง', 'ร.ต.', 'ร.ต.หญิง',
    'พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.อ.หญิง', 'พ.อ.ท.', 'พ.อ.ท.หญิง',
    'พ.อ.ต.', 'พ.อ.ต.หญิง', 'จ.อ.', 'จ.อ.หญิง', 'จ.ท.', 'จ.ท.หญิง',
    'จ.ต.', 'จ.ต.หญิง', 'นาย', 'นาง', 'นางสาว'
]

# --- START: NEW CONFIGURATION FOR DAILY SYSTEM ---
# Dictionary to classify ranks into personnel types
RANK_CLASSIFICATION = {
    'officer': ['น.อ.(พ)', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.ท.', 'น.ต.', 'ร.อ.', 'ร.ท.', 'ร.ต.',
                'น.อ.(พ).หญิง', 'น.อ.หญิง', 'น.ท.หญิง', 'น.ต.หญิง', 'ร.อ.หญิง', 'ร.ท.หญิง', 'ร.ต.หญิง'],
    'nco': ['พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.ท.', 'พ.อ.ต.', 'จ.อ.', 'จ.ท.', 'จ.ต.',
            'พ.อ.อ.หญิง', 'พ.อ.ท.หญิง', 'พ.อ.ต.หญิง', 'จ.อ.หญิง', 'จ.ท.หญิง', 'จ.ต.หญิง'],
    'civilian': ['นาย', 'นาง', 'นางสาว']
}
# --- END: NEW CONFIGURATION FOR DAILY SYSTEM ---


# --- Helper Functions ---
def get_next_week_range_str():
    """
    Calculates the full 7-day date range (Monday to Sunday) for the upcoming week.
    ปรับปรุง: คำนวณห้วงเวลาของสัปดาห์หน้าแบบเต็ม 7 วัน (จันทร์-อาทิตย์)
    """
    today = date.today()
    start_of_next_week = today + timedelta(days=-today.weekday(), weeks=1)
    end_of_next_week = start_of_next_week + timedelta(days=6)
    
    thai_months_abbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

    start_day = start_of_next_week.day
    start_month = thai_months_abbr[start_of_next_week.month - 1]
    start_year_be = str(start_of_next_week.year + 543)
    
    end_day = end_of_next_week.day
    end_month = thai_months_abbr[end_of_next_week.month - 1]
    end_year_be = str(end_of_next_week.year + 543)

    if start_year_be != end_year_be:
        return f"{start_day} {start_month} {start_year_be} - {end_day} {end_month} {end_year_be}"
    
    if start_month != end_month:
        return f"{start_day} {start_month} - {end_day} {end_month} {end_year_be}"
        
    return f"{start_day} - {end_day} {end_month} {end_year_be}"

# --- START: NEW HELPER FOR DAILY SYSTEM LOGIC ---
def get_daily_target_date(cursor):
    """
    Determines the next working day for daily reports, skipping weekends and holidays.
    """
    cursor.execute("SELECT date FROM holidays")
    holidays = {date.fromisoformat(row['date']) for row in cursor.fetchall()}

    cursor.execute("SELECT MAX(report_date) FROM archived_daily_reports")
    last_archived_row = cursor.fetchone()
    start_date = date.today()
    if last_archived_row and last_archived_row[0]:
        start_date = date.fromisoformat(last_archived_row[0])

    cursor.execute("SELECT MAX(report_date) FROM daily_reports")
    last_daily_row = cursor.fetchone()
    if last_daily_row and last_daily_row[0]:
        last_daily_date = date.fromisoformat(last_daily_row[0])
        if last_daily_date > start_date:
            return last_daily_date

    next_day = start_date
    while True:
        next_day += timedelta(days=1)
        # weekday() -> Monday is 0 and Sunday is 6
        if next_day.weekday() >= 5 or next_day in holidays:
            continue
        return next_day
# --- END: NEW HELPER FOR DAILY SYSTEM LOGIC ---


# --- Database Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, key BLOB NOT NULL, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, department TEXT, role TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS personnel (id TEXT PRIMARY KEY, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, specialty TEXT, department TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS archived_reports (id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, date TEXT NOT NULL, department TEXT, submitted_by TEXT, report_data TEXT, timestamp DATETIME)')
    cursor.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE)')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS persistent_statuses (
            id TEXT PRIMARY KEY,
            personnel_id TEXT NOT NULL,
            department TEXT NOT NULL,
            status TEXT,
            details TEXT,
            start_date TEXT,
            end_date TEXT,
            FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id TEXT PRIMARY KEY,
            report_date TEXT NOT NULL,
            department TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            timestamp DATETIME,
            summary_data TEXT,
            report_data TEXT
        )
    ''')
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archived_daily_reports (
            id TEXT PRIMARY KEY,
            year INTEGER NOT NULL,
            month INTEGER NOT NULL,
            report_date TEXT NOT NULL,
            department TEXT NOT NULL,
            submitted_by TEXT NOT NULL,
            timestamp DATETIME,
            summary_data TEXT,
            report_data TEXT
        )
    ''')

    cursor.execute('''
        CREATE TABLE IF NOT EXISTS holidays (
            date TEXT PRIMARY KEY,
            description TEXT NOT NULL
        )
    ''')

    cursor.execute("SELECT * FROM users WHERE username = ?", ('jeerawut',))
    if not cursor.fetchone():
        print("กำลังสร้างผู้ดูแลระบบ 'jeerawut'...")
        salt, key = hash_password("Jee@wut2534")
        cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('jeerawut', salt, key, 'น.อ.', 'จีราวุฒิ', 'ผู้ดูแลระบบ', 'ผู้ดูแลระบบ', 'ส่วนกลาง', 'admin'))
    conn.commit()
    conn.close()
    print("ฐานข้อมูล SQLite พร้อมใช้งาน")

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

# --- START: NEW HELPER FUNCTION ---
def classify_personnel(personnel_list):
    """Classifies a list of personnel into three categories based on their rank."""
    classified = {
        'officer': [],
        'nco': [],
        'civilian': []
    }
    for p in personnel_list:
        person_rank = p.get('rank')
        if person_rank in RANK_CLASSIFICATION['officer']:
            classified['officer'].append(p)
        elif person_rank in RANK_CLASSIFICATION['nco']:
            classified['nco'].append(p)
        elif person_rank in RANK_CLASSIFICATION['civilian']:
            classified['civilian'].append(p)
    return classified
# --- END: NEW HELPER FUNCTION ---


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

def handle_get_dashboard_summary(payload, conn, cursor):
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    query = "SELECT sr.department, sr.report_data, sr.timestamp, u.rank, u.first_name, u.last_name FROM status_reports sr JOIN users u ON sr.submitted_by = u.username WHERE sr.timestamp = (SELECT MAX(timestamp) FROM status_reports WHERE department = sr.department)"
    cursor.execute(query)
    submitted_info = {}
    for row in cursor.fetchall():
        items = json.loads(row['report_data'])
        submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
        submitted_info[row['department']] = {'submitter_fullname': submitter_fullname, 'timestamp': row['timestamp'], 'status_count': len(items)}
    cursor.execute("SELECT report_data FROM status_reports")
    status_summary = defaultdict(int)
    for report in cursor.fetchall():
        for item in json.loads(report['report_data']):
            status_summary[item.get('status', 'ไม่ระบุ')] += 1
    cursor.execute("SELECT COUNT(id) as total FROM personnel")
    total_personnel = cursor.fetchone()['total']
    total_on_duty = total_personnel - sum(status_summary.values())
    summary = {"all_departments": all_departments, "submitted_info": submitted_info, "status_summary": dict(status_summary), "total_personnel": total_personnel, "total_on_duty": total_on_duty, "weekly_date_range": get_next_week_range_str()}
    return {"status": "success", "summary": summary}

def handle_list_users(payload, conn, cursor):
    page = payload.get("page", 1)
    search_term = payload.get("searchTerm", "").strip()
    offset = (page - 1) * ITEMS_PER_PAGE
    count_query = "SELECT COUNT(*) as total FROM users"
    data_query = "SELECT username, rank, first_name, last_name, position, department, role FROM users"
    params = []
    where_clause = ""
    if search_term:
        where_clause = " WHERE username LIKE ? OR first_name LIKE ? OR last_name LIKE ? OR department LIKE ?"
        term = f"%{search_term}%"
        params.extend([term, term, term, term])
    cursor.execute(count_query + where_clause, params)
    total_items = cursor.fetchone()['total']
    data_query += where_clause + " LIMIT ? OFFSET ?"
    params.extend([ITEMS_PER_PAGE, offset])
    cursor.execute(data_query, params)
    users = [{k: escape(str(v)) if v is not None else '' for k, v in dict(row).items()} for row in cursor.fetchall()]
    return {"status": "success", "users": users, "total": total_items, "page": page}

def handle_add_user(payload, conn, cursor):
    data = payload.get("data", {}); username = data.get("username"); password = data.get("password")
    if not username or not password: return {"status": "error", "message": "กรุณากรอก Username และ Password"}
    if not is_password_complex(password): return {"status": "error", "message": "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร และมีตัวพิมพ์เล็ก, พิมพ์ใหญ่, และตัวเลข"}
    cursor.execute("SELECT username FROM users WHERE username = ?", (username,))
    if cursor.fetchone(): return {"status": "error", "message": "Username นี้มีผู้ใช้อยู่แล้ว"}
    salt, key = hash_password(password)
    cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                   (username, salt, key, data.get('rank', ''), data.get('first_name', ''), data.get('last_name', ''), data.get('position', ''), data.get('department', ''), data.get('role', 'user')))
    conn.commit()
    return {"status": "success", "message": f"เพิ่มผู้ใช้ '{escape(username)}' สำเร็จ"}

def handle_update_user(payload, conn, cursor):
    data = payload.get("data", {}); username = data.get("username"); password = data.get("password")
    if password:
        if not is_password_complex(password): return {"status": "error", "message": "รหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร และมีตัวพิมพ์เล็ก, พิมพ์ใหญ่, และตัวเลข"}
        salt, key = hash_password(password)
        cursor.execute("UPDATE users SET rank=?, first_name=?, last_name=?, position=?, department=?, role=?, salt=?, key=? WHERE username=?",
                       (data.get('rank'), data.get('first_name'), data.get('last_name'), data.get('position', ''), data.get('department', ''), data.get('role', ''), salt, key, username))
    else:
        cursor.execute("UPDATE users SET rank=?, first_name=?, last_name=?, position=?, department=?, role=? WHERE username=?",
                       (data.get('rank'), data.get('first_name'), data.get('last_name', ''), data.get('position', ''), data.get('department', ''), data.get('role', ''), username))
    conn.commit()
    return {"status": "success", "message": f"อัปเดตข้อมูล '{escape(username)}' สำเร็จ"}

def handle_delete_user(payload, conn, cursor):
    username = payload.get("username")
    if username == 'jeerawut': return {"status": "error", "message": "ไม่สามารถลบบัญชีผู้ดูแลระบบหลักได้"}
    cursor.execute("DELETE FROM users WHERE username = ?", (username,))
    conn.commit()
    return {"status": "success", "message": f"ลบผู้ใช้ '{escape(username)}' สำเร็จ"}

def handle_list_personnel(payload, conn, cursor, session):
    page = payload.get("page", 1)
    search_term = payload.get("searchTerm", "").strip()
    fetch_all = payload.get("fetchAll", False)
    offset = (page - 1) * ITEMS_PER_PAGE
    base_query = " FROM personnel"
    params, where_clauses = [], []
    is_admin, department = session.get("role") == "admin", session.get("department")
    
    if not is_admin:
        where_clauses.append("department = ?"); params.append(department)

    if search_term:
        where_clauses.append("(first_name LIKE ? OR last_name LIKE ? OR position LIKE ?)")
        params.extend([f"%{search_term}%"] * 3)
        
    # แก้ไข: กรองให้แสดงเฉพาะนายทหารสัญญาบัตรในหน้าส่งยอดประจำสัปดาห์
    if fetch_all:
        officer_ranks = RANK_CLASSIFICATION['officer']
        placeholders = ', '.join('?' for _ in officer_ranks)
        where_clauses.append(f"rank IN ({placeholders})")
        params.extend(officer_ranks)

    where_clause_str = ""
    if where_clauses: where_clause_str = " WHERE " + " AND ".join(where_clauses)
    
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
    all_departments = [] # เพิ่ม: สำหรับส่งให้ Admin dropdown
    if fetch_all:
        today = date.today()
        end_of_current_week = today + timedelta(days=6 - today.weekday())
        end_of_current_week_str = end_of_current_week.isoformat()

        dept_to_query = department
        
        if is_admin:
            cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != '' ORDER BY department")
            all_departments = [row['department'] for row in cursor.fetchall()]

        query = "SELECT personnel_id, department, status, details, start_date, end_date FROM persistent_statuses WHERE end_date > ?"
        params_status = [end_of_current_week_str]
        if not is_admin:
            query += " AND department = ?"
            params_status.append(department)
        
        cursor.execute(query, params_status)
        persistent_statuses = [dict(row) for row in cursor.fetchall()]

    response_data = {
        "status": "success",
        "personnel": personnel,
        "total": total_items,
        "page": page,
        "submission_status": submission_status,
        "weekly_date_range": get_next_week_range_str(),
        "persistent_statuses": persistent_statuses
    }
    if is_admin and fetch_all:
        response_data["all_departments"] = all_departments
        
    return response_data


def handle_get_personnel_details(payload, conn, cursor):
    person_id = payload.get("id")
    if not person_id: return {"status": "error", "message": "ไม่พบ ID ของกำลังพล"}
    cursor.execute("SELECT * FROM personnel WHERE id = ?", (person_id,))
    personnel_data = cursor.fetchone()
    if personnel_data: return {"status": "success", "personnel": dict(personnel_data)}
    return {"status": "error", "message": "ไม่พบข้อมูลกำลังพล"}

def handle_add_personnel(payload, conn, cursor):
    data = payload.get("data", {})
    if not all(data.get(f) for f in ['rank', 'first_name', 'last_name', 'position', 'specialty', 'department']):
        return {"status": "error", "message": "ข้อมูลไม่ครบถ้วน กรุณากรอกข้อมูลให้ครบทุกช่อง"}
    cursor.execute("INSERT INTO personnel (id, rank, first_name, last_name, position, specialty, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
                   (str(uuid.uuid4()), data["rank"], data["first_name"], data["last_name"], data["position"], data["specialty"], data["department"]))
    conn.commit()
    return {"status": "success", "message": "เพิ่มข้อมูลกำลังพลสำเร็จ"}

def handle_update_personnel(payload, conn, cursor):
    data = payload.get("data", {})
    if not all(data.get(f) for f in ['id', 'rank', 'first_name', 'last_name', 'position', 'specialty', 'department']):
        return {"status": "error", "message": "ข้อมูลไม่ครบถ้วน กรุณากรอกข้อมูลให้ครบทุกช่อง"}
    cursor.execute("UPDATE personnel SET rank=?, first_name=?, last_name=?, position=?, specialty=?, department=? WHERE id=?",
                   (data["rank"], data["first_name"], data["last_name"], data["position"], data["specialty"], data["department"], data["id"]))
    conn.commit()
    return {"status": "success", "message": "อัปเดตข้อมูลสำเร็จ"}

def handle_delete_personnel(payload, conn, cursor):
    cursor.execute("DELETE FROM personnel WHERE id = ?", (payload.get("id"),))
    conn.commit()
    return {"status": "success", "message": "ลบข้อมูลสำเร็จ"}

def handle_import_personnel(payload, conn, cursor):
    new_data = payload.get("personnel", [])
    cursor.execute("DELETE FROM personnel")
    for p in new_data:
        cursor.execute("INSERT INTO personnel (id, rank, first_name, last_name, position, specialty, department) VALUES (?, ?, ?, ?, ?, ?, ?)",
                       (str(uuid.uuid4()), p['rank'], p['first_name'], p['last_name'], p['position'], p['specialty'], p['department']))
    conn.commit()
    return {"status": "success", "message": f"นำเข้าข้อมูลกำลังพลจำนวน {len(new_data)} รายการสำเร็จ"}

def handle_submit_status_report(payload, conn, cursor, session):
    report_data = payload.get("report", {})
    submitted_by = session.get("username")
    user_department = report_data.get("department", session.get("department"))
    server_now = datetime.utcnow() + timedelta(hours=7)
    date_str = server_now.strftime('%Y-%m-%d')
    timestamp_str = server_now.strftime('%Y-%m-%d %H:%M:%S')
    
    cursor.execute("DELETE FROM status_reports WHERE department = ?", (user_department,))
    cursor.execute("INSERT INTO status_reports (id, date, submitted_by, department, report_data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (str(uuid.uuid4()), date_str, submitted_by, user_department, json.dumps(report_data["items"]), timestamp_str))
    
    today_str = date.today().isoformat()
    cursor.execute("DELETE FROM persistent_statuses WHERE department = ?", (user_department,))
    
    for item in report_data.get("items", []):
        if item.get("status") != "ไม่มี" and item.get("end_date", "") >= today_str:
            cursor.execute(
                """INSERT INTO persistent_statuses
                   (id, personnel_id, department, status, details, start_date, end_date)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (
                    str(uuid.uuid4()),
                    item["personnel_id"],
                    user_department,
                    item["status"],
                    item["details"],
                    item["start_date"],
                    item["end_date"],
                )
            )
    
    conn.commit()
    return {"status": "success", "message": "ส่งยอดกำลังพลสำเร็จ"}

def handle_get_status_reports(payload, conn, cursor):
    cursor.execute("SELECT sr.id, sr.date, sr.department, sr.timestamp, sr.report_data, u.rank, u.first_name, u.last_name FROM status_reports sr JOIN users u ON sr.submitted_by = u.username ORDER BY sr.timestamp DESC")
    reports = []
    submitted_departments = set()
    for row in cursor.fetchall():
        report = dict(row)
        report["items"] = json.loads(report["report_data"])
        del report["report_data"]
        reports.append(report)
        submitted_departments.add(report['department'])

    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]

    return {
        "status": "success",
        "reports": reports,
        "weekly_date_range": get_next_week_range_str(),
        "all_departments": all_departments,
        "submitted_departments": list(submitted_departments)
    }

def handle_archive_reports(payload, conn, cursor):
    for report in payload.get("reports", []):
        report_date = report["date"]
        department = report["department"]
        cursor.execute("DELETE FROM archived_reports WHERE date = ? AND department = ?", (report_date, department))
        year, month = map(int, report_date.split('-')[:2])
        submitted_by = f"{report['rank']} {report['first_name']} {report['last_name']}"
        cursor.execute("INSERT INTO archived_reports (id, year, month, date, department, submitted_by, report_data, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                       (str(uuid.uuid4()), year, month, report_date, department, submitted_by, json.dumps(report["items"]), report["timestamp"]))
    cursor.execute("DELETE FROM status_reports")
    conn.commit()
    return {"status": "success", "message": "เก็บรายงานและรีเซ็ตแดชบอร์ดสำเร็จ"}

def handle_get_archived_reports(payload, conn, cursor):
    cursor.execute("SELECT * FROM archived_reports ORDER BY year DESC, month DESC, date DESC")
    archives = defaultdict(lambda: defaultdict(list))
    for row in cursor.fetchall():
        report = dict(row)
        report["items"] = json.loads(report["report_data"])
        del report["report_data"]
        archives[str(report["year"])][str(report["month"])].append(report)
    return {"status": "success", "archives": dict(archives)}

def handle_get_submission_history(payload, conn, cursor, session):
    user_dept = session.get("department")
    if not user_dept: return {"status": "error", "message": "ไม่พบข้อมูลแผนกของผู้ใช้"}
    query = """
    SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source
    FROM status_reports WHERE department = :dept
    UNION ALL
    SELECT id, date, submitted_by, department, timestamp, report_data, 'archived' as source
    FROM archived_reports WHERE department = :dept
    ORDER BY timestamp DESC
    """
    cursor.execute(query, {"dept": user_dept})
    
    history_by_month = defaultdict(lambda: defaultdict(list))
    
    for row in cursor.fetchall():
        report = dict(row)
        report["items"] = json.loads(report["report_data"])
        del report["report_data"]
        
        timestamp_dt = datetime.strptime(report["timestamp"].split('.')[0], '%Y-%m-%d %H:%M:%S')
        year_be = str(timestamp_dt.year + 543)
        month = str(timestamp_dt.month)
        
        history_by_month[year_be][month].append(report)
        
    return {"status": "success", "history": dict(history_by_month)}

def handle_get_report_for_editing(payload, conn, cursor):
    report_id = payload.get("id")
    if not report_id: return {"status": "error", "message": "ไม่พบ ID ของรายงาน"}
    cursor.execute("SELECT report_data, department FROM status_reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    if not report:
        cursor.execute("SELECT report_data, department FROM archived_reports WHERE id = ?", (report_id,))
        report = cursor.fetchone()
    if report:
        return {"status": "success", "report": {"items": json.loads(report['report_data']), "department": report['department']}}
    return {"status": "error", "message": "ไม่พบข้อมูลรายงาน"}

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
        WHERE ps.end_date >= ?
    """
    params_unavailable = [today_str]
    if not is_admin:
        query_unavailable += " AND ps.department = ?"
        params_unavailable.append(department)
    
    cursor.execute(query_unavailable, params_unavailable)
    unavailable_personnel = [dict(row) for row in cursor.fetchall()]
    unavailable_ids = {p['personnel_id'] for p in unavailable_personnel}

    query_all = "SELECT id, rank, first_name, last_name, department FROM personnel"
    params_all = []
    if not is_admin:
        query_all += " WHERE department = ?"
        params_all.append(department)

    cursor.execute(query_all, params_all)
    all_personnel = [dict(row) for row in cursor.fetchall()]

    available_personnel = [p for p in all_personnel if p['id'] not in unavailable_ids]

    def get_rank_index(item):
        try:
            return RANK_ORDER.index(item['rank'])
        except ValueError:
            return len(RANK_ORDER)

    unavailable_personnel.sort(key=get_rank_index)
    available_personnel.sort(key=get_rank_index)
    
    total_personnel_in_scope = len(all_personnel)

    return {
        "status": "success",
        "active_statuses": unavailable_personnel,
        "available_personnel": available_personnel,
        "total_personnel": total_personnel_in_scope
    }

# --- START: DAILY SYSTEM ACTION HANDLERS (REVISED LOGIC) ---
def handle_get_daily_dashboard_summary(payload, conn, cursor, session):
    target_date = get_daily_target_date(cursor)
    target_date_str = target_date.strftime('%Y-%m-%d')
    
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]

    query = """
        SELECT
            dr.department, dr.summary_data, dr.timestamp,
            u.rank, u.first_name, u.last_name
        FROM daily_reports dr
        JOIN users u ON dr.submitted_by = u.username
        WHERE dr.report_date = ?
    """
    cursor.execute(query, (target_date_str,))
    
    submitted_info = {}
    for row in cursor.fetchall():
        submitter_fullname = f"{row['rank']} {row['first_name']} {row['last_name']}"
        summary = json.loads(row['summary_data'])
        submitted_info[row['department']] = {
            'submitter_fullname': submitter_fullname,
            'timestamp': row['timestamp'],
            'summary': {
                'officer': summary.get('officer', {}),
                'nco': summary.get('nco', {}),
                'civilian': summary.get('civilian', {})
            }
        }

    return {"status": "success", "summary": {"all_departments": all_departments, "submitted_info": submitted_info, "report_date": target_date_str}}

def handle_get_daily_personnel_for_submission(payload, conn, cursor, session):
    is_admin = session.get("role") == "admin"
    user_department = session.get("department")
    all_departments = []

    if is_admin:
        cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != '' ORDER BY department")
        all_departments = [row['department'] for row in cursor.fetchall()]

    department_to_view = (payload.get("department") or (all_departments[0] if all_departments else None)) if is_admin else user_department

    if not department_to_view:
        response_data = {"status": "success", "personnel": {'officer':[], 'nco':[], 'civilian':[]}, "department": "", "report_date": date.today().isoformat(), "submission_status": None}
        if is_admin: response_data["all_departments"] = all_departments
        return response_data

    target_date = get_daily_target_date(cursor)
    target_date_str = target_date.isoformat()

    submission_status = None
    if not is_admin:
        cursor.execute("SELECT timestamp FROM daily_reports WHERE report_date = ? AND department = ?", (target_date_str, user_department))
        last_submission = cursor.fetchone()
        if last_submission:
            submission_status = {"timestamp": last_submission['timestamp']}

    cursor.execute("SELECT * FROM personnel WHERE department = ?", (department_to_view,))
    personnel_in_dept = [dict(row) for row in cursor.fetchall()]
    classified_personnel = classify_personnel(personnel_in_dept)
    
    cursor.execute("SELECT * FROM persistent_statuses WHERE end_date >= ? AND start_date <= ? AND department = ?",
                   (target_date_str, target_date_str, department_to_view))
    active_statuses = {row['personnel_id']: dict(row) for row in cursor.fetchall()}

    for category in classified_personnel:
        for person in classified_personnel[category]:
            if person['id'] in active_statuses:
                person['status'] = active_statuses[person['id']]['status']
                person['details'] = active_statuses[person['id']]['details']
                person['start_date'] = active_statuses[person['id']]['start_date']
                person['end_date'] = active_statuses[person['id']]['end_date']
            else:
                person['status'] = 'ไม่มี'
                person['details'] = ''
                person['start_date'] = ''
                person['end_date'] = ''
                
    response_data = {
        "status": "success",
        "personnel": classified_personnel,
        "department": department_to_view,
        "report_date": target_date_str,
        "submission_status": submission_status
    }

    if is_admin:
        response_data["all_departments"] = all_departments
        
    return response_data

def handle_submit_daily_report(payload, conn, cursor, session):
    data = payload.get("data", {})
    submitted_by = session.get("username")
    department = data.get("department")
    report_date_str = data.get("report_date")
    
    if not all([department, report_date_str]):
        return {"status": "error", "message": "ข้อมูลไม่ครบถ้วน"}

    server_now = datetime.utcnow() + timedelta(hours=7)
    timestamp_str = server_now.strftime('%Y-%m-%d %H:%M:%S')

    cursor.execute("DELETE FROM daily_reports WHERE department = ? AND report_date = ?", (department, report_date_str))
    cursor.execute(
        "INSERT INTO daily_reports (id, report_date, department, submitted_by, timestamp, summary_data, report_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), report_date_str, department, submitted_by, timestamp_str, json.dumps(data.get("summary_data", {})), json.dumps(data.get("report_data", {})))
    )

    # --- START: Update persistent_statuses for NCOs and Civilians ---
    cursor.execute("SELECT id, rank FROM personnel WHERE department = ?", (department,))
    personnel_in_dept = cursor.fetchall()
    
    nco_civ_ids = [
        p['id'] for p in personnel_in_dept
        if p['rank'] in RANK_CLASSIFICATION['nco'] or p['rank'] in RANK_CLASSIFICATION['civilian']
    ]

    if nco_civ_ids:
        placeholders = ', '.join('?' for _ in nco_civ_ids)
        cursor.execute(f"DELETE FROM persistent_statuses WHERE department = ? AND personnel_id IN ({placeholders})", [department] + nco_civ_ids)

    report_data = data.get("report_data", {})
    for category_key in ['nco', 'civilian']:
        for item in report_data.get(category_key, []):
            if item.get("status") != 'ไม่มี' and item.get("end_date", "") >= report_date_str:
                cursor.execute(
                    "INSERT INTO persistent_statuses (id, personnel_id, department, status, details, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (str(uuid.uuid4()), item["personnel_id"], department, item["status"], item["details"], item["start_date"], item["end_date"])
                )
    # --- END: Update persistent_statuses ---

    conn.commit()
    return {"status": "success", "message": f"ส่งยอดกำลังพลสำหรับวันที่ {report_date_str} สำเร็จ"}


def handle_get_daily_submission_history(payload, conn, cursor, session):
    is_admin = session.get("role") == "admin"
    department = session.get("department")
    
    query = "SELECT report_date, department, submitted_by, timestamp, summary_data FROM daily_reports"
    params = []
    
    if not is_admin:
        query += " WHERE department = ?"
        params.append(department)
    
    query += " ORDER BY report_date DESC"
    cursor.execute(query, params)
    
    history_by_month = defaultdict(lambda: defaultdict(list))
    
    for row in cursor.fetchall():
        report = dict(row)
        report_dt = datetime.strptime(report["report_date"], '%Y-%m-%d')
        year_be = str(report_dt.year + 543)
        month = str(report_dt.month)
        
        report['summary'] = json.loads(report.get("summary_data", "{}"))
        del report["summary_data"]
        
        history_by_month[year_be][month].append(report)
        
    return {"status": "success", "history": dict(history_by_month)}

def handle_get_daily_final_report(payload, conn, cursor, session):
    target_date = get_daily_target_date(cursor)
    target_date_str = target_date.strftime('%Y-%m-%d')

    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != '' ORDER BY department")
    all_departments = [row['department'] for row in cursor.fetchall()]
    
    query = """
        SELECT dr.*, u.rank, u.first_name, u.last_name
        FROM daily_reports dr JOIN users u ON dr.submitted_by = u.username
        WHERE dr.report_date = ?
    """
    cursor.execute(query, (target_date_str,))
    reports = [dict(row) for row in cursor.fetchall()]

    for report in reports:
        report['summary_data'] = json.loads(report['summary_data'])
        report['report_data'] = json.loads(report['report_data'])

    submitted_departments = [r['department'] for r in reports]
    
    return {
        "status": "success",
        "reports": reports,
        "report_date": target_date_str,
        "all_departments": all_departments,
        "submitted_departments": submitted_departments
    }
    
def handle_archive_daily_reports(payload, conn, cursor, session):
    reports_to_archive = payload.get("reports", [])
    if not reports_to_archive:
        return {"status": "error", "message": "ไม่พบรายงานที่จะเก็บ"}

    for report in reports_to_archive:
        report_date = report["report_date"]
        department = report["department"]
        cursor.execute("DELETE FROM archived_daily_reports WHERE report_date = ? AND department = ?", (report_date, department))
        year, month, _ = map(int, report_date.split('-'))
        
        submitted_by = f"{report['rank']} {report['first_name']} {report['last_name']}"
        
        cursor.execute(
            """INSERT INTO archived_daily_reports
               (id, year, month, report_date, department, submitted_by, timestamp, summary_data, report_data)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()), year, month, report_date, department,
                submitted_by, report["timestamp"],
                json.dumps(report["summary_data"]), json.dumps(report["report_data"])
            )
        )
    
    report_date_to_clear = reports_to_archive[0]["report_date"]
    cursor.execute("DELETE FROM daily_reports WHERE report_date = ?", (report_date_to_clear,))
    conn.commit()
    return {"status": "success", "message": f"เก็บรายงานวันที่ {report_date_to_clear} และรีเซ็ตแดชบอร์ดสำเร็จ"}

def handle_get_archived_daily_reports(payload, conn, cursor, session):
    cursor.execute("SELECT * FROM archived_daily_reports ORDER BY year DESC, month DESC, report_date DESC")
    archives = defaultdict(lambda: defaultdict(list))
    for row in cursor.fetchall():
        report = dict(row)
        report["summary_data"] = json.loads(report["summary_data"])
        report["report_data"] = json.loads(report["report_data"])
        archives[str(report["year"])][str(report["month"])].append(report)
    return {"status": "success", "archives": dict(archives)}

def handle_list_holidays(payload, conn, cursor, session):
    cursor.execute("SELECT date, description FROM holidays ORDER BY date ASC")
    holidays = [dict(row) for row in cursor.fetchall()]
    return {"status": "success", "holidays": holidays}

def handle_add_holiday(payload, conn, cursor, session):
    holiday_date = payload.get("date")
    description = payload.get("description")
    if not holiday_date or not description:
        return {"status": "error", "message": "กรุณากรอกข้อมูลวันหยุดให้ครบถ้วน"}
    try:
        cursor.execute("INSERT INTO holidays (date, description) VALUES (?, ?)", (holiday_date, description))
        conn.commit()
        return {"status": "success", "message": f"เพิ่มวันหยุด '{escape(description)}' สำเร็จ"}
    except sqlite3.IntegrityError:
        return {"status": "error", "message": "วันหยุดนี้มีอยู่ในระบบแล้ว"}

def handle_delete_holiday(payload, conn, cursor, session):
    holiday_date = payload.get("date")
    if not holiday_date:
        return {"status": "error", "message": "ไม่พบข้อมูลวันที่ที่จะลบ"}
    cursor.execute("DELETE FROM holidays WHERE date = ?", (holiday_date,))
    conn.commit()
    return {"status": "success", "message": "ลบวันหยุดสำเร็จ"}
# --- END: DAILY SYSTEM ACTION HANDLERS ---


# --- HTTP Request Handler ---
class APIHandler(BaseHTTPRequestHandler):
    ACTION_MAP = {
        # Weekly System Actions
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

        # Daily System Actions
        "get_daily_dashboard_summary": {"handler": handle_get_daily_dashboard_summary, "auth_required": True, "admin_only": True},
        "get_daily_personnel_for_submission": {"handler": handle_get_daily_personnel_for_submission, "auth_required": True},
        "submit_daily_report": {"handler": handle_submit_daily_report, "auth_required": True},
        "get_daily_submission_history": {"handler": handle_get_daily_submission_history, "auth_required": True},
        "get_daily_final_report": {"handler": handle_get_daily_final_report, "auth_required": True, "admin_only": True},
        "archive_daily_reports": {"handler": handle_archive_daily_reports, "auth_required": True, "admin_only": True},
        "get_archived_daily_reports": {"handler": handle_get_archived_daily_reports, "auth_required": True, "admin_only": True},
        "list_holidays": {"handler": handle_list_holidays, "auth_required": True, "admin_only": True},
        "add_holiday": {"handler": handle_add_holiday, "auth_required": True, "admin_only": True},
        "delete_holiday": {"handler": handle_delete_holiday, "auth_required": True, "admin_only": True},
    }

    def _serve_static_file(self):
        parsed_path = urlparse(self.path)
        path = parsed_path.path
        
        path_map = {'/': '/login.html', '/main': '/main.html', '/daily': '/daily.html'}
        path = path_map.get(path, path)
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
                # Updated session-requiring actions list
                if session and action_name in [
                    "logout", "list_personnel", "submit_status_report",
                    "get_submission_history", "get_active_statuses",
                    "get_daily_personnel_for_submission", "submit_daily_report",
                    "get_daily_dashboard_summary", "get_daily_submission_history",
                    "get_daily_final_report", "archive_daily_reports",
                    "get_archived_daily_reports",
                    "list_holidays", "add_holiday", "delete_holiday" # Add new actions
                    ]:
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