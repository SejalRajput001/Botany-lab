# Herbarium — Invertis University Botany Lab

A student & experiment tracker for the Botany laboratory, with a real backend
and a SQLite database (not just browser storage).

## Requirements
- Python 3.8+ only. No pip installs, no external packages — everything used
  is in the Python standard library (`http.server`, `sqlite3`).

## Run it

```
python3 server.py
```

Then open **http://localhost:8000** in your browser.

The first time it runs, it creates `botany_lab.db` (SQLite) next to
`server.py` and seeds it with 12 standard Botany practicals and 6 sample
students. After that, all your changes are saved permanently in that file —
close the server, restart your computer, whatever — the data stays.

To stop the server, press `Ctrl+C` in the terminal.

To run on a different port:
```
PORT=9000 python3 server.py
```

## What's inside

- **server.py** — the backend: a REST API (students, experiments, progress
  records) backed by SQLite, plus the code that serves the web page itself.
- **index.html** — the frontend: talks to the API with `fetch`, no build
  step or frameworks required.
- **botany_lab.db** — created automatically on first run. This is your
  database; back it up by copying this file.

## Features

- **Dashboard** — enrollment counts, overall completion %, top batch,
  completion-by-experiment bars, recent activity feed
- **Students** — add / edit / delete, search, filter by batch or semester,
  per-student progress bar
- **Experiments** — categorized catalogue (Plant Physiology, Anatomy,
  Cytology, Microbiology & Pathology, Taxonomy & Ecology), fully editable,
  pre-seeded with 12 standard practicals
- **Progress Matrix** — student × experiment grid; click a cell to cycle
  Not started → In progress → Completed
- **Student profile** — per-experiment status, marks, and remarks
- **Reports** — class summary with completion % and average marks, plus a
  CSV export (`/api/export.csv`) generated live from the database

## Notes on multi-computer / network access

By default the server listens on all interfaces (`0.0.0.0:8000`), so other
devices on the same Wi-Fi/LAN can reach it at `http://<your-computer's-IP>:8000`
if your firewall allows it. This is a lightweight single-process server meant
for lab/classroom use, not for public internet hosting.
