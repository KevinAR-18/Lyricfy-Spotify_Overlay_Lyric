# Panduan rilis dan pembaruan Lyricfy

Lyricfy mengecek GitHub Releases saat dibuka dan melalui menu tray **Check for Updates…**. Pengguna memilih apakah ingin mengunduh dan menjalankan installer. Ini **bukan instalasi senyap**: wizard InstallForge dan persetujuan UAC dapat muncul, dan pengguna harus menyelesaikannya. Opsi membuka Lyricfy kembali tersedia di akhir wizard jika dicentang.

## Persiapan satu kali — sebelum membangun v1.6.2

1. Instal dependensi: `.venv\Scripts\python.exe -m pip install -r requirements.txt`.
2. Buat kunci di luar repository, misalnya:

   ```powershell
   .venv\Scripts\python.exe tools\release_signing.py generate-key "$env:USERPROFILE\lyricfy-release-private.pem"
   ```

3. Salin nilai **public key** yang dicetak ke `PUBLIC_KEY_HEX` di `src/lyric_overlay/update_key.py`, lalu commit perubahan tersebut sebelum build. `build.bat` menolak build jika kunci belum diisi.
4. Simpan dan cadangkan file **private key** dengan aman. Jangan unggah ke GitHub, jangan masukkan ke installer atau bagikan. Kunci ini tidak dienkripsi oleh skrip; batasi akses file menggunakan izin Windows dan simpan cadangan di tempat aman. Jika hilang, instalasi yang sudah terbit tidak akan bisa memverifikasi kunci baru tanpa pembaruan manual; jika bocor, pihak lain dapat menandatangani pembaruan. Migrasi kunci memerlukan rencana khusus.

## Untuk setiap rilis stabil

1. Perbarui versi secara konsisten di `src/lyric_overlay/__init__.py`, `build.bat`, dan konfigurasi InstallForge (`instalforgeLyricfy.ifp`, termasuk nama output). Tag harus berupa `vMAJOR.MINOR.PATCH`, misalnya `v1.6.3`.
2. Commit kode yang akan dirilis, lalu jalankan `build.bat` dan buat installer melalui InstallForge. Untuk v1.6.2 **buat ulang** installer setelah kunci dan updater terpasang; installer lama tidak memiliki updater. Periksa nama file, misalnya `releases\Lyricfy Setup v1.6.3.exe`.
3. Tandatangani installer **final**:

   ```powershell
   .venv\Scripts\python.exe tools\release_signing.py sign "$env:USERPROFILE\lyricfy-release-private.pem" v1.6.3 "releases\Lyricfy Setup v1.6.3.exe"
   ```

   Skrip menghasilkan `releases\update-manifest.json` dan `releases\update-manifest.sig`. Manifest memakai nama aset GitHub dengan titik, misalnya `Lyricfy.Setup.v1.6.3.exe`, karena GitHub mengubah spasi pada nama file yang diunggah. Pastikan nama aset GitHub cocok persis dengan nama di manifest dan private key adalah pasangan public key yang disematkan di build pengguna. Jangan mengubah installer atau manifest setelah penandatanganan; jika berubah, jalankan skrip lagi.
4. Di [GitHub Releases](https://github.com/KevinAR-18/Lyricfy-Spotify_Overlay_Lyric/releases), pilih **Draft a new release**. Buat tag yang cocok dari commit yang dibangun; isi judul dan catatan rilis.
5. Unggah **ketiga** file sebagai release assets: installer, `update-manifest.json`, dan `update-manifest.sig`. File *Source code* otomatis GitHub bukan installer. Pastikan rilis bukan draft atau pre-release saat dipublikasikan. Endpoint `latest` hanya memilih rilis stabil publik; tag dan versi manifest harus cocok.
6. Verifikasi dari mesin uji: versi lama mendeteksi rilis, unduhan berhasil, installer memperbarui lokasi yang benar, data `%APPDATA%\Lyricfy` tetap ada dan aplikasi dapat dibuka lagi. Pastikan juga installer yang diunduh manual dapat berjalan.

Pengguna v1.6.1 dan sebelumnya harus memasang v1.6.2 secara manual sekali. Jika koneksi gagal atau tanda tangan/checksum tidak cocok, updater tidak menjalankan installer; pengguna bisa mengunjungi halaman Releases secara manual. Aset updater harus tersedia di repository publik karena aplikasi tidak menyimpan token GitHub.

## Pengujian sebelum publikasi

Jalankan `.venv\Scripts\python.exe -m pytest`. Uji juga secara manual pada Windows menggunakan salinan instalasi dan data uji: versi tidak berubah, versi lebih baru, offline, aset hilang/diubah, UAC ditolak, installer dibatalkan, folder instalasi khusus dan restart. Uji di repository GitHub uji yang terisolasi dengan build uji yang dikonfigurasi untuk repo itu, atau mock endpoint; jangan publikasikan rilis palsu sebagai latest produksi. Verifikasi khusus perilaku InstallForge saat upgrade dan izin UAC sebelum rilis: implementasi ini menjalankan wizard biasa dan tidak menjamin instalasi senyap, pemilihan folder sebelumnya, atau restart otomatis tanpa interaksi.
