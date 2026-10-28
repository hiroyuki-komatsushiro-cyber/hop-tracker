"""
説明文からのホップ抽出(hop_text.py)の回帰テスト。実際の商品説明から取った例で、拾えるべきものと
拾ってはいけないもの(シトラス/フローラル/クリスタルモルト/地名/比較文など)を確認する。

hop_text.py の辞書やルールを変えたら必ず実行すること:
    python scripts/test_hop_text.py
(失敗があれば終了コード1。週次/月次のワークフローには組み込んでいない)
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import update_products as up  # noqa: E402

CHART = up.known_hop_names()


def extract(text):
    return up.hops_from_description(text, CHART)


# (説明文, 期待するホップ)  ※実在の商品説明から抜粋(出典の商品はコメント)
POSITIVE = [
    ("シトラとアマリロホップを使用した、力強いNew England IPA。華やかなシトラスとトロピカルフルーツのアロマが広がります。",
     ["Citra", "Amarillo"]),  # Heavy Riff Daisy Glaze
    ("ネルソン、リワカ、シムコーホップを使用し、白ブドウやパッションフルーツを思わせる華やかな果実味に、粘り気のある樹脂感が重なります。",
     ["Nelson Sauvin", "Riwaka", "Simcoe"]),  # Piha Break
    ("ホップにシトラ、モザイク、エルドラド、ネルソンを使用したHazy Pale Ale。",
     ["Citra", "Mosaic", "El Dorado", "Nelson Sauvin"]),  # Vertere UNLEARN
    ("更にエルドラード、モトゥエカ、メリディアン、そしてシムコーといったフレッシュなホップでドライホップを加えました。",
     ["El Dorado", "Motueka", "Meridian", "Simcoe"]),  # Jester King Das Wunderkind
    ("Bière de Coupage is young farmhouse ale cut with mature SPON, then dry hopped with organic Fuggle and Perle from The Oregon Hophouse.",
     ["Fuggle", "Perle"]),  # Jester King Biere de Coupage (英語段落)
    ("T90、クライオ、ダイナブースト、リキッド・ルプリンとさまざまな形態のモザイクをはじめ、シトラ、シトラ・クライオ、チヌーク、シムコーを贅沢に使用。",
     ["Mosaic", "Citra", "Citra Cryo", "Chinook", "Simcoe"]),  # Complicated Shirt(ホップ語が文中に無くても目立つ名前は拾う)
    ("ホップ：Citra, Cascade, Chinook", ["Citra", "Cascade", "Chinook"]),
    ("Mosaic、Apollo、Columbusホップを贅沢に使用", ["Mosaic", "Apollo", "Columbus"]),  # Faction Pale
    ("Mosaic と El Doradoホップ由来のマンゴーやパイナップルのようなトロピカルフルーツを思わせる味わい。", ["Mosaic", "El Dorado"]),
    ("Cashmere, Mandarina Bavaria, Amarilloホップの柑橘やトロピカルフルーツのような味わいが際立つ", ["Cashmere", "Mandarina Bavaria", "Amarillo"]),
    ("希少な実験的ホップHBC 1134を使用したイタリアンスタイル・ピルスナー。", ["HBC 1134"]),
    ("ニュージーランド産のネクタロンを中心に、人気の高いモザイク（通常版とクライオ）を使用しました", ["Nectaron", "Mosaic"]),
    ("リワカとモザイクをダブルドライホップでたっぷり使用し、ジューシーなグアバ、完熟パイナップルの風味が広がります。", ["Riwaka", "Mosaic"]),
    ("モザイクとヴィクシークレットホップを使ったCold IPA。", ["Mosaic", "Vic Secret"]),
    ("ワイメアホップのみを使用した、フレッシュで華やかな味わいが魅力の一杯。", ["Waimea"]),
    ("そこにザーツホップ由来のスパイシーなキレが加わり", ["Saaz"]),
    ("フランスのアルザス地方で栽培されている最高級のアロマホップ、フレンチ・ストリッセルシュパルトを組み合わせています。", ["Strisselspalter"]),
    ("ドルシータ、シトラ、モザイクホップを限界まで投入！", ["Dolcita", "Citra", "Mosaic"]),  # Belching Beaver
    ("マニリタ、センテニアル、ネクタロン、エルドラドの新たなホップとモルトの組み合わせが生み出す", ["Manilita", "Centennial", "Nectaron", "El Dorado"]),
    ("シトラ、ギャラクシー、クラッシュという強力な3種のホップを贅沢に使用したHazy Double IPAです。", ["Citra", "Galaxy", "Krush"]),
    ("クラッシュ・クライオ、リワカ、ストラータ、カスケードホップを使用し、ピルスナーモルトを組み合わせています。",
     ["Krush Cryo", "Riwaka", "Strata", "Cascade"]),
    # --- カタカナ表記(ユーザー質問 2026-10-28: Citra→シトラ、Mosaic→モザイク。辞書にある表記は拾える) ---
    ("シトラを使用したIPA", ["Citra"]),
    ("モザイクとシトラ", ["Mosaic", "Citra"]),
    ("シトラホップとモザイクホップをたっぷり使用", ["Citra", "Mosaic"]),
    ("ホップはシトラ、モザイク、シムコー", ["Citra", "Mosaic", "Simcoe"]),
    ("ホップはベルマ、シトラ、モザイクを使用", ["Belma", "Citra", "Mosaic"]),
    ("テトナングホップのスパイシーな香りと、スタイリアンゴールディングホップ由来の穏やかな苦味", ["Tettnanger", "Savinjski Golding"]),
    ("エクイノックスホップを使用したIPA", ["Ekuanot"]),
    ("ペッコ、アデーナ、マニリタホップを使用", ["Pekko", "Adeena", "Manilita"]),
    ("リバティホップとオパールホップを使用", ["Liberty", "Opal"]),  # 日常語と同形の名前は「…ホップ」と続くときだけ
]

# 拾ってはいけない例(すべて空リストが期待値)
NEGATIVE = [
    "ジューシーなシトラスのアロマに、完熟したストーンフルーツの味わいが重なります。",  # シトラス=citrus
    "松の木と柑橘の力強いアロマ。シエラネバダが誇るダンクフルIPA。",  # シエラ(Sierra)
    "トウモロコシの穀物感がアクセントとなったラガー。フローラルなアロマ。",  # フローラル=floral
    "ナッツの風味と、僅かなスモークモルト、クリスタルモルト、そしてチョコレートのべースが特徴です。",  # crystal malt
    "コロラド州の小さな町パリセード産のフレッシュなピーチを使用したサワーエール。",  # 地名
    "ノーブルホップによるフローラルで爽快なアロマに香ばしいパンのようなニュアンス。",  # 品種名なし
    "Waves of pineapple, melon, and citrus cascade across the palate leaving trails of tropical punch.",  # 動詞のcascade
    "Summer Sapling is a simple yet elegant hoppy Belgian-style blonde brewed last summer.",  # Summer(ホップ名と同形)
    "Cascade、Chinook、Centennialホップを使用したクラシックな苦味のTower 10 IPAとは対照的に、トロピカルなアロマを前面に押し出した。",  # 比較文
    "驚くほどクリスプで、ドイツにあるSeitz Familyホップのハーバルな香りと絶妙に調和します。",  # 農家名
    "Cascade Brewing's barrel-aged sour is blended with hops grown nearby.",  # ブルワリー名
    "カスケード山脈で育ったホップをふんだんに使っています。",  # 地名
    "レシピには全てクライオ系のホップを使用し、その95％を煮沸後に加えることで", # 品種名なし
    "ホッピーなオレンジジュースを絞ったかのような一杯です。",  # ホッピー(風味)
    "Troy氏と初めて会ったのは、Moonlight Brewingの伝説的なホップ畑で、約20年前のことでした。",  # ホップ畑
    "ジューシーなシトラスのような香りと、モザイクタイルのラベル。",  # citrus / mosaic tile
    "オーロラの下で飲みたくなる、リバティ号のような自由なビール。",  # ホップ語が無い一般名詞
    "プログレスバーのように少しずつ苦味が増していく。",  # 一般名詞
    "「オーロラのようにホップアロマが輝く」新サンディエゴスタイルIPA",  # 比喩のオーロラ(実例: Karl Strauss Aurora Hoppyalis)
    "ホップにはリバティ号のような自由さがある。",  # 日常語のリバティ(ホップ語は同じ文にあるが名前の直後に「ホップ」が無い)
]


def main():
    failures = []
    for text, expected in POSITIVE:
        got = extract(text)
        if got != expected:
            failures.append(f"POSITIVE expected {expected} got {got}: {text[:60]}")
    for text in NEGATIVE:
        got = extract(text)
        if got:
            failures.append(f"NEGATIVE expected [] got {got}: {text[:60]}")
    total = len(POSITIVE) + len(NEGATIVE)
    if failures:
        print(f"FAILED {len(failures)}/{total}")
        for f in failures:
            print("  " + f)
        sys.exit(1)
    print(f"OK: {total} cases passed ({len(POSITIVE)} positive, {len(NEGATIVE)} negative)")


if __name__ == "__main__":
    main()
