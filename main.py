import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client, Client


# --- 1. 接続設定  ---
SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# --- LINE設定 ---
LINE_TOKEN = os.environ.get("LINE_CHANNEL_ACCESS_TOKEN")
LINE_USER_ID = os.environ.get("LINE_USER_ID")

# --- ここから新見市のサイトをスクレイピング ---
TARGET_URL = "https://www.city.niimi.okayama.jp/akurashi/customer/customer_search"

def send_line_push(message):
    """LINE Messaging APIを使用してプッシュ通知を送信する"""
    if not LINE_TOKEN or not LINE_USER_ID:
        print("⚠️ LINE Secretsが設定されていないため、通知をスキップします。")
        return

    url = "https://api.line.me/v2/bot/message/push"
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {LINE_TOKEN}"
    }
    payload = {
        "to": LINE_USER_ID,
        "messages": [{"type": "text", "text": message}]
    }
    
    try:
        response = requests.post(url, headers=headers, json=payload)
        if response.status_code != 200:
            print(f"❌ LINE送信失敗: {response.text}")
    except Exception as e:
        print(f"❌ LINE通信エラー: {e}")

def scrape_niimi_list():
    headers = {"User-Agent": "Mozilla/5.0"}
    response = requests.get(TARGET_URL, headers=headers)
    response.encoding = response.apparent_encoding
    soup = BeautifulSoup(response.text, 'html.parser')

    # 物件をすべて取得
    property_cards = soup.select('.p-bukken')
    
    results = []

    for card in property_cards:
        try:
            # 1. 登録番号の取得
            id_dt = card.find('dt', string=re.compile('登録番号'))
            property_id = id_dt.find_next_sibling('dd').get_text(strip=True) if id_dt else None
            if not property_id: continue

            # 2. 販売価格があるかチェック（賃料しかない物件は無視する）
            price_dt = card.find('dt', string='販売価格') # 完全一致で「販売価格」を探す
            if not price_dt:
                print(f"スキップ：登録番号{property_id} は賃貸物件のようです。")
                continue

            price_text = price_dt.find_next_sibling('dd').get_text(strip=True)
            
            # 3. 価格の数値化
            raw_number_match = re.search(r'([\d,.]+)', price_text)
            price_val = 0
            if raw_number_match:
                raw_number = float(raw_number_match.group(1).replace(',', ''))
                # 単位に応じた計算(万と千のみ)
                if "万" in price_text:
                    price_val = int(raw_number * 10000)
                elif "千" in price_text:
                    price_val = int(raw_number * 1000)
                else:
                    price_val = int(raw_number)

            # 4. 所在地
            loc_dt = card.find('dt', string=re.compile('所在地'))
            location = loc_dt.find_next_sibling('dd').get_text(strip=True) if loc_dt else "新見市"

            # 5. 詳細URL (「詳しく見る」ボタンのリンク)
            link_tag = card.find('a', string=re.compile('詳しく見る'))
            detail_url = link_tag['href'] if link_tag else TARGET_URL

            # 6. タイトルの生成 (登録番号と所在地を組み合わせる)
            title = f"登録番号{property_id}（{location}）"

            results.append({
                "id": f"niimi_{property_id}",
                "title": title,
                "price": price_val,
                "status": "公開中",
                "url": detail_url
            })
        except Exception as e:
            print(f"1件解析エラー: {e}")
            continue

    return results

def save_to_supabase(data_list):
    for data in data_list:
        if data['price'] <= 0:
            continue

        # 1. 既存データの確認 [cite: 302]
        existing_data = supabase.table("properties") \
            .select("price") \
            .eq("id", data['id']) \
            .execute()

        # A. 物件がすでに存在する場合 [cite: 303]
        if existing_data.data:
            old_price = existing_data.data[0]['price']
            new_price = data['price']
            diff = old_price - new_price 

            if old_price != new_price:
                # 最新情報に更新し、履歴に保存 [cite: 304, 336]
                supabase.table("properties").upsert(data).execute()
                history_record = {
                    "property_id": data['id'],
                    "price": new_price,
                    "changed_at": "now()" 
                }
                supabase.table("price_history").insert(history_record).execute() [cite: 305]

                # 通知判定 [cite: 306, 337]
                if diff >= 100000:
                    msg = f"🔥 【大幅値下げ】\n{data['title']}\n{old_price:,}円 → {new_price:,}円 (▲{diff:,}円)\n{data['url']}"
                    send_line_push(msg)
                else:
                    msg = f"✨ 【価格変更】\n{data['title']}\n{old_price:,}円 → {new_price:,}円"
                    send_line_push(msg) [cite: 338]
            else:
                # 価格変更なし。生存確認として更新 
                supabase.table("properties").upsert(data).execute()
        
        # B. 新着物件の場合 [cite: 307, 339]
        else:
            supabase.table("properties").upsert(data).execute() [cite: 339]
            # 新着通知を送信
            msg = f"🆕 【新着物件！】\n{data['title']}\n価格: {data['price']:,}円\n{data['url']}"
            print(msg) [cite: 339]
            send_line_push(msg) # ここでLINE通知

if __name__ == "__main__":
    print(f"--- 新見市公式：データ同期開始 ---")
    akiya_list = scrape_niimi_list()
    print(f"解析成功: {len(akiya_list)} 件の物件が見つかりました。")
    save_to_supabase(akiya_list)