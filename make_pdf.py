import re, json, os, io, base64
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.lib.colors import HexColor

HERE = os.path.dirname(os.path.abspath(__file__))
# label-map.html and index.html are meant to be identical; use whichever is present.
SRC = next((os.path.join(HERE, f) for f in ('label-map.html', 'index.html')
            if os.path.exists(os.path.join(HERE, f))), None)
if SRC is None:
    raise SystemExit('no label-map.html or index.html next to %s' % __file__)
OUT = os.path.join(HERE, 'label-map.pdf')
s = open(SRC).read()

def grab(v):
    i = s.index('const %s=' % v); j = i + len('const %s=' % v); depth = 0; k = j
    while True:
        ch = s[k]
        if ch in '{[': depth += 1
        elif ch in '}]':
            depth -= 1
            if depth == 0: break
        elif ch == '"':
            k += 1
            while s[k] != '"' or s[k-1] == '\\': k += 1
        k += 1
    return s[j:k+1]

def to_json(src):
    out = []; i = 0; n = len(src)
    key = re.compile(r'([A-Za-z_]\w*)\s*:')
    while i < n:
        ch = src[i]
        if ch == '"':
            j = i + 1
            while src[j] != '"' or src[j-1] == '\\': j += 1
            out.append(src[i:j+1]); i = j + 1; continue
        m = key.match(src, i)
        if m:
            out.append('"%s":' % m.group(1)); i = m.end(); continue
        out.append(ch); i += 1
    txt = ''.join(out)
    return re.sub(r',(\s*[\]\}])', r'\1', txt)   # JS allows trailing commas, JSON does not

T = json.loads(to_json(grab('T')))
INDIE = json.loads(to_json(grab('INDIE')))
DIST = json.loads(to_json(grab('DIST')))

# Logos come from the HTML's own LOGO block, so the PDF is derived entirely
# from the HTML and cannot drift from it.
_logo_src = grab('LOGO')
LOGOS = {k: base64.b64decode(v) for k, v in
         re.findall(r'(\w+)\s*:\s*["\']data:image/[^;]+;base64,([^"\']+)["\']', _logo_src)}
for _k in ('umg', 'sony', 'wmg'):
    if _k not in LOGOS: raise SystemExit('LOGO block is missing %r' % _k)
C = {'umg': HexColor('#181818'), 'sony': HexColor('#E60000'),
     'wmg': HexColor('#00309C'), 'indie': HexColor('#3D6B4A')}
INK, MUTED, RULE, SOFT = HexColor('#14171C'), HexColor('#697079'), HexColor('#D3D8DC'), HexColor('#EFF1F3')

LH, IND, MARGIN, GAP = 12.2, 11.0, 42, 26
W = 1300.0

def lines(nd): return 1 + sum(lines(k) for k in nd.get('c', []))
def nodes(nd): return sum(1 + nodes(k) for k in nd.get('c', []))

col_lines = {k: sum(lines(b) for b in T[k]['b']) for k in T}
tallest = max(col_lines.values())
HEAD = 108
IND_ROWS = max(1 + len(g['c']) for g in INDIE)
IND_BLOCK = 46 + IND_ROWS * LH + 30
H = HEAD + tallest * LH + 52 + IND_BLOCK + MARGIN

c = canvas.Canvas(OUT, pagesize=(W, H))
c.setTitle('Major label map')

# ---------- header ----------
c.setFillColor(INK); c.setFont('Helvetica-Bold', 25)
c.drawString(MARGIN, H - MARGIN - 14, 'MAJORS')
c.setFillColor(MUTED); c.setFont('Helvetica', 9.5)
c.drawString(MARGIN + 124, H - MARGIN - 13,
             'Dashed = distribution or JV, not ownership')

COLW = (W - 2 * MARGIN - 2 * GAP) / 3.0

def draw_branch(nds, x0, y, depth, col):
    """Draw a list of sibling nodes; return the y after the last one."""
    kid_ys = []
    for nd in nds:
        aff = nd.get('aff'); kids = nd.get('c', [])
        y_top = y
        y -= LH
        kid_ys.append(y)
        tx = x0 + depth * IND
        if depth == 0:
            c.setFont('Helvetica-Bold', 9.6); c.setFillColor(INK)
        else:
            c.setFont('Helvetica', 8.6); c.setFillColor(HexColor('#2C333A'))
        label = nd['n']
        maxw = COLW - depth * IND - 34
        while c.stringWidth(label, c._fontname, c._fontsize) > maxw and len(label) > 6:
            label = label[:-2]
        if label != nd['n']: label += '…'
        c.drawString(tx + 9, y + 3, label)
        if depth == 0 and kids:
            c.setFont('Helvetica', 7.4); c.setFillColor(MUTED)
            c.drawRightString(x0 + COLW - 8, y + 3, str(nodes(nd)))
        if aff:
            c.setFillColor(col); c.setFont('Helvetica-Bold', 6)
            pill_x = tx + 13 + c.stringWidth(label, 'Helvetica-Bold', 9.6)
            rel = nd.get('rel', 'DIST')
            pw = c.stringWidth(rel, 'Helvetica-Bold', 6) + 7
            c.roundRect(pill_x, y + 1.5, pw, 8, 2, stroke=0, fill=1)
            c.setFillColor(HexColor('#FFFFFF'))
            c.drawString(pill_x + 3.4, y + 3.9, rel)
        if not kids and aff:
            c.setStrokeColor(col); c.setLineWidth(0.7); c.setDash(2, 2)
            c.roundRect(tx + 2, y - 1.5, COLW - depth * IND - 6, LH + 1, 4, stroke=1, fill=0)
            c.setDash()
        if kids:
            y_after = draw_branch(kids, x0, y, depth + 1, col)
            if aff:
                c.setStrokeColor(col); c.setLineWidth(0.7); c.setDash(2, 2)
                c.roundRect(tx + 2, y_after + 1, COLW - depth * IND - 6,
                            (y_top - LH + 9) - y_after, 4, stroke=1, fill=0)
                c.setDash()
            y = y_after
    # indent guide + ticks for this sibling group
    if depth > 0 and kid_ys:
        gx = x0 + (depth - 1) * IND + 13
        c.setStrokeColor(RULE); c.setLineWidth(0.6)
        c.line(gx, kid_ys[0] + 8, gx, kid_ys[-1] + 3)
        for ky in kid_ys:
            c.line(gx, ky + 3, gx + 6, ky + 3)
    return y

top_y = H - HEAD
for i, k in enumerate(['umg', 'sony', 'wmg']):
    x0 = MARGIN + i * (COLW + GAP)
    total = sum(1 + nodes(b) for b in T[k]['b'])
    # column card
    c.setFillColor(HexColor('#FFFFFF')); c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.roundRect(x0 - 10, MARGIN + IND_BLOCK - 6, COLW + 20,
                (top_y + 46) - (MARGIN + IND_BLOCK - 6), 6, stroke=1, fill=1)
    c.setFillColor(C[k])
    c.rect(x0 - 10, top_y + 42, COLW + 20, 4, stroke=0, fill=1)
    img = ImageReader(io.BytesIO(LOGOS[k]))
    iw, ih = img.getSize()
    lh = 34.0 if iw / ih < 1.7 else 26.0          # square-ish marks need more height
    c.drawImage(img, x0, top_y + 4, width=iw * lh / ih, height=lh,
                mask='auto', preserveAspectRatio=True)
    c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.line(x0 - 10, top_y - 8, x0 + COLW + 10, top_y - 8)
    draw_branch(T[k]['b'], x0, top_y - 12, 0, C[k])

# ---------- indies ----------
iy = MARGIN + IND_BLOCK - 26
c.setFillColor(INK); c.setFont('Helvetica-Bold', 15)
c.drawString(MARGIN, iy, 'INDIES')
iy -= 20
bw = (W - 2 * MARGIN - 4 * 14) / 5.0
for i, g in enumerate(INDIE):
    bx = MARGIN + i * (bw + 14)
    bh = 22 + len(g['c']) * LH
    c.setFillColor(HexColor('#FFFFFF')); c.setStrokeColor(RULE); c.setLineWidth(0.6)
    c.roundRect(bx, iy - bh, bw, bh, 5, stroke=1, fill=1)
    c.setFillColor(C['indie']); c.rect(bx, iy - bh, 2.5, bh, stroke=0, fill=1)
    c.setFillColor(INK); c.setFont('Helvetica-Bold', 9.6)
    c.drawString(bx + 12, iy - 15, g['n'])
    c.setFillColor(MUTED); c.setFont('Helvetica', 7.4)
    c.drawRightString(bx + bw - 8, iy - 15, str(len(g['c'])))
    yy = iy - 15
    for ch in g['c']:
        yy -= LH
        c.setStrokeColor(RULE); c.setLineWidth(0.6)
        c.line(bx + 16, yy + 3, bx + 22, yy + 3)
        c.setFillColor(HexColor('#2C333A')); c.setFont('Helvetica', 8.6)
        c.drawString(bx + 26, yy, ch)
    c.setStrokeColor(RULE)
    c.line(bx + 16, iy - 20, bx + 16, yy + 3)

c.showPage(); c.save()
print('%s -> %s\npages: 1  size: %dx%d pt' %
      (os.path.basename(SRC), os.path.basename(OUT), W, H))
