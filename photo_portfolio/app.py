import streamlit as st
import os
import json
from PIL import Image, ImageOps
from PIL.ExifTags import TAGS
import datetime
import logging
import time
import base64
import hashlib
import shutil
from dotenv import load_dotenv

# 環境変数の読み込み
load_dotenv()

# パスワードを環境変数から取得
ADMIN_PASSWORD = os.getenv('ADMIN_PASSWORD', 'default_password')

# 定数定義
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
DATA_DIR = os.path.join(BASE_DIR, "data")
LOG_DIR = os.path.join(DATA_DIR, "logs")
PHOTO_CATEGORIES = ["動物", "風景", "街並み", "スポーツ", "自然", "ポートレート"]

# 必要なディレクトリを作成
for directory in [UPLOAD_DIR, DATA_DIR, LOG_DIR]:
    os.makedirs(directory, exist_ok=True)

# カテゴリーディレクトリの作成
for category in PHOTO_CATEGORIES:
    os.makedirs(os.path.join(UPLOAD_DIR, category), exist_ok=True)

# 設定ファイルのパス
CONFIG_FILES = {
    "profile": os.path.join(DATA_DIR, "profile_data.json"),
    "sns": os.path.join(DATA_DIR, "sns_data.json"),
    "site": os.path.join(DATA_DIR, "site_data.json"),
    "metadata": os.path.join(DATA_DIR, "photos_metadata.json")
}

# ロギング設定（ディレクトリ作成後に実行）
logging.basicConfig(
    filename=os.path.join(LOG_DIR, 'app.log'),
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    encoding='utf-8'
)

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()

def load_metadata():
    try:
        with open(CONFIG_FILES["metadata"], 'r', encoding='utf-8') as f:
            return json.load(f)
    except FileNotFoundError:
        return {"photos": {}}

def save_metadata(metadata):
    with open(CONFIG_FILES["metadata"], 'w', encoding='utf-8') as f:
        json.dump(metadata, f, ensure_ascii=False, indent=4)

def update_photo_metadata(photo_path, new_metadata):
    metadata = load_metadata()
    if "photos" not in metadata:
        metadata["photos"] = {}
    metadata["photos"][photo_path] = new_metadata
    save_metadata(metadata)
    return True

def display_photo_details(photo_path, metadata):
    if st.session_state.authenticated:
        st.markdown("### 📝 編集")
        with st.form(f"edit_form_{photo_path}"):
            new_title = st.text_input("タイトル", metadata.get("title", ""), key=f"title_{photo_path}")
            new_location = st.text_input("撮影場所", metadata.get("location", ""), key=f"location_{photo_path}")
            new_date = st.text_input("撮影日", metadata.get("date", ""), key=f"date_{photo_path}")
            new_settings = st.text_input("カメラ設定", metadata.get("camera_settings", ""), key=f"settings_{photo_path}")
            new_desc = st.text_area("説明", metadata.get("description", ""), key=f"desc_{photo_path}")
            submitted = st.form_submit_button("更新")
            if submitted:
                new_metadata = {
                    "title": new_title,
                    "location": new_location,
                    "date": new_date,
                    "camera_settings": new_settings,
                    "description": new_desc
                }
                if update_photo_metadata(photo_path, new_metadata):
                    st.success("メタデータを更新しました")
                    st.rerun()
    else:
        st.markdown(f"""
        **タイトル**: {metadata.get("title", "無題")}  
        **撮影場所**: {metadata.get("location", "場所未設定")}  
        **撮影日**: {metadata.get("date", "日付未設定")}  
        **カメラ設定**: {metadata.get("camera_settings", "設定未設定")}  

        **説明**:  
        {metadata.get("description", "説明なし")}
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

    # 写真の表示用コンテナ
    cols = st.columns(4)
    for idx, photo in enumerate(photos):
        col = cols[idx % 4]
        with col:
            img_path = os.path.join(UPLOAD_DIR, category, photo)
            thumb = create_thumbnail(img_path)
            if thumb:
                # 写真コンテナ
                with st.container():
                    # サムネイル表示
                    st.image(thumb, use_column_width=True)
                    
                    # 管理者の場合、削除ボタンを表示
                    if st.session_state.authenticated:
                        if st.button("🗑️", key=f"delete_{photo}", help="写真を削除"):
                            if delete_photo(img_path, photo, metadata):
                                st.success(f"✅ {photo} を削除しました")
                                time.sleep(1)
                                st.rerun()
                    
                    # ボタン行
                    col1, col2 = st.columns(2)
                    with col1:
                        # 全画面表示ボタン
                        if st.button("🔍 全画面", key=f"full_{photo}"):
                            st.session_state.show_fullscreen = True
                            st.session_state.fullscreen_image = img_path
                            st.session_state.fullscreen_photo = photo
                            st.rerun()
                    
                    with col2:
                        # 詳細情報
                        with st.expander("📷 詳細"):
                            show_photo_details(img_path, metadata.get("photos", {}).get(photo, {}))

    # 全画面表示
    if getattr(st.session_state, 'show_fullscreen', False):
        with st.container():
            # 全画面表示用のカラムを作成
            col1, col2, col3 = st.columns([1, 10, 1])
            
            with col2:
                # 大きな画像を表示
                st.image(st.session_state.fullscreen_image, use_column_width=True)
                
                # EXIF情報の表示
                with st.expander("📷 撮影情報"):
                    show_photo_details(st.session_state.fullscreen_image, 
                                     metadata.get("photos", {}).get(st.session_state.fullscreen_photo, {}))
                
                # 閉じるボタン
                if st.button("✖ 閉じる", key="close_fullscreen"):
                    st.session_state.show_fullscreen = False
                    st.session_state.fullscreen_image = None
                    st.session_state.fullscreen_photo = None
                    st.rerun()

def get_image_base64(image_path):
    """画像をBase64エンコードする"""
    try:
        with open(image_path, "rb") as image_file:
            return base64.b64encode(image_file.read()).decode()
    except Exception as e:
        logging.error(f"画像エンコードエラー: {str(e)}")
        return ""

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
                
                if tag == "Model":  # カメラ本体
                    exif_data["camera"] = str(value).strip()
                elif tag == "LensModel":  # レンズ情報
                    exif_data["lens"] = str(value).strip()
                elif tag == "DateTimeOriginal":  # 撮影日時
                    try:
                        date_obj = datetime.datetime.strptime(str(value), '%Y:%m:%d %H:%M:%S')
                        exif_data["date"] = date_obj.strftime('%Y-%m-%d')
                    except:
                        pass
                elif tag == "FNumber":  # F値
                    if isinstance(value, tuple):
                        exif_data["f_number"] = f"f/{value[0]/value[1]:.1f}"
                elif tag == "ExposureTime":  # シャッタースピード
                    if isinstance(value, tuple):
                        if value[0] >= value[1]:
                            exif_data["exposure"] = f"{value[0]/value[1]:.1f}秒"
                        else:
                            exif_data["exposure"] = f"1/{value[1]/value[0]:.0f}秒"
                elif tag == "ISOSpeedRatings":  # ISO感度
                    exif_data["iso"] = f"ISO {value}"
                elif tag == "FocalLength":  # 焦点距離
                    if isinstance(value, tuple):
                        exif_data["focal_length"] = f"{value[0]/value[1]:.0f}mm"
            
            return exif_data
    except Exception as e:
        logging.error(f"EXIF読み取りエラー: {str(e)}")
        return {}

def create_thumbnail(image_path, size=(300, 300)):
    """サムネイルの作成"""
    try:
        with Image.open(image_path) as img:
            # 画像の縦横比を維持したままリサイズ
            img.thumbnail(size, Image.Resampling.LANCZOS)
            return img
    except Exception as e:
        logging.error(f"サムネイル作成エラー: {str(e)}")
        return None

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
            **exif_data
        }
        save_metadata(metadata)
        
        return True, filename
    except Exception as e:
        logging.error(f"写真アップロードエラー: {str(e)}")
        return False, str(e)

def update_metadata_from_exif(photo_path, category):
    img_path = os.path.join(f"uploads/{category}", photo_path)
    
    if not os.path.exists(img_path):
        st.error(f"ファイルが見つかりません: {img_path}")
        return False
        
    exif_data = get_exif_data(img_path)
    metadata = load_metadata()
    
    try:
        # 既存のメタデータを保持
        existing_metadata = metadata["photos"].get(photo_path, {})
        
        # カメラ設定の構築
        camera_settings = []
        if "f_number" in exif_data:
            camera_settings.append(exif_data["f_number"])
        if "exposure" in exif_data:
            camera_settings.append(exif_data["exposure"])
        if "iso" in exif_data:
            camera_settings.append(exif_data["iso"])
        
        # 新しいメタデータの作成（既存の値を保持）
        new_metadata = {
            "title": existing_metadata.get("title", os.path.splitext(photo_path)[0]),
            "location": existing_metadata.get("location", ""),
            "date": exif_data.get("date", existing_metadata.get("date", datetime.datetime.now().strftime("%Y-%m-%d"))),
            "camera_settings": ", ".join(camera_settings) if camera_settings else existing_metadata.get("camera_settings", ""),
            "camera": exif_data.get("camera", existing_metadata.get("camera", "")),
            "lens": exif_data.get("lens", existing_metadata.get("lens", "")),
            "description": existing_metadata.get("description", "")
        }
        
        metadata["photos"][photo_path] = new_metadata
        save_metadata(metadata)
        return True
        
    except Exception as e:
        st.error(f"メタデータの更新中にエラーが発生しました ({photo_path}): {str(e)}")
        return False

def initialize_session_state():
    if 'current_page' not in st.session_state:
        st.session_state.current_page = "home"
    if 'authenticated' not in st.session_state:
        st.session_state.authenticated = False

def check_password():
    """パスワード認証"""
    if "authenticated" not in st.session_state:
        st.session_state.authenticated = False
        
    if not st.session_state.authenticated:
        password = st.text_input("パスワードを入力してください", type="password")
        if st.button("ログイン"):
            if password == ADMIN_PASSWORD:
                st.session_state.authenticated = True
                st.success("ログインしました")
                st.rerun()
            else:
                st.error("パスワードが違います")
        return False
    return True

def main():
    initialize_session_state()
    
    # ページ設定
    st.set_page_config(
        page_title="E-chun's Photo Portfolio",
        page_icon="📸",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # サイドバー
    with st.sidebar:
        st.title("📸 いーちゅん's Portfolio")
        st.write("写真で切り取る私の視点")
        
        # 管理者ログイン/ログウト
        if not st.session_state.authenticated:
            with st.expander("🔒 管理者ログイン"):
                password = st.text_input("パスワード", type="password")
                if st.button("ログイン"):
                    if hash_password(password) == hash_password("echun0106"):
                        st.session_state.authenticated = True
                        st.rerun()
        else:
            if st.button("ログアウト"):
                st.session_state.authenticated = False
                st.rerun()
            
            # 管理者パネルへのリンクを追加
            if st.button("🔧 管理者パネル"):
                st.session_state.current_page = "admin"
                st.rerun()
        
        # プロフィールページへのリンク
        if st.button("👤 プロフィール"):
            st.session_state.current_page = "profile"
            st.rerun()
        
        # カテゴリーボタン
        st.markdown("### 📸 カテゴリー")
        for category in PHOTO_CATEGORIES:
            if st.button(f"📁 {category}", key=f"cat_{category}"):
                st.session_state.current_page = category
                st.rerun()
    
    # メインコンテンツ
    if st.session_state.current_page == "profile":
        show_profile()
    elif st.session_state.current_page == "admin":
        if st.session_state.authenticated:
            show_admin_panel()
        else:
            st.error("管理者権限が必要です")
            st.session_state.current_page = "home"
            st.rerun()
    else:
        show_photo_gallery()

def show_profile():
    """プロフィールページの表示"""
    st.title("👤 プロフィール")
    
    profile_data = safe_load_json(CONFIG_FILES["profile"], {
        "name": "いーちゅん / E-chun",
        "bio": "写真家 / フォトグラファー",
        "equipment": "",
        "genres": [],
        "history": []
    })
    
    sns_data = safe_load_json(CONFIG_FILES["sns"], {
        "instagram": "",
        "twitter": ""
    })
    
    col1, col2 = st.columns([1, 2])
    
    with col1:
        profile_photo_path = os.path.join(DATA_DIR, "profile_photo.jpg")
        if os.path.exists(profile_photo_path):
            st.image(profile_photo_path, width=300)
        else:
            st.info("プロフィール写真が未設定です")
    
    with col2:
        # 名前と自己紹介
        st.markdown(f"## {profile_data.get('name', 'いーちゅん / E-chun')}")
        st.write(profile_data.get('bio', '写真家 / フォトグラファー'))
        
        # 使用機材
        st.markdown("### 📸 使用機材")
        equipment_list = profile_data.get('equipment', '').split('\n')
        for item in equipment_list:
            if item.strip():
                st.write(f"- {item.strip()}")
        
        # 得意ジャンル
        st.markdown("### 🎯 得意ジャンル")
        for genre in profile_data.get('genres', []):
            st.write(f"- {genre}")
        
        # SNSリンク
        st.markdown("### 🌐 SNS")
        instagram_id = sns_data.get('instagram', '')
        twitter_id = sns_data.get('twitter', '')
        
        if instagram_id:
            st.markdown(f"[![Instagram](https://img.shields.io/badge/Instagram-E4405F?style=for-the-badge&logo=instagram&logoColor=white)](https://instagram.com/{instagram_id})")
        if twitter_id:
            st.markdown(f"[![Twitter](https://img.shields.io/badge/Twitter-1DA1F2?style=for-the-badge&logo=twitter&logoColor=white)](https://twitter.com/{twitter_id})")
        
        # 活動歴
        st.markdown("### 📅 活動歴")
        for item in profile_data.get('history', []):
            st.write(f"- {item}")

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

def show_admin_panel():
    """管理者パネルの表示"""
    st.title("🔧 管理者パネル")
    
    tabs = st.tabs([
        "📸 写真管理",
        "👤 プロフィール編集",
        "🌐 SNS設定",
        "⚙️ サイト設定"
    ])
    
    with tabs[0]:
        manage_photos()
    
    with tabs[1]:
        manage_profile()
    
    with tabs[2]:
        manage_sns()
    
    with tabs[3]:
        manage_site_settings()

def manage_photos():
    """写真管理機能"""
    st.header("📸 写真管理")
    
    # カテゴリー選択
    category = st.selectbox(
        "カテゴリーを選択",
        PHOTO_CATEGORIES,
        help="アップロード先のカテゴリーを選択してください"
    )
    
    # 既存の写真の表示と管理
    st.markdown("### アップロード済みの写真")
    category_dir = os.path.join(UPLOAD_DIR, category)
    if os.path.exists(category_dir):
        photos = [f for f in os.listdir(category_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
        if photos:
            st.write(f"📁 {category}カテゴリーの写真: {len(photos)}枚")
            
            # 写真の一覧表示と削除機能
            cols = st.columns(4)
            for idx, photo in enumerate(photos):
                col = cols[idx % 4]
                with col:
                    img_path = os.path.join(category_dir, photo)
                    thumb = create_thumbnail(img_path)
                    if thumb:
                        st.image(thumb, caption=photo, use_column_width=True)
                        if st.button("🗑️ 削除", key=f"admin_delete_{photo}"):
                            try:
                                os.remove(img_path)
                                metadata = load_metadata()
                                if photo in metadata.get("photos", {}):
                                    del metadata["photos"][photo]
                                    save_metadata(metadata)
                                st.success(f"✅ {photo} を削除しました")
                                time.sleep(1)
                                st.rerun()
                            except Exception as e:
                                st.error(f"削除に失敗しました: {str(e)}")
        else:
            st.info(f"📂 {category}カテゴリーにはまだ写真がありません")

def manage_profile():
    """プロフィール管理機能"""
    profile_data = safe_load_json(CONFIG_FILES["profile"], {
        "name": "いーちゅん / E-chun",
        "bio": "写真家 / フォトグラファー",
        "equipment": "",
        "genres": [],
        "history": []
    })
    
    st.subheader("プロフィール写真")
    col1, col2 = st.columns([1, 2])
    
    with col1:
        profile_photo_path = os.path.join(DATA_DIR, "profile_photo.jpg")
        if os.path.exists(profile_photo_path):
            st.image(profile_photo_path, width=200)
        else:
            st.info("プロフィール写真が未設定です")
    
    with col2:
        uploaded_file = st.file_uploader(
            "新しいプロフィール写真",
            type=['jpg', 'jpeg', 'png'],
            help="推奨サイズ: 1920x1920px以内"
        )
        if uploaded_file:
            if save_profile_photo(uploaded_file):
                st.success("プロフィール写真を更新しました")
                st.rerun()
            else:
                st.error("プロフィール写真の更新に失敗しました")

    with st.form("profile_form"):
        name = st.text_input("名前", profile_data.get("name", ""))
        bio = st.text_area("自己紹介", profile_data.get("bio", ""))
        equipment = st.text_area(
            "使用機材（改行で区切り）",
            profile_data.get("equipment", ""),
            help="例：NIKON Z 9\nNIKKOR Z 24-70mm f/2.8 S"
        )
        genres = st.text_area(
            "得意ジャンル（改行で区切り）",
            "\n".join(profile_data.get("genres", [])),
            help="例：ポートレート撮影\nスポーツフォト"
        )
        history = st.text_area(
            "活動歴（改行で区切り）",
            "\n".join(profile_data.get("history", [])),
            help="例：写真展「xxxxx」開催 (2024)"
        )
        
        if st.form_submit_button("更新"):
            new_data = {
                "name": name.strip(),
                "bio": bio.strip(),
                "equipment": equipment.strip(),
                "genres": [g.strip() for g in genres.split("\n") if g.strip()],
                "history": [h.strip() for h in history.split("\n") if h.strip()]
            }
            if safe_save_json(CONFIG_FILES["profile"], new_data):
                st.success("プロフィールを更新しました")
                logging.info("プロフィール情報を更新しました")
                st.rerun()
            else:
                st.error("プロフィールの更新に失敗しました")

def manage_sns():
    """SNS設定管理機能"""
    st.header("🌐 SNS設定")
    
    sns_data = safe_load_json(CONFIG_FILES["sns"], {
        "instagram": "",
        "twitter": ""
    })
    
    with st.form("sns_form"):
        instagram = st.text_input(
            "Instagram ID",
            value=sns_data.get("instagram", ""),
            help="@ 以降のユーザー名を入力（例：your_username）"
        )
        
        twitter = st.text_input(
            "Twitter ID",
            value=sns_data.get("twitter", ""),
            help="@ 以降のユーザー名を入力（例：your_username）"
        )
        
        # プレビュー表示
        if instagram or twitter:
            st.markdown("### プレビュー")
            if instagram:
                st.markdown(f"Instagram: [@{instagram}](https://instagram.com/{instagram})")
            if twitter:
                st.markdown(f"Twitter: [@{twitter}](https://twitter.com/{twitter})")
        
        if st.form_submit_button("更新"):
            new_sns_data = {
                "instagram": instagram.strip(),
                "twitter": twitter.strip()
            }
            if safe_save_json(CONFIG_FILES["sns"], new_sns_data):
                st.success("SNS設定を更新しました")
                st.rerun()
            else:
                st.error("SNS設定の更新に失敗しました")

def manage_site_settings():
    site_data = safe_load_json(CONFIG_FILES["site"], {
        "title": "いーちゅん's Photo Portfolio",
        "description": "写真で切り取る私の視点"
    })
    
    with st.form("site_form"):
        st.subheader("サイト基本設定")
        title = st.text_input("サイトタイトル", site_data.get("title", ""))
        description = st.text_area("サイト説明", site_data.get("description", ""))
        
        if st.form_submit_button("更新"):
            save_site_data({
                "title": title,
                "description": description
            })
            st.success("サイト設定を新しました")
            st.rerun()

def show_photo_management(category):
    photos_dir = os.path.join(UPLOAD_DIR, category)
    if not os.path.exists(photos_dir):
        st.warning(f"カテゴリー {category} には写真がありません")
        return
    
    photos = [f for f in os.listdir(photos_dir) if f.lower().endswith(('.jpg', '.jpeg', '.png'))]
    metadata = load_metadata()
    
    for photo in photos:
        col1, col2, col3 = st.columns([2, 3, 1])
        with col1:
            st.image(os.path.join(photos_dir, photo), width=150)
        with col2:
            st.write(f"ファイル名: {photo}")
            st.write(f"タイトル: {metadata['photos'].get(photo, {}).get('title', '未設定')}")
        with col3:
            if st.button("削除", key=f"delete_{photo}"):
                delete_photo(photo, category)
                st.rerun()

def delete_photo(photo, category):
    try:
        # ファイル削除
        os.remove(os.path.join(UPLOAD_DIR, category, photo))
        
        # メタデータから削除
        metadata = load_metadata()
        if photo in metadata["photos"]:
            del metadata["photos"][photo]
            save_metadata(metadata)
        
        st.success(f"写真を削除しました: {photo}")
    except Exception as e:
        st.error(f"削除エラー: {str(e)}")

def save_profile_photo(file):
    """プロフィール写真の保存と最適化"""
    try:
        profile_path = os.path.join(DATA_DIR, "profile_photo.jpg")
        # バックアップ作成
        if os.path.exists(profile_path):
            backup_path = os.path.join(
                DATA_DIR, 
                "backups", 
                f"profile_photo_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.jpg"
            )
            os.makedirs(os.path.dirname(backup_path), exist_ok=True)
            shutil.copy2(profile_path, backup_path)
        
        # 画像の最適化と保存
        with Image.open(file) as img:
            optimized = optimize_image(img)
            optimized.save(profile_path, "JPEG", quality=85, optimize=True)
        
        logging.info("プロフィール写真を更新しました")
        return True
    except Exception as e:
        logging.error(f"プロフィール写真の保存エラー: {str(e)}")
        return False

def safe_load_json(filepath, default_data):
    """JSONファイルの安全な読み込み"""
    try:
        if os.path.exists(filepath):
            with open(filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return default_data
    except Exception as e:
        logging.error(f"設定ファイル読み込みエラー: {str(e)}")
        return default_data

def safe_save_json(filepath, data):
    """JSONファイルの安全な保存"""
    try:
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        return True
    except Exception as e:
        logging.error(f"設定ファイル保存エラー: {str(e)}")
        return False

def save_sns_data(data):
    safe_save_json(CONFIG_FILES["sns"], data)

def save_site_data(data):
    safe_save_json(CONFIG_FILES["site"], data)

def optimize_image(image, max_size=1920):
    """画像の最適化"""
    try:
        # アスペクト比を保持しながらリサイズ
        image.thumbnail((max_size, max_size), Image.Resampling.LANCZOS)
        # 画質最適化
        optimized = ImageOps.exif_transpose(image)
        return optimized
    except Exception as e:
        logging.error(f"画像最適化エラー: {str(e)}")
        return image

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

if __name__ == "__main__":
    main()
