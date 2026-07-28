"""
네이버 블로그 통합 자동화 도구 (Streamlit 단일 파일 버전)
=============================================================
1) 네이버 오픈 API(공식)로 로그인/게시
2) GPT-4o로 블로그 초안 작성/다듬기
3) Pillow로 이미지 EXIF 제거 / 리사이즈 / 워터마크

실행:
  pip install -r requirements.txt
  streamlit run streamlit_app.py
"""

import os
from urllib.parse import urlencode

import streamlit as st
import requests

# ------------------------------------------------------------
# 페이지 설정은 반드시 다른 st 명령보다 먼저 와야 함
# ------------------------------------------------------------
st.set_page_config(page_title="네이버 블로그 통합 도구", page_icon="📝", layout="wide")


# ------------------------------------------------------------
# 키 불러오기 (secrets.toml이 없어도 앱이 죽지 않도록 안전하게 처리)
# ------------------------------------------------------------
def get_secret(key: str) -> str:
    try:
        if key in st.secrets:
            return st.secrets[key]
    except Exception:
        pass
    return os.environ.get(key, "")


NAVER_CLIENT_ID = get_secret("NAVER_CLIENT_ID")
NAVER_CLIENT_SECRET = get_secret("NAVER_CLIENT_SECRET")
OPENAI_API_KEY = get_secret("OPENAI_API_KEY")

NAVER_REDIRECT_URI = "http://localhost:8080/callback"
NAVER_AUTH_URL = "https://nid.naver.com/oauth2.0/authorize"
NAVER_TOKEN_URL = "https://nid.naver.com/oauth2.0/token"
NAVER_WRITE_POST_URL = "https://openapi.naver.com/blog/writePost.json"
NAVER_LIST_CATEGORY_URL = "https://openapi.naver.com/blog/listCategory.json"

# openai 패키지는 설치 안 되어 있어도 앱 전체가 죽지 않게 지연 처리
openai_client = None
openai_import_error = None
if OPENAI_API_KEY:
    try:
        from openai import OpenAI
        openai_client = OpenAI(api_key=OPENAI_API_KEY)
    except Exception as e:
        openai_import_error = str(e)

# pillow도 마찬가지로 안전하게 처리
pillow_import_error = None
try:
    from PIL import Image, ImageDraw, ImageFont
except Exception as e:
    pillow_import_error = str(e)


# ------------------------------------------------------------
# 네이버 오픈 API 함수
# ------------------------------------------------------------
def naver_get_login_url(state="blog_assistant"):
    params = {
        "response_type": "code",
        "client_id": NAVER_CLIENT_ID,
        "redirect_uri": NAVER_REDIRECT_URI,
        "state": state,
    }
    return f"{NAVER_AUTH_URL}?{urlencode(params)}"


def naver_get_access_token(auth_code, state="blog_assistant"):
    params = {
        "grant_type": "authorization_code",
        "client_id": NAVER_CLIENT_ID,
        "client_secret": NAVER_CLIENT_SECRET,
        "code": auth_code,
        "state": state,
    }
    res = requests.get(NAVER_TOKEN_URL, params=params, timeout=15)
    res.raise_for_status()
    return res.json()


def naver_list_categories(access_token):
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get(NAVER_LIST_CATEGORY_URL, headers=headers, timeout=15)
    res.raise_for_status()
    return res.json()


def naver_write_post(access_token, title, contents_html, category_no=None, tags=None):
    headers = {"Authorization": f"Bearer {access_token}"}
    data = {"title": title, "contents": contents_html}
    if category_no:
        data["categoryNo"] = category_no
    if tags:
        data["tag"] = ",".join(tags)
    res = requests.post(NAVER_WRITE_POST_URL, headers=headers, data=data, timeout=15)
    res.raise_for_status()
    return res.json()


# ------------------------------------------------------------
# GPT 글쓰기 함수
# ------------------------------------------------------------
def gpt_draft_post(topic: str, key_points: str, tone: str = "친근한 블로그체") -> str:
    system_prompt = (
        "당신은 블로그 작가를 돕는 글쓰기 어시스턴트입니다. "
        "사용자가 준 주제와 핵심 내용을 바탕으로 읽기 쉬운 블로그 초안을 작성합니다. "
        "이 초안은 작가가 검토하고 다듬어 최종 게시할 예정입니다."
    )
    user_prompt = (
        f"주제: {topic}\n핵심 내용: {key_points}\n톤: {tone}\n\n"
        f"위 내용을 바탕으로 블로그 글 초안을 작성해줘. 소제목을 포함해서 구조화해줘."
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


PRODUCT_REVIEW_SYSTEM_PROMPT = """당신은 제품 리뷰형 블로그 글을 쓰는 전문 작가입니다.
아래 작성 원칙을 반드시 지켜서 글을 작성하세요.

[도입부 작성 원칙]
- 도입부는 3~5문장 정도의 분량 안에서, "이 글을 읽으면 무엇을 알게 되는지 / 이 제품이 어떤 고민을
  해결해주는지"를 먼저 밝히고 시작할 것. 정확히 3문장으로 자를 필요는 없지만, 핵심 정보를 여러 문단
  뒤로 미루지 말 것.
- "이 글에서 알아보겠습니다", "끝까지 읽어보세요" 식으로 결론을 숨기고 미루는 도입부는 쓰지 말 것.
- 날씨, 계절, 개인적인 고민을 길게 늘어놓다가 한참 뒤에야 제품이나 가격을 언급하는 방식은 쓰지 말 것.
- 이 제품을 찾아보는 사람이 지금 어떤 점이 답답해서 검색했을지를 먼저 짚어주고, 그 답이나 힌트를
  도입부 안에서 함께 제시할 것.

[본문 작성 원칙]
- 각 소제목은 하나의 구체적 질문만 다루고, 그 질문에 대한 답을 분명하게 줄 것.
- 막연한 일반론 대신, 실제 사용 상황이나 판단 기준을 구체적으로 서술할 것.
- 장단점 정리 섹션에는 실제 사용 시 아쉬울 수 있는 점도 최소 1개는 솔직하게 포함할 것.

[FAQ 작성 원칙]
- 이미 본문에서 다룬 내용을 그대로 질문으로 반복하지 말 것.
- 이 글을 다 읽은 사람이 그 다음에 검색할 법한, 실용적인 질문 위주로 구성할 것.

이 초안은 작가가 검토하고 다듬어 최종 게시할 예정입니다."""


def gpt_draft_product_review(product_name, key_points, price_info="", tone="친근한 블로그체") -> str:
    user_prompt = (
        f"제품명: {product_name}\n"
        f"핵심 특징/내용: {key_points}\n"
        f"가격 정보: {price_info if price_info else '(제공되지 않음, 언급하지 말 것)'}\n"
        f"톤: {tone}\n\n"
        f"위 정보를 바탕으로 제품 리뷰 블로그 글을 작성해줘. "
        f"도입부 → 소제목별 본문 → 장단점 정리 → FAQ 순서로 구조화해줘."
    )
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": PRODUCT_REVIEW_SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.7,
    )
    return response.choices[0].message.content.strip()


def gpt_polish_text(draft: str, tone: str = "전문가") -> str:
    system_prompt = (
        "당신은 편집자입니다. 주어진 글의 핵심 내용과 사실관계는 유지하면서, "
        "문장을 더 매끄럽고 읽기 좋게 다듬습니다. 요청받은 톤에 맞게 표현을 조정합니다."
    )
    user_prompt = f"다음 글을 '{tone}' 톤으로 다듬어줘:\n\n{draft}"
    response = openai_client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.6,
    )
    return response.choices[0].message.content.strip()


# ------------------------------------------------------------
# 이미지 처리 함수
# ------------------------------------------------------------
def strip_exif(img):
    data = list(img.getdata())
    clean_img = Image.new(img.mode, img.size)
    clean_img.putdata(data)
    return clean_img


def resize_for_web(img, max_width: int = 1200):
    if img.width > max_width:
        ratio = max_width / img.width
        new_size = (max_width, int(img.height * ratio))
        img = img.resize(new_size, Image.LANCZOS)
    return img


def add_watermark(img, text: str, opacity: int = 120):
    img = img.convert("RGBA")
    overlay = Image.new("RGBA", img.size, (255, 255, 255, 0))
    draw = ImageDraw.Draw(overlay)

    font_size = max(14, img.width // 40)
    try:
        font = ImageFont.truetype("arial.ttf", font_size)
    except OSError:
        font = ImageFont.load_default()

    bbox = draw.textbbox((0, 0), text, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    margin = 20
    position = (img.width - text_w - margin, img.height - text_h - margin)

    draw.text(position, text, font=font, fill=(255, 255, 255, opacity))
    return Image.alpha_composite(img, overlay).convert("RGB")


# ==============================================================
# 화면 시작 (여기부터는 항상 렌더링되어야 흰 화면을 방지할 수 있음)
# ==============================================================

st.title("📝 네이버 블로그 통합 자동화 도구")

# 설정 상태를 항상 보여줘서 "왜 안 되는지" 바로 알 수 있게 함
with st.expander("⚙️ 설정 상태 확인 (문제 생길 때 여기부터 확인)", expanded=not (NAVER_CLIENT_ID and OPENAI_API_KEY)):
    st.write("NAVER_CLIENT_ID:", "✅ 설정됨" if NAVER_CLIENT_ID else "❌ 없음")
    st.write("NAVER_CLIENT_SECRET:", "✅ 설정됨" if NAVER_CLIENT_SECRET else "❌ 없음")
    st.write("OPENAI_API_KEY:", "✅ 설정됨" if OPENAI_API_KEY else "❌ 없음")
    if openai_import_error:
        st.error(f"openai 패키지 문제: {openai_import_error}")
    if pillow_import_error:
        st.error(f"pillow 패키지 문제: {pillow_import_error}")
    st.caption("키가 없다면 .streamlit/secrets.toml (로컬) 또는 Streamlit Cloud의 Secrets 설정을 확인하세요.")

if "access_token" not in st.session_state:
    st.session_state.access_token = None
if "draft" not in st.session_state:
    st.session_state.draft = ""
if "image_paths" not in st.session_state:
    st.session_state.image_paths = []


def post_section(prefix: str):
    st.markdown("### 네이버 블로그에 게시")
    if not st.session_state.access_token:
        st.warning("먼저 '① 네이버 로그인' 탭에서 로그인해주세요.")
        return

    if st.button("카테고리 불러오기", key=f"{prefix}_cat_load"):
        try:
            st.json(naver_list_categories(st.session_state.access_token))
        except Exception as e:
            st.error(f"카테고리 조회 실패: {e}")

    category_no = st.text_input("카테고리 번호 (없으면 비워두기)", key=f"{prefix}_cat_no")
    title = st.text_input("게시글 제목", key=f"{prefix}_title")

    if st.button("🚀 실제로 게시하기", key=f"{prefix}_post", type="primary"):
        if not title:
            st.error("제목을 입력해주세요.")
        elif not st.session_state.draft:
            st.error("먼저 초안을 생성해주세요.")
        else:
            contents_html = "<p>" + st.session_state.draft.replace("\n", "</p><p>") + "</p>"
            try:
                result = naver_write_post(
                    st.session_state.access_token, title, contents_html, category_no or None
                )
                st.success("게시 완료!")
                st.json(result)
            except Exception as e:
                st.error(f"게시 실패: {e}")


tab_login, tab_write, tab_review, tab_image = st.tabs(
    ["① 네이버 로그인", "② 일반 글쓰기", "③ 제품 리뷰 글쓰기", "④ 이미지 처리"]
)

with tab_login:
    st.subheader("네이버 로그인 (공식 OAuth)")
    if not NAVER_CLIENT_ID or not NAVER_CLIENT_SECRET:
        st.error("NAVER_CLIENT_ID / NAVER_CLIENT_SECRET이 설정되어 있지 않습니다. 위 '설정 상태 확인'을 펼쳐보세요.")
    elif st.session_state.access_token:
        st.success("로그인 완료 상태입니다.")
        if st.button("로그아웃"):
            st.session_state.access_token = None
            st.rerun()
    else:
        login_url = naver_get_login_url()
        st.markdown(f"1) 아래 링크에서 네이버 로그인 및 권한 동의를 진행하세요.\n\n[네이버 로그인 하러 가기]({login_url})")
        st.markdown("2) 동의 후 이동한 주소창의 `code=` 뒤 값을 아래에 붙여넣으세요.")
        auth_code = st.text_input("인증 code 값")
        if st.button("토큰 발급"):
            if auth_code:
                try:
                    token_data = naver_get_access_token(auth_code)
                    st.session_state.access_token = token_data["access_token"]
                    st.success("로그인 성공!")
                    st.rerun()
                except Exception as e:
                    st.error(f"토큰 발급 실패: {e}")
            else:
                st.warning("code 값을 입력해주세요.")

with tab_write:
    st.subheader("일반 블로그 글 작성")
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    else:
        topic = st.text_input("주제", key="w_topic")
        key_points = st.text_area("핵심 내용 (콤마로 구분)", key="w_points")
        tone = st.text_input("톤", value="친근한 블로그체", key="w_tone")

        if st.button("초안 생성", key="w_gen"):
            with st.spinner("GPT가 초안을 작성 중..."):
                st.session_state.draft = gpt_draft_post(topic, key_points, tone)

        if st.session_state.draft:
            st.session_state.draft = st.text_area(
                "초안 (직접 수정 가능)", value=st.session_state.draft, height=400, key="w_draft_edit"
            )
            polish_tone = st.text_input("다듬을 톤", value="전문가", key="w_polish_tone")
            if st.button("다듬기", key="w_polish"):
                with st.spinner("다듬는 중..."):
                    st.session_state.draft = gpt_polish_text(st.session_state.draft, polish_tone)
                    st.rerun()
            st.divider()
            post_section(prefix="w")

with tab_review:
    st.subheader("제품 리뷰 글 작성 (도입부/본문/FAQ 원칙 적용)")
    if not OPENAI_API_KEY:
        st.error("OPENAI_API_KEY가 설정되어 있지 않습니다.")
    else:
        product_name = st.text_input("제품명", key="r_name")
        r_points = st.text_area("핵심 특징/내용 (콤마로 구분)", key="r_points")
        price_info = st.text_input("가격 정보 (없으면 비워두기)", key="r_price")
        r_tone = st.text_input("톤", value="친근한 블로그체", key="r_tone")

        if st.button("초안 생성", key="r_gen"):
            with st.spinner("GPT가 초안을 작성 중..."):
                st.session_state.draft = gpt_draft_product_review(product_name, r_points, price_info, r_tone)

        if st.session_state.draft:
            st.session_state.draft = st.text_area(
                "초안 (직접 수정 가능)", value=st.session_state.draft, height=400, key="r_draft_edit"
            )
            r_polish_tone = st.text_input("다듬을 톤", value="전문가", key="r_polish_tone")
            if st.button("다듬기", key="r_polish"):
                with st.spinner("다듬는 중..."):
                    st.session_state.draft = gpt_polish_text(st.session_state.draft, r_polish_tone)
                    st.rerun()
            st.divider()
            post_section(prefix="r")

with tab_image:
    st.subheader("이미지 처리 (EXIF 제거 / 리사이즈 / 워터마크)")
    if pillow_import_error:
        st.error(f"pillow 패키지가 정상 설치되지 않았습니다: {pillow_import_error}")
    else:
        uploaded_files = st.file_uploader(
            "이미지 업로드", type=["jpg", "jpeg", "png"], accept_multiple_files=True
        )
        watermark_text = st.text_input("워터마크 텍스트 (예: 블로그명 · 날짜)", value="")

        if st.button("처리 실행") and uploaded_files:
            os.makedirs("output_images", exist_ok=True)
            result_paths = []
            for f in uploaded_files:
                img = Image.open(f)
                img = strip_exif(img)
                img = resize_for_web(img)
                if watermark_text:
                    img = add_watermark(img, watermark_text)
                out_path = os.path.join("output_images", f.name)
                img.save(out_path, quality=90)
                result_paths.append(out_path)
            st.session_state.image_paths = result_paths
            st.success(f"{len(result_paths)}장 처리 완료")

        if st.session_state.image_paths:
            cols = st.columns(3)
            for i, p in enumerate(st.session_state.image_paths):
                with cols[i % 3]:
                    st.image(p, caption=os.path.basename(p))
