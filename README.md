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

### Catatan
Versi ini adalah demo frontend statis. Jika Anda ingin fitur checker yang benar-benar terhubung ke backend, maka perlu deploy aplikasi FastAPI ke hosting seperti Render, Railway, atau Vercel dengan backend terpisah.
