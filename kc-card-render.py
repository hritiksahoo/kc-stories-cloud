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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-11 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (methi in-house masala, chana dal in-house daal) + 1 mandi/GREEN (masoor, canada imports down). Direction 2R+1G. 3 DISTINCT in-house news_ids (methi 332ac2e1, chana-dal fbcba991, masoor via samachar 1cfaeb1d). Category spread: spice / pulse / pulse(mandi). sona-chandi none; rujhan digest skipped. sarson-tel NOT reused (mandi 10-10 + teji 10-09 -> same commodity+direction<3d). Figures locked from in-house editorial bodies.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="मेथीदाना",
   price=f'{tri("up",RED)}₹8,200–8,300<span class="unit">/क्विंटल</span>',
   sub=f'मेथीदाना ₹400 उछलकर ₹8,200–8,300/क्विंटल; नीमच बिना छनी ₹77–78/किलो, गुजरात बढ़िया ₹80/किलो; दिवाली तक ₹10/किलो और तेजी के आसार · <b class="delta" style="color:{RED}">₹400 तेजी</b>',
   l1="क्यों", v1="इस सीजन मेथी उत्पादन ~3.45 से घटकर ~2.45 लाख टन; MP-राजस्थान से आवक आधी, पुराना स्टॉक खत्म",
   l2="क्या करें", v2="मेथी, कसूरी मेथी और अचार-मसाले का जरूरी स्टॉक अभी भर लें; सर्दी की मांग पर भाव और पकड़ेगा"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="चना दाल",
   price=f'{tri("up",RED)}₹8,750–9,200<span class="unit">/क्विंटल</span>',
   sub=f'चना दाल ₹150 उछलकर ₹8,750–9,200/क्विंटल; राजस्थानी चना ₹100 बढ़कर ₹7,675–7,700; बेसन 35किलो ₹3,400 · <b class="delta" style="color:{RED}">₹150 तेजी</b>',
   l1="क्यों", v1="त्योहारी मांग में सप्लाई कम और रबी बुआई की चिंता; मिलों की चौतरफा लिवाली, पीली मटर की कमी",
   l2="क्या करें", v2="बेसन-चना दाल-छोले की त्योहारी बिक्री तेज; जरूरी स्टॉक अभी लें, हर बढ़े भाव पर मुनाफा भी लें"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="मसूर",
   price=f'{tri("down",GREEN)}₹8,700–9,000<span class="unit">/क्विंटल</span>',
   sub=f'मसूर (राजस्थानी) ₹200 नरम होकर ₹8,700–9,000/क्विंटल; कनाडा का सस्ता माल लगातार पड़ते में, अगले महीने वहां नई फसल आएगी · <b class="delta" style="color:{GREEN}">₹200 गिरावट</b>',
   l1="क्यों", v1="कनाडा से सस्ता आयात लगातार उतर रहा है; देसी मसूर में लंबी तेजी की गुंजाइश नहीं",
   l2="क्या करें", v2="मसूर/मलका की बड़ी खरीद कुछ दिन टालें; गिरावट पर जरूरत भर का ही माल उठाएं"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d) + body-verify (all concrete Rs). ZERO oral-care (saturated in 7d: colgate/close-up/dant-kranti/dabur-red). Category spread: detergent / candy / dishwash.
 #   ariel LR5.15 scheme:Consumer (76b7ac3b: 2kg + 1kg free, MRP800), pulse-golmal LR4.47 scheme:Retailer (2af1a505: big box -> Rs50 imli packet free), exo LR4.26 scheme:Consumer (a1ca4675: Rs5 bar 50+40g extra).
 #   DROPPED: colget/colgate LR5.91 (oral-care saturated 7d), surf-excel 4.56 (2nd detergent -> category spread, only +0.09 over golmal; it is a rate-RISE not an offer), dettol/lux 4.69 (brand 7d + news_id 12d dup), martand/parle (news_id 12d dup). bikaji/fortune/ghadi = lower-LR backups.
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="एरियल डिटर्जेंट",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">2kg पर 1kg फ्री</span>',
   sub=f'₹800 MRP वाले 2 किलो एरियल डिटर्जेंट पैकेट के साथ 1 किलो पाउडर बिल्कुल फ्री — ग्राहक को कुल 3 किलो, 50% ज्यादा · <b class="delta" style="color:{SCHEME_BLUE}">1kg एक्स्ट्रा फ्री</b>',
   l1="ऑफर", v1="₹800 MRP एरियल 2 किलो पैकेट — साथ में 1 किलो पाउडर बिल्कुल फ्री (कुल 3 किलो)",
   l2="ग्राहक को", v2="एक पैकेट में 50% ज्यादा पाउडर; त्योहारी धुलाई-सफाई की तेज मांग में ग्राहक को बड़ी बचत"),
 dict(i=5, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="पल्स गोलमाल इमली",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">₹50 पैकेट फ्री</span>',
   sub=f'पल्स गोलमाल इमली कैंडी का बड़ा डिब्बा खरीदने पर ₹50 वाला गोलमाल इमली पैकेट बिल्कुल फ्री; पूरा ₹50 का माल मुफ्त · <b class="delta" style="color:{SCHEME_GREEN}">₹50 का माल फ्री</b>',
   l1="स्कीम", v1="पल्स गोलमाल इमली का बड़ा जार/डिब्बा लेने पर ₹50 का इमली पैकेट बिल्कुल फ्री",
   l2="फायदा", v2="खट्टी-मीठी इमली कैंडी बच्चों में तेज बिकती है; ₹50 फ्री माल सीधा मार्जिन में जुड़ता है"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="एक्सो बर्तन बार",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">50+40g एक्स्ट्रा</span>',
   sub=f'₹5 MRP वाले एक्सो बर्तन बार में अब 50 ग्राम के साथ 40 ग्राम एक्स्ट्रा — उतने ही दाम में कुल 90 ग्राम · <b class="delta" style="color:{SCHEME_BLUE}">40g एक्स्ट्रा फ्री</b>',
   l1="ऑफर", v1="₹5 एक्सो बर्तन बार — 50 ग्राम के साथ 40 ग्राम एक्स्ट्रा, कुल 90 ग्राम उतने ही ₹5 में",
   l2="ग्राहक को", v2="उतने ही ₹5 में ~80% ज्यादा बार; रोज़ बिकने वाला बर्तन बार, ग्राहक को सीधा फायदा"),
 # News (trending_news) - in-house 11oct Pan India Trending News 1 (7d59bdd3): 15 Oct se UPI MDR naya niyam - 0.4% charge on >Rs2000 shop payments, small shops (<=Rs1lakh/month) + all <=Rs2000 payments fully free, charge never from customer, Rs75000+ capped at Rs300. Fresh, concrete, high kirana-impact, non-bait policy. FADA rural-sales (1751) + KVP scheme (1752) are backups; LPG/scam-bait avoided.
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="UPI का नया नियम",
   price='<span class="news">15 अक्टूबर से नया MDR शुल्क</span>',
   sub='अब ₹2,000 से ऊपर के UPI दुकान पेमेंट पर 0.4% शुल्क (MDR); ₹2,000 तक के पेमेंट और ₹1 लाख/माह वाली छोटी दुकानें मुफ्त · <b class="delta">छोटी दुकानें बाहर</b>',
   l1="क्यों ज़रूरी", v1="₹75,000+ पेमेंट पर अधिकतम ₹300 शुल्क; यह शुल्क ग्राहक से कभी नहीं लिया जाएगा",
   l2="क्या करें", v2="घबराकर QR न हटाएं; ₹1 लाख/माह तक वसूली है तो आप पर शून्य शुल्क रहेगा"),
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
