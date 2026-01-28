import os
import requests
from bs4 import BeautifulSoup
import re
from supabase import create_client, Client


SUPABASE_URL = os.environ.get("SUPABASE_URL")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY")

# --- 1. 接続設定  ---
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

TARGET_URL = "https://www.city.niimi.okayama.jp/akurashi/customer/customer_search"

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

        # 1. まず、現在のデータベースに保存されている「前回の価格」を引いてくる
        existing_data = supabase.table("properties") \
            .select("price") \
            .eq("id", data['id']) \
            .execute()

        # 物件がすでに存在するかチェック
        if existing_data.data:
            old_price = existing_data.data[0]['price']
            new_price = data['price']
            diff = old_price - new_price # 値下がり額

            # 2. 価格に変更があったか？
            if old_price != new_price:
                # 価格が変わったので、最新情報を更新（upsert）
                supabase.table("properties").upsert(data).execute()

                # 履歴テーブル（price_history）に古い価格を記録
                history_record = {
                    "property_id": data['id'],
                    "price": new_price,
                    "changed_at": "now()" # Supabase側で現在時刻をいれる設定なら
                }
                supabase.table("price_history").insert(history_record).execute()

                # 3. 【核心】10万円以上の値下げか判定
                if diff >= 100000:
                    print(f"🔥 大幅値下げ検知！: {data['title']}")
                    print(f"   {old_price:,}円 → {new_price:,}円 (▲{diff:,}円)")
                else:
                    print(f"✨ 価格変更: {data['title']} ({old_price:,}円 → {new_price:,}円)")
            else:
                # 価格が変わっていないなら、生存確認（チェック時刻）だけ更新
                # （今のテーブル設計だとupsertしちゃうのが一番楽です）
                supabase.table("properties").upsert(data).execute()
        
        else:
            # 新着物件の場合
            supabase.table("properties").upsert(data).execute()
            print(f"🆕 新着物件！: {data['title']} / {data['price']:,}円")

if __name__ == "__main__":
    print(f"--- 新見市公式：データ同期開始 ---")
    akiya_list = scrape_niimi_list()
    print(f"解析成功: {len(akiya_list)} 件の物件が見つかりました。")
    save_to_supabase(akiya_list)