import time
import logging
from contextlib import contextmanager

# Thiết lập logging định dạng chuyên nghiệp
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S"
)
logger = logging.getLogger("OCR-System")

@contextmanager
def timer(description: str):
    """
    Context manager để đo thời gian chạy của một khối lệnh.
    """
    start_time = time.perf_counter()
    logger.info(f"Bắt đầu: {description}...")
    yield
    elapsed = time.perf_counter() - start_time
    logger.info(f"Hoàn thành: {description} trong {elapsed:.4f} giây.")
