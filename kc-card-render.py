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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-09 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (arhar in-house daal, pista in-house mewa) + 1 mandi/GREEN (chini MP teji_mandi UGC, bearish new-crop outlook). Direction 2R+1G. 3 DISTINCT news_ids (arhar dccd5f51 in-house, pista b7843f2d in-house, chini 2cad5af1 MP LR6.19). Category spread: pulse / dry-fruit / sugar. sona-chandi skipped; rujhan digest (b9ee412a) + samachar digest (4aa7a15d) skipped. SWAPPED OUT sarson tel (a9c8eff6, in-house teji) -> chini: avoided all-RED commodity + soft 3-day sarson repeat (sarson teji used 10-07). Figures locked from in-house + body-verified UGC bodies.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="अरहर दाल",
   price=f'{tri("up",RED)}₹9,750–9,800<span class="unit">/क्विंटल</span>',
   sub=f'दिल्ली लेमन अरहर ₹100 चढ़कर ₹9,750–9,800; अरहर दाल ₹13,000–13,800/क्विंटल; महा-कर्नाटक सूखे से फसल 18–20% घटने का डर · <b class="delta" style="color:{RED}">₹100 तेजी</b>',
   l1="क्यों", v1="कम बारिश से महाराष्ट्र-कर्नाटक में अरहर फसल बिगड़ी; अफ्रीका में भी उत्पादन घटा, आयात से राहत कम",
   l2="क्या करें", v2="त्योहार-शादी सीज़न की जरूरत भर अरहर दाल अभी बांध लें; आगे ₹9,900 तक जाने के आसार"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="पिस्ता",
   price=f'{tri("up",RED)}₹4,000–4,100<span class="unit">/किलो</span>',
   sub=f'पेशावरी पिस्ता ₹100 उछलकर ₹4,000–4,100/किलो; ईरानी ₹2,950–3,100, हरा ₹3,450–3,650; त्योहारी मिठाई-गिफ्ट मांग तेज · <b class="delta" style="color:{RED}">₹100 तेजी</b>',
   l1="क्यों", v1="मिठाई-बेकरी और गिफ्ट पैक कंपनियों की जोरदार मांग; पुराना स्टॉक निकला, नया माल सीमित",
   l2="क्या करें", v2="दिवाली तक पिस्ता सस्ता मिलने की उम्मीद कम; मिठाई-गिफ्ट वाले ग्राहकों का माल अभी भर लें"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="चीनी",
   price=f'{tri("down",GREEN)}₹49.50<span class="unit">/किलो थोक</span>',
   sub=f'थोक चीनी ₹49.50/किलो; नई गन्ना फसल की पेराई से आगे भाव ₹48 की ओर नरम पड़ने के आसार, खुदरा ₹50 · <b class="delta" style="color:{GREEN}">नई फसल से मंदी</b>',
   l1="क्यों", v1="नई गन्ना फसल आ गई; मंडी में आवक बढ़ने से आगे थोक चीनी के भाव नीचे आने की उम्मीद",
   l2="क्या करें", v2="अभी जरूरत भर चीनी ही लें; बड़ा स्टॉक नई फसल की सस्ती चीनी आने तक रोकें"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d) + body-verify (all concrete Rs). Category spread: snack product-change / snack launch / oral-care margin.
 #   aakash-namkeen LR6.55 fmcg_product_change (c3a4a57a: Aakash namkeen Rs5, weight 16g->20g, +4g, price same), real-bites LR5.38 new_product_launch (2a76219f: Real Bites Nadiyadi Mix Rs5 naya, MRP5 kharid3.70 margin1.30/26%), dabur-red LR4.67 scheme/retailer-margin (a4a2472a: Dabur Red gel 300g MRP246 WS buy Rs111, sell Rs200 -> Rs89 margin).
 #   DROPPED brand within 7d (ledger): dettol c2ada0d3 LR7.63, colgate 595033e7/0ac19c68, patanjali-dant-kanti a5aa7489/cf442ab3, godrej-no1 91ba4a7b, vivel 8518d8a5, maxo 1e5c40f0, solar-surf d49937da, amber 3a852200. SWAPPED (category spread, soft): hara-matar 2da6f1c2 LR4.76 -> also_shown (3rd Rs5 snack = same-category domination; dabur-red LR4.67 taken for oral-care spread + strongest margin number). dant-kranti 20ccb8e5 LR4.72 skipped: no concrete Rs figure (body-verify fail) + oral-care fatigue + near patanjali-dant-kanti used within 7d.
 dict(i=4, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="आकाश नमकीन",
   price='<span class="wt">16g</span><span class="arrow">→</span><span class="wt">20g</span>',
   sub='₹5 वाली आकाश नमकीन में अब 4 ग्राम ज्यादा — वजन 16g से बढ़कर 20g, दाम वही ₹5 · <b class="delta">4g ज्यादा, दाम वही</b>',
   l1="बदलाव", v1="₹5 पैकेट का वजन 16 ग्राम से बढ़ाकर 20 ग्राम; कीमत ₹5 ही रखी",
   l2="फायदा", v2="उसी दाम में ज्यादा नमकीन — ग्राहक को अच्छी लगेगी, दुकान पर तेज बिकेगी"),
 dict(i=5, eyebrow="FMCG", label="नया प्रोडक्ट लॉन्च", stripe=LAUNCH_AMBER, headline="रियल बाइट्स",
   price=f'<span class="newtag" style="background:{LAUNCH_AMBER}">नया</span><span class="mrp">MRP ₹5</span>',
   sub=f'रियल नमकीन का नया "नाडियादी मिक्स" फ्लेवर ₹5 पैकेट; खरीद ₹3.70, बिक्री ₹5, मार्जिन ₹1.30/पैकेट (26%) · <b class="delta" style="color:{LAUNCH_AMBER}">₹1.30 मार्जिन</b>',
   l1="नया क्या", v1="रियल बाइट्स का नया नाडियादी मिक्स फ्लेवर, ₹5 के छोटे पैकेट में लॉन्च",
   l2="फायदा", v2="हर पैकेट ₹1.30 (26%) मार्जिन; चाय के साथ तेज बिक्री, रोज 15–20 पैकेट"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="डाबर रेड पेस्ट",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">₹89 तक मार्जिन</span>',
   sub=f'डाबर रेड जेल टूथपेस्ट 300g (MRP ₹246) थोक खरीद ₹111; ₹200 में बेचें तो भी ₹89 मार्जिन · <b class="delta" style="color:{SCHEME_GREEN}">₹89/नग मार्जिन</b>',
   l1="स्कीम", v1="300g डाबर रेड पेस्ट, MRP ₹246, थोक खरीद सिर्फ ₹111 प्रति नग",
   l2="फायदा", v2="₹200 में बेचें तो ₹89 मार्जिन; ग्राहक को MRP से सस्ता, दुकानदार को मोटा फायदा"),
 # News (trending_news) - in-house 9oct Pan India Trending 1 (b54e69b2): GST Council 57th meeting (8 Oct) recommends scrapping Section 69 (arrest power), prosecution threshold Rs1cr->Rs5cr, refund window 15->10 days, no notice below Rs10k. Non-bait (relief, not arrest-bait), concrete, high trader/kirana relevance. News=1 base. (TN2 monsoon 3b35aa4d = advisory, weaker; Pan India Scheme postoffice f92d1be5 = scheme explainer -> not used.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="GST में राहत",
   price='<span class="news">अब GST में गिरफ्तारी नहीं</span>',
   sub='GST काउंसिल ने जांच में गिरफ्तारी वाली धारा 69 हटाने की सिफारिश की; मुकदमे की सीमा ₹1 करोड़ से ₹5 करोड़, रिफंड 15 से 10 दिन में · <b class="delta">कारोबारियों को राहत</b>',
   l1="क्यों ज़रूरी", v1="छोटे दुकानदारों का गिरफ्तारी का डर घटेगा; ₹10,000 से कम के मामलों में नोटिस नहीं",
   l2="क्या करें", v2="अभी ये काउंसिल की सिफारिशें हैं; GST रेट नहीं बदले, माल के दाम पर सीधा असर नहीं"),
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
