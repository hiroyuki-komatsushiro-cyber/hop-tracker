"""
説明文からのホップ品種の抽出 (scripts/hop_text.py)

スペック欄(ABV/ホップ等)にホップの記載が無い商品でも、説明文に品種名が書かれていることがある
(例: 「シトラとアマリロホップを使用した、力強いNew England IPA」)。それを拾って hops に追記する。
2026-10-28、ユーザー指示「ホップ成分に記載がなくても、説明に記載があれば成分として追記する」で導入。

方針は「誤抽出ゼロを優先」。ホップ名を捏造しない原則(README_MIGRATION.md 更新ルール)を守るため、
  - 品種名は辞書(アロマチャートの名前+日本語表記のカタカナ辞書)に載っているものだけ
  - カタカナ名は前後にカタカナが続く場合は除外(「シトラス」=citrus、「フローラル」=floral、「シエラ」ネバダ等の誤検出防止)
  - 一般名詞と同形の名前(Cascade/Summit/Target/Summer/クラッシュ等)は、ホップを指す語(ホップ/hops/dry hop等)が
    同じ文にあるときだけ採用。英語表記はさらに「大文字小文字が一致」かつ「hopに隣接 or 同じ文に別の確実なホップ名がある」を要求
  - ブルワリー名(Cascade Brewing)・地名(カスケード山脈、Mt. Hood以外のMount)は除外
で運用する。精度は 2026-10-28 時点の実データ(商品896件)で検証済み(README_MIGRATION.md参照)。
辞書にない新しい日本語表記は拾えない(取りこぼし=ホップ空のまま)ので、月次監査(audit_catalog.py)で人間/Claudeが確認する。
"""
import re

# --- 区切り・ホップを指す語 ---------------------------------------------------------------
# 「ホッピー」「hoppy」は含めない(ホップの"風味が強い"の意味で、品種の記載ではない)
HOP_MARKER_RE = re.compile(r"ホップ|ホッピング|\bhops?\b|\bhopped\b|\bhopping\b|dry[- ]?hop", re.I)
SPLIT_RE = re.compile(r"[。！？!?\n；;]+|(?<=[A-Za-z0-9\)])\.\s+")

# 他の銘柄との比較で出てくるホップ(例: 「Cascade、Chinook、Centennialホップを使用したTower 10 IPAとは対照的に」)は
# この商品のホップではないので、比較を示す語がある文は読み飛ばす
CONTRAST_RE = re.compile(r"対照的|とは異なり|とは違い|に対し|と比べ|に比べ|unlike|in contrast|compared (?:to|with)|versus", re.I)

KATA = "ァ-ヶー"

# --- 日本語(カタカナ)表記 -> 英語名 ------------------------------------------------------------
# 目立つ固有名: 文中のどこに出ても採用(前後にカタカナが続く場合は除外)
JP_DISTINCT = {
    "アマリロ": "Amarillo", "アタナム": "Ahtanum", "アザッカ": "Azacca", "アザカ": "Azacca",
    "センテニアル": "Centennial", "チヌーク": "Chinook", "チヌック": "Chinook", "シトラ": "Citra",
    "エルドラド": "El Dorado", "エルドラード": "El Dorado", "アイダホ7": "Idaho 7", "アイダホセブン": "Idaho 7",
    "ジャリロ": "Jarrylo", "ローラル": "Loral", "モザイク": "Mosaic", "マウントフッド": "Mt. Hood",
    "ラカウ": "Rakau", "リワカ": "Riwaka", "サブロ": "Sabro", "シムコー": "Simcoe", "シムコ": "Simcoe",
    "ソラチエース": "Sorachi Ace", "ストラータ": "Strata", "タルス": "Talus",
    "ヴィクシークレット": "Vic Secret", "ヴィックシークレット": "Vic Secret", "ビックシークレット": "Vic Secret",
    "ビクシークレット": "Vic Secret", "ウィラメット": "Willamette", "ゼウス": "Zeus", "ザッパ": "Zappa",
    "ハラタウブラン": "Hallertau Blanc", "ザーツ": "Saaz", "ザーズ": "Saaz", "ファグル": "Fuggle",
    "モトゥエカ": "Motueka", "モツエカ": "Motueka", "モテューカ": "Motueka", "モトエカ": "Motueka", "モチュエカ": "Motueka",
    "ネルソンソーヴィン": "Nelson Sauvin", "ネルソンソービン": "Nelson Sauvin", "ネルソン・ソーヴィン": "Nelson Sauvin",
    "ネルソン・ソービン": "Nelson Sauvin", "ネルソンソーバン": "Nelson Sauvin",
    "ネクタロン": "Nectaron", "ワイメア": "Waimea", "サザンクロス": "Southern Cross", "コハツ": "Kohatu",
    "ワカトゥ": "Wakatu", "エクアノット": "Ekuanot", "マンダリーナバヴァリア": "Mandarina Bavaria",
    "マンダリーナ・バヴァリア": "Mandarina Bavaria", "ヒュルメロン": "Huell Melon", "レモンドロップ": "Lemondrop",
    "ルミノーサ": "Luminosa", "ドルシータ": "Dolcita", "ドルチータ": "Dolcita", "ドルチタ": "Dolcita",
    "モウテレ": "Moutere", "ムーテレ": "Moutere", "マニリタ": "Manilita", "ピーチャリン": "Peacharine",
    "ストリッセルシュパルト": "Strisselspalt", "パシフィカ": "Pacifica", "ワイイティ": "Wai Iti",
    "ファルコナーズフライト": "Falconer's Flight",
}
# 一般名詞・地名・人名と同形の名前: ホップを指す語が同じ文にあるときだけ採用
JP_CONTEXT = {
    "ブラボー": "Bravo", "カスケード": "Cascade", "コロンバス": "Columbus", "コロンブス": "Columbus",
    "クリスタル": "Crystal", "クラスター": "Cluster", "ギャラクシー": "Galaxy", "グレイシャー": "Glacier",
    "クラッシュ": "Krush", "ロータス": "Lotus", "ナゲット": "Nugget", "パリセード": "Palisade", "サミット": "Summit",
    "ウォリアー": "Warrior", "ネルソン": "Nelson Sauvin", "エニグマ": "Enigma", "トパーズ": "Topaz",
    "カシミア": "Cashmere", "カリプソ": "Calypso", "カリスタ": "Callista", "コメット": "Comet", "デルタ": "Delta",
    "マグナム": "Magnum", "メリディアン": "Meridian", "ミレニアム": "Millennium", "アポロ": "Apollo",
    "ガレナ": "Galena", "ピルグリム": "Pilgrim", "ターゲット": "Target", "チャレンジャー": "Challenger",
    "ペルレ": "Perle", "ニューポート": "Newport", "ポラリス": "Polaris",
    "ヘリオス": "Helios", "ホライズン": "Horizon", "パイロット": "Pilot", "サルタナ": "Sultana",
    "タンジェール": "Tangier", "ヴィスタ": "Vista", "ザンバ": "Zamba", "デナリ": "Denali",
    "ヴァンガード": "Vanguard", "スターリング": "Sterling", "エラ": "Ella",
}
# 前後にカタカナが続かなければ採用する語に付く接尾「ホップ」(例: シトラホップ)
JP_SUFFIX_OK = "(?:ホップ)?"
# 地名・ブルワリー名の一部になる場合の除外(例: カスケード山脈、ウィラメットバレー)
JP_EXCLUDE_AFTER = re.compile(r"^(?:山脈|バレー|ブルーイング|ブルワリー|ビール)")

# --- 加工品の表記 -------------------------------------------------------------------------
FORM_JP = {"クライオ": "Cryo", "ルプマックス": "Lupomax", "インコグニート": "Incognito", "スペクトラム": "Spectrum",
           "クアンタム": "Quantum", "プリズマ": "Prysma", "ハイパーブースト": "HyperBoost", "ルポコア": "Lupocore",
           "アブストラックス": "Abstrax", "ダイナブースト": "Dynaboost", "キーフ": "Kief"}
FORM_EN = ["Cryo", "CGX", "Lupomax", "Incognito", "Spectrum", "Quantum", "Prysma", "HyperBoost", "Lupocore",
           "Abstrax", "Dynaboost", "Kief"]
_FORM_JP_ALT = "|".join(re.escape(k) for k in sorted(FORM_JP, key=len, reverse=True))
_FORM_RE = re.compile(
    r"^(?:ホップ)?[・\s\-/]*(" + "|".join(sorted(list(FORM_JP) + FORM_EN, key=len, reverse=True)) + r")(?![A-Za-z])", re.I)

# --- 英語表記 ----------------------------------------------------------------------------
# 一般的な英単語・地名・人名と同形: ホップ語が同じ文にあり、大文字小文字が一致し、
# (hop/hopsに隣接 または 同じ文に確実なホップ名がある)ときだけ採用
EN_COMMON = {
    "Cascade", "Summer", "Crystal", "Target", "Pilot", "Delta", "Summit", "Progress", "Liberty", "Triumph", "Horizon",
    "Opal", "Olympic", "Sterling", "Vanguard", "Challenger", "Comet", "Apollo", "Cluster", "Glacier", "Magnum",
    "Newport", "Galaxy", "Columbus", "Chinook", "Nugget", "Warrior", "Lotus", "Vista", "Zappa", "Bravo", "Centennial",
    "Mosaic", "Strata", "Talus", "Loral", "Calypso", "Meridian", "Southern Cross", "Sultana", "Enigma", "Topaz", "Sylva", "Helios", "Contessa", "Aurora",
    "Vera", "Millennium", "Phoenix", "Polaris", "Pilgrim", "Premiant", "Santiam", "Saphir", "Sladek", "Sovereign",
    "Spalter", "Super Pride", "Tahoma", "Tangier", "Triskel", "Zamba", "Ella", "Ernest", "Helga", "Herkules", "Kazbek",
    "Lorien", "Mistral", "Moutere", "Mt. Hood", "Mt. Rainier", "Northdown", "Northern Brewer", "Pekko", "Perle",
    "Fuggle", "Challenger", "Bobek", "Celeia", "Audacia", "Aramis", "Adeena", "Belma", "Delta", "Elani", "Erebus",
    "Endeavour", "Equinox", "First Gold", "Progress", "Zythos Blend", "Pink Boots Blend", "Veterans' Blend",
}
# 英語表記で、ブルワリー名の一部になる場合の除外
EN_EXCLUDE_AFTER = re.compile(r"^\s*(?:Brewing|Brewery|Brewers|Brewhouse|Beer Co|Barrel House|Ales\b|Cellars)", re.I)

# 「Hop」の表記ゆれで、辞書(チャート名)と別名の英語表記
EN_ALIASES = {"Nelson Sauvin": ["Nelson Sauvign"], "Mandarina Bavaria": ["Mandarina"], "Hallertau Blanc": ["Hallertauer Blanc"],
              "Strisselspalter": ["Strisselspalt"], "Idaho 7": ["Idaho7"], "Vic Secret": ["Vic's Secret"]}


def _chart_bases(chart_names):
    """チャート名 -> 本文の検索に使う基本名(丸括弧の供給元表記と加工品の接尾を除く)"""
    names = set(chart_names)
    bases = set()
    for n in names:
        b = re.sub(r"\s*\(.*?\)$", "", n)
        m = re.match(r"^(.*?)\s+(Cryo|CGX|Lupomax|Incognito|Spectrum|Quantum|Prysma|HyperBoost|Lupocore|Abstrax|Dynaboost|Kief)$", b)
        if m and m.group(1) in names:
            b = m.group(1)
        bases.add(b)
    return bases


def _spans(seg, chart_names, bases):
    """文中のホップ名の出現位置: (start, end, canonical, needs_context, common_en)"""
    out = []
    # 日本語(カタカナ)
    for table, needs_ctx in ((JP_DISTINCT, False), (JP_CONTEXT, True)):
        for key, canon in table.items():
            for m in re.finditer(r"(?<![%s])%s%s(?:(?=%s)|(?![%s]))" % (KATA, re.escape(key), JP_SUFFIX_OK, _FORM_JP_ALT, KATA), seg):
                tail = seg[m.end():]
                if JP_EXCLUDE_AFTER.match(tail):
                    continue
                # 「ホップ」を含めてマッチさせたので、名前の終端はキー末尾
                end = m.start() + len(key)
                out.append((m.start(), end, canon, needs_ctx, False))
    # 英語
    for base in bases:
        pats = [base] + EN_ALIASES.get(base, [])
        for p in pats:
            common = base in EN_COMMON
            flags = 0 if common else re.I
            for m in re.finditer(r"(?<![A-Za-z])%s(?![A-Za-z])" % re.escape(p), seg, flags):
                if EN_EXCLUDE_AFTER.match(seg[m.end():]):
                    continue
                # 「Mt. Hood」以外の "Mount X" など、人名・地名の一部は除く
                if re.search(r"(?:Mount|Mt\.?|Lake|Fort|Port|Cape)\s+$", seg[:m.start()]) and not base.startswith("Mt."):
                    continue
                out.append((m.start(), m.end(), base, True if common else False, common))
    return out


def extract_hops_from_text(text, chart_names, normalize=lambda s: s):
    """説明文 -> 記載されているホップ名(アロマチャートの表記、出現順、重複なし)。
    chart_names: アロマチャートの品種名集合(update_products.known_hop_names())。
    normalize: 表記ゆれ正規化(update_products.normalize_hop)。"""
    if not text:
        return []
    chart_names = set(chart_names)
    bases = _chart_bases(chart_names)
    result = []
    for seg in SPLIT_RE.split(text):
        if not seg.strip():
            continue
        if CONTRAST_RE.search(seg):
            continue
        has_marker = bool(HOP_MARKER_RE.search(seg))
        spans = _spans(seg, chart_names, bases)
        if not spans:
            continue
        # 確実なホップ名(文脈不要のもの)がこの文にあるか
        sure_in_seg = any(not needs_ctx for (_, _, _, needs_ctx, _) in spans)
        # 長い一致を優先して重なりを除く(例: Nelson Sauvin と Nelson)
        spans.sort(key=lambda s: (s[0], -(s[1] - s[0])))
        kept, last_end = [], -1
        for s in spans:
            if s[0] >= last_end:
                kept.append(s)
                last_end = s[1]
        # ホップ語のある文に品種名が2つ以上並ぶなら、一般名詞と同形のもの(Fuggle and Perle等)も品種の列挙とみなす
        listing = len({k[2] for k in kept}) >= 2
        for start, end, canon, needs_ctx, common_en in kept:
            if needs_ctx and not has_marker:
                continue
            if common_en:
                near_hop = re.search(r"\bhops?\b|hopped|dry[- ]?hop", seg[max(0, start - 14):end + 14], re.I)
                if not (near_hop or sure_in_seg or listing):
                    continue
            name = canon
            fm = _FORM_RE.match(seg[end:])
            if fm:
                form = FORM_JP.get(fm.group(1)) or next((f for f in FORM_EN if f.lower() == fm.group(1).lower()), None)
                if form and f"{canon} {form}" in chart_names:
                    name = f"{canon} {form}"
            name = normalize(name)
            if name and name not in result:
                result.append(name)
    return result
