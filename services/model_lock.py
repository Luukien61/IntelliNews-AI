import threading

# A global lock to prevent concurrent initialization of Hugging Face models
# from multiple worker threads, which can cause PyTorch meta tensor errors.
global_model_load_lock = threading.Lock()
