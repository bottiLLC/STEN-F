[![CI](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml/badge.svg)](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml)

# STEN-F

![Compliance](https://img.shields.io/badge/Compliance-Dencho_Act_%26_Invoice_System-blue)

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.13+-yellow.svg)](https://www.python.org/)
[![Reflex](https://img.shields.io/badge/Reflex-0.6.7+-bf40bf.svg)](https://reflex.dev/)

**STEN-F** は、既存のクラウド会計ソフト（SaaS）による「データの囲い込み」と「貧相な日本のDX」からベンチャー企業を救うべく開発された、エンジニア主導の経理・会計アプリケーションです。

**Pure Python Web Framework (Reflex)** をベースに構築されており、仕訳入力から決算書の作成までをシンプルかつ効率的に行えます。
データは全てローカル（または自前の管理下）にあるSQLiteに保存され、あなたがその所有権を完全に掌握できます。

## Philosophy (行動指針)
0.  **This is your Stengun.** これはステンガンだ。シンプルでタフな勝つための武器だ。（[ステン短機関銃](https://ja.wikipedia.org/wiki/%E3%82%B9%E3%83%86%E3%83%B3%E7%9F%AD%E6%A9%9F%E9%96%A2%E9%8A%83)）
1.  **Of course it's free** この程度のもの、当然無料だ。
2.  **No Vendor Lock-in:** 財務データは人質ではない。いつでも生のSQLでアクセス可能であるべきだ。
3.  **Local First:** ネットワークが切れても経理は止まらない。
4.  **Don't pay for apps, pay for AI:** 金を払うならアプリ代ではなく、AIによる推論（OCR・自動仕訳）に対して払うべきだ。

## 主な機能

*   **期首残高（BS）入力機能**: 法人の期首残高（資産・負債・純資産）を貸借一致のバリデーション付きで安全かつ簡単に登録可能。
*   **高速な仕訳入力**: 貸方・借方を選択し、キーボード操作主体のUIでスピーディに取引を入力。
*   **電子帳簿保存法 & インボイス制度対応**:
    *   **論理削除 (Soft Delete)**: 仕訳の修正・削除履歴を完全に保持し、監査証跡を残します。
    *   **T番号管理**: 取引先ごとの適格請求書発行事業者登録番号（T番号）を管理。
    *   **証憑保存**: レシートや請求書のPDF/画像を取引に紐づけて保存可能（非同期保存）。
*   **洗練されたマスタ管理**:
    *   編集フォームが常に表示され、煩わしいモーダル遷移を排除。
    *   法人情報、取引先の柔軟な管理。
    *   **会計年度管理 & 期末処理**: 既存年度の名称変更（インライン編集）および、次期名称を動的に指定可能な安全な「年度締め」機能（次年度繰越・ステータスロック）を実装。
*   **レポート機能**:
    *   合計残高試算表 (Trial Balance)
    *   財務諸表（貸借対照表、損益計算書）
    *   総勘定元帳（ドリルダウン可能）
*   **決算報告書出力**: 監査にも対応可能な形式のPDF決算報告書をワンクリックで生成（**完全非同期オフロード対応**により出力中もUIがフリーズしません）。
*   **AI OCR (Beta)**:
    *   **Google Gemini 3 Flash Preview** を採用（最先端の非同期API統合）。
    *   **Self-Healing QA & Resilient API**: ネットワーク一時的エラーに対する自動リトライ機能（`@resilient_api_call`）を実装。
    *   **Native PDF Support**: PDFは画像変換せず、Geminiのネイティブ機能で直接解析（高精度）。
    *   **Smart Image Optimization**: 画像は自動で最適化（最大2000px / 200dpi）し、トークン節約と精度向上を両立。
    *   **Smart Counterparty Matching**: OCR結果の店舗名をマスタ登録済みの取引先と自動照合。
    *   **Nested Tax Breakdown**: 複雑な税区分（8%/10%の混在など）も正確に構造化して読み取り。
    *   **Async Processing**: 完全なる非同期処理により、アップロードや推論中も操作をブロックしません。
*   **完全日本語対応**: UIおよび出力帳票は全て日本語にローカライズ済み。

## 技術スタック

*   **言語**: Python 3.13+
*   **UIフレームワーク**: **Reflex** (Pure Python Web App)
*   **データベース**: SQLite (via **SQLAlchemy 2.0 Async** + aiosqlite)
*   **AI/LLM**: Google GenAI SDK (Gemini 3 Flash Preview)
*   **データ検証**: **Pydantic V2** (Strict Config)
*   **非同期I/O**: aiofiles
*   **PDF生成**: ReportLab
*   **テスト**: Pytest + Asyncio + AsyncExitStack
*   **アーキテクチャ**: Clean Architecture (Layered Architecture) with Dependency Injection

## ディレクトリ構造

```text
STEN-F/
├── app/
│   ├── app.py              # Reflex Entry Point
│   ├── domain/             # ドメインモデル (厳格なPydantic V2)・リポジトリIF
│   ├── infrastructure/     # インフラ層 (DB接続, Gemini API, FileSystem, Repo実装)
│   ├── application/        # アプリケーションロジック (Async Service)
│   ├── ui/                 # UI層 (Reflex Pages)
│   │   ├── pages/          # 画面ルーティング
│   │   ├── components/     # 機能ごとのモジュール群 (master/, reports/, journal/ 等)
│   │   ├── view_models/    # Reflex State (UIとドメインの仲介処理)
│   │   └── layout.py       # 共通ベースレイアウト
│   ├── config.py           # グローバル設定
│   └── core/               # コア機能 (Logger, Error Resilience 等)
├── tests/                  # テストコード (Pytest Async)
├── bookkeeping.db          # データベースファイル
├── pytest.ini              # テスト設定ファイル
├── requirements.txt        # 依存ライブラリ
└── README.md               # 本ファイル
```

## セットアップ手順

### 1. 必須環境
*   Python 3.13 以上
*   Git

### 2. インストール
リポジトリをクローンし、`uv` を用いて環境を構築します。

```bash
git clone https://github.com/bottiLLC/STEN-F.git
cd STEN-F
uv sync
```

### 3. 環境設定 (.env)
ルートディレクトリに `.env` ファイルを作成し、必要な環境変数を設定してください。
サンプル (`.env.sample`) をコピーして使用できます。

```ini
# Database (Default)
DATABASE_URL=sqlite+aiosqlite:///bookkeeping.db

# Optional: AI Features (Google Gemini)
# GOOGLE_API_KEY=AIzaSy...
```

### 4. 起動
以下のコマンドでアプリケーションを起動するか、各OS用の起動スクリプトを使用できます。

**コマンドで起動する場合:**
```bash
uv run reflex run
```

**ダブルクリックで起動する場合:**
*   **Windows**: `start.bat` をダブルクリックして実行します。
*   **macOS**: `start.command` をダブルクリックして実行します。
    *   ※初回のみ、ターミナルで `chmod +x start.command` を実行して権限を付与してください。

ブラウザが自動的に開き、アプリケーションが表示されます (`http://localhost:3000`)。

### 5. テスト実行
品質担保のため、以下のコマンドで非同期テストを実行できます。

```bash
uv run pytest
```

## ライセンス (License)
Copyright (c) 2026 Botti LLC (Contract LLC Bocchi)

本ソフトウェアは GNU General Public License v3.0 (GPLv3) の下で公開されています。

あなたは以下の権利を有します：

*   **使用の自由**: 目的を問わず、本ソフトウェアを使用すること。
*   **研究と改変の自由**: 本ソフトウェアのソースコードを研究し、自分のニーズに合わせて改変すること。
*   **再配布の自由**: 本ソフトウェアのコピーを（改変の有無に関わらず）再配布すること。

**【重要】制約事項（コピーレフト）**: もしあなたが本ソフトウェア（またはその改変版）を再配布する場合、あるいはネットワーク経由でサービスとして提供する場合、そのソースコード全体をGPLv3の下で公開する義務が生じます。これにより、このソフトウェアの自由は下流のユーザーに対しても永久に保証されます。

詳細については、リポジトリに含まれる `LICENSE` ファイル、または [GNU General Public License](https://www.gnu.org/licenses/gpl-3.0.html) を参照してください。

## 免責事項 (Disclaimer)
本ソフトウェアは「現状のまま」提供され、明示または黙示を問わず、いかなる保証も行われません。本ソフトウェアの使用によって生じた、いかなる損害（データの損失、業務の中断、税務申告の誤りなど）についても、作者および著作権者は責任を負いません。ご利用は自己責任でお願いします。
