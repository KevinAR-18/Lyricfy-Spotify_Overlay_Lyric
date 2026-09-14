# 📋 Cinematic Background Style Roadmap & Context Baseline

Dokumen ini berisi rangkuman arsitektur saat ini dan roadmap pengembangan fitur background style untuk sesi berikutnya.

---

## 1. Context Baseline (Status Terkini)

### Komponen & File Kunci
* **`src/lyric_overlay/cinematic/Cinematic.qml`**:
  * Arsitektur: **Declarative Qt Quick Animations**, tanpa per-frame JavaScript loop; `Loader` hanya memuat efek aktif.
  * Performa pada layar *high refresh rate* dan penggunaan CPU/GPU perlu diukur pada perangkat target; belum ada jaminan CPU < 1%.
  * Layer ambient tidak memakai clipping eksplisit; gust menggunakan `Translate` agar tidak berbenturan dengan anchors.
* **`src/lyric_overlay/cinematic/preferences.py` & `settings.py`**:
  * Opsi persisten di `.env`:
    * `ambient_effect`: `["none", "leaves", "snowfall", "rain", "fireflies", "blobs", "stardust"]` (Aurora telah dihapus; konfigurasi lama `aurora` dinormalisasi menjadi `none`)
    * `ambient_intensity`: `10` – `100%` (mengontrol opasitas & kontras partikel).
* **Sistem Reaksi Aliran Lirik**:
  * Trigger: Pergantian baris, pergantian lagu (termasuk indeks yang sama), dan resume playback.
  * Efek: Hembusan angin (`gustAnim`) berdurasi 750 ms dan denyut pendar (`pulseAnim`) 900 ms; keduanya dihentikan dan direset saat paused.
* **Edge Fade Bawaan**:
  * Setiap partikel memiliki animasi *fade-in* saat muncul dan *fade-out* sebelum keluar layar secara deklaratif, sehingga tidak ada potongan tajam di tepi jendela.
* **Windows Media Session Safety (`spotify_client.py`)**:
  * Dilindungi `asyncio.wait_for(..., timeout=2.0)` untuk mencegah deadlock COM/WinRT.

---

## 2. Roadmap Pengembangan Style Background

### Tahap 1: Penambahan Preset Efek Visual Baru (✅ Selesai)
1. **Winter Snowfall (Salju Melayang)** (`snowfall`)
   * Butiran salju halus dengan ukuran acak dan goyangan *sine-wave* lambat.
2. **Gentle Rain & Mist (Hujan Rintik Halus)** (`rain`)
   * Garis-garis rintik tipis transparan diagonal dengan hembusan angin saat pergantian bait dan kabut di dasar.
3. **Fireflies / Forest Embers (Kunang-Kunang Hutan)** (`fireflies`)
   * Partikel cahaya keemasan/hijau neon yang melayang perlahan dengan kedipan berdenyut alami.
4. **Fluid Lava / Color Blobs (Gelombang Warna Organik)** (`blobs`)
   * Pendaran bola cahaya dinamis menyatu di belakang lirik yang bereaksi terhadap warna album.

---

### Tahap 2: Responsivitas Musik yang Lebih Dinamis (✅ Selesai)
1. **Tempo-Aware Motion**:
   * Kecepatan dihitung dari `state.remaining` saat pergantian baris/lagu dan resume, dibatasi 0,75–1,35; nilai tidak valid atau paused memakai tempo netral 1,0:
     * Lagu bertempo cepat (remaining pendek): Animasi bergerak lebih lincah dan dinamis.
     * Lagu lambat/ballad: Partikel melayang perlahan dan menenangkan.
2. **Adaptive Color Harmony**:
   * Penyesuaian palet warna partikel secara dinamis mengikuti warna album aktif (`cinematic.albumColor`), `active_color`, dan `glow_color`.
   * Artwork diminta untuk leaves, rain, fireflies, blobs, dan stardust, termasuk preview dengan background transparan dan cover nonaktif. Snowfall memakai warna style tanpa membutuhkan artwork.

---

### Tahap 3: Opsi Kustomisasi Tambahan di Menu Style (`Shift+S`) (Pending / Next)
1. **Particle Density (Kerapatan Partikel)**:
   * Pilihan: *Minimalist (8 partikel)*, *Standard (16 partikel)*, *Lush (24 partikel)*.
2. **Flow Direction (Arah Aliran)**:
   * Pilihan arah angin: *Diagonal Down (Default)*, *Upward Float*, atau *Left-to-Right Drift*.

---

### Tahap 4: Modularitas Kode (Jika Efek Semakin Banyak)
* Saat ini terdapat enam efek dalam komponen inline yang dimuat melalui `Loader`. Pemisahan ke file tersendiri (misal `LeavesEffect.qml`, `SnowfallEffect.qml`) menjadi tindak lanjut; pastikan jalur `build.bat` menyertakan seluruh aset QML terkait.
