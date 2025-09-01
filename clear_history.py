# -*- coding: utf-8 -*-
import sqlite3
import os

DB_FILE = "database.db"

def clear_all_reports():
    """
    Connects to the database and clears all records from the report, 
    archive, and persistent status tables.
    """
    if not os.path.exists(DB_FILE):
        print(f"ข้อผิดพลาด: ไม่พบไฟล์ฐานข้อมูล '{DB_FILE}'")
        return

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

        print("กำลังลบข้อมูลจากตาราง status_reports...")
        cursor.execute("DELETE FROM status_reports")
        
        print("กำลังลบข้อมูลจากตาราง archived_reports...")
        cursor.execute("DELETE FROM archived_reports")
        
        print("กำลังลบข้อมูลจากตาราง persistent_statuses...")
        cursor.execute("DELETE FROM persistent_statuses")
        
        conn.commit()
        print("\nล้างข้อมูลประวัติการส่งยอดทั้งหมดเรียบร้อยแล้ว!")
        
    except sqlite3.Error as e:
        print(f"เกิดข้อผิดพลาดในการเชื่อมต่อฐานข้อมูล: {e}")
    finally:
        if conn:
            conn.close()

if __name__ == "__main__":
    # Ask for confirmation before deleting
    confirm = input("คุณแน่ใจหรือไม่ว่าต้องการลบประวัติการส่งรายงานทั้งหมด? การกระทำนี้ไม่สามารถย้อนกลับได้ (พิมพ์ 'yes' เพื่อยืนยัน): ")
    if confirm.lower() == 'yes':
        clear_all_reports()
    else:
        print("ยกเลิกการลบข้อมูล")
