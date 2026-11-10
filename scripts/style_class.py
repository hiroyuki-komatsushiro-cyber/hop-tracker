"""
スタイルの細分類とアルコール度数の帯 (scripts/style_class.py)

製品別ホップ成分表(docs/index.html)の絞り込み用。商品の `style`(収集元ごとの自由記述。2026-11時点で384種類の
表記ゆれ)を、7つの大分類・36の細分類に振り分け、`abv`(例: "6.5%")を数値と度数帯にする。
build_html.py が画面を作るときにだけ使い、products.json 自体は変更しない(ルールを直せば全商品に反映される)。

方針:
  - 1商品=1つの細分類(排他)。優先順位は RULES の並び順(上から最初に一致したもの)
  - 分類の対象は style 欄の文字列。ただしセット商品は style 欄が中の1本の値になっているので、商品名で見分ける
  - どれにも当てはまらないものは「その他のビール」に入れ、build_html.py のログに出す(新しい表記を見つけたら
    RULES に足して test_style_class.py に例を追加する)
  - Python標準ライブラリのみ(GitHub ActionsのPython 3.11で動く)
"""
import re

# (大分類キー, 表示名, [(細分類キー, 表示名), ...])。画面の並び順もこの順
GROUPS = [
    ("ipa", "IPA系", [
        ("ipa_hazy", "ヘイジーIPA"),
        ("ipa_wc", "ウエストコースト・NW IPA"),
        ("ipa_plain", "IPA（アメリカン・NZ・指定なし）"),
        ("ipa_double", "ダブル・トリプルIPA"),
        ("ipa_session", "セッションIPA"),
        ("ipa_cold_brut", "コールド・ブリュットIPA"),
        ("ipa_color", "ブラック・レッド・ベルジャンIPA"),
        ("ipa_sour", "サワー・ミックスカルチャーIPA"),
        ("ipa_special", "フルーツ・副原料・特殊IPA"),
    ]),
    ("ale", "ペールエール・エール系", [
        ("pale_american", "アメリカンペールエール"),
        ("pale_hazy_nz", "ヘイジー・NZペールエール"),
        ("ale_blonde", "ブロンド・ゴールデンエール"),
        ("ale_amber", "アンバー・レッドエール"),
        ("ale_brown_english", "ブラウン・英国系エール"),
    ]),
    ("lager", "ラガー・ピルスナー系", [
        ("lager_pils", "ピルスナー"),
        ("lager_hoppy", "ホッピーラガー・IPL"),
        ("lager_light", "ラガー（ヘレス・アメリカン・ライト）"),
        ("lager_mexican", "メキシカン・ラテンラガー"),
        ("lager_dark_amber", "ダーク・アンバー・ウィーン系ラガー"),
        ("lager_special", "スモーク・ライス・和風ラガー"),
    ]),
    ("wheat_belgian", "小麦・ベルギー・セゾン系", [
        ("wheat", "小麦ビール（ヘフェ・ウィート）"),
        ("bel_wit", "ヴィット"),
        ("bel_ale", "ベルジャンエール"),
        ("bel_strong", "トリペル・クアッド・ストロング"),
        ("sai_farm", "セゾン・ファームハウス"),
    ]),
    ("sour", "サワー・ワイルド系", [
        ("sour_fruit", "サワーエール（フルーツ・ケトル）"),
        ("sour_gose", "ゴーゼ・ベルリナーヴァイセ"),
        ("sour_wild", "ワイルド・ランビック・ブレット"),
    ]),
    ("dark", "スタウト・ポーター・ストロング系", [
        ("dark_stout", "スタウト"),
        ("dark_porter", "ポーター"),
        ("dark_imperial", "インペリアル・樽熟成スタウト/ポーター"),
        ("dark_strong", "バーレイワイン・ストロングエール"),
    ]),
    ("other", "サイダー・ミード・セット・その他", [
        ("cider", "サイダー"),
        ("mead", "ミード"),
        ("set_mix", "セット・詰め合わせ"),
        ("other_beer", "その他のビール"),
    ]),
]

SUB_TO_GROUP = {sub: g for g, _, subs in GROUPS for sub, _ in subs}
SUB_LABEL = {sub: label for _, _, subs in GROUPS for sub, label in subs}
GROUP_LABEL = {g: label for g, label, _ in GROUPS}
FALLBACK = "other_beer"

# 度数帯: (キー, 表示名, 下限以上, 上限未満)。度数が読めない商品は "abv_unknown"
ABV_BANDS = [
    ("abv_lt5", "〜4.9%", 0.0, 5.0),
    ("abv_5", "5.0〜5.9%", 5.0, 6.0),
    ("abv_6", "6.0〜6.9%", 6.0, 7.0),
    ("abv_7", "7.0〜7.9%", 7.0, 8.0),
    ("abv_8", "8.0〜9.9%", 8.0, 10.0),
    ("abv_10", "10%〜", 10.0, 1000.0),
]
ABV_UNKNOWN = ("abv_unknown", "度数不明")

# セット商品は style 欄が「中の1本」の値になっているので、商品名で見分ける
SET_NAME_RE = re.compile(r"セット|パック|詰め合わせ|詰合せ|飲み比べ|アソート|\d+\s*本入|[（(]\s*\d+\s*本\s*[）)]|mix\s*pack|variety|\bset\b", re.I)

# 細分類のルール。上から順に評価し、最初に一致したものを採用する(順序が意味を持つ)
# 評価対象は _norm() で正規化した style 文字列(小文字・ハイフンや記号を空白に)
RULES = [
    ("set_mix", r"^(mix|variety pack)$"),
    ("cider", r"\bcider\b|\bcidre\b|\bperry\b"),
    ("mead", r"\bmead\b"),
    # --- ダーク・ストロング系(ベルジャンのストロング/クアッドより先に。"Blend of Stout, Quadrupel, and Barleywine"対策)
    ("dark_strong", r"barley ?wine|wheat ?wine|old ale|scotch ale|wee heavy|american strong ale"),
    ("dark_imperial", r"(stout|porter).*(imperial|russian|barrel|bourbon|double|\bba\b|aged)|(imperial|russian|barrel aged|bourbon barrel|\bba\b|double barrel).*(stout|porter)"),
    ("dark_stout", r"stout"),
    ("dark_porter", r"porter"),
    # --- サワー・ワイルド系(IPA/セゾンより先に。"Sour IPA""Sour Saison"を正しく振り分けるため)
    ("sour_gose", r"gose|berliner|lichtenhainer"),
    ("ipa_sour", r"sour.*(ipa|dipa|tipa)|(mixed culture|brux|brett) ipa"),
    ("sour_wild", r"lambic|wild ale|mixed culture|foeder|brett|appalachian|barrel aged sour|oak aged.*wild|coupage|\bspon\b"),
    ("sour_fruit", r"sour"),
    # --- ホッピーラガー(IPLはIPAではなくラガー)
    ("lager_hoppy", r"\bipl\b|\btipl\b|hoppy lager|west coast lager"),
    # --- IPA系(ダブル > セッション > コールド/ブリュット > 色付き > 特殊 > ヘイジー > ウエストコースト > その他)
    ("ipa_double", r"\bd ?ipa\b|dipa|tipa|iipa|\b(double|triple|imperial)\s+(?:[a-z]+\s+)?(?:\w*ipa|india)"),
    ("ipa_session", r"session.*(ipa|hazy|ale)"),
    ("ipa_cold_brut", r"cold ipa|brut ipa"),
    ("ipa_color", r"black ipa|cascadian|red ipa|belgian ipa|rye ipa|brown ipa|white ipa"),
    ("ipa_special", r"(fruit|milkshake|spruce|terpene|cbd|oat|kveik|fresh hop|banana|wheat).*ipa|ipa.*(fruit|milkshake|terpene)|\boat cream\b"),
    ("ipa_hazy", r"(hazy|neipa|ne style|northeast|new england|murky|juicy|milky|tropical|turbid).*(ipa|india)|neipa"),
    ("ipa_wc", r"(west coast|\bwc\b|san diego|northwest).*(ipa|india)|nw ?ipa"),
    ("ipa_plain", r"ipa|india pale"),
    # --- ベルジャン・小麦・セゾン
    ("bel_wit", r"\bwit\b|witbier|white ale|belgian.*wheat"),
    ("bel_strong", r"tripel|quad|dubbel|belgian.*strong|strong dark|abbey"),
    ("bel_ale", r"belgian"),
    ("sai_farm", r"saison|saizon|saiosn|farmhouse|grisette|biere de garde"),
    ("wheat", r"wheat|weizen|hefe|weiss"),
    # --- ラガー(ペールエールの "Pale Lager" より先に)。"unfiltered lager"が"red lager"に部分一致しないよう単語境界を付ける
    ("lager_pils", r"pils|bohemian"),
    ("lager_mexican", r"mexican|baja"),
    ("lager_special", r"smoked|rauch|\brice\b|japanese|hojicha|pseudo"),
    ("lager_dark_amber", r"\bdark lager\b|schwarz|\bvienna\b|\bamber lager\b|\bred lager\b|marzen|festbier|oktoberfest|\bbock\b|doppelbock|dunkel"),
    ("lager_light", r"lager|helles|american beer"),
    # --- ペールエール・エール系
    ("pale_hazy_nz", r"hazy pale|nz pale|new zealand pale|nz hazy|tdh"),
    ("ale_brown_english", r"english|british|bitter|\besb\b|\bmild\b|brown ale|german pale ale|norwegian pale|dark ale"),
    ("pale_american", r"pale ale|strong pale|\bapa\b|california pale|\bpale\b"),
    ("ale_amber", r"\bamber\b|red ale|irish red|altbier"),
    ("ale_blonde", r"blonde|blond|golden|honey ale|bolnde|kolsch|cream ale"),
]
_COMPILED = [(key, re.compile(pat)) for key, pat in RULES]


def _norm(s):
    s = (s or "").lower().replace("ö", "o").replace("ä", "a").replace("ü", "u").replace("è", "e").replace("é", "e")
    s = re.sub(r"[-_/,&()]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def classify_style(style, name=""):
    """(大分類キー, 細分類キー) を返す。どれにも当てはまらなければ FALLBACK(その他のビール)。"""
    if name and SET_NAME_RE.search(name):
        return SUB_TO_GROUP["set_mix"], "set_mix"
    text = _norm(style)
    for key, rx in _COMPILED:
        if rx.search(text):
            return SUB_TO_GROUP[key], key
    # style欄が「0」「Fruit」等で判断できないときだけ、商品名のサイダー/ミードで救う(例: "Plum Mead")
    name_text = _norm(name)
    for key in ("cider", "mead"):
        if re.search(dict(RULES)[key], name_text):
            return SUB_TO_GROUP[key], key
    return SUB_TO_GROUP[FALLBACK], FALLBACK


def parse_abv(abv):
    """"6.5%" -> 6.5。"-"や空は None。0以下も度数不明として扱う(データ上の穴埋め値)。"""
    m = re.search(r"(\d+(?:\.\d+)?)", abv or "")
    if not m:
        return None
    v = float(m.group(1))
    return v if v > 0 else None


def abv_band(v):
    if v is None:
        return ABV_UNKNOWN[0]
    for key, _, lo, hi in ABV_BANDS:
        if lo <= v < hi:
            return key
    return ABV_UNKNOWN[0]


def derive(product):
    """商品1件から画面用の派生値を作る: sg=大分類, ss=細分類, av=度数(数値)、ab=度数帯。"""
    sg, ss = classify_style(product.get("style", ""), product.get("name", ""))
    av = parse_abv(product.get("abv", ""))
    return {"sg": sg, "ss": ss, "av": av, "ab": abv_band(av)}


def tree_for_js():
    """画面に渡す分類表。groups: [[キー, 表示名, [[細分類キー, 表示名], ...]], ...]、abv: [[キー, 表示名], ...]"""
    return {
        "groups": [[g, label, [[s, sl] for s, sl in subs]] for g, label, subs in GROUPS],
        "abv": [[k, label] for k, label, _, _ in ABV_BANDS] + [list(ABV_UNKNOWN)],
    }
