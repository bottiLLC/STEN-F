# STEN-F (Simple Tough Effective Next-generation Finance)

[![CI](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml/badge.svg)](https://github.com/bottiLLC/STEN-F/actions/workflows/ci.yml) [![Python](https://img.shields.io/badge/Python-3.14-yellow.svg)](https://www.python.org/) [![Streamlit](https://img.shields.io/badge/Streamlit-1.64.0-FF4B4B.svg)](https://streamlit.io/) [![License: GPL v3](https://img.shields.io/badge/License-GPLv3-blue.svg)](LICENSE) [![Code style: ruff](https://img.shields.io/badge/code%20style-ruff-000000.svg)](https://github.com/astral-sh/ruff) [![Checked with mypy](https://img.shields.io/badge/mypy-strict-blue)](https://mypy-lang.org/) [![Coverage](https://img.shields.io/badge/coverage-pytest--cov-green)](https://pytest.org/)

## Overview
日本の複式簿記（振替伝票・仕訳帳・総勘定元帳・試算表・B/S・P/L）および電子帳簿保存法・インボイス制度に完全準拠し、Gemini AI OCR による証憑自動読取から振替伝票自動展開までをローカル完結で提供する、100% Pure Python 製のオープンソース経理・会計システム。

## Quick Start (TL;DR)
```bash
# 1. 依存関係の同期
uv sync --all-groups

# 2. テストスイートの実行
uv run pytest -m "not fuzz"

# 3. アプリケーションの起動（または run.bat をダブルクリック）
uv run streamlit run app.py
```

## Architecture & Features
- **Monocoque Clean Architecture & 不変性制約**: UI層（Streamlit）、ドメイン契約層（Pydantic V2）、永続化層（SQLAlchemy 2.0 Async / aiosqlite）を厳格に分離し、仕訳の改変・削除を完全遮断して赤伝（反対仕訳）による完全な監査証跡を保持。
- **マルチモーダル AI OCR 証憑自動読取ワークフロー**: PDFおよび画像（PNG/JPG）の領収書・請求書から Google Gemini API を介して取引日・金額・取引先（T番号照合）・勘定科目を高精度に自動抽出し、振替伝票へ即時仮入力。
- **財務諸表自動生成 & 日本語 PDF 帳票出力**: 左右対照バランスシート（B/S）、段階損益計算書（P/L）、合計残高試算表（T/B）、総勘定元帳を即時集計し、ReportLab による決算書日本語 PDF をワンクリック出力。
- **永続化データ絶対隔離 (`./data`) & アトミック ZIP 検証バックアップ**: すべての DB・証憑ファイル・設定を `./data` ディレクトリに完全集約し、`backup_manager.py` による `testzip()` 破損検証付きアトミック ZIP バックアップと外部同期フォルダ連携を提供。

## Environment Variables
| Variable | Default | Description |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` | *(None / Required)* | Google Gemini API キー（AI OCR 証憑読取機能に必須） |
| `GEMINI_DEFAULT_MODEL` | `gemini-2.0-flash` | OCR推論に使用するデフォルト Gemini モデル識別子 |
| `DATABASE_URL` | `sqlite+aiosqlite:///./data/sten_f.db` | 非同期 SQLAlchemy データベース接続文字列 |
| `BACKUP_DIR` | `data/backups` | 自動バックアップアーカイブ（ZIP）の保存先ディレクトリパス |

## Limits & Known Trade-offs
- **単一テナント排他制御**: SQLite を利用したローカルファースト運用の単一事業体向けシステムであり、複数ユーザーによる同時書き込みトランザクションは想定外。
- **実務申告の利用者自己責任**: 本システムは複式簿記および電帳法・インボイス制度の要件支援を提供しますが、帳簿の適法性および税務申告内容の妥当性は利用者が自己の責任において確認・判断するものとします。
- **AI OCR 従量制 API 利用枠**: Gemini API の利用上限（Rate Limit / Quota）やネットワーク障害が発生した場合、手動入力による振替伝票作成へのフォールバックを推奨。

---
Copyright (C) 2026 合同会社ぼっち (bottiLLC). All rights reserved.
