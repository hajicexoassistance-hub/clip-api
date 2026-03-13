# Portrait Generator API Guide

Panduan penggunaan API untuk membuat video portrait otomatis (Smart Crop + Active Speaker Detection).

## Workflow Utama

Proses pembuatan video dibagi menjadi dua tahap utama:
1.  **Stage 1 (Analisis)**: Download video, ekstrak audio, transkripsi AI, dan analisis topik viral.
2.  **Stage 2 (Clipping)**: Memotong video berdasarkan topik pilihan dan me-render hasil portrait (Smart Crop).

---

## Cek History via URL

Ingin tahu apakah suatu video sudah pernah diproses tanpa perlu menyimpan `job_id`? Gunakan endpoint ini.

-   **Endpoint**: `GET /job/by-url`
-   **Parameter**:
    -   `url`: URL YouTube video (Wajib)
-   **Response**: Mengembalikan data `JobResponse` yang sama seperti `/job/{id}`. Jika tidak ditemukan, statusnya adalah `not_found`.

---

## Contoh CURL & n8n

### 1. Memulai Download (Stage 1)
**CURL:**
```bash
curl -X GET "http://localhost:8000/download?url=https://www.youtube.com/watch?v=aqz-KE-bpKQ"
```
**n8n (HTTP Request Node):**
- **Method**: `GET`
- **URL**: `http://localhost:8000/download`
- **Query Parameters**: Add `url` with your YouTube link.

---

### 2. Cek Status Job
**CURL:**
```bash
curl -X GET "http://localhost:8000/job/JOB_ID_ANDA"
```
**n8n (HTTP Request Node):**
- **Method**: `GET`
- **URL**: `http://localhost:8000/job/{{ $node["HTTP Request"].json["job_id"] }}`

---

### 3. Ambil Daftar Topik (Potongan Viral)
Gunakan ini untuk melihat bagian video mana yang dianggap viral oleh AI sebelum membuat clip.

**CURL:**
```bash
curl -X GET "http://localhost:8000/analyze?job_id=JOB_ID_ANDA"
```
**n8n (HTTP Request Node):**
- **Method**: `GET`
- **URL**: `http://localhost:8000/analyze`
- **Query Parameters**: Add `job_id` with your ID.

---

### 4. Membuat Clip Portrait (Stage 2)
**CURL:**
```bash
curl -X POST "http://localhost:8000/clip" \
     -H "Content-Type: application/json" \
     -d '{
       "job_id": "JOB_ID_ANDA",
       "topics": [0]
     }'
```
**n8n (HTTP Request Node):**
- **Method**: `POST`
- **URL**: `http://localhost:8000/clip`
- **Send Body**: `true`
- **Body Parameters**:
    - `job_id`: (ID dari step 1)
    - `topics`: `[0]` (Array berisi index topik)

---

## Guide n8n Lengkap
Untuk membuat workflow otomatis di n8n:
1.  **Wait Node**: Karena proses rendering video membutuhkan waktu (CPU Xeon sangat cepat tapi transkripsi & burning subtitle tetap memakan waktu), gunakan node **Wait** (sekitar 30-60 detik) di antara step Status Check dan Download Hasil.
2.  **Loop/IF**: Gunakan node **IF** untuk mengecek properti `status`. Jika masih `processing`, putar balik (loop) ke node **Wait** sampai statusnya `completed`.
3.  **Download Hasil**: Setelah status `completed`, gunakan link di `result_url` untuk mendownload file final.

---

## Tips Tambahan
-   **Thread CPU**: Sistem sudah dioptimalkan menggunakan 16 thread Xeon Anda.
-   **Smart Crop**: Sistem secara otomatis mendeteksi orang dan mengikuti pembicara aktif (**Active Speaker Detection**) menggunakan analisis gerakan mulut.
-   **GPU**: Rendering dilakukan di CPU untuk stabilitas maksimal mengingat dukungan driver hardware.

---

## Clipping Progress Monitoring

Untuk memantau progress Stage 2 (Clipping), gunakan endpoint ini:

-   **Endpoint**: `GET /job/{job_id}/clip-status`
-   **Response**:
    ```json
    {
      "job_id": "...",
      "stage1_status": "completed",
      "total_topics": 5,
      "completed": 2,
      "failed": 0,
      "rendering": 3,
      "is_finished": false,
      "clips": [...] 
    }
    ```
-   **Logika n8n**:
    1. Loop polling ke `/job/{job_id}/clip-status`.
    2. Cek property `is_finished`. Jika `true`, lanjut ke step berikutnya.
    3. Untuk mengambil hanya yang berhasil, gunakan data dari field `clips` dan filter yang memiliki `status == "completed"`.

Aplikasi berjalan di: `http://localhost:8000`
