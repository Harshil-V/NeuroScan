# NeuroScan Workstation — Demo Script

**Slice 1 — Vertical spine**
Run through this top to bottom to see the full upload → view → audit flow.

---

## Before you start

Make sure OrbStack is running (open `/Applications/OrbStack.app` if it isn't).

**Start the stack** (run this once per session):

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
export PATH="$HOME/.orbstack/bin:$PATH"
docker compose -f infra/docker-compose.yml up -d
```

Wait ~15 seconds, then confirm everything is healthy:

```bash
curl -s http://localhost:8000/health | python3 -m json.tool
```

You should see `"status": "ok"` with both `orthanc_reachable` and `db_reachable` as `true`.

---

## Step 1 — Upload a real MRI DICOM

Open **Finder** and press **⌘⇧G**, then paste:

```
/Users/harshilvyas/Documents/Github Repos/NeuroScan/data/sample-dicom/real
```

You'll find `brain_mr.dcm` — a real 64×64 MR DICOM from a public test dataset.

Now open the web app:

**http://localhost:5173/upload**

Drag `brain_mr.dcm` onto the dropzone. Within 1–2 seconds you should see:

```
Uploaded successfully.
Study UID: 1.3.6.1.4.1.5962...
Checksum: 3e4c8c9f...  (64 hex chars)
[Open study]
```

---

## Step 2 — View the study

Click **"Open study"** (or go to **http://localhost:5173/studies** and click **"View →"** on the row).

On the detail page you'll see:
- Patient metadata and study date
- A **series heading** ("Synthetic Test Series" or similar)
- A **grayscale MR preview image** — this is rendered live from Orthanc

> The real brain_mr.dcm renders as a 64×64 grayscale MR slice. It looks like noise but it is actual MR pixel data from a public test set.

---

## Step 3 — View the audit log

Go to **http://localhost:5173/audit**.

You'll see the upload event with:
- `event_type: dicom_uploaded`
- `status: success`
- The study UID and checksum matching what was shown on upload

Use the **Status** dropdown to filter — try `Failure` (it'll be empty if you've only uploaded valid files so far).

---

## Step 4 — Trigger a failure (optional)

Go back to **http://localhost:5173/upload** and drop any non-DICOM file — a `.txt`, `.png`, `.pdf`, anything.

You should see a red error:
```
invalid_dicom: File is missing DICOM File Meta Information...
```

Go to **http://localhost:5173/audit** → set Status filter to **Failure** → you'll see the rejected upload logged with the error message.

---

## Step 5 — Orthanc DICOM archive UI

Open **http://localhost:8042** → login with `orthanc` / `orthanc`.

Click into the study → series → instance. At the bottom you'll see:
- **DICOM Tags** — all metadata fields (Patient, Study, Series, Instance UIDs, Rows, Columns, etc.)
- **Preview the Instance** — Orthanc's own rendering of the MR pixel data
- **Download the DICOM file** — download the raw `.dcm` back out

This is the same archive that the web viewer and API read from.

---

## Step 6 — API docs

Open **http://localhost:8000/docs** — the interactive FastAPI Swagger UI.

Try these endpoints live:
- `GET /health` — check system status
- `GET /api/studies` — list all uploaded studies
- `GET /api/audit/events` — view audit log (filter by `status=failure` or `status=success`)
- `POST /api/dicom/upload` — upload a DICOM directly (click "Try it out", choose a file)

---

## Generate more test DICOMs (synthetic)

To generate additional synthetic MR DICOMs with random pixel data:

```bash
cd "/Users/harshilvyas/Documents/Github Repos/NeuroScan"
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py data/sample-dicom/synthetic/test2.dcm
```

Each run generates a unique DICOM with fresh UIDs — upload as many as you want to populate the studies list.

---

## Stop the stack

```bash
docker compose -f infra/docker-compose.yml down          # stop, keep data
docker compose -f infra/docker-compose.yml down -v       # stop + wipe all data (fresh start)
```

---

## What's working in Slice 1

| Feature | Status |
|---|---|
| DICOM upload via web UI | ✓ |
| DICOM validation (reject non-DICOM) | ✓ |
| SHA-256 checksum on every upload | ✓ |
| Orthanc DICOM archive storage | ✓ |
| Study / series / instance list | ✓ |
| Preview image (PNG rendered by Orthanc) | ✓ |
| Audit log (success + failure events) | ✓ |
| Interactive API docs | ✓ |
| Full test suite (36 tests) | ✓ |

## What's coming in later slices

| Feature | Slice |
|---|---|
| Qt desktop viewer (slice/pan/zoom, window/level) | 2 |
| MRI reconstruction from k-space data | 3 |
| MinIO secure object storage simulation | 4 |
| De-identification scanner | 5 |
| Authentication / RBAC | 6 |
| Prometheus + Grafana metrics | 7 |
| Cornerstone3D web viewer (multi-frame, measurements) | 8 |
