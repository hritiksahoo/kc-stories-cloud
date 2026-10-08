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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-08 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (moong in-house daal, chhuhara in-house mewa) + 1 mandi/GREEN (haldi in-house Samachar). Direction 2R+1G. 3 DISTINCT in-house posts (moong 4082b59a, chhuhara cf4bc59b, haldi 2c1119bb-Samachar). Category spread: pulse / dry-fruit / spice. sona-chandi skipped; rujhan digest (1725) skipped; soya/sarson tel over-cover avoided (oil + sarson covered within 3d -> used haldi mandi from Samachar for the green instead of palm-oil). Figures locked from in-house bodies.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="मूंग",
   price=f'{tri("up",RED)}₹8,200–8,700<span class="unit">/क्विंटल</span>',
   sub=f'नई फसल के बीच भी बढ़िया मूंग मजबूत; राजस्थान में ₹9,200 तक, मूंग धोया दाल ₹11,300–12,300 · <b class="delta" style="color:{RED}">भाव मजबूत</b>',
   l1="क्यों", v1="नई मूंग आ गई पर बढ़िया पुराना माल कम; अच्छी क्वालिटी के भाव नीचे नहीं आए",
   l2="क्या करें", v2="नवरात्रि व्रत में मूंग की खपत बढ़ती है; बढ़िया माल का स्टॉक अभी रख लें"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="छुहारा",
   price=f'{tri("up",RED)}₹12,000–13,000<span class="unit">/क्विंटल</span>',
   sub=f'छुहारा ₹1,000 उछला → लाल ₹12,000–13,000, काला ₹11,000–12,000/क्विंटल; नवरात्रि-दशहरा व शादी मांग · <b class="delta" style="color:{RED}">₹1,000 तेजी</b>',
   l1="क्यों", v1="स्टॉकिस्ट माल रोक रहे; रुपया कमजोर से आयात महंगा, बंदरगाह पर कंटेनर कम",
   l2="क्या करें", v2="व्रत-त्योहार का छुहारा-गोला-बादाम अभी भर लें; आगे और तेजी के आसार"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="हल्दी",
   price=f'{tri("down",GREEN)}₹19,800–20,000<span class="unit">/क्विंटल</span>',
   sub=f'हल्दी ₹200 नरम → इरोड गट्ठा ₹19,800–20,000/क्विंटल; लगातार तेजी के बाद मुनाफावसूली · <b class="delta" style="color:{GREEN}">₹200 गिरी</b>',
   l1="क्यों", v1="लंबी तेजी के बाद बिकवाली; मुनाफावसूली चलने से इरोड लाइन में भाव नरम पड़े",
   l2="क्या करें", v2="गिरावट पर त्योहारी-मसाला मांग का हल्दी स्टॉक भर लें; रुझान आगे फिर मजबूती का"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d) + body-verify (all concrete Rs). Category spread: personal-care soap / home-repellent / confectionery.
 #   vivel LR6.64 Consumer Scheme (8518d8a5: Vivel soap 4+1 free, set of 5 kharid Rs100 sell Rs140, per pc MRP 35), maxo LR6.61 Consumer Scheme (1e5c40f0: Maxo liquid vaporiser MRP75 kharid46 sell60 Rs15 margin + Rs10 Exo bartan bar free, pack of 10 ~Rs150 margin), amber LR5.56 Retailer Scheme (3a852200: Amber smooth coffee chocolate 220-unit jar WS Rs160 Rs60 margin + 1 steel water glass free).
 #   DROPPED brand within 7d (ledger): sensodyne (878840ac LR6.83). SWAPPED for category spread + thin body: godrej no.1 soap (91ba4a7b LR5.69 -> also_shown; body only "set + 1pc Rs30 free", no buy price/margin, and a 2nd soap). dant-kranti (20ccb8e5 LR6.18) skipped: ambiguous vs patanjali-dant-kanti used within 7d + oral-care fatigue. hara-matar fmcg_product_change (2da6f1c2) + maggi (e06193c5) skipped: no concrete figure / below top-3.
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="विवेल साबुन",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">4 + 1 साबुन फ्री</span>',
   sub='विवेल साबुन 4 खरीदने पर 5वां साबुन फ्री; 5 साबुन का सेट बिक्री ₹140 (खरीद ₹100), हर साबुन MRP ₹35 · <b class="delta">ग्राहक को 1 फ्री</b>',
   l1="ऑफर", v1="4 साबुन के साथ 5वां साबुन (MRP ₹35) बिल्कुल फ्री",
   l2="ग्राहक को", v2="सेट ₹140 में; दुकानदार को अच्छा मार्जिन, ग्राहक को ₹35 का साबुन मुफ्त"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="मैक्सो वेपोराइज़र",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">₹10 Exo बार फ्री</span>',
   sub='मैक्सो लिक्विड वेपोराइज़र (MRP ₹75) के साथ ₹10 वाला Exo बर्तन बार फ्री; खरीद ₹46, बिक्री ₹60 · <b class="delta">₹15/नग मार्जिन</b>',
   l1="ऑफर", v1="हर मैक्सो वेपोराइज़र के साथ ₹10 वाला Exo बर्तन बार मुफ्त",
   l2="ग्राहक को", v2="₹60 में वेपोराइज़र + फ्री बार; पूरे पैक (10 नग) पर करीब ₹150 मार्जिन"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="एम्बर कॉफी",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">स्टील गिलास फ्री</span>',
   sub='एम्बर स्मूद कॉफी चॉकलेट जार (220 नग); थोक खरीद ₹160, पूरे जार पर ₹60 मार्जिन, साथ में स्टील पानी गिलास फ्री · <b class="delta">₹60/जार मार्जिन</b>',
   l1="स्कीम", v1="220 नग का जार ₹160 में; साथ में एक छोटा स्टील पानी गिलास बिल्कुल फ्री",
   l2="फायदा", v2="हर जार पर ₹60 का मार्जिन; बच्चों में तेज बिकने वाली कॉफी चॉकलेट टॉफी"),
 # News (trending_news) - in-house 8oct Pan India Trending 1 (cee14a57): Maharashtra/Karnataka cane farmers protest early crushing, demand MSP/ethanol hike -> sugar may get costlier; mill delivery Rs4,900-5,050/qtl, Mumbai M-grade Rs4,700-4,852 (+Rs50). Non-bait, policy/market-impact, concrete numbers, universal kirana relevance (sugar = top-selling SKU). News=1 base. (TN2 festival-stocking advice 1727 = no hard number; Pan India Schemes PM-KISAN 1728 = evergreen explainer -> not used.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="चीनी में तेजी",
   price='<span class="news">मिल भाव ₹4,900–5,050/क्विंटल</span>',
   sub='महाराष्ट्र-कर्नाटक में गन्ना किसानों का विरोध; MSP बढ़ाने की मांग, त्योहार पर चीनी महंगी हो सकती है · <b class="delta">मिल ₹4,900–5,050</b>',
   l1="क्यों ज़रूरी", v1="चीनी हर दुकान का सबसे चलने वाला माल; MSP बढ़ा या पेराई टली तो थोक भाव ऊपर",
   l2="क्या करें", v2="नवरात्रि-दिवाली की त्योहारी चीनी का स्टॉक आज के भाव पर ही बांध लें"),
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
