# Fieldroom IFC Weight Viewer

Viewer IFC berbasis browser untuk meninjau model struktur, memilih beberapa elemen, dan menghitung total berat pilihan.

## Fitur

- Membuka file `.ifc` dari komputer atau dengan drag and drop.
- Menampilkan geometri IFC dalam viewport 3D dengan orbit dan zoom.
- Memilih beberapa elemen lewat model atau daftar, lalu melihat berat total dalam kg.
- Mencari nama, GUID, atau mark; memfilter kategori IFC.
- Mengekspor daftar elemen terpilih ke CSV.
- Memprioritaskan kuantitas `NetWeight`; memakai properti `Weight` sebagai fallback.
- Menandai elemen tanpa data berat dan mengecualikannya dari penjumlahan.
- Menghindari hitung ganda ketika assembly dan elemen turunannya sama-sama dipilih.

## Menjalankan

Buka `index.html` di Chrome atau Microsoft Edge. Koneksi internet diperlukan saat aplikasi dimuat agar Three.js, web-ifc, dan WebAssembly parser dapat diambil dari CDN. File IFC dibaca dan diproses di browser; aplikasi tidak mengunggah model.

## Upload ke GitHub

1. Buat repository baru di GitHub.
2. Pilih **Private** atau **Public** sesuai kebutuhan.
3. Dari halaman repository, pilih **Add file → Upload files**.
4. Upload `index.html`, `README.md`, dan `.gitignore` dari folder aplikasi ini.
5. Pilih **Commit changes**.

Jangan unggah IFC proyek ke repository publik kecuali memang ingin membagikannya. `.gitignore` disertakan untuk mencegah file IFC dan CSV pilihan masuk ke Git secara tidak sengaja.

## Publikasikan sebagai situs dengan GitHub Pages

Setelah file diunggah, buka **Settings → Pages** pada repository. Di **Build and deployment**, pilih **Deploy from a branch**, pilih branch `main` dan folder `/ (root)`, lalu tekan **Save**. Setelah GitHub Pages selesai menerbitkan situs, buka alamat yang ditampilkan di bagian Pages. `index.html` akan menjadi halaman utama.

## Perhitungan berat

Berat dibaca dari data IFC yang terkait ke elemen. Nilai `NetWeight` diutamakan, lalu properti `Weight` atau kuantitas berat lain. Unit massa IFC dikonversi ke kilogram. Model tanpa berat elemen tidak diberi perkiraan dari geometri.

## Teknologi

- [web-ifc](https://github.com/ThatOpen/engine_web-ifc) untuk membaca IFC dan mengambil geometri.
- [Three.js](https://threejs.org/) untuk viewport 3D dan navigasi model.
