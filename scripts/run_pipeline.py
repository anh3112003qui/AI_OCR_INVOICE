"""
Demo: chạy full pipeline từ ảnh hóa đơn → ghi vào Excel.

Cách chạy:
    python scripts/run_pipeline.py data/invoice.png
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Setup logging để thấy từng bước pipeline chạy
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s  %(levelname)-7s  %(message)s",
    datefmt="%H:%M:%S",
)

from invoice_ocr import build_pipeline

# Đường dẫn file Excel staging (chỉnh lại nếu cần)
WORKBOOK_PATH = Path("data/HE_THONG_KE_TOAN_TT99.xlsx")


def main(image_path: str) -> None:
    pipeline = build_pipeline(workbook_path=WORKBOOK_PATH)
    result = pipeline.run(image_path)

    print("\n" + "=" * 50)

    if not result.success:
        print(f"❌ Pipeline thất bại: {result.error}")
        sys.exit(1)

    print(f"✅ Pipeline hoàn tất: {result.image_path.name}")
    print(f"   Rows ghi vào sheet : {result.rows_written}")
    print(f"   Hóa đơn hợp lệ    : {result.validation.is_valid}")

    if result.validation.errors:
        print(f"   ⚠ Errors ({len(result.validation.errors)}):")
        for e in result.validation.errors:
            print(f"      - {e}")

    if result.validation.warnings:
        print(f"   ℹ Warnings ({len(result.validation.warnings)}):")
        for w in result.validation.warnings:
            print(f"      - {w}")

    invoice = result.validation.invoice
    print(f"\n   Ngày HĐ  : {invoice.ngay_hd}")
    print(f"   Số HĐ    : {invoice.so_hd}")
    print(f"   MST NCC  : {invoice.mst_ncc}")
    print(f"   Tên NCC  : {invoice.ten_ncc_raw}")
    print(f"   Line items:")
    for i, item in enumerate(invoice.line_items, 1):
        print(f"      {i}. {item.ten_vt_raw} | {item.dvt} | SL={item.so_luong} | Giá={item.don_gia} | Thuế={item.thue_suat_pct}%")

    print("=" * 50)
    print(f"\n📂 Mở file để kiểm tra:")
    print(f"   {WORKBOOK_PATH.resolve()}")
    print(f"   Sheet: 29a_AI_OCR_STAGING")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python scripts/run_pipeline.py <image_path>")
        print("Example: python scripts/run_pipeline.py data/invoice.png")
        sys.exit(1)

    main(sys.argv[1])