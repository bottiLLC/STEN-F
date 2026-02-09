[![CI](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml/badge.svg)](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml)

# STEN-F (Simple Tax Entry for No-nonsense Freelancers) v1.0.0

[![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](https://www.gnu.org/licenses/gpl-3.0)
[![Python](https://img.shields.io/badge/Python-3.13+-yellow.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.42+-red.svg)](https://streamlit.io/)

**STEN-F** は、既存のクラウド会計ソフト（SaaS）による「データの囲い込み」と「貧相な日本のDX」からベンチャー企業を救うべく開発された、エンジニア主導の経理・会計アプリケーションです。

Python (Streamlit) をベースに構築されており、仕訳入力から決算書の作成までをシンプルかつ効率的に行えます。
データは全てローカル（または自前の管理下）にあるSQLiteに保存され、あなたがその所有権を完全に掌握できます。

本バージョン(v1.0.0)では、モダンなアーキテクチャ（Clean Architecture, Async, Pydantic V2）を全面的に採用し、保守性と拡張性を大幅に向上させました。ハックして自分好みに改造してください。

## Philosophy (行動指針)
0.  **This is your Stengun.** これはステンガンだ。シンプルでタフな勝つための武器だ。（[ステン短機関銃](https://ja.wikipedia.org/wiki/%E3%82%B9%E3%83%86%E3%83%B3%E7%9F%AD%E6%A9%9F%E9%96%A2%E9%8A%83)）
1.  **Of course it's free** この程度のもの、当然無料だ。
2.  **No Vendor Lock-in:** 財務データは人質ではない。いつでも生のSQLでアクセス可能であるべきだ。
3.  **Local First:** ネットワークが切れても経理は止まらない。
4.  **Don't pay for apps, pay for AI:** 金を払うならアプリ代ではなく、AIによる推論（OCR・自動仕訳）に対して払うべきだ。

## 主な機能

*   **高速な仕訳入力**: 貸方・借方を選択し、キーボード操作主体のUIでスピーディに取引を入力。
*   **マスタ管理**: 法人情報、会計年度、勘定科目、摘要などを柔軟に管理。
*   **レポート機能**:
    *   合計残高試算表
    *   財務諸表（貸借対照表、損益計算書）
    *   総勘定元帳（ドリルダウン可能）
*   **決算報告書出力**: 監査にも対応可能な形式のPDF決算報告書をワンクリックで生成。
*   **AI OCR (Beta)**: Google Gemini (Flash Lite) を用いたレシートOCRと勘定科目提案機能。（要 API Key）
*   **完全日本語対応**: UIおよび出力帳票は全て日本語にローカライズ済み。

## 技術スタック

*   **言語**: Python 3.13+
*   **フレームワーク**: Streamlit (Web UI)
*   **データベース**: SQLite (via SQLAlchemy 2.0 Async + aiosqlite)
*   **AI/LLM**: Google GenAI SDK (Gemini 2.5 Flash Lite)
*   **データ検証**: Pydantic V2
*   **PDF生成**: ReportLab
*   **アーキテクチャ**: Clean Architecture (Layered Architecture) with Dependency Injection

## ディレクトリ構造

```text
STEN-F/
├── app/
│   ├── application/        # アプリケーションロジック（Service層）
│   ├── domain/             # ドメインモデル・インターフェース
│   ├── infrastructure/     # DB接続、外部API（PDF, Gemini等）、リポジトリ実装
│   ├── presentation/       # UI層 (Page, Component)
│   ├── config.py           # 設定ファイル
│   ├── container.py        # DIコンテナ
│   └── main.py             # アプリケーションエントリーポイント
├── bookeeping.db           # データベースファイル（初回起動時に自動生成）
├── requirements.txt        # 依存ライブラリ
└── README.md               # 本ファイル
```

## セットアップ手順

### 1. 必須環境
*   Python 3.13 以上
*   Git

### 2. インストール
リポジトリをクローンし、依存ライブラリをインストールします。

```bash
git clone https://github.com/bottiLLC/STEN-F.git
cd STEN-F
pip install -r requirements.txt
```

### 3. 環境設定 (.env)
ルートディレクトリに `.env` ファイルを作成し、必要な環境変数を設定してください。

```ini
# Database (Default)
DATABASE_URL=sqlite+aiosqlite:///bookkeeping.db

# Optional: AI Features (Google Gemini)
# GOOGLE_API_KEY=AIzaSy...
```

### 4. 起動
以下のコマンドでアプリケーションを起動します。

```bash
streamlit run app/main.py
```

ブラウザが自動的に開き、アプリケーションが表示されます。

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
