# ThinkKoma

人の指示なしで、作業場を巡回し、欠陥を自分で見つけて閉じる自律型シンクタンク・エージェントです。

起動に必要なのはワークスペースだけです。問題文、確認、採用の選択は求めません。

## 完全自律走行

```text
thinkkoma drive
    -> 0号 偵察（テスト失敗・構文・ログ・inbox）
    -> 信号がなければ quiet で停止（または --watch で再巡回）
    -> 最も優先度の高い欠陥を自分で問題文化する
    -> 4号 批評、6号 加点、7号 減点。誤差を工程へ逆伝播
    -> 規定（oracle/safety）を満たさなければ再施行
    -> 解けたら次の信号、解けなければ指紋を exhausted にして無限ループしない
    -> 5号 が outbox / patrol へ提出
```

```bash
cd projects/thinkkoma
uv sync --dev
uv run thinkkoma drive --workspace examples/broken_add
```

問題文は不要です。落ちているテストを自分で見つけ、直して、静穏（quiet）になったら終わります。常駐するなら:

```bash
uv run thinkkoma drive --workspace . --watch --backend ollama
```

`--watch` は quiet のあと再スキャンします。止めるのは `Ctrl+C`、`--max-idle`、`--max-missions` です。

`thinkkoma run` に問題文を書かない場合も、同じ巡回を一度だけ行います。

## 自分で見つける信号

| 優先度 | 信号 | 自律行動 |
| --- | --- | --- |
| 高 | 落ちているテスト | 修復して再検証 |
| 高 | Python 構文エラー | 診断し、閉じられるものから着手 |
| 中 | traceback / ERROR ログ | 診断。テストがあれば修復 |
| 中 | inbox ファイル | あれば処理（必須ではない） |
| 低 | `NotImplementedError` / TODO | 検証器があるときだけ実装。なければ提出して次へ |

同じ欠陥で停滞したら指紋を exhausted にし、人間の再指示を待たずに次の信号へ進みます。

## 提供・提案・提出

| 段階 | 成果物 | 行先 |
| --- | --- | --- |
| 提供 | 自分で書いた問題、成功条件、原因仮説 | `.thinkkoma/reports/` |
| 提案 | 順位付き行動案 | `.thinkkoma/outbox/` |
| 提出 | ミッション JSON、巡回ステータス | `.thinkkoma/outbox/` と `.thinkkoma/patrol/` |

ローカル LLM（Ollama）は任意です。無くてもヒューリスティックで偵察と修復ができます。

```bash
export THINKKOMA_BACKEND=ollama
export THINKKOMA_MODEL=llama3.2
uv run thinkkoma drive --workspace . --backend ollama
```

## 止まるタイミング

人が止める場合: `Ctrl+C`。`--watch` なしなら quiet で終了します。

エージェントが自分で止まる場合:

| 理由 | いつ |
| --- | --- |
| `quiet` | 検証可能な欠陥がもう無い |
| `patrol_complete` | 残信号が exhausted、またはミッション上限 |
| `solved` / `submitted` | 一件のミッションが証跡で閉じた（巡回は次へ） |
| `budget_attempts` / `budget_steps` / `budget_time` | 一件の予算切れ → exhausted にして次へ |
| `stalled` | 同じ失敗が続く → exhausted にして次へ |
| `denied` | 危険操作の連続拒否 → exhausted にして次へ |

## 加点・減点と逆伝播

10視点を、規定値との残差で採点します。

| 視点 | 規定 | 見るもの |
| --- | --- | --- |
| oracle | 1.0 | テスト／成果物オラクル |
| safety | 1.0 | 危険操作の拒否 |
| integrity | 1.0 | 批評の完了判定がオラクルと一致するか |
| reenact | 0.8 | 肯定側・否定側が独立に再施行した結果 |
| completeness | 0.8 | 提出の有無 |
| evidence | 0.7 | 証跡 |
| progress | 0.5 | 前進したステップ |
| halt | 0.6 | 停止の妥当性 |
| autonomy | 0.9 | 人待ちをしていないこと |
| consensus | 0.5 | 加点と減点の一致 |

- **6号 肯定**は加点だけ。テスト失敗を加点しない。独立にオラクルを再施行する
- **7号 否定**は減点だけ。検証器なしの完了と、記録と食い違う再施行を拒否する。こちらも独立に再施行する
- `net = clip(加点 - 減点)`、`residual = 規定 - net`
- 残差を interpret / plan / act / verify / submit へ逆伝播し、次の再施行の焦点にする
- 規定ゲートは `oracle` / `safety` / `integrity`。残差が小さく、肯定と否定が食い違わないときだけ `spec_ok`

肯定と否定が hard 視点で食い違うと、両方をもう一度再施行してから判定します。

## 安全境界

- ワークスペース外、`.env` / `.ssh`、`sudo`、`git push` は拒否
- テストが落ちたまま「直った」とは提出しない
- 権限を広げるための無人化ではない

## テスト

```bash
uv run pytest
uv run ruff check thinkkoma tests
```

## バックエンド

| 環境変数 / フラグ | 役割 |
| --- | --- |
| `--backend` / `THINKKOMA_BACKEND` | `heuristic`（既定） / `ollama` / `local` / `openai` / `cursor` |
| `THINKKOMA_OLLAMA_HOST` | 既定 `http://127.0.0.1:11434` |
| `THINKKOMA_MODEL` | Ollama 既定 `llama3.2` |
