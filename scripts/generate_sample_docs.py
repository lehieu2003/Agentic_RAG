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
    # Generate realistic technical electrical schematic drawing on image canvas
    width, height = 1400, 950
    img = Image.new("RGB", (width, height), color=(255, 255, 255))
    draw = ImageDraw.Draw(img)

    # Khung ban ve ky thuat tieu chuan (Border & Grid)
    draw.rectangle([(20, 20), (width - 20, height - 20)], outline=(0, 0, 0), width=3)
    draw.rectangle([(26, 26), (width - 26, height - 26)], outline=(0, 0, 0), width=1)

    # Grid references around border
    for i, x in enumerate(range(100, width - 100, 200)):
        if i < 6:
            draw.text((x, 8), str(i + 1), fill=(0, 0, 0))
            draw.text((x, height - 18), str(i + 1), fill=(0, 0, 0))
    for i, y in enumerate(range(120, height - 120, 180)):
        if i < 4:
            ch = chr(ord('A') + i)
            draw.text((8, y), ch, fill=(0, 0, 0))
            draw.text((width - 16, y), ch, fill=(0, 0, 0))

    # Tieu de ban ve tren cung
    draw.text((50, 40), "SO DO NGUYEN LY MACH DIEN DONG LUC VA DIEU KHIEN MAY BOM TKE-380", fill=(0, 0, 0))
    draw.line([(50, 60), (950, 60)], fill=(0, 0, 0), width=1)

    # ==============================================================
    # COT 1: MACH DONG LUC 3 PHA (380V / 50HZ)
    # ==============================================================
    draw.text((50, 75), "I. MACH DONG LUC (380V AC / 3 PHA - 50HZ)", fill=(0, 0, 0))
    # Thanh cai nguon L1, L2, L3, PE
    draw.line([(100, 105), (380, 105)], fill=(0, 0, 0), width=2)
    draw.line([(100, 125), (380, 125)], fill=(0, 0, 0), width=2)
    draw.line([(100, 145), (380, 145)], fill=(0, 0, 0), width=2)
    draw.line([(100, 165), (380, 165)], fill=(0, 0, 0), width=1)
    draw.text((65, 98), "L1", fill=(0, 0, 0))
    draw.text((65, 118), "L2", fill=(0, 0, 0))
    draw.text((65, 138), "L3", fill=(0, 0, 0))
    draw.text((65, 158), "PE", fill=(0, 0, 0))

    # Drop lines from L1, L2, L3
    x_phases = [170, 220, 270]
    y_phases = [105, 125, 145]
    for xp, yp in zip(x_phases, y_phases):
        draw.ellipse([(xp - 3, yp - 3), (xp + 3, yp + 3)], fill=(0, 0, 0))
        draw.line([(xp, yp), (xp, 200)], fill=(0, 0, 0), width=2)

    # MCCB Q1 (Aptomat khoi dong)
    draw.rectangle([(140, 200), (300, 260)], outline=(0, 0, 0), width=2)
    draw.text((160, 215), "MCCB Q1 (40A)", fill=(0, 0, 0))
    draw.text((155, 235), "Cat mach tong 3P", fill=(0, 0, 0))
    for xp in x_phases:
        draw.line([(xp, 260), (xp, 310)], fill=(0, 0, 0), width=2)

    # Contactor KM1
    draw.rectangle([(140, 310), (300, 370)], outline=(0, 0, 0), width=2)
    draw.text((155, 325), "CONTACTOR KM1", fill=(0, 0, 0))
    draw.text((165, 345), "3P - 32A / 380V", fill=(0, 0, 0))
    for xp in x_phases:
        draw.line([(xp, 370), (xp, 420)], fill=(0, 0, 0), width=2)

    # Ro le nhiet FR1
    draw.rectangle([(130, 420), (310, 490)], outline=(0, 0, 0), width=2)
    draw.text((155, 435), "RO LE NHIET FR1", fill=(0, 0, 0))
    draw.text((140, 455), "Bao ve qua tai dong co", fill=(0, 0, 0))
    draw.text((140, 470), "CAI DAT O MUC 24A", fill=(0, 0, 0))
    for xp in x_phases:
        draw.line([(xp, 490), (xp, 540)], fill=(0, 0, 0), width=2)

    # Dong co may bom M 3~
    mot_x, mot_y = 220, 600
    draw.ellipse([(mot_x - 55, mot_y - 55), (mot_x + 55, mot_y + 55)], outline=(0, 0, 0), width=3)
    draw.text((mot_x - 12, mot_y - 25), "M", fill=(0, 0, 0))
    draw.text((mot_x - 12, mot_y), "3~", fill=(0, 0, 0))
    draw.text((130, 670), "DONG CO MAY BOM TKE-380", fill=(0, 0, 0))
    draw.text((140, 690), "P = 11kW, U = 380V, In = 22A", fill=(0, 0, 0))

    # Day tiep dia PE xuong dong co
    draw.line([(350, 165), (350, mot_y), (mot_x + 55, mot_y)], fill=(0, 0, 0), width=1)
    draw.text((mot_x + 65, mot_y - 8), "Tiep dia PE", fill=(0, 0, 0))

    # ==============================================================
    # COT 2: MACH DIEU KHIEN (220V AC)
    # ==============================================================
    draw.text((450, 75), "II. MACH DIEU KHIEN (220V AC)", fill=(0, 0, 0))

    # Thanh nguon dieu khien
    draw.line([(450, 105), (450, 750)], fill=(0, 0, 0), width=2)  # Day pha L
    draw.line([(620, 105), (620, 750)], fill=(0, 0, 0), width=2)  # Day trung tinh N
    draw.text((435, 95), "L", fill=(0, 0, 0))
    draw.text((625, 95), "N", fill=(0, 0, 0))

    # Cau chi bao ve FU1
    draw.rectangle([(440, 140), (460, 190)], outline=(0, 0, 0), width=2)
    draw.text((470, 160), "FU1 (4A)", fill=(0, 0, 0))

    # Tiep diem thuong dong Ro le nhiet 95-96
    draw.line([(450, 220), (520, 220)], fill=(0, 0, 0), width=2)
    draw.rectangle([(520, 205), (590, 235)], outline=(0, 0, 0), width=1)
    draw.text((525, 215), "FR1 (95-96)", fill=(0, 0, 0))
    draw.line([(590, 220), (590, 260)], fill=(0, 0, 0), width=2)

    # Nut nhan dung STOP SB1 (NC)
    draw.rectangle([(565, 260), (615, 300)], outline=(0, 0, 0), width=2)
    draw.text((545, 305), "SB1 (STOP NC)", fill=(0, 0, 0))
    draw.line([(590, 300), (590, 350)], fill=(0, 0, 0), width=2)

    # Nhanh START SB2 va tiep diem duy tri KM1 (13-14)
    draw.line([(590, 350), (540, 350), (540, 380)], fill=(0, 0, 0), width=2)
    draw.line([(590, 350), (640, 350), (640, 380)], fill=(0, 0, 0), width=2)

    draw.rectangle([(515, 380), (565, 420)], outline=(0, 0, 0), width=2)
    draw.text((495, 425), "SB2 (START)", fill=(0, 0, 0))

    draw.rectangle([(615, 380), (665, 420)], outline=(0, 0, 0), width=1)
    draw.text((605, 425), "KM1 (13-14)", fill=(0, 0, 0))

    draw.line([(540, 420), (540, 460), (590, 460)], fill=(0, 0, 0), width=2)
    draw.line([(640, 420), (640, 460), (590, 460)], fill=(0, 0, 0), width=2)
    draw.line([(590, 460), (590, 500)], fill=(0, 0, 0), width=2)

    # Cuon hut Contactor KM1 (A1-A2)
    draw.rectangle([(560, 500), (620, 550)], outline=(0, 0, 0), width=2)
    draw.text((565, 515), "CUON KM1", fill=(0, 0, 0))
    draw.text((570, 532), "(A1 - A2)", fill=(0, 0, 0))
    draw.line([(590, 550), (590, 580), (620, 580)], fill=(0, 0, 0), width=2)

    # Den bao trang thai RUN & TRIP
    draw.ellipse([(575, 630), (605, 660)], outline=(0, 0, 0), width=2)
    draw.text((550, 665), "DEN BAO RUN", fill=(0, 0, 0))

    draw.ellipse([(575, 710), (605, 740)], outline=(0, 0, 0), width=2)
    draw.text((550, 745), "DEN BAO TRIP", fill=(0, 0, 0))

    # ==============================================================
    # COT 3: BANG CANH BAO AN TOAN VA GHI CHU KY THUAT
    # ==============================================================
    draw.rectangle([(710, 75), (width - 40, 400)], outline=(0, 0, 0), width=2)
    draw.rectangle([(715, 80), (width - 45, 115)], outline=(0, 0, 0), width=1)
    draw.text((730, 90), "CANH BAO AN TOAN VA QUY DINH BAO TRI:", fill=(0, 0, 0))

    draw.text((730, 130), "CANH BAO AN TOAN: CANH BAO AP SUAT CAO VA NGUY HIEM DIEN AP 380V", fill=(0, 0, 0))
    draw.text((730, 155), "NGAT CAU DAO TRUOC KHI SUA CHUA HOAC BAO TRI MACH DIEN.", fill=(0, 0, 0))

    draw.text((730, 195), "THIET BI BAO VE QUA TAI:", fill=(0, 0, 0))
    draw.text((730, 220), "RO LE NHIET BAO VE MACH DIEN DIEU KHIEN DUOC CAI DAT O MUC 24A.", fill=(0, 0, 0))

    draw.text((730, 260), "GHI CHU VAN HANH AN TOAN:", fill=(0, 0, 0))
    draw.text((730, 285), "- Chi nhan vien ky thuat co chung chi moi duoc mo tu dien.", fill=(0, 0, 0))
    draw.text((730, 310), "- Kiem tra dien ap bang dong ho VOM truoc khi thao tac tiep xuc.", fill=(0, 0, 0))
    draw.text((730, 335), "- AP SUAT HE THONG CANH BAO KHI VUOT QUA 10 BAR.", fill=(0, 0, 0))
    draw.text((730, 360), "- Kiem tra dien tro tiep dia PE phai nho hon hoac bang 4 Ohm.", fill=(0, 0, 0))

    # Bang thong so ky thuat
    draw.rectangle([(710, 420), (width - 40, 650)], outline=(0, 0, 0), width=1)
    draw.text((730, 435), "BANG THONG SO KY THUAT THIET BI:", fill=(0, 0, 0))
    draw.text((730, 465), "1. Nguon cap: 380V AC 3 Pha 50Hz, He thong tiep dia TN-S.", fill=(0, 0, 0))
    draw.text((730, 495), "2. Dong co may bom: 11kW, Dong dinh muc In = 22A, Cos phi = 0.85.", fill=(0, 0, 0))
    draw.text((730, 525), "3. Khoi dong tu Contactor: KM1 tieu chuan AC-3 dong cat 32A.", fill=(0, 0, 0))
    draw.text((730, 555), "4. Ro le nhiet FR1: Dai cai dat 18A - 26A, dat chuan bao ve tai 24A.", fill=(0, 0, 0))
    draw.text((730, 585), "5. Dien ap mach dieu khien: 220V AC trich qua cau chi FU1 4A.", fill=(0, 0, 0))
    draw.text((730, 615), "6. Cap bao ve tu dien cong nghiep: IP54 chong bui va nuoc ban.", fill=(0, 0, 0))

    # ==============================================================
    # KHUNG TEN BAN VE (TITLE BLOCK) GOC DUOI BEN PHAI
    # ==============================================================
    tb_x1, tb_y1 = 710, 670
    tb_x2, tb_y2 = width - 40, height - 35
    draw.rectangle([(tb_x1, tb_y1), (tb_x2, tb_y2)], outline=(0, 0, 0), width=2)
    draw.line([(tb_x1, tb_y1 + 45), (tb_x2, tb_y1 + 45)], fill=(0, 0, 0), width=1)
    draw.line([(tb_x1, tb_y1 + 90), (tb_x2, tb_y1 + 90)], fill=(0, 0, 0), width=1)
    draw.line([(tb_x1 + 350, tb_y1 + 45), (tb_x1 + 350, tb_y2)], fill=(0, 0, 0), width=1)

    draw.text((tb_x1 + 20, tb_y1 + 15), "TKE INDUSTRIAL AUTOMATION & ENGINEERING SYSTEMS", fill=(0, 0, 0))
    draw.text((tb_x1 + 20, tb_y1 + 55), "SO DO MACH DIEN DIEU KHIEN MAY BOM TKE-380", fill=(0, 0, 0))
    draw.text((tb_x1 + 20, tb_y1 + 72), "HE THONG CUNG CAP NUOC AP LUC CAO - CONG SUAT 11KW", fill=(0, 0, 0))

    draw.text((tb_x1 + 20, tb_y1 + 105), "MA BAN VE: DWG-TKE-2026-E01", fill=(0, 0, 0))
    draw.text((tb_x1 + 20, tb_y1 + 125), "NGUOI VE: KS. NGUYEN VAN AN", fill=(0, 0, 0))
    draw.text((tb_x1 + 370, tb_y1 + 105), "TY LE: NTS   |   REV: 02", fill=(0, 0, 0))
    draw.text((tb_x1 + 370, tb_y1 + 125), "NGAY DUYET: 15/10/2026", fill=(0, 0, 0))

    img_buf = io.BytesIO()
    img.save(img_buf, format="PNG")
    img_bytes = img_buf.getvalue()

    scanned_doc = pymupdf.open()
    scanned_page = scanned_doc.new_page(width=width, height=height)
    scanned_page.insert_image(pymupdf.Rect(0, 0, width, height), stream=img_bytes)
    scanned_pdf_path = out_path / "scanned_circuit_diagram.pdf"
    scanned_doc.save(str(scanned_pdf_path))
    scanned_doc.close()

    print(f"Generated: {digital_pdf_path}")
    print(f"Generated: {scanned_pdf_path}")


if __name__ == "__main__":
    generate_sample_documents()

