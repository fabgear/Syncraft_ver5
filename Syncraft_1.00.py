# ===============================================================
# ▼▼▼ Streamlit UI ▼▼▼
# ===============================================================
st.set_page_config(page_title="Syncraft", page_icon="📝", layout="wide")

st.title('Syncraft')
st.caption('　ナレーション原稿作成ツール with gemini(β)')

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# --- セッションステートの初期化 ---
if "ai_result_cache" not in st.session_state: st.session_state["ai_result_cache"] = ""
if "last_input_hash" not in st.session_state: st.session_state["last_input_hash"] = None
if "input_text" not in st.session_state: st.session_state["input_text"] = ""

st.markdown("""<style> textarea { font-size: 14px !important; } </style>""", unsafe_allow_html=True)

placeholder_text = """ここにPremiereのテロップ情報をペーストするか、
下のボタンからXMLファイルをアップロードしてください。

【ペーストする場合の推奨フォーマット】
00;00;00;00 - 00;00;02;29
Nああああ
"""

help_text = """
【機能詳細】
・ENDタイムとH（時間）をまたぐ時の仕切り自動挿入
・✅N強制挿入がONの場合、本文頭に自動で全角「Ｎ」が挿入されます
　ＶＯや実況などの時は注意！
・ナレーション本文の半角英数字は全て全角に変換されます
・✅ｍｍ：ｓｓがONの場合タイムコードにコロンが入ります
・✅誤字脱字チェックをONにするとAIが原稿の校正を行います
　注意箇所には🔴がつきます

【フォーマット】
・Premiereのキャプションをテキストで書き出した形式が
　半秒単位でタイムが出るのでオススメです
・サイトでxmlから変換したフォーマットも使えます
"""

# --- コールバック関数の定義 ---
def on_upload_change():
    """ファイルアップローダーの状態が変わった時に呼ばれるコールバック"""
    uploaded_file = st.session_state.get("xml_uploader")
    if uploaded_file:
        with st.spinner("XMLファイルを解析中..."):
            parsed_text = parse_premiere_xml(uploaded_file)
            st.session_state["input_text"] = parsed_text

def on_text_area_change():
    """テキストエリアが手動で編集された時に呼ばれるコールバック"""
    st.session_state["input_text"] = st.session_state.get("input_text_area", "")

# --- UIレイアウト ---
col1_main, col2_main = st.columns(2)
with col1_main:
    # XMLアップローダー
    st.file_uploader(
        "Premiere ProのシーケンスXML (.xml) をアップロード",
        type=['xml'],
        key="xml_uploader",
        on_change=on_upload_change
    )
    
    # テキストエリア
    st.text_area(
        "　ここに元原稿をペーストするか、上記からXMLをアップロードしてください。", 
        height=420,
        placeholder=placeholder_text,
        help=help_text,
        key="input_text_area",
        on_change=on_text_area_change,
        value=st.session_state["input_text"]
    )

# --- キャッシュ管理 ---
cur_hash = hash(st.session_state["input_text"].strip())
if st.session_state["last_input_hash"] != cur_hash:
    st.session_state["ai_result_cache"] = ""
    st.session_state["last_input_hash"] = cur_hash

# --- コントロールエリア ---
col1_opt, col2_opt, col3_opt, _ = st.columns([1.5, 1.5, 3, 7.5]) 
with col1_opt: n_force_insert = st.checkbox("Ｎ強制挿入", value=True)
with col2_opt: mm_ss_colon = st.checkbox("ｍｍ：ｓｓ", value=False)
with col3_opt: ai_check_flag = st.checkbox("誤字脱字チェック(β)", value=False)

# --- 変換実行と結果表示 ---
if st.session_state["input_text"]:
    try:
        current_input = st.session_state["input_text"]
        initial_result = convert_narration_script(current_input, n_force_insert, mm_ss_colon)
        ai_data = initial_result["ai_data"]
        block_start_times = initial_result["start_times"]
        highlight_indices = set()
        ai_display_text = ""

        if ai_check_flag:
            with st.spinner("Geminiが誤字脱字をチェック中...数分お待ちください🙇"):
                if not st.session_state.get("ai_result_cache"):
                    ai_result_md = check_narration_with_gemini(ai_data, GEMINI_API_KEY)
                    st.session_state["ai_result_cache"] = ai_result_md
            ai_result_md = st.session_state.get("ai_result_cache", "")
            if ai_result_md and "問題ありませんでした" not in ai_result_md:
                new_table_header = "| タイム | 修正提案 | 理由 |\n|---|---|---|"
                new_table_rows = []
                for line in ai_result_md.splitlines():
                    if line.strip().startswith('|') and '---' not in line and 'No.' not in line:
                        try:
                            parts = [p.strip() for p in line.strip().strip('|').split('|')]
                            num_str, suggestion, reason = parts[0], parts[1], parts[2]
                            index = int(re.search(r'\d+', num_str).group()) - 1
                            if 0 <= index < len(block_start_times):
                                highlight_indices.add(index)
                                start_time = block_start_times[index]
                                new_table_rows.append(f"| {start_time} | {suggestion} | {reason} |")
                        except (ValueError, IndexError): continue
                if new_table_rows: ai_display_text = new_table_header + "\n" + "\n".join(new_table_rows)
                else: ai_display_text = "AIによる指摘事項はありませんでした。"
            else: ai_display_text = ai_result_md

        final_result = convert_narration_script(current_input, n_force_insert, mm_ss_colon, highlight_indices)
        
        with col2_main:
             st.text_area("　変換完了！コピーしてお使いください", value=final_result["narration_script"], height=500)
             
        if ai_check_flag:
            st.markdown("---")
            st.subheader("📝 AI校正チェック結果")
            st.markdown(ai_display_text)
            
    except Exception as e:
        with col2_main:
            st.error(f"エラーが発生しました: {e}")
            st.text_area("　", value="", height=500, disabled=True)
else:
    with col2_main:
        st.markdown('<div style="height: 500px;"></div>', unsafe_allow_html=True)
            
# --- フッター ---
st.markdown("---")
st.markdown(
    """
    <div style="text-align: right; font-size: 12px; color: #C5D6B9;">
        © 2025 kimika Inc. All rights reserved.
    </div>
    """,
    unsafe_allow_html=True
)

st.markdown('<div style="height: 200px;"></div>', unsafe_allow_html=True)
