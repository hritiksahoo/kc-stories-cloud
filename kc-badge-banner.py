# -*- coding: utf-8 -*-
# Render KC badge design VARIANTS for operator sign-off. Each line is nowrap (no accidental wrap);
# fs tuned per badge so nothing overflows the ring. Full-circle image + gradient scrim + yellow text.
import base64, subprocess, os, sys, shutil, glob
from PIL import Image, ImageDraw
HERE=os.environ.get("KC_DIR", os.getcwd())
# Prefer CHROME_BIN (setup.sh exports a verified binary) then the pre-installed Playwright chromium;
# /usr/bin/chromium-browser is a broken snap stub in the sandbox — do NOT prefer it.
_C=[os.environ.get("CHROME_BIN",""),
    *sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux/chrome"), reverse=True),
    *sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux/chrome")), reverse=True),
    shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
    "/usr/bin/google-chrome","/usr/bin/google-chrome-stable","/usr/bin/chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe"]
EDGE=next((p for p in _C if p and os.path.exists(p)),_C[0]); PROFILE=os.path.join(HERE,".vprofile")
D=1080
def b64(p):
    with open(p,"rb") as f: return base64.b64encode(f.read()).decode()
# gradient presets
SOFT="rgba(11,13,17,0) 40%, rgba(11,13,17,0.30) 56%, rgba(11,13,17,0.74) 76%, rgba(11,13,17,0.94) 92%, rgba(11,13,17,0.97) 100%"
HARD="rgba(11,13,17,0) 14%, rgba(11,13,17,0.45) 34%, rgba(11,13,17,0.82) 58%, rgba(11,13,17,0.95) 80%, rgba(11,13,17,0.98) 100%"
# TALL: darkens earlier/higher so BIG text that reaches up to ~45% of the circle stays legible (2026-07-09)
TALL="rgba(11,13,17,0) 8%, rgba(11,13,17,0.35) 26%, rgba(11,13,17,0.72) 44%, rgba(11,13,17,0.92) 66%, rgba(11,13,17,0.97) 100%"
# CURVED-BANNER design (operator, 2026-07-09 — "image + text separate like before, curved separator not a
# straight line, text banner >50%"). Top = product photo; bottom = dark banner whose top edge is a smooth
# CURVE (quadratic Bézier) with a gold trim stroke; BIG yellow 2-line clicky headline sits in the banner.
# BEDGE = banner top y at the LEFT/RIGHT edges; BCTRL = Bézier control y at centre (>BEDGE = dips at centre / concave).
# 2026-07-09 v6 — operator: the contain+blur look was OFF (boxy image, empty-looking blurred side bars). Go back to
# FULL-BLEED cover (image fills the ENTIRE top space, no bars); the FIX for "half/cropped image" is to use photos
# COMPOSED to fill the whole frame with stuff (dense overhead flat-lays) so the top cover-crop always looks full.
# Keep the line spacing that fixed the touching lines (line-height 1.1 + per-line margin). BEDGE/BCTRL = banner curve.
BEDGE=470; BCTRL=560
TPL='''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;width:1080px;height:1080px;overflow:hidden;background:#0B0D11;font-family:'Nirmala UI','Segoe UI',sans-serif;}}
.b{{width:1080px;height:1080px;position:relative;overflow:hidden;}}
.subj{{position:absolute;inset:0;width:1080px;height:1080px;object-fit:cover;object-position:center;}}
.banner{{position:absolute;inset:0;}}
.t{{position:absolute;left:22px;right:22px;bottom:{bottom}px;text-align:center;color:#F4C842;font-weight:800;line-height:1.1;letter-spacing:0px;text-shadow:0 3px 6px rgba(0,0,0,.92);}}
.t div{{white-space:nowrap;font-size:{fs}px;margin:7px 0;}}
</style></head><body><div class="b">
<img class="subj" src="data:image/png;base64,{subj}">
<svg class="banner" width="1080" height="1080" viewBox="0 0 1080 1080" xmlns="http://www.w3.org/2000/svg">
  <path d="M0,{edge} Q540,{ctrl} 1080,{edge} L1080,1080 L0,1080 Z" fill="#0E1116"/>
  <path d="M0,{edge} Q540,{ctrl} 1080,{edge}" fill="none" stroke="#C8A24A" stroke-width="9"/>
</svg>
<div class="t">{lines}</div></div></body></html>'''
# Outer-ring conic gradient (operator 2026-07-16): blend ONLY the warm tones #D45339, #B92B0F, #F16943
# into a rich red-orange sweep AROUND the ring. NO Instagram pink/purple — all three stops are warm reds/oranges.
# Positioned stops = a single BRIGHT pole (#F16943) opposite a single DARK pole (#B92B0F), with #D45339 blending
# both sides. This directional sweep reads as an obvious gradient (2026-07-16 v2: even 3-cycle averaged out / looked
# flat — operator: "gradient not visible enough"). Still ONLY the 3 warm tones, no pink/purple.
RING_STOPS=[(0.00,(0xF1,0x69,0x43)),(0.25,(0xD4,0x53,0x39)),(0.50,(0xB9,0x2B,0x0F)),(0.75,(0xD4,0x53,0x39)),(1.00,(0xF1,0x69,0x43))]
def _lerp(a,b,t): return tuple(int(round(a[i]+(b[i]-a[i])*t)) for i in range(3))
def _conic(t):  # t in [0,1] -> colour by position along RING_STOPS (bright pole at t=0/1, dark pole at t=0.5)
    t=t%1.0
    for j in range(len(RING_STOPS)-1):
        p0,c0=RING_STOPS[j]; p1,c1=RING_STOPS[j+1]
        if p0<=t<=p1: return _lerp(c0,c1,(t-p0)/(p1-p0) if p1>p0 else 0.0)
    return RING_STOPS[-1][1]
def gradient_ring(D,r_outer,r_inner,S=4,steps=720):
    # RGBA layer with a conic (angular) red-orange gradient annulus [r_inner..r_outer], supersampled S then LANCZOS-down for clean AA.
    big=Image.new("RGBA",(D*S,D*S),(0,0,0,0)); dd=ImageDraw.Draw(big)
    Rc=D*S/2.0; rmid=(r_outer+r_inner)/2.0*S; w=int(round((r_outer-r_inner)*S))
    bbox=(Rc-rmid,Rc-rmid,Rc+rmid,Rc+rmid)
    for k in range(steps):
        a0=360.0*k/steps
        dd.arc(bbox,a0,360.0*(k+1)/steps+0.8,fill=_conic(k/steps),width=w)  # +0.8 overlap kills seams between arcs
    return big.resize((D,D),Image.LANCZOS)

def render(tag, cfg, grad, bottom):
    # Ring, outside -> in: solid RED band (4.5%, OUTERMOST, flush to the edge) + thin WHITE separator (2%) + photo.
    # The white separator is the white canvas showing through (photo pasted at r_in; red painted at the edge).
    # 2026-07-10 (operator): make the INNER white ring clearly visible so the red doesn't start flush on the photo;
    # red stays the outermost ring (NO outer white ring). In the PN export this white separator is cut to
    # TRANSPARENT ("the middle white should be transparent in pn"), so the PN = photo + transparent gap + red.
    R=D//2; red_w=round(0.045*D); sep_w=round(0.0304*D); r_in=R-red_w-sep_w  # sep_w -5% (operator 2026-07-16): 0.032->0.0304·D (25%->15%->5%)
    for c in cfg:
        lines="".join(f"<div>{ln}</div>" for ln in c["lines"])
        html=TPL.format(edge=BEDGE,ctrl=BCTRL,bottom=bottom,fs=c["fs"],subj=b64(os.path.join(HERE,c["src"])),lines=lines)
        hp=os.path.join(HERE,f'v_{tag}_{c["i"]}.html'); op=os.path.join(HERE,f'vshot_{tag}_{c["i"]}.png')
        with open(hp,"w",encoding="utf-8") as f: f.write(html); f.flush(); os.fsync(f.fileno())
        if os.path.exists(op): os.remove(op)
        for _ in range(3):
            subprocess.run([EDGE,"--headless=new","--disable-gpu","--no-sandbox","--hide-scrollbars",
                "--no-first-run","--no-default-browser-check",f"--user-data-dir={PROFILE}",
                "--force-device-scale-factor=1",f"--screenshot={op}","--window-size=1080,1080",hp],capture_output=True)
            if os.path.exists(op): break
        im=Image.open(op).convert("RGB"); canvas=Image.new("RGB",(D,D),(255,255,255))
        m=Image.new("L",(D,D),0); ImageDraw.Draw(m).ellipse((R-r_in,R-r_in,R+r_in,R+r_in),fill=255)
        canvas.paste(im,(0,0),m); d=ImageDraw.Draw(canvas)
        # PIL grows an ellipse stroke INWARD from the bbox. So:
        # crisp WHITE separator ring: bbox outer = red's inner edge (R-red_w); stroke sep_w fills inward to r_in.
        ri=R-red_w
        d.ellipse((R-ri,R-ri,R+ri,R+ri),outline=(255,255,255),width=sep_w+2)
        # RED-ORANGE band, OUTERMOST + flush to the badge edge [R-red_w .. R]: conic warm gradient (operator 2026-07-16),
        # composited over the flat fill so its own alpha AA blends cleanly. Reused by the PN export below (matches ring).
        gr=gradient_ring(D,R,R-red_w); canvas.paste(gr,(0,0),gr)
        canvas.save(os.path.join(HERE,f'v{tag}_{c["i"]}.png'))
        # --- Transparent square PN export (WebEngage multi_icon), emitted here so it always matches the ring ---
        # PN = photo + TRANSPARENT gap + red ring. Built on a TRANSPARENT base (NOT the white entry canvas) so the
        # red ring's outer AA fades to transparent — this removes the stray WHITE OUTER RING that the entry canvas'
        # white base used to bleed at the red's anti-aliased outer edge (operator 2026-07-20). The middle gap
        # [r_in..red_inner] stays transparent (never black/white); corners transparent; red is the outermost pixel.
        pnc=Image.new("RGBA",(D,D),(0,0,0,0))
        cm=Image.new("L",(D,D),0); ImageDraw.Draw(cm).ellipse((R-r_in,R-r_in,R+r_in,R+r_in),fill=255)
        pnc.paste(im.convert("RGBA"),(0,0),cm)   # photo -> CONTENT disc only; the gap and everything outside stay transparent
        pnc.alpha_composite(gr)                  # red ring composited over transparent: gap stays transparent, no white outer bleed
        pnc.resize((500,500),Image.LANCZOS).save(os.path.join(HERE,f'badge_pn_{c["i"]}.png'))
        print(f'v{tag}_{c["i"]} + badge_pn_{c["i"]} done')

# OPTION D (operator-chosen final): full-circle photo + soft bottom gradient scrim + BIG yellow short-hook text
# 2026-07-09: mandi=लाल मिर्च तेज़ · fmcg=फ्री माल स्कीम · tn=ई-श्रम ₹2 लाख मुफ्त बीमा (shorter word on line 2)
# 2026-07-09 v3 — CURVED-BANNER design + CLICKY copy (operator direction).
#   mandi = {commodity} में तेजी/मंदी · fmcg = communicate the actual offer · news = mini-headline w/ hook.
# 2026-07-09 v7 — operator: (a) UNIFORM text size across all 3 badges (was 3 different fs); (b) more ring
# clearance (text still grazing border in spots); (c) FMCG uses the REAL product photo (D2R post media:
# Center Fruit jar with the "2 Godrej No.1 soap free" offer label). Single FS for all; raised bottom.
# FS 160->154 (2026-07-10): the inner WHITE ring (sep 3.2%) shrank the usable content circle to radius ~454,
# so the widest line ("1 पैक फ्री") grazed it at FS160 (3px). 154 keeps every badge's widest line >=~15px clear
# of the white ring while staying uniform. ALWAYS re-check max_text_radius <= ~438 (white-ring inner 454) after
# changing copy — the widest line caps FS.
FS=130   # 2026-08-25: dropped 138->130, "तूर दाल" upper line grazed ring at 455 (>448) at 138
# 2026-09-25: mandi=साबूदाना/तेज़ (Navratri sago rally, dense pearl flat-lay), fmcg=पिटारा/स्कीम (Pitaara namkeen real photo, 5L container free), news=UPI पर/शुल्क (new UPI merchant fee 15 Oct). 2-line short hooks; verify radial clearance after render. साबूदाना is a wide word -> fs lowered.
# 2026-09-29: mandi=देसी चना/तेज़ (desi chana +Rs300 rally, dense chana flat-lay), fmcg=3 पर 1/फ्री (Gillette Presto 3+1 scheme, real razor packs), news=MSME दर्जा/मुफ्त (Kirana MSME status + free Udyam registration, certificate flat-lay). Wide word on the upper (wider) line; verify radial clearance after render.
# 2026-10-01: mandi=अरहर/तेज़ (arhar/toor 3rd-day rally Rs9,150/qtl, dense toor-dal flat-lay), fmcg=घड़ी/1kg फ्री (Ghadi 500g bori -> 1kg free, real Ghadi pack photo), news=12.6% कम/बारिश (monsoon departed 12.6% below normal, cracked-earth flat-lay). Short 2-line hooks, wider element on the UPPER line; verify radial clearance <=~448 after render.
# 2026-10-02: mandi=मोठ/तेज़ (moth +Rs200 rally, dense moth-bean flat-lay), fmcg=₹70 ब्रश/फ्री (Sensodyne paste MRP185 + Rs70 brush free, REAL D2R pack photo with the FREE Rs70 label in the top zone), news=गैस ₹62/महंगी (commercial 19kg LPG +Rs62.50, red cylinder). Short 2-line hooks, wider element on the UPPER line; verify radial clearance <=~448 after render.
# 2026-10-04: mandi=मसूर/तेज़ (masoor +Rs50 -> 6,900/qtl rally, dense red-lentil flat-lay), fmcg=150ml/ज्यादा (Mountain Dew Rs20 bottle now +150ml extra, real MD bottle photo), news=जेल नहीं/जुर्माना (Jan Vishwas 2026 - small FSSAI lapses no jail from 1 Oct, documents+scale). Short 2-line hooks, wider element on the UPPER line; verify radial clearance <=~448 after render.
DAY=[dict(i=1,src="subjfull_1.png",lines=["मसूर","तेज़"],fs=160),
     dict(i=2,src="subjfull_2.png",lines=["150ml","ज्यादा"],fs=150),
     dict(i=3,src="subjfull_3.png",lines=["जेल नहीं","जुर्माना"],fs=140)]
if __name__=="__main__":
    render("D", DAY, TALL, 190)   # bottom raised for FS130 + wide tn bottom line: seats block higher in the circle's wider zone to clear the ring
    # 2026-07-14 crop fix: operator flagged text CROPPING at the ring. Root cause — the
                                  # BOTTOM line sits low in the circle where it's narrow, so a 2-WORD bottom line
                                  # ('फ्री मिले'/'सस्ता माल') hit the ring (455>448) no matter the FS. Fix = make every
                                  # bottom line ONE short word (तेजी/फ्री/सस्ता, like badge1's safe 388) and put the longer
                                  # element on the UPPER line where the circle is wide. Copy stays logical: 'तूर दाल तेजी',
                                  # '12 पर 2 फ्री' (Colgate shown in photo), '20-40% सस्ता' (goods shown). FS back up to 150
                                  # for prominence. Also swapped to ZOOMED single-subject photos (dal macro / 2 Colgate
                                  # packs / goods+cash) so the small in-app asset stays legible. FS 152->166 (2026-07-13): 205 seated the 2-line block in the
                                  # UPPER half of the dark banner (empty gap below = "text drifting to the top").
                                  # Operator then wanted it BIGGER + centered so the banner feels fully covered. Swept
                                  # uniform FS: 166 is the largest that keeps every badge's widest line clear of the
                                  # inner white ring (max radial 439 <= ~448; FS174 hit 453 = clip-risk). bottom is
                                  # set to CENTER the taller block in the banner: bottom ≈ 325 - (2*FS*1.1+14)/2 ≈ 135.
                                  # Re-measure max_text_radius after any FS/copy change; cap FS where max radial ~446.
