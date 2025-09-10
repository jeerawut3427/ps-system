# migrate_database.py
import sqlite3
import os

DB_FILE = "database.db"

def migrate():
    if not os.path.exists(DB_FILE):
        print(f"ไม่พบไฟล์ฐานข้อมูล '{DB_FILE}' ไม่จำเป็นต้องทำการอัปเกรด")
        return

    print("กำลังเชื่อมต่อฐานข้อมูลเพื่อทำการอัปเกรด...")
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()

    try:
        # 1. เปลี่ยนชื่อตารางเก่าเพื่อสำรองข้อมูลไว้
        print("กำลังสำรองข้อมูลตาราง archived_reports เดิม...")
        cursor.execute("ALTER TABLE archived_reports RENAME TO archived_reports_old")
        print(" -> สำรองข้อมูลสำเร็จ")

        # 2. สร้างตาราง archived_reports ใหม่ด้วยโครงสร้างที่ถูกต้อง
        print("กำลังสร้างตาราง archived_reports ใหม่...")
        cursor.execute('''
            CREATE TABLE archived_reports (
                id TEXT PRIMARY KEY,
                week_range TEXT,
                report_data TEXT,
                archived_by TEXT,
                timestamp DATETIME
            )
        ''')
        print(" -> สร้างตารางใหม่สำเร็จ")
        
        conn.commit()
        print("\n✅ อัปเกรดฐานข้อมูลเรียบร้อยแล้ว!")
        print("ข้อมูลกำลังพลและผู้ใช้งานยังอยู่ครบถ้วนเหมือนเดิม")
        print("ข้อมูลประวัติการเก็บรายงานเก่าได้ถูกสำรองไว้ในตาราง 'archived_reports_old'")

    except sqlite3.OperationalError as e:
        if "already exists" in str(e):
            print("\nดูเหมือนว่าตารางได้รับการอัปเกรดแล้ว ไม่ต้องดำเนินการใดๆ เพิ่มเติม")
        else:
            print(f"\nเกิดข้อผิดพลาด: {e}")
    except Exception as e:
        print(f"\nเกิดข้อผิดพลาดที่ไม่คาดคิด: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    migrate()