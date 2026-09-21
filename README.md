# Chaptca-Checker
Untuk mengecek apakah email ada Chaptca atau tidak.

## Versi GitHub Pages
Proyek ini sudah memiliki versi statis yang bisa dipublikasi ke GitHub Pages tanpa membutuhkan ngrok atau server Python.

### File utama
- `index.html` — halaman utama
- `styles.css` — styling
- `script.js` — logika login dan validasi email
- `.github/workflows/pages.yml` — workflow otomatis deploy ke GitHub Pages

### Cara publish ke GitHub Pages
1. Push semua file ke repo GitHub.
2. Buka repository di GitHub.
3. Pilih Settings → Pages.
4. Pada Source, pilih "GitHub Actions".
5. Setelah proses deploy selesai, GitHub akan memberi URL seperti:
   `https://username.github.io/nama-repo/`

### Deploy FastAPI penuh ke Render / Railway
Project backend asli di [gemini_code.py](gemini_code.py) sudah disiapkan untuk deployment penuh.

#### File pendukung deploy
- `Dockerfile` — container runtime untuk FastAPI + Playwright
- `requirements.txt` — semua dependency Python
- `render.yaml` — konfigurasi Render
- `railway.toml` — konfigurasi Railway
- `.env.example` — contoh environment variable

#### Langkah deploy
1. Push repo ke GitHub.
2. Import repo ke Render atau Railway.
3. Untuk Render: pilih repo dan deploy otomatis dari `render.yaml`.
4. Untuk Railway: pilih repo dan deploy otomatis dari `railway.toml`.
5. Pastikan environment variable berikut tersedia:
   - `MIDTRANS_CLIENT_KEY`
   - `MIDTRANS_SERVER_KEY`
   - `IS_PRODUCTION`
   - `PORT`
6. Aplikasi akan berjalan menggunakan `uvicorn gemini_code:app --host 0.0.0.0 --port $PORT`.

#### Catatan
GitHub Pages hanya untuk frontend statis. Backend FastAPI seperti [gemini_code.py](gemini_code.py) dan fitur Playwright/Midtrans harus di-deploy ke layanan yang menjalankan Python secara penuh seperti Render atau Railway.
