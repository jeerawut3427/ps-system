import sqlite3
import hashlib
import os
import getpass

DB_FILE = "database.db"
ADMIN_USERNAME = "jeerawut"

def hash_password(password, salt=None):
    """Hashes a password with a salt using PBKDF2-HMAC-SHA256."""
    if salt is None:
        salt = os.urandom(16)
    key = hashlib.pbkdf2_hmac('sha256', password.encode('utf-8'), salt, 100000)
    return salt, key

def reset_admin_password():
    """Resets the password for the admin user."""
    print(f"กำลังทำการรีเซ็ตรหัสผ่านสำหรับผู้ใช้: {ADMIN_USERNAME}")

    # รับรหัสผ่านใหม่จากผู้ใช้
    new_password = getpass.getpass("กรุณาป้อนรหัสผ่านใหม่: ")
    confirm_password = getpass.getpass("ยืนยันรหัสผ่านใหม่อีกครั้ง: ")

    if new_password != confirm_password:
        print("\nรหัสผ่านไม่ตรงกัน! การรีเซ็ตถูกยกเลิก")
        return

    if len(new_password) < 8:
        print("\nรหัสผ่านต้องมีความยาวอย่างน้อย 8 ตัวอักษร! การรีเซ็ตถูกยกเลิก")
        return

    # ทำการ Hash รหัสผ่านใหม่
    new_salt, new_key = hash_password(new_password)

    try:
        # เชื่อมต่อฐานข้อมูลและอัปเดต
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        cursor.execute("UPDATE users SET salt = ?, key = ? WHERE username = ?", (new_salt, new_key, ADMIN_USERNAME))

        if cursor.rowcount == 0:
            print(f"\nไม่พบผู้ใช้ชื่อ '{ADMIN_USERNAME}' ในฐานข้อมูล!")
        else:
            conn.commit()
            print(f"\nรีเซ็ตรหัสผ่านสำหรับ '{ADMIN_USERNAME}' สำเร็จแล้ว!")

    except sqlite3.Error as e:
        print(f"\nเกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    reset_admin_password()