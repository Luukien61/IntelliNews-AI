# CPU Core Limiting Implementation

## Vấn đề

Khi chạy AI service, bạn thấy ứng dụng sử dụng tất cả 8 cores CPU mặc dù đã set `AI_MAX_CORES=4`. Điều này xảy ra vì:

1. **ThreadPoolExecutor** chỉ giới hạn số lượng thread workers, không giới hạn số cores mà mỗi thread sử dụng
2. **PyTorch, NumPy, và các thư viện số học** mặc định sử dụng tất cả cores có sẵn thông qua:
   - OpenMP (multi-threading)
   - Intel MKL (Math Kernel Library)
   - OpenBLAS
   - Và các thư viện tối ưu khác

## Giải pháp

Để thực sự giới hạn CPU usage, chúng ta cần set environment variables TRƯỚC KHI import bất kỳ thư viện nào:

### 1. Module `services/cpu_limiter.py`

Module này được tạo ra để:
- Set environment variables cho tất cả các thư viện threading
- Phải được import ở đầu tiên trong application
- Tự động set limits khi được import

```python
# Environment variables được set:
OMP_NUM_THREADS          # OpenMP (used by NumPy, PyTorch)
MKL_NUM_THREADS          # Intel MKL
NUMEXPR_NUM_THREADS      # NumExpr
OPENBLAS_NUM_THREADS     # OpenBLAS
VECLIB_MAXIMUM_THREADS   # macOS Accelerate
```

### 2. Import Order trong `main.py`

**Rất quan trọng**: `cpu_limiter` phải được import ở dòng đầu tiên:

```python
# ĐÚNG ✅
import services.cpu_limiter  # Import đầu tiên
import torch  # Torch sẽ respect env vars đã set

# SAI ❌
import torch  # Torch đã được import trước
import services.cpu_limiter  # Quá muộn, torch đã init với tất cả cores
```

### 3. PyTorch Thread Limiting

Ngoài environment variables, PyTorch còn cần được set threads sau khi import:

```python
import torch
torch.set_num_threads(4)
torch.set_num_interop_threads(4)
```

Điều này được thực hiện trong `AIProcessorService.__init__()`.

## Architecture

### Thứ tự khởi tạo

```
1. main.py imports cpu_limiter
   └─> cpu_limiter sets environment variables
   
2. main.py imports other modules
   └─> torch, numpy, transformers respect env vars
   
3. AIProcessorService.__init__()
   └─> Sets PyTorch threads explicitly
   
4. Models are loaded
   └─> All operations respect CPU limits
```

### Flow Chart

```
Application Start
    │
    ├─> Import cpu_limiter
    │   └─> Set OMP_NUM_THREADS=4
    │   └─> Set MKL_NUM_THREADS=4
    │   └─> Set OPENBLAS_NUM_THREADS=4
    │   └─> etc.
    │
    ├─> Import torch, numpy
    │   └─> Libraries read env vars
    │   └─> Configure internal thread pools
    │
    ├─> Initialize AIProcessorService
    │   └─> Set torch.set_num_threads(4)
    │   └─> Set torch.set_num_interop_threads(4)
    │
    └─> Run AI operations
        └─> All operations limited to 4 cores
```

## Configuration

Trong file `.env`:

```bash
# Set số cores tối đa cho AI operations
AI_MAX_CORES=4

# Number of parallel workers (should be <= AI_MAX_CORES)
AI_PROCESS_MAX_WORKERS=4
```

## Testing

### 1. Kiểm tra Environment Variables

```bash
python test_cpu_limiting.py
```

Script này sẽ kiểm tra:
- ✅ Environment variables đã được set đúng
- ✅ PyTorch threads đã được cấu hình
- ✅ NumPy configuration
- ✅ CPU usage simulation (optional)

### 2. Kiểm tra CPU Usage trong Production

```bash
# Terminal 1: Start application
python main.py
# hoặc
uvicorn main:app --host 0.0.0.0 --port 8000

# Terminal 2: Monitor CPU usage
top -p $(pgrep -f "main:app")
# hoặc
htop -p $(pgrep -f "main:app")

# Terminal 3: Trigger AI processing
curl -X POST http://localhost:8000/api/summarization/...
```

### 3. Verify trong Logs

Khi application khởi động, bạn sẽ thấy:

```
2026-04-09 22:00:00 - services.cpu_limiter - INFO - CPU core limits set to 4: OMP_NUM_THREADS, MKL_NUM_THREADS, ...
2026-04-09 22:00:05 - services.ai_processor_service - INFO - PyTorch threads limited to 4
2026-04-09 22:00:05 - services.ai_processor_service - INFO - AIProcessorService initialized with max_workers=4 (ai_max_cores=4)
```

## Troubleshooting

### Problem: Vẫn thấy sử dụng full cores

**Kiểm tra:**

1. **Environment variables có được set không?**
   ```python
   import os
   print(os.environ.get("OMP_NUM_THREADS"))  # Should be "4"
   ```

2. **Torch threads có được set không?**
   ```python
   import torch
   print(torch.get_num_threads())  # Should be 4
   ```

3. **Import order có đúng không?**
   - `cpu_limiter` phải được import ở dòng đầu tiên trong `main.py`
   - Kiểm tra không có module nào import torch/numpy trước cpu_limiter

4. **Có process khác đang chạy không?**
   ```bash
   ps aux | grep python
   ```

### Problem: Performance giảm quá nhiều

**Giải pháp:**

1. **Tăng AI_MAX_CORES:**
   ```bash
   # Trong .env
   AI_MAX_CORES=6  # Thay vì 4
   ```

2. **Giảm AI_PROCESS_MAX_WORKERS:**
   ```bash
   # Nếu mỗi worker dùng nhiều cores, giảm số workers
   AI_PROCESS_MAX_WORKERS=2
   ```

3. **Balance giữa throughput và latency:**
   - Nhiều cores = Xử lý nhanh hơn mỗi task
   - Ít cores = Có thể xử lý nhiều tasks parallel hơn

## Technical Details

### Tại sao cần set cả env vars và torch.set_num_threads()?

1. **Environment variables:** 
   - Được đọc khi library được import/khởi tạo
   - Ảnh hưởng đến OpenMP, MKL, BLAS layer bên dưới
   - Không thể thay đổi sau khi library đã init

2. **torch.set_num_threads():**
   - PyTorch có thread pool riêng
   - Có thể thay đổi runtime
   - Override default behavior

Cả hai cần được set để đảm bảo toàn bộ stack respect CPU limits.

### Libraries bị ảnh hưởng

- ✅ **PyTorch:** Tất cả operations (matmul, conv, etc.)
- ✅ **NumPy:** BLAS operations (dot, matmul, svd, etc.)
- ✅ **Transformers:** Model inference (dùng PyTorch/NumPy)
- ✅ **SciPy:** Scientific computing operations
- ✅ **UMAP:** Dimensionality reduction (dùng NumPy)
- ✅ **HDBSCAN:** Clustering (dùng NumPy/SciPy)

## Monitoring Commands

```bash
# Real-time CPU usage per core
mpstat -P ALL 1

# Process CPU usage
top -H -p $(pgrep -f "main:app")

# Detailed per-thread info
ps -eLo pid,tid,class,rtprio,ni,pri,psr,pcpu,stat,wchan:14,comm | grep python

# Number of threads per process
ps -o nlwp $(pgrep -f "main:app")
```

## References

- [PyTorch Threading Documentation](https://pytorch.org/docs/stable/notes/cpu_threading_torchscript_inference.html)
- [NumPy Multithreading](https://numpy.org/doc/stable/reference/c-api/config.html)
- [OpenMP Environment Variables](https://www.openmp.org/spec-html/5.0/openmpse50.html)

