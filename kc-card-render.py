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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-07 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (rajma-chitra in-house daal, sarson in-house oil post) + 1 mandi/GREEN (makhana in-house Samachar). Direction balance 2R+1G. 3 DISTINCT in-house posts (rajma 785c21ae, makhana f1c94a80, sarson 54a404cb). Category spread: pulse / fox-nut / oilseed. sona-chandi skipped; rujhan digest (1717) skipped; soya-tel over-cover avoided by framing the tel post as SARSON (seed) teji, not soya. MP teji_mandi rows are survey-form outlook (no concrete Rs card) -> not used. Text trimmed after QC so the last grid row clears the bottom CTA reserve.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="राजमां चित्रा",
   price=f'{tri("up",RED)}₹120–122<span class="unit">/किलो</span>',
   sub=f'राजमां चित्रा ₹120–122/किलो; थोक मंडी भाव ₹12,000/क्विंटल, आपूर्ति घटी व आयात महंगा · <b class="delta" style="color:{RED}">₹12,000/क्विंटल थोक</b>',
   l1="क्यों", v1="बीड-बारसी लाइन से आवक घटी; विदेशी व चीन से आयात महंगा व कम हुआ, इसलिए भाव चढ़े",
   l2="क्या करें", v2="त्योहारी मांग के लिए राजमां का माल अभी रख लें; आगे और तेजी के प्रबल आसार"),
 dict(i=2, label="मंडी भाव", stripe=GREEN, headline="मखाना",
   price=f'{tri("down",GREEN)}₹700–1,200<span class="unit">/किलो</span>',
   sub=f'मखाना ₹60–70 टूटकर ₹700–1,200/किलो; फोड़ी वालों की बिकवाली, बंपर उत्पादन · <b class="delta" style="color:{GREEN}">₹70 गिरा</b>',
   l1="क्यों", v1="उत्पादन कई साल के मुकाबले बहुत ज्यादा; उठाव कमजोर, भाव पिछले साल से ~50% नीचे",
   l2="क्या करें", v2="सस्ते भाव पर त्योहारी-व्रत का स्टॉक अभी भर लें; सीजन का मंदा व्यापार के लिए शुभ"),
 dict(i=3, label="मंडी भाव", stripe=RED, headline="सरसों",
   price=f'{tri("up",RED)}₹8,600–8,625<span class="unit">/क्विंटल</span>',
   sub=f'सरसों लगातार तीसरे दिन +₹25–50 → ₹8,600–8,625/क्विंटल (जयपुर ₹8,800); आवक घटी, मिल मांग · <b class="delta" style="color:{RED}">₹50 तेजी</b>',
   l1="क्यों", v1="मंडी आवक 2.5 से घटकर ~2 लाख बोरी; तेल मिलों की मांग बनी, सरसों तेल ₹17,100/क्विंटल",
   l2="क्या करें", v2="सरसों व सरसों तेल की खरीद में देरी भारी पड़ सकती है; जरूरत का माल अभी लें"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d incl also_shown) + body-verify (all concrete Rs). Category spread: beverage / personal-care / stationery.
 #   coca-cola LR6.50 Consumer Scheme (802625f8: Rs99 2L pack + 250ml Sprite worth Rs20 free w/ pack, peti of 9 -> Rs160 saving; offer confirmed by D2R on-pack photo "250ml SPRITE WORTH Rs20 FREE WITH THIS PACK, Rs99"), dermi-cool LR6.36 Consumer Scheme (809dc464: Rs155 pack + Rs75 Dermi Cool powder free), doms LR5.96 Retailer Scheme (6dafb3ef: Zoom pencil box of 10 dabbi, Rs5/pencil, Rs60/box margin + sharpener+eraser free per dabbi).
 #   DROPPED brand within 7d (ledger): ghadi(d5299e48 LR7.98)/patanjali-dant-kanti(77c7b80f)/sensodyne(c8ad8c35)/surf-excel(5d0e2a66)/dettol(f718c7a9). DROPPED no-figure/vague: godrej hair colour (88618734 packing-only, no price/wt change), unbranded blade patta (67b82046 no brand), solar surf coupon (d49937da vague). dbeb3555(LR7.95)/5634d531/875f7627/b6bc774c = news_id used within 12d. Backups not used: marigold+goodday(cc12d8fb), pass-pass-pulse(86b84d90), vicks(e4f033b3), bagh-bakri navchetan(a35c3c10).
 dict(i=4, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="कोका-कोला",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">250ml स्प्राइट ₹20 फ्री</span>',
   sub='₹99 वाले 2 लीटर पैक के साथ ₹20 की 250ml स्प्राइट बोतल फ्री; पेटी (9 पैक) पर ₹160 की बचत · <b class="delta">₹160 बचत</b>',
   l1="ऑफर", v1="हर ₹99 वाले 2 लीटर पैक पर ₹20 वाली 250ml स्प्राइट बोतल बिल्कुल फ्री",
   l2="ग्राहक को", v2="पेटी (9 पैक) खरीद पर ₹160 की सीधी बचत; त्योहारी बिक्री में तेज"),
 dict(i=5, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="डर्मी कूल",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">₹75 पाउडर फ्री</span>',
   sub='₹155 वाले डर्मी कूल पैक के साथ ₹75 वाला डर्मी कूल पाउडर बिल्कुल फ्री · <b class="delta">₹75 फ्री</b>',
   l1="ऑफर", v1="₹155 के डर्मी कूल प्रिकली-हीट पैक के साथ ₹75 वाला पाउडर पैक मुफ्त",
   l2="ग्राहक को", v2="एक पैक की कीमत में ज्यादा माल; ग्राहक को ₹75 की सीधी बचत"),
 dict(i=6, eyebrow="FMCG", label="व्यापारी स्कीम", stripe=SCHEME_GREEN, headline="डोम्स ज़ूम पेंसिल",
   price=f'<span class="offer" style="background:{SCHEME_GREEN}">शार्पनर + इरेज़र फ्री</span>',
   sub='डोम्स ज़ूम पेंसिल बॉक्स (10 डिब्बी); हर पेंसिल ₹5 बिक्री, पूरे बॉक्स पर ₹60 मार्जिन, साथ में 10 शार्पनर व 10 इरेज़र फ्री · <b class="delta">₹60/बॉक्स मार्जिन</b>',
   l1="स्कीम", v1="बॉक्स में 10 डिब्बी; हर डिब्बी के साथ शार्पनर व इरेज़र बिल्कुल फ्री",
   l2="फायदा", v2="हर पेंसिल ₹5 बिक्री, पूरे बॉक्स पर ₹60 मार्जिन; स्कूल सीजन में तेज बिक्री"),
 # News (trending_news) - in-house 7oct Pan India Trending 1 (f07ff50a): kharif paddy MSP procurement started Punjab/Haryana/UP, MSP +Rs72 -> Rs2,441/qtl, money flows to villages ahead of festive season. Non-bait, policy/market-impact, concrete numbers, universal kirana demand relevance. News=1 base. (TN2 DigiDukaan/ONDC bb5ea7f7 = fewer hard numbers; Pan India Schemes GeM 1720 = explainer, no market-impact number -> not used.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="धान खरीद शुरू",
   price='<span class="news">MSP ₹2,441/क्विंटल</span>',
   sub='खरीफ 2026-27 की धान सरकारी खरीद पंजाब-हरियाणा-UP में शुरू; MSP ₹72 बढ़कर ₹2,441/क्विंटल, किसान के खाते में सीधा पैसा · <b class="delta">MSP +₹72</b>',
   l1="क्यों ज़रूरी", v1="फसल का पैसा सीधे किसान के खाते में; यही पैसा त्योहार पर गांव-कस्बे के बाजार में घूमेगा",
   l2="क्या करें", v2="नवरात्रि-दिवाली मांग से पहले तेल, दाल, चीनी, मेवा व पूजा सामग्री का स्टॉक अभी भरें"),
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
