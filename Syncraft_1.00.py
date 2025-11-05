# ===========================================
# Caption to Narration - 最終完成版 (ヘルプテキスト追加)
# ===========================================

import streamlit as st
import re
import math
# ▼▼▼ Gemini API 関連 ▼▼▼
from google import genai
from google.genai.errors import APIError


# ===============================================================
# ▼▼▼ AIチェックの本体（Gemini API呼び出し部分）▼▼▼
# ===============================================================
def check_narration_with_gemini(narration_blocks, api_key):
    """
    Gemini APIを使用してナレーションをチェックする。
    入力に番号を振り、AIが出力でその番号を使うように指示。
    """
    if not api_key:
        return "エラー：Gemini APIキーが設定されていません。Streamlit Secretsを確認してください。"

    try:
        client = genai.Client(api_key=api_key)
        # AIに渡すテキストに番号を付与
        formatted_text = "\n".join([f"No.{i+1}: {b['text']}" for i, b in enumerate(narration_blocks)])

        # プロンプトを更新。番号で位置を返してもらうように指示
        prompt = f"""
        あなたはプロの校正者です。以下のナレーション原稿の誤字脱字をチェックし、修正案を提示してください。

        # 制約条件
        - ナレーション特有の句読点やスペースは修正しない。
        - 芸能人の名前は正しく校正する。
        - 文末が不自然でも、意図的なものとして修正しない。
        - 漢数字は使用せず、算用数字のままにする。
        - 誤りがない場合は「問題ありませんでした。」とだけ出力する。
        
        # 出力形式
        - 誤りがある場合のみ、以下のMarkdownテーブル形式で出力する。
        - 「No.」列には必ず元の番号を入れる。
        - 「修正提案」列で誤字脱字を指摘する時は「○○ → △△」のようにどう間違ってるか明確に記載。
        - 「理由」列は「〇〇の誤り」、「〇〇では？」のように簡潔に記載する。
        
        【出力形式】
        | No. | 修正提案 | 理由 |
        |---|---|---|
        | (番号) | (正しい単語・フレーズ) | (修正理由) |
        
        【ナレーション原稿】
        ---
        {formatted_text}
        ---
        """

        
        response = client.models.generate_content(
            model='gemini-2.5-flash',
            contents=prompt,
        )
        return getattr(response, "text", "") or ""

    except APIError as e:
        return f"Gemini APIエラーが発生しました。詳細: {e}"
    except Exception as e:
        return f"予期せぬエラー: {e}"


# ===============================================================
# ▼▼▼ ナレーション変換エンジン ▼▼▼
# ===============================================================
def convert_narration_script(text, n_force_insert_flag=True, mm_ss_colon_flag=False, highlight_indices=None):
    """
    ナレーションスクリプトを生成する。
    - highlight_indices を受け取り、該当行にマーカーを付ける機能を追加。
    - 各ブロックの開始タイムのリストを返す機能を追加。
    """
    if highlight_indices is None:
        highlight_indices = set()
        
    FRAME_RATE = 30.0
    CONNECTION_THRESHOLD = 1.0 + (10.0 / FRAME_RATE)

    to_zenkaku_num = str.maketrans('0123456789', '０１２３４５６７８９')
    hankaku_symbols = '!@#$%&-+='
    zenkaku_symbols = '！＠＃＄％＆－＋＝'
    hankaku_chars = 'abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789 ' + hankaku_symbols
    zenkaku_chars = 'ａｂｃｄｅｆｇｈｉｊｋｌｍｎｏｐｑｒｓｔｕｖｗｘｙｚＡＢＣＤＥＦＧＨＩＪＫＬＭＮＯＰＱＲＳＴＵＶＷＸＹＺ０１２３４５６７８９　' + zenkaku_symbols
    to_zenkaku_all = str.maketrans(hankaku_chars, zenkaku_chars)
    to_hankaku_time = str.maketrans('０１２３４５６７８９：〜', '0123456789:~')

    lines = text.strip().split('\n')
    start_index = -1
    time_pattern = r'(\d{2})[:;](\d{2})[:;](\d{2})[;.](\d{2})\s*-\s*(\d{2})[:;](\d{2})[:;](\d{2})[;.](\d{2})'

    for i, line in enumerate(lines):
        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', line)
        normalized_line = line_with_frames.strip().translate(to_hankaku_time).replace('~', '-')
        if re.match(time_pattern, normalized_line):
            start_index = i
            break
            
    if start_index == -1: 
        return {"narration_script": "エラー：変換可能なタイムコードが見つかりませんでした。", "ai_data": [], "start_times": []}
        
    relevant_lines = lines[start_index:]
    blocks = []
    i = 0
    while i < len(relevant_lines):
        current_line = relevant_lines[i].strip()
        if not current_line:
            i += 1
            continue

        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', current_line)
        normalized_line = line_with_frames.translate(to_hankaku_time).replace('~', '-')

        if re.match(time_pattern, normalized_line):
            time_val = current_line
            text_lines = []
            
            i += 1
            while i < len(relevant_lines):
                if not relevant_lines[i].strip():
                    break
                
                next_line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', relevant_lines[i].strip())
                next_normalized = next_line_with_frames.translate(to_hankaku_time).replace('~', '-')
                if re.match(time_pattern, next_normalized):
                    break

                text_lines.append(relevant_lines[i])
                i += 1
            
            text_val = "\n".join(text_lines)
            blocks.append({'time': time_val, 'text': text_val})
        else:
            i += 1
        
    output_lines = []
    narration_blocks_for_ai = []
    parsed_blocks = []
    block_start_times = []

    for block in blocks:
        line_with_frames = re.sub(r'(\d{2}:\d{2}:\d{2})(?![:.]\d{2})', r'\1.00', block['time'])
        normalized_time_str = line_with_frames.translate(to_hankaku_time).replace('~', '-')
        time_match = re.match(time_pattern, normalized_time_str)
        if not time_match: continue
        
        groups = time_match.groups()
        start_hh, start_mm, start_ss, start_fr, end_hh, end_mm, end_ss, end_fr = [int(g or 0) for g in groups]
        # AIに渡すデータは元のテキストをそのまま使う
        narration_blocks_for_ai.append({'time': block['time'].strip(), 'text': block['text'].strip()})
        parsed_blocks.append({
            'start_hh': start_hh, 'start_mm': start_mm, 'start_ss': start_ss, 'start_fr': start_fr,
            'end_hh': end_hh, 'end_mm': end_mm, 'end_ss': end_ss, 'end_fr': end_fr,
            'text': block['text']
        })

    previous_end_hh = None
    for i, block in enumerate(parsed_blocks):
        start_hh, start_mm, start_ss, start_fr = block['start_hh'], block['start_mm'], block['start_ss'], block['start_fr']
        end_hh, end_mm, end_ss, end_fr = block['end_hh'], block['end_mm'], block['end_ss'], block['end_fr']
        should_insert_h_marker = False
        marker_hh_to_display = -1
        if i == 0:
            if start_hh > 0: should_insert_h_marker = True; marker_hh_to_display = start_hh
            previous_end_hh = end_hh
        else:
            if start_hh < end_hh: should_insert_h_marker = True; marker_hh_to_display = end_hh
            elif previous_end_hh is not None and start_hh > previous_end_hh: should_insert_h_marker = True; marker_hh_to_display = start_hh
        if should_insert_h_marker:
             output_lines.append("")
             output_lines.append(f"【{str(marker_hh_to_display).translate(to_zenkaku_num)}Ｈ】")
        previous_end_hh = end_hh
        total_seconds_in_minute_loop = (start_mm % 60) * 60 + start_ss
        spacer = ""; is_half_time = False; base_time_str = ""
        if 0 <= start_fr <= 9:
            display_mm = (total_seconds_in_minute_loop // 60) % 60; display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"; spacer = "　　　"
        elif 10 <= start_fr <= 22:
            display_mm = (total_seconds_in_minute_loop // 60) % 60; display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"; spacer = "　　"; is_half_time = True
        else:
            total_seconds_in_minute_loop += 1
            display_mm = (total_seconds_in_minute_loop // 60) % 60; display_ss = total_seconds_in_minute_loop % 60
            base_time_str = f"{display_mm:02d}{display_ss:02d}"; spacer = "　　　"
        colon_time_str = f"{base_time_str[:2]}：{base_time_str[2:]}" if mm_ss_colon_flag else base_time_str
        formatted_start_time = f"{colon_time_str.translate(to_zenkaku_num)}半" if is_half_time else colon_time_str.translate(to_zenkaku_num)
        block_start_times.append(formatted_start_time)
        
        ### ▼▼▼ 変更点：話者分離ロジックを最終修正 ▼▼▼
        text_content = block['text'].strip(' \u3000')
        speaker_symbol = ''
        body = ''
        
        if n_force_insert_flag:
            speaker_symbol = 'Ｎ'
            # 元のテキストの先頭がN記号だった場合、それを取り除いた部分を本文とする
            n_match = re.match(r'^[\s　]*[NnＮｎ](?:[\s　]*[：:])?(?![A-Za-z0-9])[\s　]*(.*)$', text_content, re.DOTALL)
            if n_match:
                body = n_match.group(1)
            else:
                # N記号で始まらない場合は、入力テキスト全体を本文とする
                body = text_content
        else:
            # OFFの時は、話者判定を行わず、入力全体を本文とする
            speaker_symbol = ''
            body = text_content

        body = body.strip(' \u3000')
        if not body: body = "※注意！本文なし！"
        body = body.translate(to_zenkaku_all)
        ### ▲▲▲ 変更ここまで ▲▲▲

        end_string = ""; add_blank_line = True
        if i + 1 < len(parsed_blocks):
            next_block = parsed_blocks[i+1]
            end_total_seconds = (end_hh * 3600) + (end_mm * 60) + end_ss + (end_fr / FRAME_RATE)
            next_start_total_seconds = (next_block['start_hh'] * 3600) + (next_block['start_mm'] * 60) + next_block['start_ss'] + (next_block['start_fr'] / FRAME_RATE)
            if next_start_total_seconds - end_total_seconds < CONNECTION_THRESHOLD: add_blank_line = False
        if add_blank_line:
            adj_ss = end_ss; adj_mm = end_mm
            if 0 <= end_fr <= 9: adj_ss = end_ss - 1
            if adj_ss < 0: adj_ss = 59; adj_mm -= 1
            adj_mm_display = adj_mm % 60
            if start_hh != end_hh or (start_mm % 60) != adj_mm_display: formatted_end_time = f"{adj_mm_display:02d}{adj_ss:02d}".translate(to_zenkaku_num)
            else: formatted_end_time = f"{adj_ss:02d}".translate(to_zenkaku_num)
            end_string = f" ／{formatted_end_time}"

        line_prefix = "🔴" if i in highlight_indices else ""
        body_lines = body.split('\n')
        
        first_line_prefix_parts = [formatted_start_time, spacer]
        if speaker_symbol:
            first_line_prefix_parts.append(f"{speaker_symbol}　")
        
        first_line_prefix = "".join(first_line_prefix_parts)
        indent_space = '　' * len(first_line_prefix)
        
        first_line_text = body_lines[0].lstrip(' \u3000')
        end_string_for_first_line = end_string if len(body_lines) == 1 else ""
        output_lines.append(f"{line_prefix}{first_line_prefix}{first_line_text}{end_string_for_first_line}")
        
        if len(body_lines) > 1:
            for k, line_text in enumerate(body_lines[1:]):
                end_string_for_this_line = end_string if k == len(body_lines) - 2 else ""
                output_lines.append(f"{indent_space}{line_text.lstrip(' \\u3000')}{end_string_for_this_line}")

        if add_blank_line and i < len(parsed_blocks) - 1:
            output_lines.append("")
            
    return {"narration_script": "\n".join(output_lines), "ai_data": narration_blocks_for_ai, "start_times": block_start_times}


# ===============================================================
# ▼▼▼ Streamlit UI ▼▼▼
# ===============================================================
st.set_page_config(page_title="Syncraft", page_icon="📝", layout="wide")



st.title('Syncraft')
st.caption('　ナレーション原稿作成ツール with gemini(β)')

GEMINI_API_KEY = st.secrets.get("GEMINI_API_KEY", "")

if "ai_result_cache" not in st.session_state: st.session_state["ai_result_cache"] = ""
if "last_input_hash" not in st.session_state: st.session_state["last_input_hash"] = None

st.markdown("""<style> textarea { font-size: 14px !important; } </style>""", unsafe_allow_html=True)

# --- 1段目：タイトル ---
#col1_top, col2_top = st.columns(2)
#with col1_top: st.header('')
#with col2_top: st.header('')

# --- 2段目：メインのテキストエリア【変更】---
# ▼▼▼ placeholderとhelp用のテキストを定義 ▼▼▼
placeholder_text = """Supported Formats  
  
➤ Recommended:
00;00;00;00 - 00;00;02;29
Nああああ

➤ Standard:
００:００:１５　〜　００:００:１８
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
# ▲▲▲ ここまで ▲▲▲

col1_main, col2_main = st.columns(2)
with col1_main:
    # ▼▼▼ st.text_area に placeholder と help を追加 ▼▼▼
    input_text = st.text_area(
        label="　ここに元原稿をペーストして Ctrl+Enter を押してください。", 
        height=500,
        placeholder=placeholder_text,
        help=help_text
    )
    # ▲▲▲ ここまで ▲▲▲


# --- キャッシュ管理 ---
cur_hash = hash(input_text.strip())
if st.session_state["last_input_hash"] != cur_hash:
    st.session_state["ai_result_cache"] = ""
    st.session_state["last_input_hash"] = cur_hash

# --- 3段目：コントロールエリア ---
col1_opt, col2_opt, col3_opt, _ = st.columns([1.5, 1.5, 3, 7.5]) 
with col1_opt: n_force_insert = st.checkbox("Ｎ強制挿入", value=True)
with col2_opt: mm_ss_colon = st.checkbox("ｍｍ：ｓｓ", value=False)
with col3_opt: ai_check_flag = st.checkbox("誤字脱字チェック(β)", value=False)

# --- 4段目：変換実行と結果表示 ---
if input_text:
    try:
        initial_result = convert_narration_script(input_text, n_force_insert, mm_ss_colon)
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
                        except (ValueError, IndexError):
                            continue
                
                if new_table_rows:
                    ai_display_text = new_table_header + "\n" + "\n".join(new_table_rows)
                else:
                    ai_display_text = "AIによる指摘事項はありませんでした。"
            else:
                ai_display_text = ai_result_md

        final_result = convert_narration_script(input_text, n_force_insert, mm_ss_colon, highlight_indices)
        
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
        st.markdown('<div style="height: 500px;"></div>', unsafe_allow_html=True)#ここ500pxです。いつも538と書いてくる
            
# --- フッター ---
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












