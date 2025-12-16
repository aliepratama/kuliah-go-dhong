# GO-DHONG (Smart Garden Manager v2.0)

**Go-Dhong** adalah aplikasi web berbasis AI untuk pemantauan presisi tanaman (khususnya pepaya) menggunakan segmentasi instan YOLOv11. Aplikasi ini memungkinkan manajemen kebun berbasis spasial (grid), pencatatan riwayat pertumbuhan daun, dan analisis visual otomatis.

![Go-Dhong Dashboard](https://via.placeholder.com/800/F4F1EA/1A1A1A?text=GO-DHONG+Dashboard+Preview)

## 🌟 Fitur Utama

### 1. 🗺️ Manajemen Kebun Spasial (Garden Grid)
- **Visualisasi Grid**: Tampilan kebun dalam bentuk grid interaktif (baris x kolom).
- **Status Tanaman**: Indikator visual untuk slot kosong, tanaman sehat, atau kritis.
- **Multi-Garden**: Dukungan untuk mengelola banyak kebun sekaligus.

### 2. 🍃 Smart Leaf Analysis (AI Powered)
- **Deteksi Otomatis**: Menggunakan **YOLOv11-seg** untuk mendeteksi daun dan koin referensi.
- **Pengukuran Luas**: Menghitung luas daun akurat dalam cm² menggunakan koin Rp500 sebagai referensi skala.
- **Dukungan Kamera**: Ambil foto langsung dari kamera HP/Laptop atau upload file.

### 3. 📊 Plant Inspector & History
- **Detail Tanaman**: Klik slot grid untuk melihat umur tanaman, luas daun terakhir, dan catatan.
- **Riwayat Lengkap**: Log pertumbuhan per tanaman dengan grafik dan data historis.
- **Pencarian & Filter**: Cari riwayat scan berdasarkan nama tanaman, ID, atau status deteksi koin.
- **Client-Side Pagination**: Navigasi data riwayat yang cepat dan responsif.

### 4. 🎨 Neo-Brutalism UI
- Antarmuka modern dengan gaya **Neo-Brutalism**.
- Responsif untuk desktop dan mobile.
- Interaksi cepat tanpa reload halaman (menggunakan **HTMX** & **Alpine.js**).

---

## 🛠️ Instalasi & Menjalankan Aplikasi

Aplikasi ini dirancang untuk berjalan di dalam container Docker untuk kemudahan deployment.

### Prasyarat
- **Docker** & **Docker Compose** terinstall.
- Model YOLOv11 yang sudah dilatih (`models/best.pt`).
- RAM minimal 4GB disarankan.

### Langkah-langkah

1. **Clone Repository**
   ```bash
   git clone https://github.com/username/go-dhong.git
   cd go-dhong
   ```

2. **Siapkan Model**
   Pastikan file model `best.pt` ada di folder `models/`.

3. **Konfigurasi Environment**
   Salin file `.env.example` menjadi `.env` dan sesuaikan konfigurasinya.
   ```bash
   cp .env.example .env
   ```
   Sesuaikan variabel di dalam file `.env` jika diperlukan (misalnya untuk Ngrok atau database).

4. **Jalankan dengan Docker Compose**
   ```bash
   docker-compose up --build
   ```
   _Proses ini akan mendownload image yang dibutuhkan dan membangun container aplikasi._

5. **Akses Aplikasi**
   Buka browser dan kunjungi:
   - **Dashboard**: [http://localhost:8000](http://localhost:8000)
   - **Dokumentasi API**: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 📖 Cara Penggunaan

### 1. Membuat Kebun Baru
1. Di halaman Dashboard, jika belum ada kebun, klik tombol **"Buat Garden"**.
2. Masukkan nama kebun dan ukuran grid (contoh: 4 baris x 4 kolom).
3. Klik **Simpan**.

### 2. Menambahkan Tanaman
1. Klik salah satu slot **"EMPTY"** (+) pada grid kebun.
2. Masukkan nama tanaman (contoh: "Pepaya A1") dan catatan opsional.
3. Klik **Simpan**. Slot akan berubah menjadi ikon tanaman.

### 3. Melakukan Scan Daun
1. Klik tanaman yang ingin discan pada grid.
2. Panel **Plant Inspector** akan muncul di sebelah kanan.
3. Klik tombol **"+ SCAN DAUN BARU"**.
4. Pilih metode:
   - **Upload**: Pilih foto dari galeri.
   - **Camera**: Ambil foto langsung (pastikan izin kamera aktif).
5. **PENTING**: Pastikan dalam foto terdapat **Daun** dan **Koin Rp500 (Silver)** sebagai pembanding ukuran.
6. Klik **Scan**. Hasil luas daun akan muncul otomatis.

### 4. Melihat Riwayat
- **Per Tanaman**: Lihat di panel Plant Inspector setelah mengklik tanaman.
- **Semua Data**: Klik menu **HISTORY** di navigasi atas untuk melihat tabel lengkap dengan fitur pencarian dan filter.

---

## 🔧 Teknologi

- **Backend**: FastAPI (Python 3.10)
- **Database**: PostgreSQL (Async SQLAlchemy)
- **AI Engine**: Ultralytics YOLOv11
- **Frontend**: Jinja2 Templates
- **Interactivity**: HTMX, Alpine.js
- **Styling**: TailwindCSS (Custom Neo-Brutalism Config)

## 📂 Struktur Project

```
pp-inference-daun/
├── app/
│   ├── main.py             # Entry point aplikasi FastAPI
│   ├── ml_engine.py        # Logika inferensi YOLOv11
│   ├── models.py           # Definisi Database Models
│   ├── database.py         # Koneksi Database
│   ├── static/             # File statis (CSS, JS, Uploads)
│   └── templates/          # File HTML (Jinja2)
│       └── components/     # Komponen UI modular
├── models/
│   └── best.pt             # Model YOLOv11
├── docker-compose.yml      # Konfigurasi Docker Service
├── Dockerfile              # Definisi Image Docker
└── requirements.txt        # Dependensi Python
```

## 📝 Lisensi

Project ini dibuat untuk tujuan penelitian dan edukasi.
