"""Script to generate realistic technical PDF documents for testing and evaluation."""

import io
from pathlib import Path
from PIL import Image, ImageDraw
import pymupdf


def generate_sample_documents(output_dir: str = "sample_docs"):
    out_path = Path(output_dir)
    out_path.mkdir(parents=True, exist_ok=True)

    # 1. Digital PDF: pump_maintenance_guide.pdf (4 pages)
    doc = pymupdf.open()

    # Page 1
    p1 = doc.new_page()
    text_p1 = (
        "QUY TRINH BAO TRI VA VAN HANH HE THONG MAY BOM CONG NGHIEP (TKE-PUMP)\n\n"
        "1. Tong quan ve ap suat dau ra cua may bom:\n"
        "Nhung nguyen nhan chinh khien ap suat dau ra cua may bom bi giam bao gom:\n"
        "- Ro ri van xa hoac van mot chieu bi ket can ban.\n"
        "- Canh bom bi mon co hoc sau thoi gian dai hoat dong.\n"
        "- Duong ong hut bi tac nghen do can ban hoac luoi loc dau vao bi bit kin.\n\n"
        "2. Bao tri dinh ky canh bom:\n"
        "Quy trinh kiem tra va bao tri dinh ky canh bom yeu cau kiem tra do mon co hoc, "
        "ve sinh can ban va siet chat bu long co dinh dinh ky 6 thang mot lan."
    )
    p1.insert_text((50, 70), text_p1, fontsize=11)

    # Page 2
    p2 = doc.new_page()
    text_p2 = (
        "THONG SO AP SUAT VA CHE DO BOI TRON HE THONG\n\n"
        "3. Ap suat van hanh tieu chuan:\n"
        "Ap suat van hanh tieu chuan cua he thong may bom la 6.5 bar den 8.0 bar.\n"
        "Trong qua trinh van hanh, can lien tuc theo doi dong ho do ap suat dau ra.\n\n"
        "4. Co che hoat dong cua van an toan:\n"
        "Van an toan tu dong kich hoat xa ap khi ap luc duong ong vuot qua nguong 10 bar "
        "de bao ve toan bo he thong duong ong va phong ngua no ap.\n\n"
        "5. Quy dinh boi tron o bi:\n"
        "Loai dau boi tron duoc khuyen nghi cho o bi la dau boi tron cong nghiep ISO VG 46, "
        "chu ky thay the la 3 thang hoac sau moi 1000 gio van hanh."
    )
    p2.insert_text((50, 70), text_p2, fontsize=11)

    # Page 3
    p3 = doc.new_page()
    text_p3 = (
        "GIOI HAN NHIET DO VA XU LY SU CO KHAN CAP\n\n"
        "6. Gioi han nhiet do hoat dong:\n"
        "Nhiet do toi da cho phep cua than bom trong qua trinh hoat dong lien tuc la 85 do C. "
        "Neu vuot qua nguong nay, he thong phai duoc giam tai ngay lap tuc.\n\n"
        "7. Kiem tra phot co khi:\n"
        "Dau hieu cho thay phot co khi cua may bom bi hong can thay the ngay la co hien tuong "
        "ro ri chat long tai truc bom vuot qua 5 giot/phut hoac co tieng keu bat thuong.\n\n"
        "8. Cac buoc xu ly khan cap khi qua nhiet:\n"
        "Cac buoc xu ly khan cap khi dong co may bom phat sinh hien tuong qua nhiet:\n"
        "- Ngat nguon dien ngay lap tuc de bao ve cuon day.\n"
        "- Dong van dau vao va kiem tra he thong lam mat cung tai dong co."
    )
    p3.insert_text((50, 70), text_p3, fontsize=11)

    # Page 4
    p4 = doc.new_page()
    text_p4 = (
        "THONG SO KY THUAT DIEN VA DONG CO\n\n"
        "9. Thong so dien danh dinh:\n"
        "Dien ap danh dinh 380V 3 pha, tan so 50Hz, cong suat danh dinh 11kW.\n\n"
        "10. Thong so dong dien toi da:\n"
        "Thong so dong dien dinh muc toi da cua dong co may bom la 22A.\n"
        "He thong tu dong ngat khi dong dien vuot qua 25A trong 5 giay lien tuc."
    )
    p4.insert_text((50, 70), text_p4, fontsize=11)

    digital_pdf_path = out_path / "pump_maintenance_guide.pdf"
    doc.save(str(digital_pdf_path))
    doc.close()

    # 2. Scanned / Image PDF: scanned_circuit_diagram.pdf (1 page)
    # Generate high-resolution image with text
    img = Image.new("RGB", (1200, 800), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)
    draw.text((60, 100), "SO DO MACH DIEN DIEU KHIEN MAY BOM TKE-380", fill=(0, 0, 0))
    draw.text(
        (60, 200),
        "CANH BAO AN TOAN: CANH BAO AP SUAT CAO VA NGUY HIEM DIEN AP 380V\n"
        "NGAT CAU DAO TRUOC KHI SUA CHUA HOAC BAO TRI MACH DIEN.",
        fill=(0, 0, 0)
    )
    draw.text(
        (60, 350),
        "THIET BI BAO VE QUA TAI:\n"
        "RO LE NHIET BAO VE MACH DIEN DIEU KHIEN DUOC CAI DAT O MUC 24A.",
        fill=(0, 0, 0)
    )

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    scanned_doc = pymupdf.open()
    scanned_page = scanned_doc.new_page(width=1200, height=800)
    scanned_page.insert_image(pymupdf.Rect(0, 0, 1200, 800), stream=img_bytes)
    scanned_pdf_path = out_path / "scanned_circuit_diagram.pdf"
    scanned_doc.save(str(scanned_pdf_path))
    scanned_doc.close()

    print(f"Generated: {digital_pdf_path}")
    print(f"Generated: {scanned_pdf_path}")


if __name__ == "__main__":
    generate_sample_documents()

