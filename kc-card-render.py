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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-05 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (jeera in-house masala, shakkar in-house daal/shakkar) + 1 mandi/GREEN (basmati chawal in-house Samachar lead). Direction balance 2R+1G. 3 DISTINCT in-house posts (jeera 2f978cdf, shakkar 7523afcb, basmati e48d45a5). Category spread: spice / sweetener / grain. sona-chandi skipped; rujhan digest (1701) skipped; oil (soya/sarson/binola) over-covered -> skipped. MP teji_mandi rows are survey-form outlook (no concrete Rs card) -> not used.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="जीरा",
   price=f'{tri("up",RED)}₹24,200<span class="unit">/क्विंटल</span>',
   sub=f'जीरा +₹600 → बढ़िया माल ₹24,200/क्विंटल (ऊंझा); थोक सामान्य ₹23,900–24,200, नया माल ₹26,100–27,300; रबी बुवाई नज़दीक, माल रुका · <b class="delta" style="color:{RED}">₹600 तेजी</b>',
   l1="क्यों", v1="रबी सीजन की बुवाई का समय पास और मौसम अनिश्चित; ऊंझा में किसान-व्यापारी माल रोक रहे, प्रोसेसर-स्टॉकिस्ट की खरीद तेज",
   l2="क्या करें", v2="2–3 महीने की जरूरत का जीरा अभी के भाव पर उठा लें; नया माल आने में वक्त, गिरावट की उम्मीद कम"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="शक्कर",
   price=f'{tri("up",RED)}₹6,000–6,300<span class="unit">/क्विंटल</span>',
   sub=f'शक्कर +₹200 → ₹6,000–6,300/क्विंटल; गुड़ भी ₹100–300 चढ़कर ₹6,000–6,100 (हापुड़ बाल्टी ₹2,100–2,150/40किलो); त्योहारी मिठाई मांग · <b class="delta" style="color:{RED}">₹200 तेजी</b>',
   l1="क्यों", v1="बारिश से यूपी मंडियों में नए गुड़ की आवक कमजोर; नवरात्रि-दिवाली की मिठाई-खोया मांग से शक्कर-गुड़ में दम",
   l2="क्या करें", v2="शक्कर और गुड़ का माल अभी उठा लें, त्योहार पास आते ही और महंगा होगा; चीनी में जल्दबाजी न करें (सरकारी सख्ती)"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="बासमती चावल",
   price=f'{tri("down",GREEN)}₹8,100–8,300<span class="unit">/क्विंटल</span>',
   sub=f'1509 बासमती सेला हफ्तेभर की तेजी के बाद मुनाफावसूली से ₹300–400 टूटा → मिल भाव ₹8,100–8,300/क्विंटल; ₹500 और गिरावट बताई जा रही · <b class="delta" style="color:{GREEN}">₹400 गिरी</b>',
   l1="क्यों", v1="1509 धान ₹400 चढ़कर ₹4,000–4,350 हुआ और चावल भी उछला, फिर आखिरी दिन मुनाफावसूली से भाव लुढ़के",
   l2="क्या करें", v2="चावल की बड़ी खरीद अभी रोककर रखें; ₹500 और गिरावट के आसार, नीचे भाव पर ही माल उठाएं"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d incl also_shown) + body-verify (all concrete Rs). Category spread: oral-care / cooling-powder / confectionery.
 #   close-up LR7.64 Retailer (MRP20 paste, 6+1 free, buy 107, saving 33), navratna LR7.40 Consumer (Rs10 jar par 10x Rs1 pouch free = Rs10 free), corazon LR6.21 Retailer (600-unit candy jar Rs480 + free steel bottle, ~Rs120 benefit).
 #   DROPPED: lifebuoy/mountain-dew/my-fruit-jelly/param-ghee/dettol/sensodyne/dabur-glucose-d = brand within 7d (ledger). parle eclairs LR6.82 = fmcg_product_change bucket but body is a free-toffee/margin SCHEME (jar pe 11 toffee free), no price/weight arrow -> segment/body mismatch, swapped. himalaya LR6.24 = valid backup, edged out by corazon for category spread (vs 2 personal-care already).
 dict(i=4, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="क्लोज़अप",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">6+1 फ्री · ₹33 बचत</span>',
   sub='क्लोज़अप ₹20 MRP वाला पेस्ट — 6+1 फ्री (कुल 7 नग) की होलसेल खरीद ₹107; यानी ₹140 के माल पर सीधी ₹33 की बचत · <b class="delta">₹33 बचत</b>',
   l1="स्कीम", v1="₹20 MRP के 6 पेस्ट खरीदने पर 1 पेस्ट फ्री; पूरा लॉट (7 नग) ₹107 में पड़ता है",
   l2="फायदा", v2="₹140 MRP का माल ₹107 में — दुकानदार को सीधी ₹33 बचत, हर नग पर मार्जिन बढ़ा"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="नवरत्न पाउडर",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">₹10 जार पर ₹10 के पाउच फ्री</span>',
   sub='नवरत्न ₹10 बिक्री वाला पाउडर — अब एक जार लेने पर ₹1 वाले 10 पाउच बिल्कुल फ्री, यानी ₹10 का अतिरिक्त माल मुफ्त · <b class="delta">₹10 फ्री</b>',
   l1="ऑफर", v1="₹10 वाले नवरत्न पाउडर का जार लेने पर ₹1 वाले 10 पाउच बिल्कुल मुफ्त",
   l2="ग्राहक को", v2="₹10 का माल बिल्कुल फ्री — ज्यादा वैल्यू से बिक्री भी तेज होती है"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="कोराज़ोन कैंडी",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">जार पर स्टील बोतल फ्री</span>',
   sub='कोराज़ोन लव कैंडी का बड़ा जार (600 नग) ₹480 में, साथ में अच्छी स्टील पानी बोतल बिल्कुल फ्री; दुकानदार को करीब ₹120 का फायदा · <b class="delta">₹120 फायदा</b>',
   l1="स्कीम", v1="600 नग कैंडी वाला बड़ा जार ₹480 में, साथ में अच्छी स्टील पानी बोतल मुफ्त",
   l2="फायदा", v2="कैंडी की बिक्री पर ~₹120 मुनाफा और ऊपर से फ्री बोतल — दोहरा फायदा"),
 # News (trending_news) - in-house 5oct Pan India Trending 1 (d101a5d5): Navratri festive stocking advisory. Non-bait, concrete festival calendar + 7-10 day supply lead time, universal kirana relevance. News=1 base. (TN2 nakli-note gang = scam/fraud bait -> skipped per SKIP-ALWAYS; Stand Up India scheme 17b26f21 kept as backup but scheme-heavy recent run favoured the fresh festive angle.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="नवरात्रि की तैयारी",
   price='<span class="news">अभी ऑर्डर दें, वरना पछताएंगे</span>',
   sub='नवरात्रि 11 अक्टूबर से, दशहरा 20 अक्टूबर, धनतेरस 6 नवंबर, दिवाली 8 नवंबर; थोक से माल आने में 7–10 दिन लगते हैं, इसलिए व्रत-पूजा स्टॉक अभी भरें · <b class="delta">सिर्फ 6 दिन बाकी</b>',
   l1="क्यों ज़रूरी", v1="साल की सबसे बड़ी बिक्री सिर पर; त्योहार शुरू होने के बाद ऑर्डर देने पर माल समय पर नहीं आता",
   l2="क्या करें", v2="कुट्टू-सिंघाड़ा आटा, सेंधा नमक, साबूदाना, मखाना, मेवा, देसी घी व पूजा सामान अभी ऑर्डर कर दें"),
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
