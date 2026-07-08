#!/usr/bin/env python3
"""
Herbarium — Invertis University Botany Lab
Backend: Python standard library only (no pip installs required) + SQLite.

Run with:  python3 server.py
Then open: http://localhost:8000
"""

import json
import sqlite3
import threading
import csv
import io
import os
from http.server import BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from http.server import HTTPServer
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "botany_lab.db")
STATIC_DIR = os.path.dirname(os.path.abspath(__file__))
PORT = int(os.environ.get("PORT", 8000))

db_lock = threading.Lock()

DEFAULT_EXPERIMENTS = [
    ("Study of Stomata and Stomatal Index", "Plant Physiology",
     "Peel epidermis and estimate stomatal frequency and index under the compound microscope.", 10),
    ("Osmotic Pressure via Potato Osmometer", "Plant Physiology",
     "Demonstrate osmosis and estimate osmotic pressure using a hollowed potato tuber.", 10),
    ("Estimation of Chlorophyll Content", "Plant Physiology",
     "Extract leaf pigments in acetone and estimate chlorophyll a & b spectrophotometrically.", 10),
    ("Separation of Plant Pigments by Paper Chromatography", "Plant Physiology",
     "Resolve leaf pigments into bands and calculate Rf values for each.", 10),
    ("Measurement of Rate of Transpiration", "Plant Physiology",
     "Use a simple potometer to measure water loss through a leafy twig.", 10),
    ("Anatomy of Dicot Stem — T.S. Study", "Plant Anatomy",
     "Prepare and stain a transverse section; identify vascular bundle arrangement.", 10),
    ("Anatomy of Monocot Root — T.S. Study", "Plant Anatomy",
     "Section, stain and label the primary structure of a monocot root.", 10),
    ("Study of Mitosis in Onion Root Tip", "Cytology",
     "Squash-stain technique to observe and identify stages of mitotic division.", 10),
    ("Callus Induction in Plant Tissue Culture", "Cytology",
     "Inoculate explants on MS medium and record callus initiation under aseptic conditions.", 10),
    ("Fungal Specimen Study — Rhizopus & Aspergillus", "Microbiology & Pathology",
     "Mount and examine mycelial structure and spore-bearing organs.", 10),
    ("Morphology of Bryophytes and Pteridophytes", "Taxonomy & Ecology",
     "Examine and sketch gametophyte/sporophyte generations of representative specimens.", 10),
    ("Soil pH and Its Effect on Seed Germination", "Taxonomy & Ecology",
     "Test germination rates of seeds sown in soils of varying pH.", 10),
]

DEFAULT_STUDENTS = [
    ("Ananya Sharma", "IU/BSC-BOT/2024/401", "B.Sc. (Hons.) Botany", "III", "A", "ananya.sharma@invertis.org", "", ""),
    ("Rohan Verma", "IU/BSC-BOT/2024/402", "B.Sc. (Hons.) Botany", "III", "B", "rohan.verma@invertis.org", "", ""),
    ("Priya Singh", "IU/BSC-BOT/2024/403", "B.Sc. (Hons.) Botany", "III", "A", "priya.singh@invertis.org", "", ""),
    ("Kabir Khan", "IU/BSC-BOT/2024/404", "B.Sc. (Hons.) Botany", "V", "B", "kabir.khan@invertis.org", "", ""),
    ("Ishita Gupta", "IU/BSC-BOT/2024/405", "B.Sc. (Hons.) Botany", "V", "A", "ishita.gupta@invertis.org", "", ""),
    ("Devansh Yadav", "IU/BSC-BOT/2024/406", "B.Sc. (Hons.) Botany", "V", "B", "devansh.yadav@invertis.org", "", ""),
]


def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    with db_lock:
        conn = get_conn()
        cur = conn.cursor()
        cur.executescript("""
        CREATE TABLE IF NOT EXISTS students (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            enrollment_no TEXT,
            course TEXT,
            semester TEXT,
            batch TEXT,
            email TEXT,
            phone TEXT,
            remarks TEXT
        );
        CREATE TABLE IF NOT EXISTS experiments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            category TEXT,
            description TEXT,
            max_marks INTEGER DEFAULT 10
        );
        CREATE TABLE IF NOT EXISTS records (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            student_id INTEGER NOT NULL,
            experiment_id INTEGER NOT NULL,
            status TEXT DEFAULT 'not_started',
            marks REAL,
            date TEXT,
            remarks TEXT,
            UNIQUE(student_id, experiment_id),
            FOREIGN KEY(student_id) REFERENCES students(id) ON DELETE CASCADE,
            FOREIGN KEY(experiment_id) REFERENCES experiments(id) ON DELETE CASCADE
        );
        """)
        conn.commit()

        cur.execute("SELECT COUNT(*) AS c FROM experiments")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO experiments (title, category, description, max_marks) VALUES (?,?,?,?)",
                DEFAULT_EXPERIMENTS,
            )
        cur.execute("SELECT COUNT(*) AS c FROM students")
        if cur.fetchone()["c"] == 0:
            cur.executemany(
                "INSERT INTO students (name, enrollment_no, course, semester, batch, email, phone, remarks) "
                "VALUES (?,?,?,?,?,?,?,?)",
                DEFAULT_STUDENTS,
            )
        conn.commit()
        conn.close()


def row_to_dict(row):
    return {k: row[k] for k in row.keys()}


class Handler(BaseHTTPRequestHandler):
    server_version = "HerbariumHTTP/1.0"

    def log_message(self, fmt, *args):
        print("[%s] %s" % (self.log_date_time_string(), fmt % args))

    # ---------- helpers ----------
    def _send_json(self, data, status=200):
        body = json.dumps(data).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.end_headers()
        self.wfile.write(body)

    def _send_file(self, path, content_type):
        try:
            with open(path, "rb") as f:
                body = f.read()
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        except FileNotFoundError:
            self._send_json({"error": "not found"}, 404)

    def _read_json(self):
        length = int(self.headers.get("Content-Length", 0))
        if length == 0:
            return {}
        raw = self.rfile.read(length)
        try:
            return json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError:
            return {}

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET,POST,PUT,DELETE,OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    # ---------- routing ----------
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path

        if path == "/" or path == "/index.html":
            return self._send_file(os.path.join(STATIC_DIR, "index.html"), "text/html; charset=utf-8")

        if path == "/api/students":
            return self.list_students()
        if path == "/api/experiments":
            return self.list_experiments()
        if path == "/api/records":
            return self.list_records()
        if path == "/api/export.csv":
            return self.export_csv()
        if path == "/api/health":
            return self._send_json({"status": "ok"})

        self._send_json({"error": "not found"}, 404)

    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        body = self._read_json()

        if path == "/api/students":
            return self.create_student(body)
        if path == "/api/experiments":
            return self.create_experiment(body)
        if path == "/api/records":
            return self.upsert_record(body)

        self._send_json({"error": "not found"}, 404)

    def do_PUT(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")
        body = self._read_json()

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "students":
            return self.update_student(int(parts[2]), body)
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "experiments":
            return self.update_experiment(int(parts[2]), body)

        self._send_json({"error": "not found"}, 404)

    def do_DELETE(self):
        parsed = urlparse(self.path)
        parts = parsed.path.strip("/").split("/")

        if len(parts) == 3 and parts[0] == "api" and parts[1] == "students":
            return self.delete_student(int(parts[2]))
        if len(parts) == 3 and parts[0] == "api" and parts[1] == "experiments":
            return self.delete_experiment(int(parts[2]))

        self._send_json({"error": "not found"}, 404)

    # ---------- students ----------
    def list_students(self):
        with db_lock:
            conn = get_conn()
            rows = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
            conn.close()
        self._send_json([row_to_dict(r) for r in rows])

    def create_student(self, b):
        with db_lock:
            conn = get_conn()
            cur = conn.execute(
                "INSERT INTO students (name, enrollment_no, course, semester, batch, email, phone, remarks) "
                "VALUES (?,?,?,?,?,?,?,?)",
                (b.get("name", ""), b.get("enrollment_no", ""), b.get("course", ""),
                 b.get("semester", ""), b.get("batch", ""), b.get("email", ""),
                 b.get("phone", ""), b.get("remarks", "")),
            )
            conn.commit()
            new_id = cur.lastrowid
            row = conn.execute("SELECT * FROM students WHERE id=?", (new_id,)).fetchone()
            conn.close()
        self._send_json(row_to_dict(row), 201)

    def update_student(self, sid, b):
        with db_lock:
            conn = get_conn()
            conn.execute(
                "UPDATE students SET name=?, enrollment_no=?, course=?, semester=?, batch=?, "
                "email=?, phone=?, remarks=? WHERE id=?",
                (b.get("name", ""), b.get("enrollment_no", ""), b.get("course", ""),
                 b.get("semester", ""), b.get("batch", ""), b.get("email", ""),
                 b.get("phone", ""), b.get("remarks", ""), sid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM students WHERE id=?", (sid,)).fetchone()
            conn.close()
        if row is None:
            return self._send_json({"error": "not found"}, 404)
        self._send_json(row_to_dict(row))

    def delete_student(self, sid):
        with db_lock:
            conn = get_conn()
            conn.execute("DELETE FROM students WHERE id=?", (sid,))
            conn.commit()
            conn.close()
        self._send_json({"deleted": sid})

    # ---------- experiments ----------
    def list_experiments(self):
        with db_lock:
            conn = get_conn()
            rows = conn.execute("SELECT * FROM experiments ORDER BY category, title").fetchall()
            conn.close()
        self._send_json([row_to_dict(r) for r in rows])

    def create_experiment(self, b):
        with db_lock:
            conn = get_conn()
            cur = conn.execute(
                "INSERT INTO experiments (title, category, description, max_marks) VALUES (?,?,?,?)",
                (b.get("title", ""), b.get("category", "General"), b.get("description", ""),
                 int(b.get("max_marks", 10) or 10)),
            )
            conn.commit()
            new_id = cur.lastrowid
            row = conn.execute("SELECT * FROM experiments WHERE id=?", (new_id,)).fetchone()
            conn.close()
        self._send_json(row_to_dict(row), 201)

    def update_experiment(self, eid, b):
        with db_lock:
            conn = get_conn()
            conn.execute(
                "UPDATE experiments SET title=?, category=?, description=?, max_marks=? WHERE id=?",
                (b.get("title", ""), b.get("category", "General"), b.get("description", ""),
                 int(b.get("max_marks", 10) or 10), eid),
            )
            conn.commit()
            row = conn.execute("SELECT * FROM experiments WHERE id=?", (eid,)).fetchone()
            conn.close()
        if row is None:
            return self._send_json({"error": "not found"}, 404)
        self._send_json(row_to_dict(row))

    def delete_experiment(self, eid):
        with db_lock:
            conn = get_conn()
            conn.execute("DELETE FROM experiments WHERE id=?", (eid,))
            conn.commit()
            conn.close()
        self._send_json({"deleted": eid})

    # ---------- records ----------
    def list_records(self):
        with db_lock:
            conn = get_conn()
            rows = conn.execute("SELECT * FROM records").fetchall()
            conn.close()
        self._send_json([row_to_dict(r) for r in rows])

    def upsert_record(self, b):
        student_id = b.get("student_id")
        experiment_id = b.get("experiment_id")
        if not student_id or not experiment_id:
            return self._send_json({"error": "student_id and experiment_id are required"}, 400)
        status = b.get("status", "not_started")
        marks = b.get("marks", None)
        date = b.get("date", "")
        remarks = b.get("remarks", "")
        with db_lock:
            conn = get_conn()
            conn.execute(
                """INSERT INTO records (student_id, experiment_id, status, marks, date, remarks)
                   VALUES (?,?,?,?,?,?)
                   ON CONFLICT(student_id, experiment_id)
                   DO UPDATE SET status=excluded.status, marks=excluded.marks,
                                 date=excluded.date, remarks=excluded.remarks""",
                (student_id, experiment_id, status, marks, date, remarks),
            )
            conn.commit()
            row = conn.execute(
                "SELECT * FROM records WHERE student_id=? AND experiment_id=?",
                (student_id, experiment_id),
            ).fetchone()
            conn.close()
        self._send_json(row_to_dict(row), 200)

    # ---------- export ----------
    def export_csv(self):
        with db_lock:
            conn = get_conn()
            students = conn.execute("SELECT * FROM students ORDER BY name").fetchall()
            experiments = conn.execute("SELECT * FROM experiments").fetchall()
            records = conn.execute("SELECT * FROM records").fetchall()
            conn.close()

        total_exp = len(experiments)
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["Enrollment No", "Name", "Course", "Semester", "Batch",
                          "Completed", "Total Experiments", "Completion %", "Average Marks"])
        for s in students:
            s_records = [r for r in records if r["student_id"] == s["id"]]
            done = len([r for r in s_records if r["status"] == "completed"])
            pct = round((done / total_exp) * 100) if total_exp else 0
            marked = [r["marks"] for r in s_records if r["marks"] is not None]
            avg = round(sum(marked) / len(marked), 1) if marked else ""
            writer.writerow([s["enrollment_no"], s["name"], s["course"], s["semester"],
                              s["batch"], done, total_exp, pct, avg])

        body = buf.getvalue().encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "text/csv")
        self.send_header("Content-Disposition", "attachment; filename=invertis-botany-lab-report.csv")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


def main():
    init_db()
    server = ThreadingHTTPServer(("0.0.0.0", PORT), Handler)
    print(f"Herbarium — Invertis University Botany Lab")
    print(f"Database: {DB_PATH}")
    print(f"Serving on http://localhost:{PORT}  (Ctrl+C to stop)")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nShutting down.")
        server.shutdown()


if __name__ == "__main__":
    main()
