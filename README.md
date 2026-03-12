[![CI](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml/badge.svg)](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml)

# STEN-F

![Compliance](https://img.shields.io/badge/Compliance-Dencho_Act_%26_Invoice_System-blue)
[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.13+-yellow.svg)](https://www.python.org/)
[![Reflex](https://img.shields.io/badge/Reflex-0.6.7+-bf40bf.svg)](https://reflex.dev/)

**STEN-F** は、既存のクラウド会計ソフト（SaaS）による「データの囲い込み」や「貧弱なAPIエコシステム」から開発者・ベンチャー企業を解き放つために開発された、エンジニア主導のOSS経理・会計アプリケーションです。

最先端の **Pure Python Web Framework (Reflex)** と **Clean Architecture** を基盤に構築されており、仕訳入力から決算書の作成までをシンプルかつ強固に行えます。財務データはすべてローカル（または自社管理下）のSQLiteに保存され、所有権をあなたが完全に掌握できます。

---

## 🏴 Philosophy (行動指針)

0.  **This is your Stengun.** これはステンガンだ。シンプルでタフな勝つための武器だ。（[ステン短機関銃](https://ja.wikipedia.org/wiki/%E3%82%B9%E3%83%86%E3%83%B3%E7%9F%AD%E6%A9%9F%E9%96%A2%E9%8A%83)）
1.  **Of course it's free:** この程度の経理ソフト、当然無料だ。
2.  **No Vendor Lock-in:** 財務データは人質ではない。いつでも生のSQLでアクセス可能であるべきだ。
3.  **Local First:** ネットワークが切れても、あなたの経理業務と会社の数字は止まらない。
4.  **Don't pay for apps, pay for AI:** お金を払うなら「毎月のソフト利用料」ではなく、あなたの業務を真に爆速化する「AIによる推論（OCR・自動仕訳）」に対して払うべきだ。

---

## ⚡ 主な機能 (Key Features)

### 経理・会計の基本機能
*   **高速な仕訳入力**: 貸方・借方を直感的に選択し、キーボード操作主体のUIでスピーディに入力。
*   **「別タブ」アプローチ**: 仕訳入力を止めることなく、いつでも「別タブ」で仕訳履歴・過去データの検索やCSV出力が可能な設計。
*   **期首残高（BS）入力**: 法人の期首残高（資産・負債・純資産）を貸借一致のバリデーション付きで安全登録。
*   **年度締め機能**: 既存年度の名称変更（インライン編集）および、次期名称を動的に指定可能な安全な「年度締め」（次年度繰越・ステータスロック機能）。
*   **セーフガード**: 締めた「CLOSED」な会計年度に対する追加入力のブロックや、自動バリデーション機能。

### 監査・電子帳簿保存法 & インボイス制度対応
*   **論理削除 (Soft Delete)**: 一度登録した仕訳の修正・削除履歴を完全にデータベース上に保持し、監査証跡（Audit Trail）を残します。
*   **T番号管理**: 取引先ごとの適格請求書発行事業者登録番号（インボイスT番号）をシステム内で統合管理できます。
*   **証憑の永久保存**: レシートや請求書のPDF/画像を取引データのトランザクションに紐づけて保存可能。

### レポート・出力 (Reporting)
*   合計残高試算表 (Trial Balance) / 財務諸表（貸借対照表、損益計算書）
*   総勘定元帳（指定期間でのドリルダウン対応）
*   **決算報告書 PDF 生成**: 非同期タスク処理 (Offloading) により、長大なPDF書類を出力している最中も、UIが一切フリーズしません。

### 🤖 AI OCR 機能 (Powered by Google Gemini / OpenAI)
最新の Google Gemini Native API (`client.aio`) および OpenAI Responses API v2.3 に準拠した強靭なAI推論モデルを組み込んでいます。
*   **Native PDF Support (Gemini 3 Flash)**: PDFを画像に変換する手間なく、Geminiのネイティブ機能で直接高精度に解析・仕訳化。
*   **Smart Image Optimization**: 自動画像リサイズ機能（トークン節約と精度向上の両立）。
*   **Smart Counterparty Matching**: AIが読み取った店舗名と、マスタ上の既存取引先・T番号を自動で照合。
*   **Self-Healing QA & Resilient API**: インターネットが瞬断した際のエラーもシステム側で一時吸収し、自動リトライを行う `@resilient_api_call` の採用。

---

## 🏗 技術スタック & アーキテクチャ

*   **Language**: Python 3.13+ (100% Pure Python)
*   **Package Manager**: `uv` (Fast & Deterministic virtual environment)
*   **UI Framework**: Reflex 0.6.7+
*   **Database**: SQLite via **SQLAlchemy 2.0 Async** (`aiosqlite`)
*   **Data Validation**: **Pydantic V2** (Strict Config)
*   **Testing**: Pytest + Asyncio + AsyncExitStack

### Clean Architecture & Independent SubStates
STEN-Fのバックエンドはクリーンアーキテクチャに基づき、ドメイン・インフラ・アプリケーションレイヤーを厳重に分離しています。
UI側の状態管理（View Model）においては肥大化（神クラス化）を防ぐため、Reflexのベストプラクティスである「Independent SubStates パターン」を採用。
機能ごとに `app/ui/view_models/journal/` ディレクトリ配下等へ `FormState`, `MasterState`, `OCRState`, `ListState` と独立・直交化して分割し、高い保守性を保っています。

```text
STEN-F/
├── app/
│   ├── app.py              # Reflex Entry Point
│   ├── config.py           # 環境変数 (Pydantic Settings)
│   ├── core/               # コアモジュール (Logger, API Resilience 等)
│   ├── domain/             # ドメイン層 (Pydantic V2 Models)
│   ├── infrastructure/     # インフラ層 (AI/DBリポジトリ実装)
│   ├── application/        # ユースケース・サービス層
│   └── ui/                 # UIレイヤー
│       ├── pages/          # 各画面ごとのルーティング
│       ├── components/     # 再利用可能な部品 (Sidebar, Modals 等)
│       └── view_models/    # Reflex State (分離されたSubState構成群)
├── tests/                  # Pytest 自動テスト環境
├── bookkeeping.db          # データベース (デフォルト設定時ローカル保存)
└── uv.lock / pyproject.toml# パッケージ管理
```

---

## 🚀 セットアップと起動手順

開発および動作には Python 3.13+ および `uv` が必要です。仮想環境の構築もすべて `uv` に任せ、非常に高速に初期セットアップが終わります。

### 1. インストール
リポジトリをクローンし、`uv sync` で依存パッケージを一括インストールします。
```bash
git clone https://github.com/bottiLLC/STEN-F.git
cd STEN-F
uv sync
```

### 2. 環境設定 (.env)
ルートディレクトリに `.env` ファイルを作成し、APIキー等を設定します（初期の `.env.sample` を複製してください）。
```ini
# Database Connection
DATABASE_URL=sqlite+aiosqlite:///bookkeeping.db

# API Keys for AI features 
# GOOGLE_API_KEY=AIzaSy...
# OPENAI_API_KEY=sk-proj...
```

### 3. アプリケーションの起動
`uv run` を経由して Reflex 開発サーバーを立ち上げます。
```bash
uv run reflex run
```
もしWindowsやmacOSをご利用の場合、設定後、ディレクトリ直下の `start.bat` または `start.command`（※要chmod実行権限付与）を**ダブルクリックするだけ**でも簡単にサーバーが起動します。
起動後、ブラウザで自動的に `http://localhost:3000` にアクセスされます。

### 4. テスト実行
```bash
uv run pytest
```

---

## 🧰 運用・保守・リカバリ (Ops & Maintenance)

SaaS に依存せずローカルで一元管理されるため、**あなた自身がデータを完全にコントロール** できます。
不測の事態（PCの紛失、ハードディスクの故障、誤操作など）に備え、以下のファイル・フォルダを定期的に「外部・クラウドストレージ」などにバックアップしてください。

### ✅ バックアップ対象 (Backup Targets)
1.  `bookkeeping.db` : 全ての仕訳データ、財務履歴、設定類が記録された魂のファイル。（**最重要**）
2.  `storage/` および `uploaded_files/` : AI-OCR解析時や手動添付時に保存され、各仕訳に紐付けられた電子帳簿保存法対応の証憑ファイル（PDF・画像データ）。
3.  `.env` : 外部APIキーなどを含む機微な環境設定ファイル。
*(STEN-FのUI上にある「システム（管理）」タブからも、全対応フォルダを含めたシステム全体のZIP出力が可能です)*

### 🔄 リカバリ手順 (Full Recovery)
新しいPCなどにシステムを完全復旧させる、あるいは別の環境へ移行する手順は以下の通りです。

1. 新しいPCで上記セットアップ手順（`git clone` ～ `uv sync`）を完了させる。
2. STEN-Fプログラムが完全に**停止している**状態を作る。（※起動中の上書きはデータベース破損の原因になります）
3. 事前に定期バックアップしておいた以下の3つのデータを、新しいプロジェクトフォルダ直下へ配置・上書きコピーする。
   * `bookkeeping.db`
   * `.env`
   * `storage/` ディレクトリ全体（および存在する場合は `uploaded_files/`）
4. アプリケーション (`uv run reflex run`) を起動し、仕訳帳の取引履歴リストと、それぞれの証憑（PDFアイコン等）が正常にリンク・表示できるか確認する。

---

## 📜 ライセンス制限 (License - GPLv3)

Copyright (c) 2026 Botti LLC (Contract LLC Bocchi)

本ソフトウェアは **GNU General Public License v3.0 (GPLv3)** の下で公開されています。
*   **目的を問わず無料**で自由に使用および改変が可能です。
*   **【重要】コピーレフトの義務**: あなたが本ソフトウェア（あるいは一部を改変した派生物）を再配布する場合、またはネットワークサービスとして外部に機能提供する場合、**そのソースコード全体を同様にGPLv3の下で一般公開する義務**が生じます。

OSSエコシステム還元へのご協力をよろしくお願いします。
詳細や完全な条項については、ソースコード内の `LICENSE` ファイルを参照してください。
