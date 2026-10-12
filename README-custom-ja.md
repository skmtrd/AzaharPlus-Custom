# AzaharPlus Custom

AzaharPlusを基にした、skmtrdの非公式カスタム版です。
上流の履歴とライセンスを引き継いだ独立リポジトリです。

上流: https://github.com/AzaharPlus/AzaharPlus

## 含まれる変更

- Windows版のDiscord連携を有効にし、設定の読み戻しを修正。
- Discordのプロフィールカード上部とメンバー一覧へプレイ中のゲーム名を送信。
- プロフィールカードの画像を、対応する4,138タイトルの公開ゲームアイコンへ切り替え。
- UDS PullPacketの正常受信長とエラー判定の修正、通信診断ログ。
- SDLコントローラー初期化時のロック順序修正とWindowsビルド用の互換性修正。

ボイスチャンネル一覧の小さい花はDiscordのアプリ登録に紐づくため、この版でも変わりません。
セーブ、ROM、個人設定、アカウント情報、別用途のBadge Lab試験変更は含めていません。

## Windowsでビルド

Git、PowerShell 7、MSYS2 CLANG64を用意します。依存パッケージ一覧は
[Windowsビルドの説明](tools/uds_diagnostics/README.md)を参照してください。

```powershell
git clone --recursive https://github.com/skmtrd/AzaharPlus-Custom.git
cd AzaharPlus-Custom
./tools/uds_diagnostics/build-windows.ps1 -MsysRoot C:/msys64 -Jobs 6
```

出力は `build-uds/bundle` です。Discord RPCの修正版はこのリポジトリに含めています。
その他の依存ライブラリーはGitサブモジュールで管理しています。
GitHub Actionsの既存ワークフローは手動実行にしてあります。

## 検証状況

配布済みWindows版では設定の保存、ゲーム名の送信、画像URLの送信を確認済みです。
Discordからの画像取得も確認しました。UDSの回帰チェックは正常受信長1,479件で誤判定なしです。
ゲーム全般の動作や2台間の通信完走は、別途確認が必要です。

## 上流の更新を取り込む

```powershell
git remote add upstream https://github.com/AzaharPlus/AzaharPlus.git
git fetch upstream
```

取得した更新を確認したうえで、必要な変更をマージしてください。
上流の説明と各ライセンスも、このリポジトリ内に保持しています。
