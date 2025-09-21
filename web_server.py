# -*- coding: utf-8 -*-
from flask import Flask, request, jsonify, send_from_directory, make_response
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

# --- Flask App Initialization ---
app = Flask(__name__, static_folder='', static_url_path='')

# --- Database Setup & Configuration ---
DB_FILE = "database.db"
FAILED_LOGIN_ATTEMPTS = {}
LOCKOUT_TIME = 300
MAX_ATTEMPTS = 5
SESSION_TIMEOUT_SECONDS = 1800 # 30 minutes
ITEMS_PER_PAGE = 15

RANK_ORDER = [
    'น.อ.(พ)', 'น.อ.(พ).หญิง', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.อ.หญิง',
    'น.ท.', 'น.ท.หญิง', 'น.ต.', 'น.ต.หญิง',
    'ร.อ.', 'ร.อ.หญิง', 'ร.ท.', 'ร.ท.หญิง', 'ร.ต.', 'ร.ต.หญิง',
    'พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.อ.หญิง', 'พ.อ.ท.', 'พ.อ.ท.หญิง',
    'พ.อ.ต.', 'พ.อ.ต.หญิง', 'จ.อ.', 'จ.อ.หญิง', 'จ.ท.', 'จ.ท.หญิง',
    'จ.ต.', 'จ.ต.หญิง', 'นาย', 'นาง', 'นางสาว'
]

RANK_CLASSIFICATION = {
    'officer': ['น.อ.(พ)', 'น.อ.หม่อมหลวง', 'น.อ.', 'น.ท.', 'น.ต.', 'ร.อ.', 'ร.ท.', 'ร.ต.',
                'น.อ.(พ).หญิง', 'น.อ.หญิง', 'น.ท.หญิง', 'น.ต.หญิง', 'ร.อ.หญิง', 'ร.ท.หญิง', 'ร.ต.หญิง'],
    'nco': ['พ.อ.อ.(พ)', 'พ.อ.อ.', 'พ.อ.ท.', 'พ.อ.ต.', 'จ.อ.', 'จ.ท.', 'จ.ต.',
            'พ.อ.อ.หญิง', 'พ.อ.ท.หญิง', 'พ.อ.ต.หญิง', 'จ.อ.หญิง', 'จ.ท.หญิง', 'จ.ต.หญิง'],
    'civilian': ['นาย', 'นาง', 'นางสาว']
}

# --- Helper Functions ---
def get_db_connection():
    conn = sqlite3.connect(DB_FILE)
    conn.row_factory = sqlite3.Row
    return conn

def get_reporting_week_range_str(cursor):
    """
    ดึงวันที่เริ่มต้นของสัปดาห์ปัจจุบันจากฐานข้อมูล แล้วคำนวณช่วงวันที่ของ "สัปดาห์ถัดไป" ที่จะส่งยอด
    """
    cursor.execute("SELECT value FROM system_settings WHERE key = 'current_week_start_date'")
    start_date_row = cursor.fetchone()
    
    if not start_date_row:
        today = date.today()
        start_of_current_week = today - timedelta(days=today.weekday())
        start_of_reporting_week = start_of_current_week + timedelta(days=7)
    else:
        start_of_current_week = date.fromisoformat(start_date_row['value'])
        start_of_reporting_week = start_of_current_week + timedelta(days=7)

    end_of_reporting_week = start_of_reporting_week + timedelta(days=6)
    
    thai_months_abbr = ["ม.ค.", "ก.พ.", "มี.ค.", "เม.ย.", "พ.ค.", "มิ.ย.", "ก.ค.", "ส.ค.", "ก.ย.", "ต.ค.", "พ.ย.", "ธ.ค."]

    start_day = start_of_reporting_week.day
    start_month = thai_months_abbr[start_of_reporting_week.month - 1]
    start_year_be = str(start_of_reporting_week.year + 543)
    
    end_day = end_of_reporting_week.day
    end_month = thai_months_abbr[end_of_reporting_week.month - 1]
    end_year_be = str(end_of_reporting_week.year + 543)

    if start_year_be != end_year_be:
        return f"{start_day} {start_month} {start_year_be} - {end_day} {end_month} {end_year_be}"
    
    if start_month != end_month:
        return f"{start_day} {start_month} - {end_day} {end_month} {end_year_be}"
        
    return f"{start_day} - {end_day} {end_month} {end_year_be}"

def get_daily_target_date(cursor):
    cursor.execute("SELECT date FROM holidays")
    holidays = {date.fromisoformat(row['date']) for row in cursor.fetchall()}
    cursor.execute("SELECT MAX(report_date) FROM archived_daily_reports")
    last_archived_row = cursor.fetchone()
    start_date_val = date.today()
    if last_archived_row and last_archived_row[0]:
        start_date_val = date.fromisoformat(last_archived_row[0])
    cursor.execute("SELECT MAX(report_date) FROM daily_reports")
    last_daily_row = cursor.fetchone()
    if last_daily_row and last_daily_row[0]:
        last_daily_date = date.fromisoformat(last_daily_row[0])
        if last_daily_date > start_date_val:
            return last_daily_date
    next_day = start_date_val
    while True:
        next_day += timedelta(days=1)
        if next_day.weekday() >= 5 or next_day in holidays:
            continue
        return next_day

def hash_password(password, salt=None):
    if salt is None: salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt, key

def verify_password(salt, key, password_to_check):
    return hmac.compare_digest(key, hash_password(password_to_check, salt)[1])
    
def classify_personnel(personnel_list):
    classified = {'officer': [], 'nco': [], 'civilian': []}
    for p in personnel_list:
        person_rank = p.get('rank')
        if person_rank in RANK_CLASSIFICATION['officer']: classified['officer'].append(p)
        elif person_rank in RANK_CLASSIFICATION['nco']: classified['nco'].append(p)
        elif person_rank in RANK_CLASSIFICATION['civilian']: classified['civilian'].append(p)
    return classified

# --- Database Initialization ---
def init_db():
    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (username TEXT PRIMARY KEY, salt BLOB NOT NULL, key BLOB NOT NULL, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, department TEXT, role TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS personnel (id TEXT PRIMARY KEY, rank TEXT, first_name TEXT, last_name TEXT, position TEXT, specialty TEXT, department TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS status_reports (id TEXT PRIMARY KEY, date TEXT NOT NULL, submitted_by TEXT, department TEXT, timestamp DATETIME, report_data TEXT)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archived_reports (
            id TEXT PRIMARY KEY, week_range TEXT, report_data TEXT, archived_by TEXT, timestamp DATETIME
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS sessions (token TEXT PRIMARY KEY, username TEXT NOT NULL, created_at DATETIME DEFAULT CURRENT_TIMESTAMP, FOREIGN KEY (username) REFERENCES users (username) ON DELETE CASCADE)')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS persistent_statuses (
            id TEXT PRIMARY KEY, personnel_id TEXT NOT NULL, department TEXT NOT NULL, status TEXT,
            details TEXT, start_date TEXT, end_date TEXT,
            FOREIGN KEY (personnel_id) REFERENCES personnel (id) ON DELETE CASCADE
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS daily_reports (
            id TEXT PRIMARY KEY, report_date TEXT NOT NULL, department TEXT NOT NULL, submitted_by TEXT NOT NULL,
            timestamp DATETIME, summary_data TEXT, report_data TEXT
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS archived_daily_reports (
            id TEXT PRIMARY KEY, year INTEGER NOT NULL, month INTEGER NOT NULL, report_date TEXT NOT NULL,
            department TEXT NOT NULL, submitted_by TEXT NOT NULL, timestamp DATETIME,
            summary_data TEXT, report_data TEXT
        )
    ''')
    cursor.execute('CREATE TABLE IF NOT EXISTS holidays (date TEXT PRIMARY KEY, description TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS system_settings (key TEXT PRIMARY KEY, value TEXT)')
    
    cursor.execute("SELECT value FROM system_settings WHERE key = 'current_week_start_date'")
    if not cursor.fetchone():
        today = date.today()
        start_of_current_week = today - timedelta(days=today.weekday())
        cursor.execute("INSERT INTO system_settings (key, value) VALUES (?, ?)", ('current_week_start_date', start_of_current_week.isoformat()))

    cursor.execute("SELECT * FROM users WHERE username = ?", ('jeerawut',))
    if not cursor.fetchone():
        print("Creating default admin user 'jeerawut'...")
        salt, key = hash_password("Jee@wut2534")
        cursor.execute("INSERT INTO users (username, salt, key, rank, first_name, last_name, position, department, role) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
                       ('jeerawut', salt, key, 'น.อ.', 'จีราวุฒิ', 'ผู้ดูแลระบบ', 'ผู้ดูแลระบบ', 'ส่วนกลาง', 'admin'))
    conn.commit()
    conn.close()
    print("Database is ready.")


# --- Action Handlers ---
def handle_login(payload, conn, cursor, client_address_ip):
    ip_address = client_address_ip
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
        cursor.execute("INSERT INTO sessions (token, username, created_at) VALUES (?, ?, ?)", (session_token, user_data["username"], datetime.now()))
        conn.commit()
        user_info = {k: user_data[k] for k in user_data.keys() if k not in ['salt', 'key']}
        return {"status": "success", "user": user_info}, [('Set-Cookie', f'session_token={session_token}; HttpOnly; Path=/; SameSite=Strict; Max-Age={SESSION_TIMEOUT_SECONDS}')]
    else:
        if ip_address in FAILED_LOGIN_ATTEMPTS: FAILED_LOGIN_ATTEMPTS[ip_address] = (FAILED_LOGIN_ATTEMPTS[ip_address][0] + 1, time.time())
        else: FAILED_LOGIN_ATTEMPTS[ip_address] = (1, time.time())
        return {"status": "error", "message": "ชื่อผู้ใช้หรือรหัสผ่านไม่ถูกต้อง"}, None

def handle_logout(payload, conn, cursor, session):
    token_to_delete = session.get("token")
    if token_to_delete:
        cursor.execute("DELETE FROM sessions WHERE token = ?", (token_to_delete,))
        conn.commit()
    return {"status": "success", "message": "ออกจากระบบสำเร็จ"}, [('Set-Cookie', 'session_token=; HttpOnly; Path=/; SameSite=Strict; Max-Age=0')]

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
    summary = {
        "all_departments": all_departments, 
        "submitted_info": submitted_info, 
        "status_summary": dict(status_summary), 
        "total_personnel": total_personnel, 
        "total_on_duty": total_on_duty, 
        "weekly_date_range": get_reporting_week_range_str(cursor)
    }
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
    all_departments = []
    if fetch_all:
        today = date.today()
        end_of_current_week = today + timedelta(days=6 - today.weekday())
        end_of_current_week_str = end_of_current_week.isoformat()
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
        "status": "success", "personnel": personnel, "total": total_items, "page": page,
        "submission_status": submission_status, "weekly_date_range": get_reporting_week_range_str(cursor),
        "persistent_statuses": persistent_statuses
    }
    if is_admin and fetch_all: response_data["all_departments"] = all_departments
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
    date_str, timestamp_str = server_now.strftime('%Y-%m-%d'), server_now.strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM status_reports WHERE department = ?", (user_department,))
    cursor.execute("INSERT INTO status_reports (id, date, submitted_by, department, report_data, timestamp) VALUES (?, ?, ?, ?, ?, ?)",
                   (str(uuid.uuid4()), date_str, submitted_by, user_department, json.dumps(report_data["items"]), timestamp_str))
    today_str = date.today().isoformat()
    cursor.execute("DELETE FROM persistent_statuses WHERE department = ?", (user_department,))
    for item in report_data.get("items", []):
        if item.get("status") != "ไม่มี" and item.get("end_date", "") >= today_str:
            cursor.execute(
                "INSERT INTO persistent_statuses (id, personnel_id, department, status, details, start_date, end_date) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (str(uuid.uuid4()), item["personnel_id"], user_department, item["status"], item["details"], item["start_date"], item["end_date"])
            )
    conn.commit()
    return {"status": "success", "message": "ส่งยอดกำลังพลสำเร็จ"}

def handle_get_status_reports(payload, conn, cursor):
    cursor.execute("SELECT sr.id, sr.date, sr.department, sr.timestamp, sr.report_data, u.rank, u.first_name, u.last_name FROM status_reports sr JOIN users u ON sr.submitted_by = u.username ORDER BY sr.timestamp DESC")
    reports, submitted_departments = [], set()
    for row in cursor.fetchall():
        report = dict(row)
        report["items"] = json.loads(report["report_data"]); del report["report_data"]
        reports.append(report)
        submitted_departments.add(report['department'])
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    return {
        "status": "success", "reports": reports, "weekly_date_range": get_reporting_week_range_str(cursor),
        "all_departments": all_departments, "submitted_departments": list(submitted_departments)
    }

def handle_archive_reports(payload, conn, cursor, session):
    reports_to_archive = payload.get("reports", [])
    week_range = payload.get("week_range", "")
    archived_by_user = session.get("username")
    if not reports_to_archive: return {"status": "error", "message": "ไม่พบข้อมูลรายงานที่จะเก็บ"}
    full_report_data = json.dumps(reports_to_archive)
    cursor.execute(
        "INSERT INTO archived_reports (id, week_range, report_data, archived_by, timestamp) VALUES (?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), week_range, full_report_data, archived_by_user, datetime.utcnow() + timedelta(hours=7))
    )
    cursor.execute("DELETE FROM status_reports")
    conn.commit()
    print("กำลังอัปเดตรอบสัปดาห์ถัดไป...")
    cursor.execute("SELECT value FROM system_settings WHERE key = 'current_week_start_date'")
    row = cursor.fetchone()
    if row:
        current_start_date_str = row['value']
        current_start_date = date.fromisoformat(current_start_date_str)
        next_week_start_date = current_start_date + timedelta(days=7)
        cursor.execute("UPDATE system_settings SET value = ? WHERE key = ?", (next_week_start_date.isoformat(), 'current_week_start_date'))
        conn.commit()
        print(f" -> อัปเดตรอบสัปดาห์ใหม่เป็น: {next_week_start_date.isoformat()}")
    return {"status": "success", "message": "เก็บรายงานและรีเซ็ตแดชบอร์ดสำเร็จ"}

def handle_get_archived_reports(payload, conn, cursor):
    cursor.execute("SELECT id, week_range, report_data, archived_by, timestamp FROM archived_reports ORDER BY timestamp DESC")
    archives_by_month = defaultdict(lambda: defaultdict(list))
    for row in cursor.fetchall():
        archive_batch = dict(row)
        archive_batch["reports"] = json.loads(archive_batch["report_data"]); del archive_batch["report_data"]
        timestamp_dt = datetime.strptime(archive_batch["timestamp"].split('.')[0], '%Y-%m-%d %H:%M:%S')
        year_be, month = str(timestamp_dt.year + 543), str(timestamp_dt.month)
        archives_by_month[year_be][month].append(archive_batch)
    return {"status": "success", "archives": dict(archives_by_month)}

def handle_get_submission_history(payload, conn, cursor, session):
    user_dept = session.get("department")
    if not user_dept: return {"status": "error", "message": "ไม่พบข้อมูลแผนกของผู้ใช้"}
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='archived_reports_old';")
    old_table_exists = cursor.fetchone()
    query = "SELECT id, date, submitted_by, department, timestamp, report_data, 'active' as source FROM status_reports WHERE department = :dept"
    if old_table_exists:
        query += " UNION ALL SELECT id, date, submitted_by, department, timestamp, report_data, 'archived' as source FROM archived_reports_old WHERE department = :dept"
    query += " ORDER BY timestamp DESC"
    cursor.execute(query, {"dept": user_dept})
    history_by_month = defaultdict(lambda: defaultdict(list))
    for row in cursor.fetchall():
        report = dict(row)
        report["items"] = json.loads(report["report_data"]); del report["report_data"]
        timestamp_dt = datetime.strptime(report["timestamp"].split('.')[0], '%Y-%m-%d %H:%M:%S')
        year_be, month = str(timestamp_dt.year + 543), str(timestamp_dt.month)
        history_by_month[year_be][month].append(report)
    return {"status": "success", "history": dict(history_by_month)}

def handle_get_report_for_editing(payload, conn, cursor):
    report_id = payload.get("id")
    if not report_id: return {"status": "error", "message": "ไม่พบ ID ของรายงาน"}
    cursor.execute("SELECT report_data, department FROM status_reports WHERE id = ?", (report_id,))
    report = cursor.fetchone()
    if not report:
        try:
            cursor.execute("SELECT report_data, department FROM archived_reports_old WHERE id = ?", (report_id,))
            report = cursor.fetchone()
        except sqlite3.OperationalError:
             return {"status": "error", "message": "ไม่พบข้อมูลรายงานที่ต้องการแก้ไข"}
    if report:
        return {"status": "success", "report": {"items": json.loads(report['report_data']), "department": report['department']}}
    return {"status": "error", "message": "ไม่พบข้อมูลรายงาน"}

def handle_get_active_statuses(payload, conn, cursor, session):
    today_str, is_admin, department = date.today().isoformat(), session.get("role") == "admin", session.get("department")
    query_unavailable = "SELECT ps.status, ps.details, ps.start_date, ps.end_date, ps.personnel_id, p.rank, p.first_name, p.last_name, p.department FROM persistent_statuses ps JOIN personnel p ON ps.personnel_id = p.id WHERE ps.end_date >= ?"
    params_unavailable = [today_str]
    if not is_admin:
        query_unavailable += " AND ps.department = ?"; params_unavailable.append(department)
    cursor.execute(query_unavailable, params_unavailable)
    unavailable_personnel = [dict(row) for row in cursor.fetchall()]
    unavailable_ids = {p['personnel_id'] for p in unavailable_personnel}
    query_all = "SELECT id, rank, first_name, last_name, department FROM personnel"
    params_all = []
    if not is_admin:
        query_all += " WHERE department = ?"; params_all.append(department)
    cursor.execute(query_all, params_all)
    all_personnel = [dict(row) for row in cursor.fetchall()]
    available_personnel = [p for p in all_personnel if p['id'] not in unavailable_ids]
    def get_rank_index(item):
        try: return RANK_ORDER.index(item['rank'])
        except ValueError: return len(RANK_ORDER)
    unavailable_personnel.sort(key=get_rank_index)
    available_personnel.sort(key=get_rank_index)
    return {"status": "success", "active_statuses": unavailable_personnel, "available_personnel": available_personnel, "total_personnel": len(all_personnel)}

def handle_get_daily_dashboard_summary(payload, conn, cursor, session):
    target_date_str = get_daily_target_date(cursor).strftime('%Y-%m-%d')
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != ''")
    all_departments = [row['department'] for row in cursor.fetchall()]
    query = "SELECT dr.department, dr.summary_data, dr.timestamp, u.rank, u.first_name, u.last_name FROM daily_reports dr JOIN users u ON dr.submitted_by = u.username WHERE dr.report_date = ?"
    cursor.execute(query, (target_date_str,))
    submitted_info = {}
    for row in cursor.fetchall():
        summary = json.loads(row['summary_data'])
        submitted_info[row['department']] = {
            'submitter_fullname': f"{row['rank']} {row['first_name']} {row['last_name']}", 'timestamp': row['timestamp'],
            'summary': {'officer': summary.get('officer', {}), 'nco': summary.get('nco', {}), 'civilian': summary.get('civilian', {})}
        }
    return {"status": "success", "summary": {"all_departments": all_departments, "submitted_info": submitted_info, "report_date": target_date_str}}

def handle_get_daily_personnel_for_submission(payload, conn, cursor, session):
    is_admin, user_department, all_departments = session.get("role") == "admin", session.get("department"), []
    if is_admin:
        cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != '' ORDER BY department")
        all_departments = [row['department'] for row in cursor.fetchall()]
    department_to_view = (payload.get("department") or (all_departments[0] if all_departments else None)) if is_admin else user_department
    if not department_to_view:
        response_data = {"status": "success", "personnel": {'officer':[], 'nco':[], 'civilian':[]}, "department": "", "report_date": date.today().isoformat(), "submission_status": None}
        if is_admin: response_data["all_departments"] = all_departments
        return response_data
    target_date_str = get_daily_target_date(cursor).isoformat()
    submission_status = None
    if not is_admin:
        cursor.execute("SELECT timestamp FROM daily_reports WHERE report_date = ? AND department = ?", (target_date_str, user_department))
        last_submission = cursor.fetchone()
        if last_submission: submission_status = {"timestamp": last_submission['timestamp']}
    cursor.execute("SELECT * FROM personnel WHERE department = ?", (department_to_view,))
    personnel_in_dept = [dict(row) for row in cursor.fetchall()]
    classified_personnel = classify_personnel(personnel_in_dept)
    cursor.execute("SELECT * FROM persistent_statuses WHERE end_date >= ? AND start_date <= ? AND department = ?", (target_date_str, target_date_str, department_to_view))
    active_statuses = {row['personnel_id']: dict(row) for row in cursor.fetchall()}
    for category in classified_personnel:
        for person in classified_personnel[category]:
            if person['id'] in active_statuses:
                person.update(active_statuses[person['id']])
            else:
                person.update({'status': 'ไม่มี', 'details': '', 'start_date': '', 'end_date': ''})
    response_data = {"status": "success", "personnel": classified_personnel, "department": department_to_view, "report_date": target_date_str, "submission_status": submission_status}
    if is_admin: response_data["all_departments"] = all_departments
    return response_data

def handle_submit_daily_report(payload, conn, cursor, session):
    data, submitted_by = payload.get("data", {}), session.get("username")
    department, report_date_str = data.get("department"), data.get("report_date")
    if not all([department, report_date_str]): return {"status": "error", "message": "ข้อมูลไม่ครบถ้วน"}
    timestamp_str = (datetime.utcnow() + timedelta(hours=7)).strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute("DELETE FROM daily_reports WHERE department = ? AND report_date = ?", (department, report_date_str))
    cursor.execute(
        "INSERT INTO daily_reports (id, report_date, department, submitted_by, timestamp, summary_data, report_data) VALUES (?, ?, ?, ?, ?, ?, ?)",
        (str(uuid.uuid4()), report_date_str, department, submitted_by, timestamp_str, json.dumps(data.get("summary_data", {})), json.dumps(data.get("report_data", {})))
    )
    cursor.execute("SELECT id, rank FROM personnel WHERE department = ?", (department,))
    personnel_in_dept = cursor.fetchall()
    nco_civ_ids = [p['id'] for p in personnel_in_dept if p['rank'] in RANK_CLASSIFICATION['nco'] or p['rank'] in RANK_CLASSIFICATION['civilian']]
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
    conn.commit()
    return {"status": "success", "message": f"ส่งยอดกำลังพลสำหรับวันที่ {report_date_str} สำเร็จ"}

def handle_get_daily_submission_history(payload, conn, cursor, session):
    is_admin, department = session.get("role") == "admin", session.get("department")
    query = "SELECT report_date, department, submitted_by, timestamp, summary_data FROM daily_reports"
    params = []
    if not is_admin: query += " WHERE department = ?"; params.append(department)
    query += " ORDER BY report_date DESC"
    cursor.execute(query, params)
    history_by_month = defaultdict(lambda: defaultdict(list))
    for row in cursor.fetchall():
        report = dict(row)
        report_dt = datetime.strptime(report["report_date"], '%Y-%m-%d')
        year_be, month = str(report_dt.year + 543), str(report_dt.month)
        report['summary'] = json.loads(report.get("summary_data", "{}")); del report["summary_data"]
        history_by_month[year_be][month].append(report)
    return {"status": "success", "history": dict(history_by_month)}

def handle_get_daily_final_report(payload, conn, cursor, session):
    target_date_str = get_daily_target_date(cursor).strftime('%Y-%m-%d')
    cursor.execute("SELECT DISTINCT department FROM personnel WHERE department IS NOT NULL AND department != '' ORDER BY department")
    all_departments = [row['department'] for row in cursor.fetchall()]
    query = "SELECT dr.*, u.rank, u.first_name, u.last_name FROM daily_reports dr JOIN users u ON dr.submitted_by = u.username WHERE dr.report_date = ?"
    cursor.execute(query, (target_date_str,))
    reports = [dict(row) for row in cursor.fetchall()]
    for report in reports:
        report['summary_data'] = json.loads(report['summary_data'])
        report['report_data'] = json.loads(report['report_data'])
    submitted_departments = [r['department'] for r in reports]
    return {
        "status": "success", "reports": reports, "report_date": target_date_str,
        "all_departments": all_departments, "submitted_departments": submitted_departments
    }
    
def handle_archive_daily_reports(payload, conn, cursor, session):
    reports_to_archive = payload.get("reports", [])
    if not reports_to_archive: return {"status": "error", "message": "ไม่พบรายงานที่จะเก็บ"}
    for report in reports_to_archive:
        report_date, department = report["report_date"], report["department"]
        cursor.execute("DELETE FROM archived_daily_reports WHERE report_date = ? AND department = ?", (report_date, department))
        year, month, _ = map(int, report_date.split('-'))
        submitted_by = f"{report['rank']} {report['first_name']} {report['last_name']}"
        cursor.execute(
            "INSERT INTO archived_daily_reports (id, year, month, report_date, department, submitted_by, timestamp, summary_data, report_data) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (str(uuid.uuid4()), year, month, report_date, department, submitted_by, report["timestamp"], json.dumps(report["summary_data"]), json.dumps(report["report_data"]))
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
    holiday_date, description = payload.get("date"), payload.get("description")
    if not holiday_date or not description: return {"status": "error", "message": "กรุณากรอกข้อมูลวันหยุดให้ครบถ้วน"}
    try:
        cursor.execute("INSERT INTO holidays (date, description) VALUES (?, ?)", (holiday_date, description))
        conn.commit()
        return {"status": "success", "message": f"เพิ่มวันหยุด '{escape(description)}' สำเร็จ"}
    except sqlite3.IntegrityError:
        return {"status": "error", "message": "วันหยุดนี้มีอยู่ในระบบแล้ว"}

def handle_delete_holiday(payload, conn, cursor, session):
    holiday_date = payload.get("date")
    if not holiday_date: return {"status": "error", "message": "ไม่พบข้อมูลวันที่ที่จะลบ"}
    cursor.execute("DELETE FROM holidays WHERE date = ?", (holiday_date,))
    conn.commit()
    return {"status": "success", "message": "ลบวันหยุดสำเร็จ"}

# --- ACTION MAP ---
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

# --- Flask Routes ---
@app.route('/')
def root():
    return send_from_directory('.', 'login.html')

@app.route('/<path:path>')
def serve_static(path):
    if '..' in path or path.startswith('/'):
        return "Not Found", 404
    known_files = ['login.html', 'main.html', 'daily.html', 'selection.html', 'admin.html',
                   'app.js', 'api.js', 'ui.js', 'utils.js', 'handlers.js', 'login.js', 
                   'admin.js', 'daily.js', 'style.css']
    if path in known_files or os.path.exists(path):
        return send_from_directory('.', path)
    return send_from_directory('.', 'login.html')

@app.route('/api', methods=['POST'])
def api_handler():
    action_name = "unknown"
    try:
        session_token = request.cookies.get('session_token')
        session = None
        if session_token:
            conn_session = get_db_connection()
            cursor_session = conn_session.cursor()
            expiry_limit = datetime.now() - timedelta(seconds=SESSION_TIMEOUT_SECONDS)
            cursor_session.execute("DELETE FROM sessions WHERE created_at < ?", (expiry_limit,))
            conn_session.commit()
            cursor_session.execute("SELECT u.username, u.role, u.department FROM sessions s JOIN users u ON s.username = u.username WHERE s.token = ?", (session_token,))
            session_data = cursor_session.fetchone()
            if session_data:
                session = dict(session_data)
                session['token'] = session_token
            conn_session.close()

        request_data = request.get_json()
        action_name, payload = request_data.get("action"), request_data.get("payload", {})
        action_config = ACTION_MAP.get(action_name)

        if not action_config: return jsonify({"status": "error", "message": "ไม่รู้จักคำสั่งนี้"}), 404
        if action_config.get("auth_required") and not session: return jsonify({"status": "error", "message": "Unauthorized"}), 401
        if action_config.get("admin_only") and (not session or session.get("role") != "admin"): return jsonify({"status": "error", "message": "คุณไม่มีสิทธิ์ดำเนินการ"}), 403

        conn = get_db_connection()
        cursor = conn.cursor()
        try:
            handler_kwargs = {"payload": payload, "conn": conn, "cursor": cursor}
            if action_name == "login": handler_kwargs["client_address_ip"] = request.remote_addr
            
            session_actions = [
                "logout", "list_personnel", "submit_status_report", "get_submission_history", 
                "get_active_statuses", "get_daily_personnel_for_submission", "submit_daily_report",
                "get_daily_submission_history", "get_daily_final_report", "archive_daily_reports",
                "get_archived_daily_reports", "archive_reports", "list_holidays", 
                "add_holiday", "delete_holiday"
            ]
            if session and action_name in session_actions:
                handler_kwargs["session"] = session

            response_data = action_config["handler"](**handler_kwargs)
            
            headers = None
            if isinstance(response_data, tuple):
                response_data, headers = response_data
            
            resp = make_response(jsonify(response_data))
            if headers:
                for h_key, h_value in headers:
                    if h_key.lower() == 'set-cookie':
                        parts = h_value.split(';')
                        cookie_parts = parts[0].split('=')
                        name, value = cookie_parts[0], cookie_parts[1]
                        
                        max_age_part = next((p for p in parts if 'max-age=' in p.lower()), None)
                        max_age = int(max_age_part.split('=')[1]) if max_age_part else None

                        resp.set_cookie(name, value, max_age=max_age, httponly=True, samesite='Strict')
            return resp
        finally:
            conn.close()
    except Exception as e:
        print(f"API Error on action '{action_name}': {e}")
        return jsonify({"status": "error", "message": "Server error"}), 500

# --- Server Start ---
if __name__ == '__main__':
    init_db()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 9999)), debug=False)

