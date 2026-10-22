"""Rebuild the 3-page A4 PDF and editable HTML from the measured results.

Optional authoring dependency: reportlab. Benchmark itself needs no packages.
Run from this folder: python build_report.py
"""
import html
import json
import os
from pathlib import Path
from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER
from reportlab.lib.styles import ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas
from reportlab.platypus import Paragraph

ROOT = Path(__file__).resolve().parent
OUT = ROOT.parent
W, H = 595.276, 841.89
M, CW, GAP = 27, W-54, 11
HALF = (CW-GAP)/2
PINK, LIME, DARK, PAPER, MAGENTA = '#e99ab0', '#c3df7a', '#321d26', '#f4eef2', '#a62968'
ROWS = json.loads((ROOT/'results/benchmark.json').read_text(encoding='utf-8'))['rows']
INDEX = {(r['test_id'],r['algorithm']):r for r in ROWS}


def font_setup():
    candidates = [Path(os.environ.get('WINDIR','C:/Windows'))/'Fonts', Path('/usr/share/fonts/truetype/dejavu')]
    for folder in candidates:
        if (folder/'arial.ttf').exists():
            regular,bold,italic = folder/'arial.ttf',folder/'arialbd.ttf',folder/'ariali.ttf'
            break
        if (folder/'DejaVuSans.ttf').exists():
            regular,bold,italic = folder/'DejaVuSans.ttf',folder/'DejaVuSans-Bold.ttf',folder/'DejaVuSans-Oblique.ttf'
            break
    else:
        raise RuntimeError('Install Arial or DejaVu Sans to render Vietnamese')
    for name,path in [('Arial',regular),('ArialB',bold),('ArialI',italic)]:
        pdfmetrics.registerFont(TTFont(name,str(path)))
    pdfmetrics.registerFontFamily('Arial',normal='Arial',bold='ArialB',italic='ArialI',boldItalic='ArialB')


def num(value, places=2):
    if value == 'inf': return '∞'
    return f'{value:,.{places}f}'.replace(',','~').replace('.',',').replace('~','.')


def r(tid,alg):
    row = INDEX[(tid,alg)]
    assert row['status']=='PASS'
    return row


class Page:
    def __init__(self,c):
        self.c, self.el = c, []
        c.setFillColor(colors.toColor(PAPER)); c.rect(0,0,W,H,stroke=0,fill=1)
    def rect(self,x,t,w,h,fill='white',stroke=None,radius=12):
        c=self.c; c.setFillColor(colors.toColor(fill))
        c.setStrokeColor(colors.toColor(stroke or fill)); c.setLineWidth(1)
        c.roundRect(x,H-t-h,w,h,radius,fill=1,stroke=bool(stroke))
        self.el.append(f'<div class="shape" style="left:{x}pt;top:{t}pt;width:{w}pt;height:{h}pt;background:{fill};border:1pt solid {stroke or fill};border-radius:{radius}pt"></div>')
    def text(self,x,t,w,text,size=10,leading=None,bold=False,color=DARK,max_h=None,align=0):
        style=ParagraphStyle('p',fontName='ArialB' if bold else 'Arial',fontSize=size,leading=leading or size*1.3,
                             textColor=colors.toColor(color),alignment=align,spaceAfter=0)
        p=Paragraph(text,style); _,h=p.wrap(w,800)
        if max_h is not None and h>max_h+.1:
            raise ValueError(f'Text overflow {h:.1f}>{max_h} at y={t}: {text[:90]}')
        if t+h>H-7:
            raise ValueError('Page overflow')
        p.drawOn(self.c,x,H-t-h)
        self.el.append(f'<div contenteditable="true" class="txt" style="left:{x}pt;top:{t}pt;width:{w}pt;font-size:{size}pt;line-height:{leading or size*1.3}pt;color:{color};font-weight:{700 if bold else 400};text-align:{"center" if align==1 else "left"}">{text}</div>')
        return h
    def card(self,x,t,w,h,title,body,fill='white',stroke=None,size=10):
        self.rect(x,t,w,h,fill,stroke)
        self.text(x+13,t+11,w-26,title,14,17,True,max_h=36)
        self.text(x+13,t+38,w-26,body,size,size*1.3,max_h=h-46)
    def header(self,title,subtitle,page,pending=False):
        self.rect(M,22,CW,71,PINK)
        self.text(M+16,32,350,'PHÂN TÍCH NÂNG CẤP THUẬT TOÁN TÌM ĐƯỜNG',7.6,10,True)
        self.text(M+16,48,310,title,28,34,True)
        self.text(W-M-208,45,191,subtitle,9.8,12.7,align=0,max_h=43)
        self.text(M,818,CW,f'Đức tổng hợp • 18/10/2026 • {page}/3' + (' • CHỜ BÀI NỘP' if pending else ''),7,9,color='#6b5963')
    def steps(self,items,t=310):
        sw=(CW-2*GAP)/3
        for i,(title,body) in enumerate(items):
            self.rect(M+i*(sw+GAP),t,sw,57,'white' if i<2 else '#d4678d')
            self.text(M+i*(sw+GAP)+10,t+9,sw-20,title,10.4,13,True,color=MAGENTA if i<2 else 'white')
            self.text(M+i*(sw+GAP)+10,t+26,sw-20,body,9,11.3,color=DARK if i<2 else 'white',max_h=27)
    def table(self,t,items,row_h=18.2,pending=False):
        widths=[90,67,57,65,86,99,77.276] if pending else [116,67,79,91,109,79.276]
        assert abs(sum(widths)-CW)<1
        headers=['Phase','Solver','Status','Cost','Expanded','Time (ms)','Peak (KB)'] if pending else ['Đầu vào','Solver','Cost','Expanded','Time (ms)','Peak (KB)']
        hh=23; total=hh+len(items)*row_h
        self.rect(M,t,CW,total,'white',radius=8)
        self.rect(M,t,CW,hh,DARK,radius=0)
        x=M
        for value,ww in zip(headers,widths):
            self.text(x+5,t+7,ww-10,value,8.5,10,True,color='white'); x+=ww
        for i,(label,row) in enumerate(items):
            top=t+hh+i*row_h
            if i%2==1:
                self.rect(M,top,CW,row_h,'#f8f3f6',radius=0)
            if row is None:
                vals=[*label,'CHỜ','—','—','—','—'] if pending else [label,'CHỜ','—','—','—','—']
            else:
                vals=[label,row['algorithm'].replace('A* (ref)','A* ref'),num(row['cost']),num(row['expanded'],0),num(row['time_ms'],3),num(row['memory_kb'],2)]
            x=M
            for j,(value,ww) in enumerate(zip(vals,widths)):
                self.text(x+5,top+4,ww-10,html.escape(str(value)),8.3,10.3,bold=(j==1 and row is not None and row['algorithm'] in ('IDA*','Bi-UCS')));x+=ww
        # HTML table replaces the PDF-only cell texts/shapes for accurate grouping.
        # Text copies are retained as individually editable positioned fields.
    def footer_source(self,text):
        self.text(M,802,CW,text,6.7,7.8,color='#6b5963',max_h=16)


def page_one(c):
    p=Page(c)
    p.header('DFS → IDA*','Tìm đường có chi phí tối ưu bằng ngưỡng f, chấp nhận tìm lại qua nhiều vòng.',1)
    p.card(M,104,HALF,170,'DFS nền tảng',
           'Đi sâu bằng <b>stack LIFO</b>; gặp đích thì dừng. Tập explored tránh xử lý lại trạng thái đã xét.<br/><br/>'
           '<b>Hạn chế</b> Không xét ưu tiên chi phí nên không đảm bảo đường rẻ nhất. Bản tích hợp bỏ cạnh cost = ∞ để không đi qua đường cấm.<br/><br/>'
           '<b>Trên Romania ngập</b> 9 node, cost 1.335,80; gấp 2,03 lần tối ưu.',stroke=PINK,size=9.9)
    p.card(M+HALF+GAP,104,HALF,170,'IDA* theo ngưỡng f',
           'Lặp DFS với <b>f = g + h</b>. Cắt nhánh có f vượt ngưỡng; vòng sau dùng f nhỏ nhất vừa bị cắt.<br/><br/>'
           'Chỉ giữ path hiện tại và on_path để tránh cycle; <b>không dùng visited toàn cục</b>. h Euclid được kiểm tra tính nhất quán trên cạnh.<br/><br/>'
           '<b>Điều kiện</b> Chi phí không âm, h admissible; node được đếm lại qua mỗi vòng.',fill=LIME,size=9.9)
    p.text(M,284,CW,'Quá trình nâng cấp',14,18,True)
    p.steps([('DFS','Một lượt đi sâu theo thứ tự láng giềng.'),('+ Heuristic và ngưỡng','f = g + h; tăng ngưỡng thay vì giữ OPEN lớn.'),('+ Chi phí ngập','c = d·(1 + α·q/Cv); q: độ ngập.<br/>q ≥ Cv: c = ∞.')])
    p.rect(M,378,CW,35,LIME)
    p.text(M+11,386,CW-22,'<b>Đường tối ưu</b> Arad → Sibiu → Rimnicu → Pitesti → Bucharest<br/>Cost 657,85; 11 vòng; 63 expanded; path tối đa 5 node, gồm đích.',9.5,12,max_h=27)
    p.text(M,425,CW,'Kết quả đo lại bằng wrapper chung',14,18,True)
    p.text(M,448,CW,'Romania: seed 42, Cv = 60, α = 2, 7 lần đo. Lưới 8×8 ngập thập phân: 1 lần đo (*). A* ref là tham chiếu.',8.2,10.4,max_h=23)
    items=[]
    for tid,label in [('common_romania_flood42','Romania ngập'),('dfs__worst_grid8x8_continuous_flood','Lưới 8×8 (*)')]:
        for a in ['DFS','IDA*','A* (ref)']:items.append((label,r(tid,a)))
    p.table(477,items)
    a=r('common_corridor100','IDA*'); ast=r('common_corridor100','A* (ref)')
    dry=r('dfs__stress_grid10x10_dry_flood','IDA*'); drya=r('dfs__stress_grid10x10_dry_flood','A* (ref)')
    p.card(M,624,HALF,132,'Best case và giới hạn RAM',
           f'Hành lang thẳng có 100 node chính và 100 nhánh cụt: h chính xác trên trục chính. IDA* chỉ cần <b>1 vòng, 100 expanded</b>.<br/><br/>'
           f'Ít vòng chưa đảm bảo ít RAM: IDA* {num(a["memory_kb"])} KB so với A* {num(ast["memory_kb"])} KB. Lưới khô 10×10 (*) giảm RAM khoảng {num(100*(1-dry["memory_kb"]/drya["memory_kb"]),0)}%.',size=9.4,stroke=PINK)
    worst=r('dfs__worst_grid8x8_continuous_flood','IDA*')
    p.card(M+HALF+GAP,624,HALF,132,'Worst case có nhiều ngưỡng',
           f'Lưới có cycle, h Euclid thấp hơn chi phí đi đường và nhiều f gần nhau. IDA* phải tìm lại: <b>2.168 vòng, 2.417.004 expanded</b>.<br/><br/>'
           f'Lần đo có tracemalloc mất {num(worst["time_ms"]/1000,1)} giây. Bộ nhớ tìm kiếm theo độ sâu khi b cố định; graph đầu vào vẫn được lưu riêng.',fill=LIME,size=9.4)
    p.rect(M,767,CW,29,'#d4678d')
    p.text(M+11,774,CW-22,'IDA* cải thiện chất lượng lời giải so với DFS; lợi ích RAM và chi phí CPU phụ thuộc đầu vào.',9.6,12,True,max_h=15)
    p.footer_source('Time và peak Python đo cùng lượt; median. KB = bytes/1024, không phải tổng RAM. (*) Một mẫu. Nguồn: dữ liệu chạy lại; Korf 1985 và Vempaty et al. 1991.')
    return p


def page_two(c):
    p=Page(c)
    p.header('UCS → Bi-UCS','Hai phía thu hẹp vùng tìm kiếm; chi phí dựng graph đảo và quản lý state vẫn phải tính.',2)
    p.card(M,104,HALF,170,'UCS nền tảng',
           'Dùng min-heap theo <b>g</b>, từ start đến goal. Lưu best cost và parent; bỏ entry cũ. Với cost không âm, goal được lấy ra có chi phí tối ưu.<br/><br/>'
           '<b>Romania khô</b> Cost 418, 13 expanded. Hòa chi phí dùng thứ tự FIFO.<br/><br/>'
           '<b>Giới hạn</b> Có thể mở rộng một vùng lớn trước khi chạm đích.',stroke=PINK,size=9.9)
    p.card(M+HALF+GAP,104,HALF,170,'Bi-UCS hai hướng',
           'Chạy từ start trên graph gốc và từ goal trên <b>graph đảo</b>. Mỗi phía có heap, g và parent; cập nhật μ là đường tốt nhất đã nối được.<br/><br/>'
           '<b>Dừng an toàn</b> min(gF) + min(gB) ≥ μ sau khi bỏ entry cũ; không dừng ở lần chạm đầu.<br/><br/>'
           '<b>Expanded</b> Tổng forward và backward. Cạnh cost = ∞ bị bỏ qua.',fill=LIME,size=9.9)
    p.text(M,284,CW,'Quá trình nâng cấp',14,18,True)
    p.steps([('Một UCS từ start','Một làn sóng theo chi phí g tăng dần.'),('+ UCS từ goal','Đảo hướng cạnh, giữ nguyên trọng số.'),('+ Cận dừng μ','Ghép parent hai phía và trả đường tối ưu.')])
    p.rect(M,378,CW,35,LIME)
    p.text(M+11,386,CW-22,'<b>Cùng đường tối ưu cost 418</b> Romania khô: UCS 13 expanded; Bi-UCS 10 = 5 + 5.<br/>Bản đo bao gồm dựng graph đảo trong solve; giảm node không đảm bảo giảm thời gian.',9.5,12,max_h=27)
    p.text(M,425,CW,'Kết quả đo lại trên các cấu trúc khác nhau',14,18,True)
    p.text(M,448,CW,'7 lần/test thông thường; đồ thị random 20.000 node dùng 1 lần (*). Cùng input, cost và chính sách đo trong mỗi cặp.',8.2,10.4,max_h=23)
    items=[]
    for tid,label in [('common_romania_dry','Romania khô'),('ucs__best_01','Lưới mở 31×31'),('ucs__stress_02','Random 20k (*)'),('ucs__worst_02','Hub có hướng')]:
        for a in ['UCS','Bi-UCS']:items.append((label,r(tid,a)))
    p.table(477,items,row_h=17.8)
    u,b=r('ucs__stress_02','UCS'),r('ucs__stress_02','Bi-UCS')
    p.card(M,650,HALF,108,'Best case có phân nhánh',
           f'Random 20k: <b>8.262 → 220 expanded</b>, giảm {num(100*(1-b["expanded"]/u["expanded"]),1)}%; time còn {num(b["time_ms"]/u["time_ms"],2)} lần UCS (*).<br/><br/>'
           'Lưới mở cũng giảm node, nhưng tốn thêm time và RAM cho graph đảo và hai phía.',size=9.25,stroke=PINK)
    p.card(M+HALF+GAP,650,HALF,108,'Worst case lệch hai phía',
           'Hub có 3.000 cạnh đi vào: tìm ngược phình lớn, <b>3.051 so với 52 expanded</b>.<br/><br/>'
           'Chuỗi 2.000 node hầu như không lợi: 1.999 so với 2.000 expanded; thêm bookkeeping.',fill=LIME,size=9.25)
    p.rect(M,767,CW,29,'#d4678d')
    p.text(M+11,774,CW-22,'Bi-UCS có lợi khi hai phía cùng phân nhánh; cần cân cả node, thời gian và bộ nhớ.',9.6,12,True,max_h=15)
    p.footer_source('Time/peak đo cùng lượt, có tracemalloc; graph đầu vào dựng sẵn. (*) Một mẫu. Nguồn: dữ liệu chạy lại; Goldberg et al., tài liệu Princeton về bidirectional Dijkstra.')
    return p


def page_three(c):
    dynamic=json.loads((ROOT/'results/dynamic.json').read_text(encoding='utf-8'))
    phases={(row['test_id'],row['algorithm'],row['phase']):row for row in dynamic['rows']}
    total={(row['test_id'],row['algorithm'],row['scope']):row for row in dynamic['totals']}
    p=Page(c)
    p.header('A* → D* Lite','Tái sử dụng g, rhs và hàng đợi để sửa đường khi chi phí ngập hoặc start thay đổi.',3)
    p.card(M,104,HALF,170,'A* chạy lại từ đầu',
           'Min-heap theo <b>f = g + h</b>; bỏ entry cũ. Khi bản đồ hoặc start thay đổi, chạy A* mới trên snapshot mới.<br/><br/>'
           '<b>Baseline thật</b> Dùng solve_astar trong bài nộp Phương Anh; A* ref của nhóm DFS chỉ dùng đối chiếu.<br/><br/>'
           '<b>Cùng điều kiện</b> Graph, cost ngập và heuristic Euclid được kiểm tra ở mọi phase.',stroke=PINK,size=9.9)
    p.card(M+HALF+GAP,104,HALF,170,'D* Lite giữ state để repair',
           'Tìm ngược từ goal; giữ <b>g, rhs, U</b>. Heap dùng khóa kép theo min(g, rhs); xử lý đỉnh chưa nhất quán.<br/><br/>'
           'Cost đổi: cập nhật nguồn cạnh. Start di chuyển: tăng <b>k_m</b>. Sửa đến khi start nhất quán.<br/><br/>'
           'Cùng một planner xuyên suốt episode; expanded đếm riêng từng phase.',fill=LIME,size=9.9)
    p.text(M,284,CW,'Quá trình nâng cấp và phép đo',14,18,True)
    p.steps([('A* theo snapshot','Mỗi lần chạy dựng lại tìm kiếm.'),('+ Trạng thái g và rhs','Giữ thông tin từ lần tìm trước.'),('+ Update và repair','Đo cả cập nhật, di chuyển và tìm lại.')])
    p.rect(M,378,CW,35,LIME)
    p.text(M+11,386,CW-22,'<b>Romania động</b> Arad → Sibiu; chặn Rimnicu-Pitesti rồi giảm ngập Fagaras-Bucharest.<br/>Mỗi path/cost được đối chiếu Dijkstra; cùng graph và chuỗi cập nhật ở hai thuật toán.',9.5,12,max_h=27)
    p.text(M,425,CW,'Initial và từng repair trên Romania',14,18,True)
    p.text(M,448,CW,'7 lần đo/phase, median; cùng tracemalloc. Time initial gồm khởi tạo; time repair gồm update + move + plan. Peak giữ state từ trước.',8.2,10.4,max_h=23)
    items=[]
    for phase,label in [('initial','Initial'),('repair_1','Repair 1'),('repair_2','Repair 2')]:
        for alg in ('A* (rerun)','D* Lite'):
            row=dict(phases[('baseline_romania_dynamic_replan',alg,phase)],algorithm='A*' if alg.startswith('A*') else alg)
            items.append((label,row))
    p.table(477,items)
    a=total[('best_dynamic_grid8x8_local_waves','A* (rerun)','repairs')]
    d=total[('best_dynamic_grid8x8_local_waves','D* Lite','repairs')]
    p.card(M,624,HALF,132,'Best case: sửa cục bộ',
           f'Lưới 8×8, 8 lần cập nhật gần start: riêng repair giảm <b>{a["expanded"]} → {d["expanded"]} expanded</b>.<br/><br/>'
           f'Tổng time repair: A* {num(a["time_ms"],2)} ms; D* Lite {num(d["time_ms"],2)} ms. Peak episode cao hơn do giữ state; giảm node chưa đủ kết luận về RAM.',stroke=PINK,size=9.4)
    wa=total[('worst_dynamic_grid7x7_goal_root_flood','A* (rerun)','episode')]
    wd=total[('worst_dynamic_grid7x7_goal_root_flood','D* Lite','episode')]
    sa,sd=r('dstar__worst_static_grid7x7_no_updates','A*'),r('dstar__worst_static_grid7x7_no_updates','D* Lite')
    p.card(M+HALF+GAP,624,HALF,132,'Worst case: ít tái sử dụng',
           f'Ngập sát goal trên lưới 7×7 làm lan truyền sửa đổi: cả episode A* <b>{wa["expanded"]}</b>, D* Lite <b>{wd["expanded"]} expanded</b>.<br/><br/>'
           f'Lưới tĩnh 7×7: A* {num(sa["time_ms"],2)} ms, D* Lite {num(sd["time_ms"],2)} ms. D* Lite trả overhead khi không có lượt repair để tái sử dụng.',fill=LIME,size=9.4)
    p.rect(M,767,CW,29,'#d4678d')
    p.text(M+11,774,CW-22,'D* Lite có lợi khi thay đổi cục bộ; chi phí dương và heuristic hợp lệ là điều kiện của adapter.',9.2,12,True,max_h=15)
    p.footer_source('Peak: Python allocations, gồm planner và output phase trước; KB = KiB, không phải RSS. Nguồn: code Phương Anh; kết quả chạy lại; Koenig & Likhachev 2002 và errata.')
    return p


def build_html(pages):
    body=''.join('<section class="page">'+''.join(p.el)+'</section>' for p in pages)
    text='''<!doctype html><html lang="vi"><head><meta charset="utf-8"><title>Báo cáo thuật toán của Đức</title>
<style>*{box-sizing:border-box}body{margin:0;background:#dcd7db;font-family:Arial,sans-serif}.toolbar{position:sticky;top:0;z-index:9;padding:12px;background:#321d26;color:white;display:flex;gap:10px;align-items:center;font-size:13px}.toolbar button{border:0;border-radius:6px;padding:9px;cursor:pointer}.page{position:relative;width:595.276pt;height:841.89pt;background:#f4eef2;margin:18px auto;box-shadow:0 4px 25px #0002;overflow:hidden}.shape,.txt{position:absolute}.txt{z-index:2;outline:none}.txt:focus{outline:1px dashed #a62968;background:#fff9}.shape{z-index:1}@page{size:A4;margin:0}@media print{body{background:white}.toolbar{display:none}.page{margin:0;box-shadow:none;break-after:page}.page:last-child{break-after:auto}.txt:focus{outline:none;background:none}}a{color:inherit}</style></head><body>
<div class="toolbar"><b>Bản A4 có thể chỉnh sửa</b><span>Bấm vào chữ để sửa; kiểm tra lại ngắt dòng trước khi in.</span><button onclick="window.print()">In hoặc lưu PDF</button><button onclick="saveHtml()">Lưu bản HTML đã sửa</button></div>'''+body+'''
<script>function saveHtml(){const data='<!doctype html>\\n'+document.documentElement.outerHTML;const link=document.createElement('a');link.href=URL.createObjectURL(new Blob([data],{type:'text/html;charset=utf-8'}));link.download='bao_cao_3_trang_da_sua.html';link.click();setTimeout(()=>URL.revokeObjectURL(link.href),1000)}</script></body></html>'''
    (OUT/'bao_cao_3_trang_chinh_sua.html').write_text(text,encoding='utf-8')


def main():
    font_setup()
    c=canvas.Canvas(str(OUT/'bao_cao_3_trang_A4.pdf'),pagesize=(W,H))
    c.setTitle('Phân tích nâng cấp thuật toán tìm đường')
    c.setAuthor('Đức và nhóm')
    pages=[]
    for fn in (page_one,page_two,page_three):
        pages.append(fn(c));c.showPage()
    c.save();build_html(pages)
    print('Created 3-page A4 PDF and editable HTML')


if __name__=='__main__':main()

