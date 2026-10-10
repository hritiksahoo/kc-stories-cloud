# -*- coding: utf-8 -*-
"""
KC STORIES — DETERMINISTIC CARD COMPOSITOR (the fix for inconsistent text)
==========================================================================
WHY: Gemini cannot render Devanagari at consistent fixed sizes — headlines drift
card-to-card and oversize until they clip (the गुड़ bug). PIL can't shape Devanagari
(no raqm/libraqm on this box). So we render the card OURSELVES from a locked HTML/CSS
template using headless Edge + the 'Nirmala UI' font (which shapes Devanagari perfectly).
Gemini now supplies ONLY the photo; every text element is pixel-identical on every card.

PIPELINE (replaces the old "generate full card + layout-lock + stripe-lock"):
  1. Gemini generates ONE PHOTO per card (still-life, NO text, NO bands) via
     generate_story_image(aspect="portrait"). Photo prompt = subject on dark weathered
     wood, soft daylight upper-left, slightly desaturated wire-photo look, no people,
     no text/labels. FMCG: the real brand pack legible. Commodity/news: generic, no brands.
     Save each as photo_<i>.png (any portrait-ish crop works; object-fit:cover handles it).
     (You may also crop the photo band out of a previously-generated card if reusing art.)
  2. Fill the CARDS list below with the 7 cards' data and run this script. It writes
     card_<i>.png at 1080x1920 — masthead label, gold rule, photo, cream panel, left
     stripe and ALL text rendered at fixed sizes. No layout-lock/stripe-lock needed.
  3. Upload each card_<i>.png via jack:upload_image(blob="news").
     ⚠ nginx caps uploads at ~1MB. If a PNG is >1MB it returns HTTP 413 — resize to
     1000px wide and re-save (im.resize((1000,1778))) to get under the cap, then it
     converts to .webp like the rest. Use the returned URL as the slide img_url.

REQUIREMENTS: Windows 'Nirmala UI' font (C:/Windows/Fonts) + msedge. Both preinstalled.
Run: PYTHONIOENCODING=utf-8 python3 kc-card-render.py   (set HERE to the working dir)

DIRECTION COLOURS: तेज़ी RED #9A2828 · मंदी GREEN #1E7A3C · FMCG/news BLACK #1A1A1A.
The stripe + commodity triangle + sub-line delta all use the direction colour.
Triangle: "up" = ▲ तेज़ी, "down" = ▼ मंदी (drawn with CSS borders, never a glyph).
Price line: commodity = tri()+₹X+unit · FMCG = ₹X →(grey) ₹Y · news = <span class="news">summary</span>.
"""
import base64, subprocess, os, shutil, glob
from PIL import Image

# Cross-platform Chromium/Chrome finder. CLOUD = Linux: prefer CHROME_BIN (setup.sh exports a VERIFIED working
# binary), then the pre-installed Playwright chromium. NOTE: /usr/bin/chromium-browser is a BROKEN snap stub in
# the sandbox (exists but errors) — do NOT prefer it. Nirmala UI comes from fonts/Nirmala.ttc. LOCAL = Windows.
_CANDS = [
    os.environ.get("CHROME_BIN", ""),
    *sorted(glob.glob("/opt/pw-browsers/chromium*/chrome-linux/chrome"), reverse=True),
    *sorted(glob.glob(os.path.expanduser("~/.cache/ms-playwright/chromium*/chrome-linux/chrome")), reverse=True),
    shutil.which("google-chrome"), shutil.which("google-chrome-stable"), shutil.which("chromium"),
    "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable", "/usr/bin/chromium",
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]
EDGE = next((p for p in _CANDS if p and os.path.exists(p)), _CANDS[0])
HERE = os.environ.get("KC_DIR", os.getcwd())   # dir holding photo_<i>.png; card_<i>.png written here
_PROFILE = os.path.join(HERE, ".browser_profile")   # clean isolated profile so launches never attach to a running browser

RED="#9A2828"; GREEN="#1E7A3C"; BLACK="#1A1A1A"; GREY="#7A7A7A"
# FMCG segment accents (stripe + pill). Segment is decided by the post's report bucket, NOT by us.
# ALL FMCG cards set eyebrow="FMCG" (gold eyebrow over the heading); label = the SHORT segment name below:
#   scheme→Retailer Scheme  -> eyebrow="FMCG" label="व्यापारी स्कीम"      stripe SCHEME_GREEN  rep = offer pill (free-goods)        grid स्कीम/फायदा
#   scheme→Consumer Scheme  -> eyebrow="FMCG" label="ग्राहक ऑफर"          stripe SCHEME_BLUE   rep = offer pill (combo ratio)       grid ऑफर/ग्राहक को
#   new_product_launch      -> eyebrow="FMCG" label="नया प्रोडक्ट लॉन्च"   stripe LAUNCH_AMBER  rep = <span class="newtag">नया</span> + MRP  grid नया क्या/फायदा
#   fmcg_product_change     -> eyebrow="FMCG" label="प्रोडक्ट बदलाव"       stripe BLACK         rep = ₹X→₹Y or 110g→100g (ARROW — this segment ONLY)  grid बदलाव/फायदा
# (commodity/news cards omit eyebrow -> single large heading "मंडी भाव" / "ट्रेंडिंग न्यूज़")
# offer pill: '<span class="offer" style="background:SCHEME_GREEN|SCHEME_BLUE">…</span>' · newtag: '<span class="newtag" style="background:LAUNCH_AMBER">नया</span><span class="mrp">MRP ₹X</span>'
SCHEME_GREEN="#1E7A3C"; SCHEME_BLUE="#1F5AA6"; LAUNCH_AMBER="#C8772A"

def tri(direction, color):
    if direction == "up":
        return f'<span class="tri" style="border-left:26px solid transparent;border-right:26px solid transparent;border-bottom:42px solid {color}"></span>'
    return f'<span class="tri" style="border-left:26px solid transparent;border-right:26px solid transparent;border-top:42px solid {color}"></span>'

def b64(path):
    with open(path, "rb") as f:
        return base64.b64encode(f.read()).decode()

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-10 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (moth in-house daal, kaju in-house mewa) + 1 mandi/GREEN (sarson tel in-house tel, profit-booking down). Direction 2R+1G. 3 DISTINCT in-house news_ids (moth a73d46b8, kaju 14ca6924, sarson-tel c1ab338f). Category spread: pulse / dry-fruit / oil. sona-chandi none; rujhan digest (8387912e) + samachar digest (be247948) skipped. chini NOT used (used 10-09 commodity + conflicting teji/mandi signals today). Figures locked from in-house editorial bodies.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="मोठ",
   price=f'{tri("up",RED)}₹9,000–9,200<span class="unit">/क्विंटल</span>',
   sub=f'राजस्थान मंडियों में मोठ ₹9,000–9,200; थोक भाव ₹9,300–9,400/क्विंटल; नीचे ₹6,800 से यहां तक चढ़ी, आगे ~4% और तेजी के आसार · <b class="delta" style="color:{RED}">~4% और तेजी</b>',
   l1="क्यों", v1="मोठ की फसल में भारी पोल, आवक का दबाव नहीं बना; बड़ी कंपनियां प्रतिस्पर्धी खरीद कर रही हैं",
   l2="क्या करें", v2="मोठ का जरूरी स्टॉक अभी बांध लें; हर बढ़े भाव पर थोड़ा मुनाफा भी लेते रहें"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="काजू",
   price=f'{tri("up",RED)}₹870–890<span class="unit">/किलो</span>',
   sub=f'दिवाली-छठ से पहले काजू ₹870–890/किलो; बादामगिरी ₹20–30 तेज होकर ₹1,080–1,200; बड़ी इलायची ₹100 बढ़कर ₹1,540/किलो · <b class="delta" style="color:{RED}">त्योहारी थोक मांग</b>',
   l1="क्यों", v1="मिठाई और गिफ्ट पैक कंपनियों की भारी थोक खरीद; पुराना स्टॉक घटा, रुपया कमजोर से आयात महंगा",
   l2="क्या करें", v2="दिवाली गिफ्ट-मिठाई की बिक्री के लिए काजू-बादाम का स्टॉक अभी भर लें; आगे भाव और चढ़ सकते हैं"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="सरसों तेल",
   price=f'{tri("down",GREEN)}₹17,350<span class="unit">/क्विंटल</span>',
   sub=f'सरसों तेल ₹100 घटकर ₹17,350/क्विंटल; कोलकाता कच्ची घानी ₹1,780/10किलो, भरतपुर ₹15 नरम होकर ₹1,785; सरसों दाना जयपुर ₹50 टूटकर ₹8,900 · <b class="delta" style="color:{GREEN}">₹100 गिरावट</b>',
   l1="क्यों", v1="ऊंचे भाव पर मुनाफा वसूली और तेल मिलों की सुस्त मांग; मंडियों में रोज ~2 लाख बोरी आवक",
   l2="क्या करें", v2="सरसों तेल की बड़ी खरीद 2–3 दिन रोकें; तिल-बिनौला तेल में सप्लाई घटी, वो स्टॉक अभी भर लें"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d) + body-verify (all concrete Rs). ZERO oral-care (category saturated in 7d: colgate/close-up/dant-kranti/dabur-red/sensodyne). Category spread: soap / biscuit / ayurvedic-digestive.
 #   lux LR5.76 scheme:Consumer (7869a1ec: Lux beauty soap MRP30, 4+1 free), parle LR5.75 scheme:Retailer (12c5e9ed: Parle Happy Happy Rs5 biscuit, 22 pcs buy -> 2 free to retailer = Rs10 extra), martand LR5.22 scheme:Retailer (87e0642d: Martand pachak churan Rs5 box + Rs10 Chandrakanta skincare free).
 #   DROPPED brand within 7d (brands7): aakash-namkeen/colgate/vivel/dettol/exo/sensodyne/dabur-red/godrej-no1(news12). khasta-kachori 30647a3a LR5.75 skipped: NO brand (detected_brands empty) -> weak FMCG slide. ghadi/amir/bikaji = lower-LR backups.
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="लक्स साबुन",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">4 + 1 फ्री</span>',
   sub=f'₹30 MRP वाले लक्स ब्यूटी साबुन पर 4 खरीदने पर 1 साबुन बिल्कुल फ्री (4+1); ग्राहक को ₹30 की सीधी बचत · <b class="delta" style="color:{SCHEME_BLUE}">5वां साबुन फ्री</b>',
   l1="ऑफर", v1="₹30 MRP लक्स ब्यूटी साबुन — 4 पीस के साथ 1 पीस बिल्कुल फ्री (4+1 स्कीम)",
   l2="ग्राहक को", v2="हर 4 साबुन पर 1 मुफ्त; त्योहार में नहाने के साबुन की तेज बिक्री, ग्राहक को ₹30 बचत"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="पार्ले हैप्पी हैप्पी",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">22 पर 2 फ्री</span>',
   sub=f'₹5 MRP वाले पार्ले हैप्पी हैप्पी चॉको-चिप बिस्किट के 22 पीस खरीदने पर 2 पीस दुकानदार को फ्री; ₹10 का एक्स्ट्रा फायदा · <b class="delta" style="color:{SCHEME_GREEN}">₹10 एक्स्ट्रा मार्जिन</b>',
   l1="स्कीम", v1="₹5 पार्ले हैप्पी हैप्पी चॉको-चिप बिस्किट, 22 पीस खरीदने पर 2 पीस फ्री",
   l2="फायदा", v2="हर 22 पीस पर ₹10 का एक्स्ट्रा मार्जिन; चॉको-चिप बिस्किट तेज बिकता है"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="मार्तंड पाचक चूर्ण",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">₹5 पर ₹10 फ्री</span>',
   sub=f'₹5 वाले मार्तंड पाचक चूर्ण के डिब्बे के साथ ₹10 की मार्तंड चंद्रकांता स्किन केयर बिल्कुल फ्री · <b class="delta" style="color:{SCHEME_GREEN}">₹10 का सामान फ्री</b>',
   l1="स्कीम", v1="₹5 मार्तंड पाचक चूर्ण के डिब्बे पर ₹10 की मार्तंड चंद्रकांता स्किन केयर फ्री",
   l2="फायदा", v2="एक दाम में दो प्रोडक्ट बेचने को मिलते हैं; कॉम्बो तेज बिकता है, मार्जिन बढ़िया"),
 # News (trending_news) - in-house 10oct Pan India Schemes (12322319): AIF (कृषि अवसंरचना निधि) - godown/sorting/cold-storage loan up to Rs2cr, 3% annual interest subvention for 7yr, + CGTMSE guarantee. Fresh, concrete, policy/scheme (explicitly preferred), non-bait, kirana-relevant (shopkeepers eligible as 'कृषि उद्यमी'). LPG (fe464cfe) skipped = repeat of Oct-2 hike; milawat raids (9299b8a4) = bait; monsoon 3b35aa4d (Oct9 MP) = weaker/stale.
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="गोदाम कर्ज राहत",
   price='<span class="news">₹2 करोड़ तक कर्ज, 3% ब्याज छूट</span>',
   sub='केंद्र की कृषि अवसंरचना निधि (AIF): अनाज-दाल गोदाम, छंटाई या कोल्ड स्टोरेज के लिए ₹2 करोड़ तक कर्ज पर हर साल 3% ब्याज छूट, 7 साल तक; साथ में CGTMSE गारंटी · <b class="delta">किराना को सस्ता कर्ज</b>',
   l1="क्यों ज़रूरी", v1="गोदाम/छंटाई यूनिट लगाने वाले दुकानदार 'कृषि उद्यमी' श्रेणी में पात्र; बड़ी जमानत का बोझ नहीं",
   l2="क्या करें", v2="agriinfra.dac.gov.in पर ऑनलाइन आवेदन करें, प्रोजेक्ट रिपोर्ट लगाएं, फिर बैंक में कागज जमा करें"),
]
TPL = '''<!doctype html><html><head><meta charset="utf-8"><style>
html,body{{margin:0;padding:0;width:1080px;height:1920px;overflow:hidden;font-family:'Nirmala UI','Segoe UI',sans-serif;}}
.card{{width:1080px;height:1920px;position:relative;background:#FAFAF7;}}
.mast{{height:300px;background:#14181F;display:flex;flex-direction:column;justify-content:center;align-items:flex-start;padding-left:80px;box-sizing:border-box;}}
.eyebrow{{font-size:40px;font-weight:700;color:#C8A24A;letter-spacing:8px;margin-bottom:10px;}}  /* FMCG-only eyebrow; keeps the long segment heading from spanning the whole masthead */
.lbl{{font-size:78px;font-weight:700;color:#F2EDDF;letter-spacing:2px;line-height:1.0;}}
.gold{{height:4px;background:#C8A24A;}}
.photo{{height:700px;width:1080px;overflow:hidden;}}
.photo img{{width:1080px;height:700px;object-fit:cover;object-position:center;display:block;}}
.panel{{position:relative;height:916px;background:#FAFAF7;box-sizing:border-box;padding:0 80px 0 150px;}}
.stripe{{position:absolute;left:0;top:0;bottom:0;width:18px;background:{stripe};}}
/* Content is TOP-ANCHORED (flex-start), NOT centred. Centring overflowed equally top+bottom,
   so tall cards (3+ wrapped lines) pushed the headline UP into the photo (the overlap bug).
   flex-start guarantees the headline always sits just below the photo; any overflow grows
   DOWN into the panel. Photo trimmed to 700 / panel raised to 916 so even the tallest card
   (1-line headline + price + 2-line sub + two 2-line grid rows ~610px) clears the bottom
   ~190px CTA reserve. NEVER set a fixed .content height with justify-content:center again. */
.content{{padding-top:30px;display:flex;flex-direction:column;justify-content:flex-start;box-sizing:border-box;}}
.headline{{font-size:100px;font-weight:700;color:#1A1A1A;line-height:1.05;margin:0 0 12px 0;}}
.price{{font-size:62px;font-weight:700;color:#1A1A1A;margin:0;display:flex;align-items:center;line-height:1.1;flex-wrap:wrap;gap:6px 0;}}
.price .unit{{font-size:38px;font-weight:400;color:#7A7A7A;margin-left:8px;}}
.price .arrow{{color:#7A7A7A;margin:0 24px;font-weight:400;}}
.price .news{{font-size:56px;}}
.tri{{width:0;height:0;display:inline-block;margin-right:18px;}}
/* FMCG scheme/launch representations (NOT product-change): offer pill + new-launch pill */
.offer{{display:inline-block;font-size:50px;font-weight:700;color:#fff;padding:10px 30px;border-radius:14px;line-height:1.15;}}
.newtag{{display:inline-block;font-size:46px;font-weight:700;color:#fff;padding:8px 28px;border-radius:14px;margin-right:24px;}}
.mrp{{font-size:60px;font-weight:700;color:#1A1A1A;}}
.wt{{font-size:62px;font-weight:700;color:#1A1A1A;}}
.sub{{font-size:37px;color:#7A7A7A;margin-top:22px;line-height:1.34;}}
.sub .delta{{font-weight:700;color:#1A1A1A;}}
.grid{{margin-top:28px;}}
.row{{display:flex;padding:20px 0;align-items:flex-start;}}
.row.b{{border-top:1px solid #E8E2D2;}}
.lab{{width:250px;font-size:31px;font-weight:700;color:#7A7A7A;letter-spacing:1px;flex-shrink:0;}}
.val{{flex:1;font-size:40px;color:#1A1A1A;line-height:1.22;}}
</style></head><body><div class="card">
<div class="mast">{eyebrow_html}<div class="lbl">{label}</div></div>
<div class="gold"></div>
<div class="photo"><img src="data:image/png;base64,{img}"></div>
<div class="panel"><div class="stripe"></div><div class="content">
<div class="headline">{headline}</div>
<div class="price">{price}</div>
<div class="sub">{sub}</div>
<div class="grid">
<div class="row"><div class="lab">{l1}</div><div class="val">{v1}</div></div>
<div class="row b"><div class="lab">{l2}</div><div class="val">{v2}</div></div>
</div></div></div></div></body></html>'''

def render():
    for c in CARDS:
        c["img"] = b64(os.path.join(HERE, f'photo_{c["i"]}.png'))
        ev = c.get("eyebrow", "")            # FMCG cards set eyebrow="FMCG"; commodity/news leave it empty
        c["eyebrow_html"] = f'<div class="eyebrow">{ev}</div>' if ev else ''
        html = TPL.format(**c)
        hp = os.path.join(HERE, f'card_{c["i"]}.html')
        op = os.path.join(HERE, f'card_{c["i"]}.png')
        with open(hp, "w", encoding="utf-8") as f:   # MUST flush+close before Edge reads it; a bare open().write() races and Edge screenshots a blank/missing page
            f.write(html); f.flush(); os.fsync(f.fileno())
        if os.path.exists(op):
            os.remove(op)
        for _attempt in range(3):
            subprocess.run([EDGE, "--headless=new", "--disable-gpu", "--no-sandbox", "--hide-scrollbars",
                "--no-first-run", "--no-default-browser-check", f"--user-data-dir={_PROFILE}",
                "--force-device-scale-factor=1", f"--screenshot={op}",
                "--window-size=1080,1920", hp], capture_output=True)
            if os.path.exists(op):
                break
        # keep upload under the ~1MB nginx cap
        if os.path.exists(op) and os.path.getsize(op) > 1_000_000:
            Image.open(op).convert("RGB").resize((1000, 1778)).save(op, optimize=True)
        print("card", c["i"], "->", os.path.exists(op), os.path.getsize(op) if os.path.exists(op) else "FAIL")

if __name__ == "__main__":
    render()
