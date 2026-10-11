# F1 2011 / UDS 診断と比較テスト

対象: Windows x64、日本版 `0004000000067B00`、上流ベース
`cf9068844820f819a6eabbeeeb6a70d546e3e85a`。
取得元: <https://github.com/AzaharPlus/AzaharPlus>。

## 既存ログで確認できたこと

このPCのログと Downloads の保存ログを、作業フォルダーの `evidence/` に退避した。
時刻は各エミュレータープロセスの起動からの秒数であり、PC間で直接比較しない。

| ログ | 時刻 | 観測 |
| --- | ---: | --- |
| 参加側 local-azahar_log.txt | 2575.877346 | ConnectToNetworkDeprecated |
| 同上 | 2575.941833 | connection sequence finished |
| 同上 | 2575.958215 | GetConnectionStatus |
| 同上 | 2582.947606 | ゲームから DisconnectNetwork。接続完了から 7.005773 秒 |
| ホスト download-azahar_log-1.txt | 4312.111262 | HandleDeauthenticationFrame |
| 同上 | 4312.124150 | SendToHLE: Destination address was 0 |

`HandleDeauthenticationFrame` は相手の MAC→ノードID 対応を消す。
したがって、その直後の送信で MAC が見つからないことは実装と整合する。
このエラーを最初の通信失敗の原因と断定する根拠はない。
別タイトル `000400000017FD00` の古い接続タイムアウトは、F1 の事象と分けて扱う。
既存の Debug ログは SendTo / PullPacket の成功や受信破棄を記録しないため、
ログに行がないだけで「送受信なし」とは判定できない。

## コード上で再現した不具合

`PullPacketHLE` の戻り値は `Common::Expected<int, ResultStatus>`。
成功時には受信したバイト数、失敗時にはエラーを持つ。
元の `PullPacket` は成功/失敗を確認せず `switch (ret.error())` を実行する。
`Expected` の値とエラーは union を共有するため、成功値をエラーとして読み、
9/10/11 バイトの受信を `RecvError_NotConnected` / `RecvError_BadNode` /
`RecvError_PacketSizeTooLarge` として処理する。C++ 上も非アクティブな union の読み取りになる。
HLE はその前に受信キューからパケットを取り出しているため、IPC で誤エラーが返ると、
そのパケットを次の Pull で再取得することもできない。

実際の `PullPacket` 関数本体、`Expected` 実装、`ResultStatus` enum を使う
`verify_pull_packet.py` で、正常長 0〜1478 と実エラー3種類を調べる。
IPC の読み書きと HLE 戻り値はテスト用スタブであり、ゲームや通信を再現する試験ではない。
表示される result=1001/1002 はスタブのエラー種別で、実機の完全な Result 値ではない。

**F1 が失敗時に 9/10/11 バイトを送った証拠は、既存ログにはまだない。**
そのため、これは確定したコード不具合と修正候補であり、F1 の原因確定・完走確認とは区別する。

## ビルド2種類

- `diagnostics-only`: ベースの通信処理に診断ログを追加。誤判定も元のまま。
- `pull-result-fix`: 同じ診断ログに、成功時に error() を読まない修正を適用。

起動後の初期化ログの `UDS_DIAG version=1 ... build=...` で区別する。
タイムアウト、エラーの戻り値、再送、シーケンス番号、UDS の接続状態の仕様は変更しない。
修正版の内容と追加の回帰検証は、同梱の調査報告を参照。

## Windows ビルド

上流の Windows MSYS2 / CLANG64 の経路を使用する。
MSYS2 の CLANG64 シェルで必要なパッケージを導入する:

```sh
pacman -Syu
# ランタイム更新で終了した場合はシェルを開き直して pacman -Syu を再実行
pacman -S --needed git make mingw-w64-clang-x86_64-toolchain \
  mingw-w64-clang-x86_64-cmake mingw-w64-clang-x86_64-ninja \
  mingw-w64-clang-x86_64-spirv-tools mingw-w64-clang-x86_64-qt6-base \
  mingw-w64-clang-x86_64-qt6-multimedia mingw-w64-clang-x86_64-qt6-multimedia-wmf \
  mingw-w64-clang-x86_64-qt6-tools mingw-w64-clang-x86_64-qt6-translations \
  mingw-w64-clang-x86_64-openssl
```

PowerShell 7 でリポジトリーのルートから実行する:

```powershell
git submodule update --init --recursive
./tools/uds_diagnostics/build-windows.ps1 -MsysRoot C:/msys64 -Jobs 6
```

既定の MSYS2 パスは、この作業で用意した `../tools/msys64`。
出力は `build-uds/bundle`。配布するときは exe 単体でなく bundle 全体をコピーする。
同梱 ZIP の `source/nwm-uds.patch` はベースからの UDS とヘッダー補完の差分。
別環境でソースを復元する場合は、上流を clone して `git checkout cf9068844`、
`git submodule update --init --recursive` を実行し、この差分を `git apply` する。
さらに ZIP の `source/tools/uds_diagnostics` をソースツリーの同じ位置へコピーする。
`manifest.json` にビルド種別、ソースの SHA256、配布ファイル一覧と SHA256 を保存する。
FFmpeg の録画機能は OFF、LTO は OFF、既存の全体テストターゲットは OFF。
新しいコンパイラーの既存警告がビルドを止めないよう warnings-as-errors は OFF。
これらは通信プロトコルを変更しない。日本語訳を含めてビルドする。
CLANG64 の OpenSSL を上流の `USE_SYSTEM_OPENSSL=ON` で使う。
Clang 23 / libc++ で必要になった Dynarmic の明示的な `<vector>` include は、
`dynarmic-clang23.patch` として分離し、スクリプトが必要な場合に一度だけ適用する。
この include 追加は JIT や UDS の動作を変えない。
同様に `src/network/artic_base/artic_base_client.h` に `<vector>`、
`externals/httplib/httplib.h` に `<exception>` を明示的に追加している。

回帰テストは Python 3 と clang++ を使う:

```powershell
python tools/uds_diagnostics/verify_pull_packet.py --revision cf9068844 --expect-bug
# 診断版ソースを試す場合:
python tools/uds_diagnostics/verify_pull_packet.py --expect-bug
# 修正版ソースを試す場合:
python tools/uds_diagnostics/verify_pull_packet.py
```

clang++ が PATH にない場合は `--compiler C:/msys64/clang64/bin/clang++.exe` を指定する。

## 2台での検証手順

1. 両PCで既存の AzaharPlus を終了する。各試験に同じ種類のビルドを使う。
   セーブデータは事前にコピーして保管する。配布物にゲームやユーザーデータは含めない。
2. ZIP をそれぞれ別フォルダーに展開し、同梱の `azahar.exe` を起動する。
   通常は既存の `%APPDATA%/AzaharPlus` を利用する。
   既存の portable 環境を使う場合は、そのPC自身の `user` をコピーして利用する。
   2台で同じ `user` を複製せず、それぞれの識別情報を維持する。
3. 設定のログフィルターを `*:Info Service.NWM:Debug Network:Debug` にする。
   `UDS_DIAG version=1` が記録されることを確認する。
   Release でも Debug レベルのログは有効。Trace は不要。
4. 両PCで同じ日本版 F1 2011 を通常起動し、同じルームへ入る。
   ホストがゲーム内の部屋を作り、参加側が参加する。
   同じCPU速度・ゲーム設定を維持し、セーブステートを使わず試験する。
5. まず diagnostics-only で既存エラーを再現する。
   画面のエラー内容と、参加操作からエラーまでのおおよその時間をメモする。
6. アプリを正常終了してログを保存する。次回起動前に実行する:

   ```powershell
   ./capture-logs.ps1 -Role host
   # 参加側は -Role client
   # portable の場合は -LogDirectory ./user/log を追加
   ```

7. 両PCを pull-result-fix に揃えて同じ操作を行う。初期化ログの build 名を確認する。
   ホスト/参加側を入れ替えた試験も行い、各回のログを別々に保存する。
8. ロビー合流が成功したら、両画面でレース開始、走行、完走、結果画面を確認する。
   一方だけ進行した場合や、レース途中で止まる場合は成功扱いにしない。
   可能なら各役割で複数回行い、試験ごとに状況を記録する。

## 追加ログの見方

- `state`: status、reason、local、total/max、node_bitmask、changed_nodes とノード一覧。
  status 3=未接続、6=ホスト、7=接続処理中、9=クライアント、10=観戦。
  reason 0=なし、1=接続成立、4=接続喪失。
- `GetConnectionStatus-return-before-clear`: ゲームへ返すスナップショット。
  changed_nodes をクリアする前に記録する。
- state のカウンターは Initialize からの累計。再参加試行の前後も追跡できる。
- `node` / `bind`: MAC とノードIDの対応、チャンネル、受信元フィルター、キュー深さ。
- `tx`: 宛先、長さ、flags と fingerprint。hle-success はルーム/相手への到達確認ではない。
- `transport result=enqueued`: ルーム送信キューに投入。到達確認ではない。
- `rx`: SecureData 到着。破棄した場合は drop-* の具体的理由を記録する。
- `result=queued` → `event action=dispatch-signal` → `result=dequeued` →
  `PullPacket-ipc reply=success`: 受信からゲームへの受け渡しを段階別に確認する。
  immediate の signal もある。dequeued 単独では IPC の成功を意味しない。
- 診断版で `has_value=true value_or_error=9`（または10/11）の後に
  `reply=not-connected/bad-bind/too-large has_value=true` が出れば、上記誤判定を通った証拠。
- `disconnect origin=guest-ipc`: ゲームがコマンド 0x000A を要求。
  API はゲーム内の失敗理由を受け取らないため、`reason=not-provided` と記録する。
  現行エミュレーターの deauth は空の本文で、切断理由コードを持たない。

`frame_hash` は送信と受信のフレーム、`payload_hash` は送信と Pull のデータを照合する。
FNV-1a の補助情報であり一意なIDではない。ノードID、チャンネル、長さ、順序も照合する。
元実装の sequence_number=0 は変更していない。
空の Pull は最初の8回と2の累乗回で記録し、総数は state の empty に残す。
元のロガーには 100 MiB の出力上限があるため、一試験ごとにログを保存する。
上限やゲームのタイムアウトは変更していない。

ペアのログを JSON に要約する:

```powershell
python analyze-logs.py --host HOST/azahar_log.txt --client CLIENT/azahar_log.txt --out summary.json
```

両PCの diagnostics-only と pull-result-fix のログ、および合流/開始/完走の成否が
揃えば、候補修正が F1 の問題を解消するか、別の破棄・ノード状態の不整合が残るか判断できる。
