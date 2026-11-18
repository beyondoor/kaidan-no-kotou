# 階段の孤島 ― 板橋区（PLATEAU）

停電や浸水のとき、階段しか残らない上の階の高齢者が、どの建物にいそうかを数えるWebツールです。

## 動かし方（Mac）
1. ターミナルを開く
2. 次の2行を貼り付けて Enter
   ```
   cd ~/Documents/応募成果物/階段の孤島_デモ
   python3 -m http.server 8000
   ```
3. Chromeで http://localhost:8000 を開く（止めるときはターミナルで Control＋C）

※ index.html を直接ダブルクリックすると、data.json を読めずに動きません。上の手順で開いてください。
※ 3D表示の部品（deck.gl）と文字（Noto Sans JP）はインターネットから読み込みます。

## キー操作
- h：パネルを隠して地図だけにする（撮影用）
- b：高島平２丁目の例の1棟の断面を出す
- パネルの「自動デモ」：字幕つきで約2分、自動で進む（動画の録画用）

## ファイル
- index.html：画面と計算（ブラウザの中で全部計算する）
- data.json：板橋区の共同住宅21,476棟と周りの建物の形・属性、町丁目の人口
- prep.py：data.json を作るPythonのスクリプト
  `python3 prep.py itabashi_plateau_buildings.json itabashi_age_by_chome.csv data.json`

## データと出典
- 国土交通省 Project PLATEAU 板橋区 建築物モデル（2025年度、LOD1、3D Tiles）CC BY 4.0 を加工
- 板橋区「令和7年版 板橋区の統計」（住民基本台帳 令和8年1月1日現在、国勢調査 令和2年）
- 人数はすべて推定です。仮定は画面の下に書いてあります。
