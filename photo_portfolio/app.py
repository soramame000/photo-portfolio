import streamlit as st
import os
import json
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import datetime
import logging
import base64
import hashlib
import shutil
import time

# 定数の定義
UPLOAD_DIR = "uploads"
CONFIG_DIR = "config"
PHOTO_CATEGORIES = ["風景", "ポートレート", "スナップ", "その他"]
CONFIG_FILES = {
    "profile": os.path.join(CONFIG_DIR, "profile.json"),
    "sns": os.path.join(CONFIG_DIR, "sns.json"),
    "metadata": os.path.join(CONFIG_DIR, "metadata.json")
}

# ディレクトリの初期化
os.makedirs(UPLOAD_DIR, exist_ok=True)
os.makedirs(CONFIG_DIR, exist_ok=True)
for category in PHOTO_CATEGORIES:
    os.makedirs(os.path.join(UPLOAD_DIR, category), exist_ok=True)

# ロギングの設定
logging.basicConfig(level=logging.INFO)

# セッション状態の初期化
if 'current_page' not in st.session_state:
    st.session_state.current_page = "ホーム"
if 'authenticated' not in st.session_state:
    st.session_state.authenticated = False
if 'show_fullscreen' not in st.session_state:
    st.session_state.show_fullscreen = False
if 'fullscreen_image' not in st.session_state:
    st.session_state.fullscreen_image = None
if 'fullscreen_photo' not in st.session_state:
    st.session_state.fullscreen_photo = None
if 'user_likes' not in st.session_state:
    st.session_state.user_likes = set()

# パスワードのハッシュ化
def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def get_admin_password():
    """パスワードを安全に取得"""
    try:
        return st.secrets["ADMIN_PASSWORD"]
    except:
        # 開発環境用のデフォルトパスワード（本番環境では必ず変更してください）
        return hash_password("admin_password")

def check_password():
    """パスワード認証"""
    if not st.session_state.authenticated:
        password = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if hash_password(password) == get_admin_password():
                st.session_state.authenticated = True
                st.success("ログインしました")
                st.experimental_rerun()
            else:
                st.error("パスワードが違います")
        return False
    return True

def load_config(config_type):
    """設定ファイルの読み込み"""
    config_path = CONFIG_FILES.get(config_type)
    if config_path and os.path.exists(config_path):
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logging.error(f"設定ファイル読み込みエラー: {str(e)}")
    return {}

def save_config(config_type, data):
    """設定ファイルの保存"""
    config_path = CONFIG_FILES.get(config_type)
    if config_path:
        try:
            with open(config_path, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            return True
        except Exception as e:
            logging.error(f"設定ファイル保存エラー: {str(e)}")
    return False

def load_metadata():
    """メタデータの読み込み"""
    return load_config("metadata")

def save_metadata(metadata):
    """メタデータの保存"""
    return save_config("metadata", metadata)

def get_exif_data(image_path):
    """EXIF情報の取得"""
    try:
        with Image.open(image_path) as img:
            exif = img._getexif()
            if not exif:
                return {}
            
            exif_data = {}
            for tag_id, value in exif.items():
                tag = TAGS.get(tag_id, tag_id)
                if tag == "Model":
                    exif_data["camera"] = str(value).strip()
                elif tag == "LensModel":
                    exif_data["lens"] = str(value).strip()
                elif tag == "ExposureTime":
                    if isinstance(value, tuple):
                        exif_data["exposure"] = f"{value[0]}/{value[1]}秒"
                    else:
                        exif_data["exposure"] = f"{value}秒"
                elif tag == "FNumber":
                    if isinstance(value, tuple):
                        exif_data["f_number"] = f"f/{value[0]/value[1]:.1f}"
                    else:
                        exif_data["f_number"] = f"f/{value:.1f}"
                elif tag == "ISOSpeedRatings":
                    exif_data["iso"] = f"ISO {value}"
                elif tag == "FocalLength":
                    if isinstance(value, tuple):
                        exif_data["focal_length"] = f"{value[0]/value[1]}mm"
                    else:
                        exif_data["focal_length"] = f"{value}mm"
                elif tag == "DateTimeOriginal":
                    try:
                        date_obj = datetime.datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                        exif_data["date"] = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
            
            return exif_data
    except Exception as e:
        logging.error(f"EXIF情報取得エラー: {str(e)}")
        return {}

def create_thumbnail(image_path, size=(300, 300)):
    """サムネイルの作成"""
    try:
        with Image.open(image_path) as img:
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
    except Exception as e:
        logging.error(f"サムネイル作成エラー: {str(e)}")
        return None

def delete_photo(img_path, photo, metadata):
    """写真を削除"""
    try:
        os.remove(img_path)
        if photo in metadata.get("photos", {}):
            del metadata["photos"][photo]
            save_metadata(metadata)
        return True
    except Exception as e:
        st.error(f"削除に失敗しました: {str(e)}")
        return False

def show_photo_details(img_path, metadata):
    """写真の詳細情報を表示"""
    exif_data = get_exif_data(img_path)
    combined_data = {**exif_data, **metadata}
    
    st.markdown(f"""
    #### 撮影情報
    - 📸 カメラ: {combined_data.get('camera', '不明')}
    - 🔭 レンズ: {combined_data.get('lens', '不明')}
    - ⚡ シャッタースピード: {combined_data.get('exposure', '不明')}
    - 🎯 絞り値: {combined_data.get('f_number', '不明')}
    - 📊 ISO感度: {combined_data.get('iso', '不明')}
    - 📏 焦点距離: {combined_data.get('focal_length', '不明')}
    - 📅 撮影日: {combined_data.get('date', '不明')}
    """)

def display_photo_grid(photos, category):
    """写真のグリッド表示"""
    metadata = load_metadata()
    
    # カスタムCSS
    st.markdown("""
    <style>
    .photo-container {
        position: relative;
        margin-bottom: 1rem;
    }
    .delete-button {
        position: absolute;
        top: 5px;
        right: 5px;
        z-index: 100;
    }
    .fullscreen-container {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        bottom: 0;
        background: rgba(0, 0, 0, 0.9);
        z-index: 1000;
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
        padding: 20px;
    }
    .fullscreen-image {
        max-width: 90vw;
        max-height: 80vh;
        object-fit: contain;
    }
    </style>
    """, unsafe_allow_html=True)

    cols = st.columns(4)
    for idx, photo in enumerate(photos):
        col = cols[idx % 4]
        with col:
            img_path = os.path.join(UPLOAD_DIR, category, photo)
            thumb = create_thumbnail(img_path)
            if thumb:
                with st.container():
                    st.image(thumb, use_column_width=True)
                    
                    if st.session_state.authenticated:
                        if st.button("🗑️", key=f"delete_{photo}", help="写真を削除"):
                            if delete_photo(img_path, photo, metadata):
                                st.success(f"✅ {photo} を削除しました")
                                time.sleep(1)
                                st.experimental_rerun()
                    
                    # いいね機能
                    if st.button("❤️ いいね", key=f"like_{photo}"):
                        st.session_state.user_likes.add(photo)
                        st.success("いいねしました！")
                    
                    # コメント表示と投稿
                    with st.expander("💬 コメント"):
                        comments = metadata.get("photos", {}).get(photo, {}).get("comments", [])
                        for comment in comments:
                            st.write(f"- {comment}")
                        new_comment = st.text_input("コメントを追加", key=f"comment_{photo}")
                        if st.button("投稿", key=f"submit_comment_{photo}"):
                            if new_comment:
                                comments.append(new_comment)
                                metadata["photos"][photo]["comments"] = comments
                                save_metadata(metadata)
                                st.success("コメントを投稿しました")
                                st.experimental_rerun()
                            else:
                                st.error("コメントを入力してください")
                    
                    # 全画面表示ボタン
                    if st.button("🔍 全画面", key=f"full_{photo}"):
                        st.session_state.show_fullscreen = True
                        st.session_state.fullscreen_image = img_path
                        st.session_state.fullscreen_photo = photo
                        st.experimental_rerun()

    # 全画面表示
    if st.session_state.show_fullscreen and st.session_state.fullscreen_image:
        st.markdown(f"""
        <div class="fullscreen-container">
            <button onclick="window.location.reload();" style="position: absolute; top: 20px; right: 20px; background: none; border: none; color: white; font-size: 24px; cursor: pointer;">✖</button>
            <img src="data:image/png;base64,{get_image_base64(st.session_state.fullscreen_image)}" class="fullscreen-image">
            <div style="margin-top: 20px;">
                <button onclick="window.location.reload();" style="padding: 10px 20px; font-size: 16px;">閉じる</button>
            </div>
        </div>
        """, unsafe_allow_html=True)

def get_image_base64(image_path):
    """画像をBase64エンコードする"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        logging.error(f"画像エンコードエラー: {str(e)}")
        return ""

def show_photo_gallery():
    """写真ギャラリーの表示"""
    if st.session_state.current_page in PHOTO_CATEGORIES:
        category = st.session_state.current_page
        st.title(f"📸 {category}")
        
        # 写真の取得
        category_dir = os.path.join(UPLOAD_DIR, category)
        if os.path.exists(category_dir):
            photos = [f for f in os.listdir(category_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
            if photos:
                display_photo_grid(photos, category)
            else:
                st.info(f"{category}の写真はまだありません")
    else:
        st.title("📸 写真ギャラリー")
        st.write("サイドバーからカテゴリーを選択してください")

def save_uploaded_photo(file, category):
    """写真のアップロードと保存"""
    try:
        # 保存先の確認・作成
        save_dir = os.path.join(UPLOAD_DIR, category)
        os.makedirs(save_dir, exist_ok=True)
        
        # ファイル名の検証と重複チェック
        filename = file.name
        file_path = os.path.join(save_dir, filename)
        
        # 同名ファイルが存在する場合は番号を付加
        base, ext = os.path.splitext(filename)
        counter = 1
        while os.path.exists(file_path):
            filename = f"{base}_{counter}{ext}"
            file_path = os.path.join(save_dir, filename)
            counter += 1
        
        # ファイル保存
        with open(file_path, "wb") as f:
            f.write(file.getbuffer())
        
        # EXIF情報の取得と保存
        exif_data = get_exif_data(file_path)
        metadata = load_metadata()
        
        if "photos" not in metadata:
            metadata["photos"] = {}
            
        metadata["photos"][filename] = {
            "category": category,
            "upload_date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "title": os.path.splitext(filename)[0],
            "comments": [],
            **exif_data
        }
        save_metadata(metadata)
        
        return True, filename
    except Exception as e:
        logging.error(f"写真アップロードエラー: {str(e)}")
        return False, str(e)

def manage_photos():
    """写真管理機能"""
    st.header("📸 写真管理")
    
    # カテゴリー選択
    category = st.selectbox(
        "カテゴリーを選択",
        PHOTO_CATEGORIES,
        help="アップロード先のカテゴリーを選択してください"
    )
    
    # アップロードフォーム
    with st.form("upload_form"):
        st.markdown("### 写真のアップロード")
        uploaded_files = st.file_uploader(
            "写真を選択",
            type=['jpg', 'jpeg', 'png'],
            accept_multiple_files=True,
            help="複数の写真を一度にアップロードできます"
        )
        
        submit_button = st.form_submit_button("アップロード")
        
        if submit_button and uploaded_files:
            progress_text = "写真をアップロード中..."
            progress_bar = st.progress(0)
            
            success_count = 0
            failed_files = []
            
            for i, file in enumerate(uploaded_files):
                progress = (i + 1) / len(uploaded_files)
                progress_bar.progress(progress)
                
                success, result = save_uploaded_photo(file, category)
                if success:
                    success_count += 1
                    st.success(f"✅ {file.name} のアップロードに成功しました")
                else:
                    failed_files.append((file.name, result))
                    st.error(f"❌ {file.name} のアップロードに失敗しました: {result}")
            
            progress_bar.empty()
            if success_count > 0:
                st.success(f"🎉 {success_count}個の写真をアップロードしました")
                time.sleep(1)
                st.experimental_rerun()
            
            if failed_files:
                st.error("以下のファイルのアップロードに失敗しました:")
                for file_name, error in failed_files:
                    st.write(f"- {file_name}: {error}")
    
    # 既存の写真の表示と管理
    st.markdown("### アップロード済みの写真")
    category_dir = os.path.join(UPLOAD_DIR, category)
    if os.path.exists(category_dir):
        photos = [f for f in os.listdir(category_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if photos:
            st.write(f"📁 {category}カテゴリーの写真: {len(photos)}枚")
            display_photo_grid(photos, category)
        else:
            st.info(f"📂 {category}カテゴリーにはまだ写真がありません")

def manage_profile():
    """プロフィール管理"""
    st.header("👤 プロフィール管理")
    
    profile = load_config("profile")
    
    # プロフィール情報の入力
    with st.form("profile_form"):
        name = st.text_input("名前", value=profile.get("name", ""))
        title = st.text_input("肩書き", value=profile.get("title", ""))
        bio = st.text_area("自己紹介", value=profile.get("bio", ""))
        email = st.text_input("メールアドレス", value=profile.get("email", ""))
        
        if st.form_submit_button("保存"):
            profile = {
                "name": name,
                "title": title,
                "bio": bio,
                "email": email
            }
            if save_config("profile", profile):
                st.success("✅ プロフィールを保存しました")
            else:
                st.error("❌ プロフィールの保存に失敗しました")

def manage_sns():
    """SNS管理"""
    st.header("📱 SNS管理")
    
    sns = load_config("sns")
    
    # SNSリンクの入力
    with st.form("sns_form"):
        twitter = st.text_input("Twitter URL", value=sns.get("twitter", ""))
        instagram = st.text_input("Instagram URL", value=sns.get("instagram", ""))
        facebook = st.text_input("Facebook URL", value=sns.get("facebook", ""))
        
        if st.form_submit_button("保存"):
            sns = {
                "twitter": twitter,
                "instagram": instagram,
                "facebook": facebook
            }
            if save_config("sns", sns):
                st.success("✅ SNS情報を保存しました")
            else:
                st.error("❌ SNS情報の保存に失敗しました")

def show_profile():
    """プロフィールページの表示"""
    st.title("👤 プロフィール")
    
    profile = load_config("profile")
    sns = load_config("sns")
    
    # プロフィール情報の表示
    if profile:
        st.markdown(f"""
        ### {profile.get('name', '')}
        #### {profile.get('title', '')}
        
        {profile.get('bio', '')}
        
        📧 {profile.get('email', '')}
        """)
    
    # SNSリンクの表示
    if sns:
        st.markdown("### SNS")
        cols = st.columns(3)
        
        if sns.get("twitter"):
            cols[0].markdown(f"[Twitter]({sns['twitter']})")
        if sns.get("instagram"):
            cols[1].markdown(f"[Instagram]({sns['instagram']})")
        if sns.get("facebook"):
            cols[2].markdown(f"[Facebook]({sns['facebook']})")

def show_home():
    """ホームページの表示"""
    st.title("📸 写真ポートフォリオ")
    
    # プロフィール情報の取得
    profile = load_config("profile")
    name = profile.get("name", "写真家")
    
    st.markdown(f"""
    ### ようこそ、{name}のポートフォリオサイトへ！
    
    サイドバーから以下のコンテンツにアクセスできます：
    
    - 📸 写真ギャラリー（カテゴリー別）
    - 👤 プロフィール
    - 💬 お問い合わせ
    
    写真をお楽しみください！
    """)

def show_contact_form():
    """お問い合わせフォームの表示"""
    st.title("💬 お問い合わせ")
    
    with st.form("contact_form"):
        name = st.text_input("お名前")
        email = st.text_input("メールアドレス")
        message = st.text_area("メッセージ")
        
        if st.form_submit_button("送信"):
            if name and email and message:
                # メール送信機能を実装する場合はここに記述
                st.success("お問い合わせを送信しました。ありがとうございます。")
            else:
                st.error("すべての項目を入力してください。")

def main():
    """メイン関数"""
    # サイドバーの設定
    st.sidebar.title("📸 Photo Portfolio")
    
    # ダークモードの切り替え
    is_dark_mode = st.sidebar.checkbox("🌙 ダークモード", value=False)
    if is_dark_mode:
        st.markdown(
            """
            <style>
            .main {
                background-color: #2E2E2E;
                color: white;
            }
            </style>
            """,
            unsafe_allow_html=True
        )
    
    # ナビゲーションメニュー
    menu_items = ["ホーム", "プロフィール", "お問い合わせ"] + PHOTO_CATEGORIES
    
    # 管理者メニュー
    if st.session_state.authenticated:
        menu_items.extend(["---", "写真管理", "プロフィール管理", "SNS管理", "ログアウト"])
    else:
        menu_items.append("---")
        menu_items.append("管理者ログイン")
    
    # メニュー選択
    selection = st.sidebar.selectbox("メニュー", menu_items)
    
    # 選択に応じたページ表示
    if selection == "ホーム":
        st.session_state.current_page = "ホーム"
        show_home()
    elif selection == "プロフィール":
        st.session_state.current_page = "プロフィール"
        show_profile()
    elif selection == "お問い合わせ":
        st.session_state.current_page = "お問い合わせ"
        show_contact_form()
    elif selection in PHOTO_CATEGORIES:
        st.session_state.current_page = selection
        show_photo_gallery()
    elif selection == "管理者ログイン":
        st.session_state.current_page = "管理者ログイン"
        check_password()
    elif selection == "写真管理" and st.session_state.authenticated:
        st.session_state.current_page = "写真管理"
        manage_photos()
    elif selection == "プロフィール管理" and st.session_state.authenticated:
        st.session_state.current_page = "プロフィール管理"
        manage_profile()
    elif selection == "SNS管理" and st.session_state.authenticated:
        st.session_state.current_page = "SNS管理"
        manage_sns()
    elif selection == "ログアウト" and st.session_state.authenticated:
        st.session_state.authenticated = False
        st.success("ログアウトしました")
        st.experimental_rerun()

if __name__ == "__main__":
    main()
