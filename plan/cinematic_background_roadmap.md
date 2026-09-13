# 📋 Cinematic Background Style Roadmap & Context Baseline

Dokumen ini berisi rangkuman arsitektur saat ini dan roadmap pengembangan fitur background style untuk sesi berikutnya.

---

## 1. Context Baseline (Status Terkini)

### Komponen & File Kunci
* **`src/lyric_overlay/cinematic/Cinematic.qml`**:
  * Arsitektur: **Declarative SceneGraph Animations** (berjalan pada GPU/C++ SceneGraph thread tanpa per-frame JavaScript loop).
  * Aman untuk layar *high refresh rate* (120Hz/144Hz/240Hz) dan CPU usage < 1%.
  * Bebas hard clipping (`clip: false`).
* **`src/lyric_overlay/cinematic/preferences.py` & `settings.py`**:
  * Opsi persisten di `.env`:
    * `ambient_effect`: `["none", "leaves", "aurora", "stardust"]`
    * `ambient_intensity`: `10` – `100%` (mengontrol opasitas & kontras partikel).
* **Sistem Reaksi Aliran Lirik**:
  * Trigger: Pergantian baris lirik aktif (`onLyricTrigger` saat `state.index` berubah).
  * Efek: Hembusan angin (`gustAnim`) dan denyut pendar (`pulseAnim`) berdurasi 850–1000ms.
* **Edge Fade Bawaan**:
  * Setiap partikel memiliki animasi *fade-in* saat muncul dan *fade-out* sebelum keluar layar secara deklaratif, sehingga tidak ada potongan tajam di tepi jendela.
* **Windows Media Session Safety (`spotify_client.py`)**:
  * Dilindungi `asyncio.wait_for(..., timeout=2.0)` untuk mencegah deadlock COM/WinRT.

---

## 2. Roadmap Pengembangan Style Background (Next Sessions)

### Tahap 1: Penambahan Preset Efek Visual Baru
1. **Winter Snowfall (Salju Melayang)**
   * Butiran salju halus dengan ukuran acak dan goyangan *sine-wave* lambat.
   * Sangat cocok untuk mode transparan pada lagu akustik, lo-fi, atau ballad.
2. **Gentle Rain & Mist (Hujan Rintik Halus)**
   * Garis-garis rintik tipis transparan diagonal dengan hembusan angin saat pergantian bait.
3. **Fireflies / Forest Embers (Kunang-Kunang Hutan)**
   * Partikel cahaya keemasan/hijau neon yang melayang perlahan dengan kedipan berdenyut alami.
4. **Fluid Lava / Color Blobs (Gelombang Warna Organik)**
   * Pendaran 2–3 bola cahaya lembut dinamis yang menyatu di belakang lirik (mirip iOS/macOS Dynamic Wallpapers).

---

### Tahap 2: Responsivitas Musik yang Lebih Dinamis
1. **Tempo-Aware Motion**:
   * Menghubungkan kecepatan aliran animasi dengan interval lirik (`state.remaining`):
     * Lagu bertempo cepat (rap/pop up-beat): Animasi bergerak lebih lincah dan responsif.
     * Lagu lambat/ballad: Partikel melayang sangat lambat dan menenangkan.
2. **Adaptive Color Harmony**:
   * Menyesuaikan palet warna partikel secara dinamis:
     * Mode Sakura (merah muda) / Autumn (oranye hangat) / Album-Sync (mengikuti `cinematic.albumColor`).

---

### Tahap 3: Opsi Kustomisasi Tambahan di Menu Style (`Shift+S`)
1. **Particle Density (Kerapatan Partikel)**:
   * Pilihan: *Minimalist (8 partikel)*, *Standard (16 partikel)*, *Lush (24 partikel)*.
2. **Flow Direction (Arah Aliran)**:
   * Pilihan arah angin: *Diagonal Down (Default)*, *Upward Float*, atau *Left-to-Right Drift*.

---

### Tahap 4: Modularitas Kode (Jika Efek Semakin Banyak)
* Jika varian efek bertambah di atas 5 jenis, pisahkan komponen efek ke file terpisah (misal `LeavesEffect.qml`, `AuroraEffect.qml`) dan pastikan jalur `build.bat` menyertakan seluruh aset QML terkait.
