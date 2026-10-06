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

# ---- EDIT THIS PER DAY: 3 commodity + 3 FMCG + 1 news ----  (2026-10-06 . experiment window CLOSED -> base 3+3+1)
CARDS = [
 # Commodity (mandi_bhav) - 2 teji/RED (urad in-house daal, badamgiri in-house mewa) + 1 mandi/GREEN (binola tel in-house oil post). Direction balance 2R+1G. 3 DISTINCT in-house posts (urad 21edc88e, badamgiri f89047e0, binola 05f95a92). Category spread: pulse / nuts / edible-oil. sona-chandi skipped; rujhan+samachar digests skipped; sarson tel over-covered (used 09-30) -> used the GREEN binola angle from the same oil post for direction balance. MP teji_mandi rows are survey-form outlook (no concrete Rs card) -> not used. Text trimmed after QC so the last grid row clears the bottom CTA reserve.
 dict(i=1, label="मंडी भाव", stripe=RED, headline="उड़द",
   price=f'{tri("up",RED)}₹9,725–9,750<span class="unit">/क्विंटल</span>',
   sub=f'उड़द FAQ +₹125 → दिल्ली ₹9,725–9,750/क्विंटल; बर्मा से आयात महंगा, भाव-भविष्य ₹10,450 तक · <b class="delta" style="color:{RED}">₹125 तेजी</b>',
   l1="क्यों", v1="दाल मिलों की मांग तेज; बर्मा से आयात $5–10 महंगा हुआ, चेन्नई का सस्ता माल निपट गया",
   l2="क्या करें", v2="उड़द व उड़द दाल का जरूरत का माल अभी भर लें; आगे ~4% और तेजी का अनुमान"),
 dict(i=2, label="मंडी भाव", stripe=RED, headline="बादामगिरी",
   price=f'{tri("up",RED)}₹1,000–1,070<span class="unit">/किलो</span>',
   sub=f'बादामगिरी +₹30–40 → कैलिफोर्निया ₹1,000–1,070/किलो; आयात घटा, रुपया कमजोर · <b class="delta" style="color:{RED}">₹40 तेजी</b>',
   l1="क्यों", v1="विदेश से बादाम का आयात घटा, कंटेनर कम आ रहे; रुपया कमजोर होने से मंगाना महंगा",
   l2="क्या करें", v2="दिवाली मांग से पहले मेवा का जरूरत का माल अभी तय कर लें, भाव और चढ़ सकता है"),
 dict(i=3, label="मंडी भाव", stripe=GREEN, headline="बिनौला तेल",
   price=f'{tri("down",GREEN)}₹14,550<span class="unit">/क्विंटल</span>',
   sub=f'बिनौला तेल ₹300 टूटकर ₹14,550/क्विंटल; पाम भी ₹50 घटकर ₹12,100; मांग कमजोर · <b class="delta" style="color:{GREEN}">₹300 गिरा</b>',
   l1="क्यों", v1="सोया पर आयात शुल्क 5% घटकर 27% हुआ पर मांग कमजोर; आयातकों की बिकवाली से तेल दबाव में",
   l2="क्या करें", v2="बिनौला/पाम की बड़ी खरीद अभी रोककर रखें, भाव नरम; जरूरत भर का माल उठाएं"),
 # FMCG (fmcg) - TOP 3 by LR desc across segments after ledger dedup (news_id 12d + brand 7d incl also_shown) + body-verify (all concrete Rs). Category spread: detergent / confectionery / oral-care.
 #   tide LR7.03 fmcg_product_change (10rs cake weight 80g->140g, +60g extra), cadbury LR6.97 (report bucket fmcg_product_change but body = NEW LAUNCH: rs10 chocolate cake, 15pc box WS130 MRP150, rs20 margin -> represented as new_product_launch per "never force a launch into an arrow" rule), colgate LR6.73 Consumer Scheme (200+100=300g + rs35 brush free, MRP208 WS187 rs21 margin).
 #   DROPPED (brand within 7d, ledger): patanjali-dant-kanti/lifebuoy/my-fruit-jelly/surf-excel/dettol/parle(eclairs)/close-up/param-ghee. Backups not used: dermi-cool LR6.37 (Consumer), navchetan chai LR5.60 (product_change), solar surf LR5.49 (coupon-inside, vague) - edged out by LR + category spread.
 dict(i=4, eyebrow="FMCG", label="प्रोडक्ट बदलाव", stripe=BLACK, headline="टाइड डिटर्जेंट केक",
   price=f'<span class="wt">80g</span><span class="arrow">&#8594;</span><span class="wt">140g</span>',
   sub='₹10 बिक्री वाला टाइड डिटर्जेंट केक अब 80g की जगह 140g का — 60g एक्स्ट्रा माल, कीमत वही ₹10 · <b class="delta">60g ज्यादा</b>',
   l1="बदलाव", v1="₹10 वाले टाइड केक का वजन 80g से बढ़ाकर 140g (60g एक्स्ट्रा), कीमत वही",
   l2="फायदा", v2="वही ₹10 में ग्राहक को ज्यादा माल — वैल्यू बढ़ी, बिक्री तेज"),
 dict(i=5, eyebrow="FMCG", label="नया प्रोडक्ट लॉन्च", stripe=LAUNCH_AMBER, headline="कैडबरी केक",
   price=f'<span class="newtag" style="background:{LAUNCH_AMBER}">नया</span><span class="mrp">MRP ₹10</span>',
   sub='कैडबरी का नया ₹10 वाला चॉकलेट केक; 15 पीस बॉक्स होलसेल ₹130 (MRP ₹150), बॉक्स पर ₹20 मुनाफा · <b class="delta">₹20 मुनाफा</b>',
   l1="नया क्या", v1="कैडबरी ने ₹10 वाला चॉकलेट केक लॉन्च किया; 15 पीस बॉक्स ₹130 में",
   l2="फायदा", v2="₹150 MRP बॉक्स पर ₹20 मुनाफा; जाना-पहचाना ब्रांड, बिक्री तेज"),
 dict(i=6, eyebrow="FMCG", label="ग्राहक ऑफर", stripe=SCHEME_BLUE, headline="कोलगेट डेंटल क्रीम",
   price=f'<span class="offer" style="background:{SCHEME_BLUE}">300g + ₹35 ब्रश फ्री</span>',
   sub='कोलगेट 300g (200+100g) के साथ ₹35 वाला टूथब्रश फ्री; MRP ₹208, होलसेल ₹187, ₹21 मार्जिन · <b class="delta">₹21 मार्जिन</b>',
   l1="ऑफर", v1="300g कोलगेट पेस्ट (200+100g एक्स्ट्रा) के साथ ₹35 का टूथब्रश बिल्कुल फ्री",
   l2="ग्राहक को", v2="₹208 MRP का पैक ₹187 होलसेल में — ₹21 मार्जिन, ग्राहक को ज्यादा वैल्यू"),
 # News (trending_news) - in-house 6oct Pan India Trending 1 (241baab7): RBI MPC repo decision tomorrow (7 Oct). Non-bait, policy/market-impact, concrete numbers (repo 5.25% -> possible 5.50%), universal kirana loan relevance. News=1 base. (TN2 Vadilal-Parle Hide&Seek launch = weaker/no-number -> not used; CGTMSE scheme kept as backup but recent run already scheme-heavy, favoured the timely RBI angle.)
 dict(i=7, label="ट्रेंडिंग न्यूज़", stripe=BLACK, headline="RBI का फैसला",
   price='<span class="news">रेपो दर पर फैसला कल</span>',
   sub='RBI की ब्याज दर समिति का फैसला कल 7 अक्टूबर; रेपो 5.25%, 0.25% बढ़कर 5.50% होने या स्थिर रहने का अनुमान · <b class="delta">कल फैसला</b>',
   l1="क्यों ज़रूरी", v1="रेपो बढ़ी तो बैंक कारोबारी कर्ज व ओवरड्राफ्ट महंगे करेंगे; त्योहारी कर्ज भारी पड़ेगा",
   l2="क्या करें", v2="त्योहारी स्टॉक का जरूरी कर्ज अभी तय दर पर ले लें; दर बढ़ी तो किस्त भारी"),
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
