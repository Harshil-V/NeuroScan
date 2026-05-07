# QA Validation Plan — Slice 1

**Last updated:** 2026-05-05
**Slice:** 1 — Vertical spine
**Spec:** [`superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md`](superpowers/specs/2026-05-05-slice-1-vertical-spine-design.md)
**Plan:** [`superpowers/plans/2026-05-05-slice-1-vertical-spine.md`](superpowers/plans/2026-05-05-slice-1-vertical-spine.md)

## Test environment

- macOS / Linux developer laptop
- Docker Desktop, OrbStack, Colima, or another container runtime (Compose v2)
- Stack started via `docker compose -f infra/docker-compose.yml up -d --build`

### macOS + OrbStack note

OrbStack does not bind `/var/run/docker.sock` by default. For testcontainers and any direct docker-py usage, set:

```bash
export PATH="$HOME/.orbstack/bin:$PATH"
export DOCKER_HOST="unix://$HOME/.orbstack/run/docker.sock"
```

The `docker compose` CLI itself works without `DOCKER_HOST` once `~/.orbstack/bin` is on PATH.

## Test data

- Synthetic MR DICOM via `scripts/generate-synthetic-dicom.py` (used by all automated tests)
- Real MR series via `scripts/download-sample-tcia.sh` (manual demo only; not exercised by tests or CI)

To generate a synthetic DICOM for manual testing:

```bash
uv run --directory services/api-service python ../../scripts/generate-synthetic-dicom.py /tmp/x.dcm
```

Note the `../../scripts/...` form — `uv run --directory` switches CWD into `services/api-service`, so the script path is relative to that.

## Manual test cases

### TC-01 Upload valid synthetic DICOM (happy path)

Steps:
1. Generate `/tmp/x.dcm` via the synthetic generator.
2. Open http://localhost:5173/upload.
3. Drop the file (or click to pick).
4. Wait for the success panel.
5. Click the "Open study" link.
6. Inspect the series and preview image.
7. Navigate to /audit.

Expected:
- Upload page shows the success panel with non-empty UIDs and a 64-char hex checksum.
- Studies page (or after clicking "Open study") shows the new study with Modality `MR`.
- Study detail page renders at least one preview image with non-zero dimensions.
- /audit shows a `dicom_uploaded` event with `success` status referencing the same study UID.

Pass criteria: all four expected outcomes met.

### TC-02 Upload non-DICOM file (negative)

Steps:
1. Drop any plain-text file (e.g. `notes.txt`) on /upload.

Expected:
- UI shows error message containing `invalid_dicom`.
- /audit shows a matching `dicom_uploaded` `failure` row.
- /studies is unchanged.

### TC-03 Upload DICOM with missing Modality tag

Steps:
1. Generate via the test fixture's `make_dicom_missing_modality()` helper:
   ```bash
   cd services/api-service
   uv run python -c "from tests.fixtures.synthetic_dicom import make_dicom_missing_modality; open('/tmp/no_mod.dcm','wb').write(make_dicom_missing_modality())"
   ```
2. Drop on /upload.

Expected:
- UI shows error containing `missing_required_tag`.
- /audit shows failure row.

### TC-04 Orthanc service down

Steps:
1. `docker compose stop orthanc`.
2. Drop a valid DICOM on /upload.
3. Refresh /health (or `curl localhost:8000/health`).

Expected:
- UI shows error with `orthanc_rejected` (after retries; allow up to ~10s).
- /audit shows failure row.
- /health returns 503 with `orthanc_reachable: false`.

Recovery: `docker compose start orthanc`. /health returns 200 within ~30s.

### TC-05 Postgres service down

Steps:
1. `docker compose stop postgres`.
2. Reload /studies (Orthanc-backed) → still works.
3. Reload /audit → fails (toast or error message).
4. Drop a valid DICOM → fails (audit write fails).

Expected:
- /audit shows error.
- /health returns 503 with `db_reachable: false`.

Recovery: `docker compose start postgres`. /health returns 200 within ~30s.

### TC-06 Persistence across restart

Steps:
1. Upload one DICOM.
2. `docker compose down` (without `-v` — volumes preserved).
3. `docker compose up -d`.
4. Visit /studies and /audit.

Expected:
- Study still listed (Orthanc volume preserved).
- Audit row still present (Postgres volume preserved).

### TC-07 Browser refresh during upload

Steps:
1. Generate a synthetic DICOM with larger dimensions:
   ```bash
   cd services/api-service
   uv run python -c "from tests.fixtures.synthetic_dicom import make_synthetic_mr_dicom_bytes; open('/tmp/big.dcm','wb').write(make_synthetic_mr_dicom_bytes(rows=1024, columns=1024))"
   ```
2. Drop and refresh mid-upload.

Expected:
- No partial study appears in /studies after Orthanc settles.
- A `failure` audit row may or may not appear depending on where the request was interrupted; either is acceptable.

### TC-08 Reconstruction round-trip (PSNR + SSIM verification)

Steps:
1. With the stack running:
   ```
   uv run --directory services/api-service python ../../scripts/generate-synthetic-kspace.py \
       "$PWD/data/sample-dicom/real-multislice/slice_010.dcm" \
       /tmp/brain.npz
   ```
2. Open http://localhost:5173/reconstruction.
3. Drop `/tmp/brain.npz`.
4. Watch the new row appear in the table; status transitions `queued → running → completed` within ~5 s.
5. Click the row to expand the side-by-side preview.
6. Click "Open reconstructed study →".

Expected:
- Status reaches `completed`.
- PSNR > 60 dB (FFT round-trip is essentially lossless).
- SSIM > 0.95.
- Reconstructed study appears under `/studies` with PatientName `Reconstruction^Output`.
- Preview image renders on the study detail page.

Pass criteria: all expected outcomes met. Reject row also added if a malformed file is uploaded.

## Automated tests as QA artifacts

The following automated suites also serve as QA evidence:

- **Unit tests** (`cd services/api-service && uv run pytest tests/unit/`): 24 tests covering DICOM validation, metadata extraction, checksum, OrthancClient mock, audit service, upload orchestrator.
- **Integration tests** (`cd services/api-service && uv run pytest tests/integration/`): 12 tests against real Postgres + Orthanc via testcontainers.
- **E2E test** (`cd tests/e2e && npm test` with stack up): 1 happy-path scenario clicking through the React UI.
- **CI** (`.github/workflows/ci.yml`): runs all of the above on every push and PR.

## Known limitations (slice 1)

- No authentication — anyone with network access to api-service can upload, view, audit.
- No de-identification scanning — Orthanc accepts whatever DICOM tags are present.
- No window/level controls — preview is fixed to Orthanc's built-in PNG render.
- No MinIO / signed-URL flow — files go directly to Orthanc.
- No Prometheus / Grafana metrics — only `/health` for observability.
- No Cornerstone3D viewer — preview thumbnails only.
- Studies/series/instances metadata is NOT cached in Postgres; every list call hits Orthanc. Acceptable for slice 1; will be revisited in slice 6.

These are deliberate scope omissions, all mapped to future slices in [`roadmap.md`](roadmap.md).

- Reconstruction supports 2D single-coil k-space only. Multi-coil (sum-of-squares) and 3D volumetric reconstruction are deferred to a future slice.
- Raw k-space inputs are stored only in a temp directory during processing and deleted on terminal status. Permanent k-space storage is Slice 4's job.
- Reconstruction jobs are not load-tested for concurrency; a real queue with worker pools comes in Slice 9.
