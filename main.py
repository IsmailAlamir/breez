from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
import sqlite3
from typing import Optional

app = FastAPI()

class AppointmentRequest(BaseModel):
    patient_name: str
    age: int 
    service: str
    appointment_date: str
    insurance_provider: Optional[str] = "None"
    notes: Optional[str] = ""

def init_db():
    conn = sqlite3.connect('dental_clinic.db')
    c = conn.cursor()
    c.execute('''
        CREATE TABLE IF NOT EXISTS appointments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            patient_name TEXT,
            age INTEGER,
            service TEXT,
            appointment_date TEXT,
            insurance_provider TEXT,
            notes TEXT
        )
    ''')
    conn.commit()
    conn.close()

init_db()

@app.get("/")
def read_root():
    return {"status": "Online", "message": "Breez Dental API is running!"}

@app.post("/book_appointment")
def book_appointment(data: AppointmentRequest):
    try:
        conn = sqlite3.connect('dental_clinic.db')
        c = conn.cursor()
        c.execute('''
            INSERT INTO appointments (patient_name, age, service, appointment_date, insurance_provider, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (data.patient_name, data.age, data.service, data.appointment_date, data.insurance_provider, data.notes))
        conn.commit()
        booking_id = c.lastrowid
        conn.close()
        
        return {
            "status": "success",
            "message": "Appointment booked successfully",
            "booking_id": booking_id,
            "patient": data.patient_name
        }
    except Exception as e:
        return {"status": "error", "detail": str(e)}

@app.get("/appointments")
def get_all_appointments():
    conn = sqlite3.connect('dental_clinic.db')
    c = conn.cursor()
    c.execute("SELECT * FROM appointments")
    rows = c.fetchall()
    conn.close()
    return {"appointments": rows}