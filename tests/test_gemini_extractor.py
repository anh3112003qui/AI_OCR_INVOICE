from __future__ import annotations

from pathlib import Path

from invoice_ocr.config import GeminiSettings
from invoice_ocr.extractors import GeminiFieldExtractor
from invoice_ocr.models import OCRResult

# Reuse the same sample invoice used in provider smoke test
_INVOICE_RAW_TEXT = (
    Path(__file__).resolve().parent.parent / "data" / "invoice.png"
)


def test_gemini_extractor_extract_invoice() -> None:
    """Smoke test: verify GeminiFieldExtractor extracts structured fields from raw OCR text."""

    # Use the real raw_text from the previous OCR run
    ocr_result = OCRResult(
        provider_name="gemini",
        raw_text=(
            "HÓA ĐƠN GIÁ TRỊ GIA TĂNG\n"
            "Ngày 12 tháng 04 năm 2026\n"
            "Mẫu số: 01GKTKT0/001\n"
            "Ký hiệu: AA/26E\n"
            "Số:\n"
            "0000087\n"
            "Đơn vị bán hàng: CÔNG TY TNHH THƯƠNG MẠI VÀ DỊCH VỤ AN PHÁT\n"
            "Mã số thuế: 0 3 1 0 9 8 7 6 5 4\n"
            "Địa chỉ: 47 Đinh Tiên Hoàng, Phường Đa Kao, Quận 1, Thành phố Hồ Chí Minh\n"
            "Điện thoại: 028 3820 4455 Email: ketoan@anphatco.com.vn\n"
            "Số tài khoản: 0310987654001 Tài khoản TMCP Á Châu (ACB) - CN Quận 1\n"
            "Họ tên người mua: Nguyen Minh Khoa\n"
            "Tên đơn vị: CÔNG TY CỔ PHẦN SẢN XUẤT NHỰA ĐÔNG NAM\n"
            "Mã số thuế: 0204567891\n"
            "Địa chỉ: Lô B12, KCN Sóng Thần 2, Thị xã Dĩ An, Tỉnh Bình Dương\n"
            "Hình thức thanh toán : Chuyển khoản\n"
            "STT Tên hàng hóa, dịch vụ Đơn vị tính Số lượng Đơn giá Thành tiền\n"
            "1 Hạt nhựa PP copolymer (PP-C30S) Kg 3.500 38.000 133.000.000\n"
            "2 Hạt nhựa HDPE (HD5502XA) Kg 1.200 42.500 51.000.000\n"
            "3 Chất phụ gia chống UV (UV-328) Kg 80 185.000 14.800.000\n"
            "Cộng tiền hàng: 198.800.000\n"
            "Thuế suất GTGT: 8%\n"
            "Tiền thuế GTGT : 15.904.000\n"
            "Tổng cộng tiền thanh toán: 214.704.000\n"
        ),
    )

    settings = GeminiSettings()
    extractor = GeminiFieldExtractor(settings=settings)
    result = extractor.extract_invoice(ocr_result)

    print("\n--- InvoiceData ---")
    print(result.model_dump())

    # Header assertions
    assert result.so_hd == "0000087", f"Expected '0000087', got '{result.so_hd}'"
    assert result.ngay_hd is not None, "ngay_hd should not be null"
    assert str(result.ngay_hd) == "2026-04-12", f"Expected '2026-04-12', got '{result.ngay_hd}'"
    assert result.mst_ncc == "0310987654", f"Expected '0310987654', got '{result.mst_ncc}'"
    assert result.ten_ncc_raw is not None, "ten_ncc_raw should not be null"
    assert result.ma_ncc is None, "ma_ncc must always be null at extraction stage"

    # Line items assertions
    assert len(result.line_items) == 3, f"Expected 3 line items, got {len(result.line_items)}"

    item_1 = result.line_items[0]
    assert item_1.dvt == "Kg", f"Expected 'Kg', got '{item_1.dvt}'"
    assert item_1.so_luong == 3500, f"Expected 3500, got '{item_1.so_luong}'"
    assert item_1.thue_suat_pct == 8, f"Expected 8, got '{item_1.thue_suat_pct}'"
    assert item_1.ma_vt is None, "ma_vt must always be null at extraction stage"
    assert item_1.ma_thue is None, "ma_thue must always be null at extraction stage"


if __name__ == "__main__":
    test_gemini_extractor_extract_invoice()
    print("\nOK")