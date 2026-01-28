# 要件定義書

## はじめに

空き家追跡MVPは、全国の空き家バンクおよび自治体の空き家情報サイトから物件情報を自動収集し、ユーザーに検索・通知機能を提供するシステムです。ユーザーは条件に合った空き家を効率的に見つけ、新規物件や価格変動の通知を受け取ることができます。

## 用語集

- **System**: 空き家追跡MVPシステム全体
- **Scraper**: Webスクレイピングを実行するコンポーネント
- **Database**: PostgreSQLデータベース
- **API**: FastAPIで実装されたRESTful API
- **User**: システムを利用する登録ユーザー
- **Property**: 空き家物件情報
- **Notification_Service**: 通知を送信するサービス
- **Scheduler**: 定期実行を管理するコンポーネント

## 要件

### 要件 1: 空き家情報の自動収集

**ユーザーストーリー:** システム管理者として、空き家情報を自動収集したい。これにより、最新の空き家情報をユーザーに提供できる。

#### 受入基準

1. WHEN Scheduler が実行される THEN THE Scraper SHALL 空き家バンクサイトから物件情報を取得する
2. WHEN 物件情報を取得する THEN THE Scraper SHALL 住所、価格、築年数、土地面積、建物面積、写真URL、備考、掲載日を抽出する
3. WHEN スクレイピングが失敗する THEN THE System SHALL エラーをログに記録し、リトライキューに追加する
4. WHEN 取得した物件情報を保存する THEN THE System SHALL Database に物件データを永続化する
5. WHEN robots.txt で禁止されているパスにアクセスしようとする THEN THE Scraper SHALL そのパスをスキップし、ログに記録する

### 要件 2: 物件情報の重複検出と履歴管理

**ユーザーストーリー:** システム管理者として、同じ物件が重複して保存されないようにしたい。また、価格変動などの履歴を追跡したい。

#### 受入基準

1. WHEN 新しい物件情報を保存する THEN THE System SHALL 住所、土地面積、建物面積、写真URLの複合キーで既存物件と照合する
2. WHEN 既存物件と一致する THEN THE System SHALL 新規レコードを作成せず、既存レコードを更新する
3. WHEN 物件の価格が変更される THEN THE System SHALL 変更日時、旧価格、新価格を履歴テーブルに記録する
4. WHEN 物件のステータスが変更される THEN THE System SHALL 変更日時とステータスを履歴テーブルに記録する
5. WHEN 物件が掲載終了する THEN THE System SHALL 物件のステータスを「掲載終了」に更新する

### 要件 3: ユーザー認証とアカウント管理

**ユーザーストーリー:** ユーザーとして、アカウントを作成してログインしたい。これにより、マイリストや通知設定を管理できる。

#### 受入基準

1. WHEN ユーザーが登録フォームを送信する THEN THE System SHALL メールアドレスとパスワードでアカウントを作成する
2. WHEN パスワードを保存する THEN THE System SHALL パスワードをハッシュ化して保存する
3. WHEN ユーザーがログインする THEN THE System SHALL 認証トークンを発行する
4. WHEN 認証トークンが無効または期限切れ THEN THE API SHALL 401エラーを返す
5. WHEN ユーザーがログアウトする THEN THE System SHALL 認証トークンを無効化する

### 要件 4: 物件検索とフィルタリング

**ユーザーストーリー:** ユーザーとして、条件を指定して空き家を検索したい。これにより、希望に合った物件を効率的に見つけられる。

#### 受入基準

1. WHEN ユーザーが /search エンドポイントにアクセスする THEN THE API SHALL 地域、価格帯、築年数でフィルタリングした物件リストを返す
2. WHEN 検索条件が指定されない THEN THE API SHALL すべての物件を返す
3. WHEN 複数の検索条件が指定される THEN THE System SHALL AND条件で物件を絞り込む
4. WHEN 検索結果が0件 THEN THE API SHALL 空の配列と200ステータスコードを返す
5. WHEN ページネーションパラメータが指定される THEN THE API SHALL 指定されたページの物件リストを返す

### 要件 5: 物件詳細情報の取得

**ユーザーストーリー:** ユーザーとして、特定の物件の詳細情報を閲覧したい。これにより、物件の全情報を確認できる。

#### 受入基準

1. WHEN ユーザーが /houses/{id} エンドポイントにアクセスする THEN THE API SHALL 指定されたIDの物件詳細を返す
2. WHEN 指定されたIDの物件が存在しない THEN THE API SHALL 404エラーを返す
3. WHEN 物件詳細を返す THEN THE API SHALL すべての物件属性と写真URLを含める
4. WHEN 物件に価格変動履歴がある THEN THE API SHALL 履歴情報も含める
5. WHEN 認証されていないユーザーがアクセスする THEN THE API SHALL 401エラーを返す

### 要件 6: マイリスト機能

**ユーザーストーリー:** ユーザーとして、気になる物件をマイリストに保存したい。これにより、後で簡単に物件を確認できる。

#### 受入基準

1. WHEN ユーザーが物件をマイリストに追加する THEN THE System SHALL ユーザーIDと物件IDの関連を保存する
2. WHEN 既にマイリストに存在する物件を追加しようとする THEN THE System SHALL 重複を防ぎ、既存の関連を維持する
3. WHEN ユーザーがマイリストを取得する THEN THE API SHALL ユーザーが保存したすべての物件を返す
4. WHEN ユーザーが物件をマイリストから削除する THEN THE System SHALL 該当する関連を削除する
5. WHEN 削除対象の物件がマイリストに存在しない THEN THE API SHALL 404エラーを返す

### 要件 7: メール通知機能

**ユーザーストーリー:** ユーザーとして、新規物件や価格変動の通知をメールで受け取りたい。これにより、最新情報を見逃さない。

#### 受入基準

1. WHEN 新規物件が登録される THEN THE Notification_Service SHALL 通知設定を有効にしているユーザーにメールを送信する
2. WHEN マイリストの物件価格が変動する THEN THE Notification_Service SHALL その物件をマイリストに保存しているユーザーにメールを送信する
3. WHEN メール送信が失敗する THEN THE System SHALL エラーをログに記録し、リトライキューに追加する
4. WHEN ユーザーが通知設定を無効にする THEN THE System SHALL そのユーザーへの通知送信を停止する
5. WHEN メール本文を生成する THEN THE System SHALL 物件の住所、価格、詳細ページURLを含める

### 要件 8: データベース接続とトランザクション管理

**ユーザーストーリー:** システム管理者として、データの整合性を保ちたい。これにより、信頼性の高いシステムを提供できる。

#### 受入基準

1. WHEN Database 接続を確立する THEN THE System SHALL 環境変数から接続情報を読み込む
2. WHEN 複数のデータベース操作を実行する THEN THE System SHALL トランザクション内で操作を実行する
3. WHEN データベース操作が失敗する THEN THE System SHALL トランザクションをロールバックする
4. WHEN トランザクションが成功する THEN THE System SHALL 変更をコミットする
5. WHEN Database 接続が切断される THEN THE System SHALL 自動的に再接続を試みる

### 要件 9: エラーハンドリングとロギング

**ユーザーストーリー:** システム管理者として、エラーを適切に処理し、ログを記録したい。これにより、問題を迅速に特定し解決できる。

#### 受入基準

1. WHEN システムエラーが発生する THEN THE System SHALL エラー詳細をログファイルに記録する
2. WHEN API エラーが発生する THEN THE API SHALL 適切なHTTPステータスコードとエラーメッセージを返す
3. WHEN スクレイピングエラーが発生する THEN THE Scraper SHALL エラーをログに記録し、次のサイトに進む
4. WHEN データベースエラーが発生する THEN THE System SHALL エラーをログに記録し、ユーザーに500エラーを返す
5. WHEN ログレベルが設定される THEN THE System SHALL 指定されたレベル以上のログのみを出力する

### 要件 10: ヘルスチェックとモニタリング

**ユーザーストーリー:** システム管理者として、システムの稼働状況を監視したい。これにより、問題を早期に発見できる。

#### 受入基準

1. WHEN /health エンドポイントにアクセスする THEN THE API SHALL システムの稼働状況を返す
2. WHEN Database 接続が正常 THEN THE API SHALL ヘルスチェックで "healthy" を返す
3. WHEN Database 接続が失敗 THEN THE API SHALL ヘルスチェックで "unhealthy" を返す
4. WHEN スクレイピングジョブが実行される THEN THE System SHALL ジョブのステータスを記録する
5. WHEN 最後のスクレイピングから24時間以上経過 THEN THE System SHALL アラートをログに記録する
