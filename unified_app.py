# --- 1. 필요한 라이브러리 설치 ---
# pip install streamlit python-dotenv langchain-openai "pinecone-client>=3.0.0" pandas openpyxl tabulate gspread google-auth-oauthlib python-docx "python-pptx" PyMuPDF chardet beautifulsoup4 lxml

import streamlit as st
import os
import io
import json
import requests
import zipfile
import fitz  # PyMuPDF
import pandas as pd
import chardet
import xml.etree.ElementTree as ET
import urllib.parse
import base64
import re
import time
from docx import Document
from pptx import Presentation
from bs4 import BeautifulSoup
from typing import Optional
from dotenv import load_dotenv, find_dotenv
from pathlib import Path


# LangChain 라이브러리
from langchain_openai import ChatOpenAI, OpenAIEmbeddings
from langchain.prompts import PromptTemplate
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import JsonOutputParser

# Pinecone & Google Sheets 라이브러리
import pinecone
import gspread
from google.oauth2.service_account import Credentials

# --- 2. 환경변수 및 기본 설정 ---
load_dotenv(find_dotenv())
OPENAI_API_KEY: Optional[str] = os.getenv("OPENAI_API_KEY")
GH_TOKEN: Optional[str] = os.getenv("GH_TOKEN")
PINECONE_API_KEY = os.getenv("PINECONE_API_KEY")
PINECONE_INDEX = os.getenv("PINECONE_INDEX", "pr-index")
GOOGLE_SHEET_KEY = os.getenv("GOOGLE_SHEET_KEY")
SERVICE_ACCOUNT_FILE = "credentials.json"
FEW_SHOT_SHEET_NAME = os.getenv("FEW_SHOT_SHEET_NAME", "Few-Shot Examples")

# --- 페이지 설정 ---
st.set_page_config(page_title="S-Kape", layout="wide")

# --- 공통 스타일: (옵션) 여백/폰트/카드 토큰 등 ---
st.markdown("""
<style>
/* 컨테이너 폭 배너 (다른 요소와 너비 동일) */
.section-band{
  width:100%;
  background:#F8D7DA;          /* 기본 배경색 */
  border-radius:10px;
  padding:10px 14px;
  margin:20px 0 12px;
}

/* 텍스트: 본문과 완전히 동일한 폰트/색을 상속 */
.section-band .title{
  display:block;
  margin:0;
  font-family: inherit;         /* 폰트 통일 포인트! */
  color: inherit;               /* 본문 텍스트 색 상속 */
  font-weight:700;
  line-height:1.4;
  text-align:center;
  font-size:1.15rem;            /* 기본 크기 (본문보다 약간 굵게) */
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
.header-wrap{
  display:flex; align-items:center; gap:16px;
  padding:8px 0 16px; margin:0;
  border-bottom:1px solid rgba(0,0,0,.06);
}

/* 왼쪽 마스코트 아이콘 */
.brand-icon{
  width:300px; height:auto; object-fit:contain; display:block;
}

/* 오른쪽 워드마크(텍스트 로고) */
.brand-wordmark{
  height:150px; width:auto; display:block;        /* ← 높이만 조절하면 됨 */
}

.tagline{ margin:.25rem 0 0 0; opacity:.8; font-size:1rem; }

/* 모바일에서 살짝 축소 */
@media (max-width: 768px){
  .brand-icon{ width:110px; }
  .brand-wordmark{ height:40px; }
}
</style>
""", unsafe_allow_html=True)

from typing import Optional
def spacer(px: int = 25):
    st.markdown(f"<div style='height:{px}px'></div>", unsafe_allow_html=True)

from typing import Optional
from pathlib import Path
import base64
import streamlit as st

def banner(
    filename: str,
    *,
    width: Optional[int] = None,          # 픽셀 고정 너비
    max_width: Optional[int] = None,      # 최대 너비 제한
    max_height: Optional[int] = None,     # 최대 높이 제한
    width_ratio: Optional[float] = None,  # 컬럼 가운데 배치 폭 비율(0~1)
    caption: Optional[str] = None         # 캡션 텍스트
) -> None:
    """이미지를 다양한 제약으로 표시. PIL 없이 CSS로 max-height 처리."""
    # 파일 로드
    p = (Path(__file__).parent / filename) if "__file__" in globals() else Path(filename)
    if not p.exists():
        st.warning(f"배너 이미지가 없습니다: {p}")
        return
    data = p.read_bytes()
    b64 = base64.b64encode(data).decode()

    # 공통 렌더 함수들
    def show_streamlit_image(**kwargs):
        st.image(data, **kwargs)

    def show_css_image(max_w: Optional[int], max_h: Optional[int], use_container: bool = False):
        styles = []
        if use_container:
            styles.append("width:100%")  # 컬럼/컨테이너 폭에 맞춤
        elif max_w is not None:
            styles.append(f"max-width:{max_w}px")
            styles.append("width:100%")
        else:
            styles.append("width:100%")
        if max_h is not None:
            styles.append(f"max-height:{max_h}px")
            styles.append("height:auto")
            styles.append("object-fit:contain")
        style_str = "; ".join(styles)
        st.markdown(
            f"<img src='data:image/png;base64,{b64}' style='{style_str}; display:block; margin:0 auto;'>"
            + (f"<div style='text-align:center; opacity:.7; font-size:.9rem'>{caption}</div>" if caption else ""),
            unsafe_allow_html=True
        )

    # 1) width_ratio가 있으면 가운데 정렬 레이아웃
    if width_ratio is not None and 0 < width_ratio <= 1:
        side = (1 - width_ratio) / 2
        c1, c2, c3 = st.columns([side, width_ratio, side])
        with c2:
            if max_height is not None or max_width is not None:
                show_css_image(max_w=max_width, max_h=max_height, use_container=True)
            elif width is not None:
                show_streamlit_image(width=width, caption=caption)
            else:
                show_streamlit_image(use_container_width=True, caption=caption)
        return

    # 2) 픽셀 고정 너비 우선
    if width is not None:
        show_streamlit_image(width=width, caption=caption)
        return

    # 3) 최대 너비/높이 제약(CSS)
    if max_height is not None or max_width is not None:
        show_css_image(max_w=max_width, max_h=max_height, use_container=False)
        return

    # 4) 기본: 컨테이너 가로 꽉 채움
    show_streamlit_image(use_container_width=True, caption=caption)


    # 기본: 컨테이너 꽉 채움
    st.image(data, use_container_width=True, caption=caption)


# 2) 로고 base64 로드
icon_b64 = base64.b64encode((Path(__file__).parent / "S-Kape_Logo_1.png").read_bytes()).decode()
wordmark_b64 = base64.b64encode((Path(__file__).parent / "S-Kape_Logo_2.png").read_bytes()).decode()


# 3) 헤더 렌더링
st.markdown(f"""
<div class="header-wrap">
  <img class="brand-icon" src="data:image/png;base64,{icon_b64}" alt="S-Kape mascot">
  <div>
    <img class="brand-wordmark" src="data:image/png;base64,{wordmark_b64}" alt="S-Kape">
    <p class="tagline">회의록 분석부터 코드 변경에 따른 Side-Effect 예측까지, S-Kape로 버그 지옥에서 탈출하자!</p>
  </div>
</div>
""", unsafe_allow_html=True)


# --- 3. 공통 LLM, RAG 및 헬퍼 함수 초기화 ---

# 요구사항 추출용 LLM
req_llm = ChatOpenAI(model="gpt-4.1", api_key=OPENAI_API_KEY, temperature=0.1)
req_output_parser = JsonOutputParser()

# Side-Effect 예측용 LLM (RAG)
se_llm = ChatOpenAI(model="gpt-4.1", temperature=0.2, api_key=OPENAI_API_KEY, max_tokens=2000)

# Pinecone 초기화
pinecone_index = None
emb = None
if PINECONE_API_KEY:
    try:
        pc = pinecone.Pinecone(api_key=PINECONE_API_KEY)
        if PINECONE_INDEX not in pc.list_indexes().names():
            st.info(f"Pinecone 인덱스 '{PINECONE_INDEX}'를 생성합니다. 몇 분 정도 소요될 수 있습니다.")
            pc.create_index(
                name=PINECONE_INDEX,
                dimension=1536,
                metric="cosine",
                spec=pinecone.ServerlessSpec(cloud="aws", region="us-east-1")
            )
            while not pc.describe_index(PINECONE_INDEX).status["ready"]:
                time.sleep(2)
        pinecone_index = pc.Index(PINECONE_INDEX)
        emb = OpenAIEmbeddings(api_key=OPENAI_API_KEY)  # 1536 차원
    except Exception as e:
        st.error(f"Pinecone 초기화 실패: {e}. .env 파일의 PINECONE_API_KEY를 확인하세요.")
else:
    st.warning("PINECONE_API_KEY가 설정되지 않아 Side-Effect 예측 시 유사사례 검색(RAG) 기능이 비활성화됩니다.")

# 공통 RAG 프롬프트 템플릿
RAG_PROMPT_TEMPLATE = PromptTemplate.from_template("""
당신은 10년 경력의 시니어 백엔드 개발자이자 QA 자동화 설계 경험자입니다.
기능 변경 시 발생할 수 있는 사이드 이펙트를 신중하게 검토하세요.
아래는 소프트웨어 요구사항과 코드 변경 내용, 그리고 참고할 만한 과거 유사 사례입니다.
Δ(차이)를 근거로 **Side Effect 유형을 복수로** 분류하고, 영향 영역을 구체적으로 기술한 뒤, 검증 가능한 테스트케이스를 생성하세요.

[참고: 과거 유사 PR 및 예측 결과]
{rag_context}

[입력]
요구사항:
{requirements}

코드 변경 내용:
{code_diff}

[규칙]
- 유형은 **최대 3개**까지, **중요도 높은 순**으로 제시하세요.
- 각 유형마다 **신뢰도(0~1)**와 **근거(한 줄)**를 함께 기재하세요.
- 영향 설명은 “● 영향 영역 - 설명 (이유)” 형식으로 **총 6개 이내**로 작성하세요.
  (영역 예: DB 쿼리, 세션/인증, 권한, 캐시, 트랜잭션, 컨트롤러/엔드포인트, 메시지큐, 배치, 모듈/클래스명, 테이블/필드명 등)
- 테스트케이스는 실제 변경을 **직접 검증**할 수 있을 때만 작성하세요 (1~4개).
- 과도한 추측은 금물이며, 아래 출력 형식을 정확히 따르세요.
- [테스트 케이스] 섹션은 반드시 마크다운 표 문법으로 출력한다.
- 각 행은 반드시 개행 문자(\n)로 구분하며, 행은 '|' 로 시작해서 '|' 로 끝나야 한다.
- 코드블록(```) 사용 금지. 표 이외의 문장 출력 금지.


[출력 형식]

[Δ 요약]
- (원본 대비 수정의 핵심 차이 1~2문장)

[유형 후보(최대 3개, 중요도 순)]
| 순위 | 유형(택: 기능 회귀 / 예외 처리 누락 / 상태 불일치 / 성능 저하 / 기타) | 신뢰도(0~1) | 근거(한 줄) |
| --- | --- | --- | --- |
| 1 |  |  |  |
| 2 |  |  |  |
| 3 |  |  |  |

[설명]
<ul>
  <li>(영역) - (설명; 이유)</li>
  <li>(영역) - (설명; 이유)</li>
  <li>(영역) - (설명; 이유)</li>
  <li>(영역) - (설명; 이유)</li>
  <li>(영역) - (설명; 이유)</li>
  <li>(영역) - (설명; 이유)</li>
</ul>
(최대 6개)

[테스트 케이스]
<table>
  <thead>
    <tr>
      <th>TC-ID</th><th>관련 유형</th><th>대상 영역</th>
      <th>테스트 목적</th><th>절차(한글 1문장)</th><th>예상 결과</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>TC-001</td><td></td><td></td><td></td><td></td><td></td>
    </tr>
    <tr>
      <td>TC-002</td><td></td><td></td><td></td><td></td><td></td>
    </tr>
    <tr>
      <td>TC-003</td><td></td><td></td><td></td><td></td><td></td>
    </tr>
    <tr>
      <td>TC-004</td><td></td><td></td><td></td><td></td><td></td>
    </tr>
  </tbody>
</table>
""")

# --- 4. 헬퍼 함수 정의 ---

def extract_text_from_uploaded_file(uploaded_file):
    """Streamlit의 UploadedFile 객체에서 텍스트를 추출하는 함수."""
    file_name = uploaded_file.name
    ext = os.path.splitext(file_name)[1].lower()
    file_bytes = uploaded_file.getvalue()
    try:
        if ext in [".txt", ".md"]:
            encoding = chardet.detect(file_bytes)["encoding"] or "utf-8"
            return file_bytes.decode(encoding)
        elif ext == ".docx":
            return "\n".join([p.text for p in Document(io.BytesIO(file_bytes)).paragraphs])
        elif ext == ".pptx":
            prs = Presentation(io.BytesIO(file_bytes))
            return "\n".join(shape.text for slide in prs.slides for shape in slide.shapes if hasattr(shape, "text"))
        elif ext == ".pdf":
            with fitz.open(stream=file_bytes, filetype="pdf") as pdf:
                return "\n".join([page.get_text() for page in pdf])
        elif ext in [".csv", ".xlsx", ".cell"]:
            df = pd.read_excel(io.BytesIO(file_bytes)) if ext in [".xlsx", ".cell"] else pd.read_csv(io.BytesIO(file_bytes))
            return df.to_string(index=False)
        elif ext == ".json":
            return json.dumps(json.load(io.StringIO(file_bytes.decode('utf-8'))), indent=2, ensure_ascii=False)
        elif ext == ".xml":
            return ET.tostring(ET.fromstring(file_bytes), encoding="unicode")
        elif ext == ".hwpx":
            # hwpx는 임시 파일 생성이 필요
            with open(file_name, "wb") as f: f.write(file_bytes)
            with zipfile.ZipFile(file_name, 'r') as zipf:
                text_chunks = []
                section_files = [f for f in zipf.namelist() if f.startswith("Contents/section") and f.endswith(".xml")]
                for section in section_files:
                    with zipf.open(section) as file:
                        soup = BeautifulSoup(file.read(), "xml")
                        texts = soup.find_all("TEXT")
                        text_chunks.extend(t.text for t in texts if t.text)
                os.remove(file_name)
                return "\n".join(text_chunks)
        else:
            raise ValueError(f"지원하지 않는 파일 형식: {ext}")
    except Exception as e:
        raise ValueError(f"파일 '{file_name}' 처리 중 오류 발생: {e}")

def read_excel_to_string(file):
    """업로드된 엑셀 파일을 읽어 마크다운 문자열로 변환하는 함수."""
    try:
        return pd.read_excel(file, engine='openpyxl').to_markdown(index=False)
    except Exception as e:
        st.error(f"엑셀 파일 읽기 오류: {e}")
        return None

def make_code_diff(orig: str, mod: str) -> str:
    """원본과 수정된 코드의 diff 문자열을 생성하는 함수."""
    return f"""[기존 코드]\n{orig or 'N/A'}\n\n[수정된 코드]\n{mod or 'N/A'}"""

def parse_pr_url(pr_url: str):
    """GitHub PR URL을 파싱하여 owner, repo, pr_number를 반환하는 함수."""
    m = re.match(r"https://github.com/(?P<owner>[\w.-]+)/(?P<repo>[\w.-]+)/pull/(?P<num>\d+)", pr_url)
    if not m:
        raise ValueError("PR URL 형식이 잘못되었습니다. (예: https://github.com/owner/repo/pull/123)")
    return m.group("owner"), m.group("repo"), int(m.group("num"))

def _gh_get(url: str, raw: bool = False, **extra_hdr):
    """GitHub API GET 요청을 보내는 내부 함수."""
    headers = {"Accept": "application/vnd.github+json", **({"Authorization": f"Bearer {GH_TOKEN}"} if GH_TOKEN else {}), **extra_hdr}
    resp = requests.get(url, headers=headers, timeout=30)
    resp.raise_for_status()
    return resp.text if raw else resp.json()

def fetch_pr_code_only(owner: str, repo: str, pr_number: int):
    """GitHub PR에서 원본과 수정된 코드 내용을 가져오는 함수."""
    API_ROOT = "https://api.github.com"
    pr = _gh_get(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}")
    base_sha, head_sha = pr["base"]["sha"], pr["head"]["sha"]

    def get_file_at_sha(path: str, sha: str):
        try:
            meta = _gh_get(f"{API_ROOT}/repos/{owner}/{repo}/contents/{path}?ref={sha}")
            return base64.b64decode(meta["content"]).decode('utf-8', errors='ignore')
        except Exception:
            return f"# '{path}' 경로의 파일을 '{sha}' 커밋에서 찾을 수 없습니다."

    files = _gh_get(f"{API_ROOT}/repos/{owner}/{repo}/pulls/{pr_number}/files")
    # .py 파일을 우선적으로 찾고, 없으면 첫 번째 파일을 대상
    py_files = [f for f in files if f["filename"].endswith(".py")]
    if not py_files and not files:
        raise ValueError("PR에 변경된 파일이 없습니다.")
    target_file = py_files[0] if py_files else files[0]
    if not py_files:
        st.warning(f"PR에서 파이썬(.py) 파일을 찾을 수 없습니다. 첫 번째 파일 '{target_file['filename']}'을 대신 사용합니다.")

    original_code = get_file_at_sha(target_file['filename'], base_sha)
    modified_code = get_file_at_sha(target_file['filename'], head_sha)
    return original_code, modified_code

def generate_modified_code(requirements: str, original_code: str) -> str:
    """요구사항을 바탕으로 원본 코드를 수정하여 새로운 코드를 생성하는 함수 (LLM 사용)."""
    code_gen_llm = ChatOpenAI(model="gpt-4.1", temperature=0.1, api_key=OPENAI_API_KEY)
    prompt = f"""
    당신은 10년차 시니어 개발자입니다. 아래 [요구사항]을 반영하여 [원본 코드]를 수정하고, 수정된 전체 코드만 응답으로 반환하세요.
    추가로 어디가 수정이 되었는지 수정된 부분에 주석도 달아주세요.

    [요구사항]
    {requirements}

    [원본 코드]
    ```python
    {original_code}
    ```
    """
    response = code_gen_llm.invoke([HumanMessage(content=prompt)])
    # LLM 응답에서 코드 블록만 깔끔하게 추출
    code_content = response.content.strip()
    match = re.search(r"```python\n(.*?)\n```", code_content, re.DOTALL)
    if match:
        return match.group(1).strip()
    # 코드 블록 마커가 없는 경우를 대비
    if code_content.startswith("```"):
        return '\n'.join(code_content.split('\n')[1:-1])
    return code_content

def embed_text(text: str):
    """텍스트를 임베딩 벡터로 변환하는 함수."""
    return emb.embed_query(text) if emb else None

def upsert_to_pinecone(pr_id: str, text: str, meta: dict):
    """임베딩된 벡터를 Pinecone에 저장하는 함수."""
    if pinecone_index and (vec := embed_text(text)):
        pinecone_index.upsert(vectors=[(pr_id, vec, meta)])
        st.sidebar.info(f"PR '{pr_id}' 정보가 Pinecone DB에 저장되었습니다.")

def search_similar_prs(query_text: str, top_k=3):
    """유사한 PR을 Pinecone에서 검색하는 함수."""
    if pinecone_index and (qvec := embed_text(query_text)):
        return pinecone_index.query(vector=qvec, top_k=top_k, include_metadata=True).matches or []
    return []

# --- 5. 탭(Tab)별 기능 구현 ---
# --- 탭 색상 CSS (탭 만들기 전에 1회만 주입) ---
st.markdown("""
<style>
/* 탭 리스트 전체 레이아웃 */
.stTabs [data-baseweb="tab-list"] {
    background-color: #FF6C6C;
    border-radius: 8px;
    padding: 0; /* 기본 padding 제거 */
    display: flex;
    justify-content: space-between; /* 일정 간격 */
}

/* 개별 탭 버튼 */
.stTabs [data-baseweb="tab"] {
    flex: 1; /* 모든 탭이 같은 너비 */
    text-align: center;
    color: white;
    padding: 8px 0;
    border-right: 1px solid rgba(255,255,255,0.4); /* 구분선 */
}

/* 마지막 탭은 오른쪽 구분선 제거 */
.stTabs [data-baseweb="tab"]:last-child {
    border-right: none;
}

/* 선택된 탭 강조 */
.stTabs [aria-selected="true"] {
    font-weight: 700;
    background-color: rgba(0,0,0,0.1); /* 선택 시 배경 살짝 어둡게 */
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
/* 컨테이너 좌우 여백을 무시하고 진짜 화면 전체 폭으로 확장 */
.band-full{
  width:100vw;
  margin-left:calc(50% - 50vw);
  margin-right:calc(50% - 50vw);
  padding:10px 16px;           /* 배너 안쪽 여백 */
}

/* 텍스트 유틸 */
.center{ text-align:center !important; }
.no-mg{ margin:0 !important; } /* h태그 기본 마진 제거 -> 배너 높이 깔끔 */
</style>
""", unsafe_allow_html=True)

def section_heading(text: str,
                    
                    size: Optional[str] = None,
                    bg: str = "#F8D7DA",
                    color: str = "inherit",
                    center: bool = True,
                    level: Optional[int] =None):
                  
    """
    본문 폰트 그대로 쓰는 섹션 배너 헤딩.
    - size: 's'|'m'|'l' (크기 선택). 지정 안 하면 level로 유추.
    - level: 1~6 (예전 API 호환용). 1→'l', 2→'m', 3→'s' 로 매핑.
    """
    # level -> size 매핑 (하위호환)
    if size is None and level is not None:
        size = {1: "l", 2: "m", 3: "s"}.get(level, "m")
    if size is None:
        size = "m"

    size_map = {"s": "1.05rem", "m": "1.15rem", "l": "1.30rem"}
    align = "center" if center else "left"

    st.markdown(
        f"""
        <div class="section-band" style="background:{bg};">
          <span class="title"
                style="font-size:{size_map[size]};
                       text-align:{align};
                       color:{color};">{text}</span>
        </div>
        """,
        unsafe_allow_html=True
    )


    
# --- 탭 만들기 ---

tab1, tab2, tab3 = st.tabs(["요구사항 명세서 추출", "Side Effect 예측", "Side Effect 예측 Plus +"])

# ==================================================================================
# << TAB 1: 요구사항 명세서 추출기 >>
# ==================================================================================
with tab1:
    
    banner("tab1.png",max_height=400)
    spacer()

    @st.cache_data(ttl=600)
    def load_req_few_shot_examples():
        """Google Sheets에서 Few-Shot 예시를 로드합니다. (10분 캐싱)"""
        if not GOOGLE_SHEET_KEY or not os.path.exists(SERVICE_ACCOUNT_FILE):
            st.sidebar.success("Google Sheets 연동 성공!.")
            return []
        try:
            scope = ['[https://spreadsheets.google.com/feeds](https://spreadsheets.google.com/feeds)', '[https://www.googleapis.com/auth/drive](https://www.googleapis.com/auth/drive)']
            creds = Credentials.from_service_account_file(SERVICE_ACCOUNT_FILE, scopes=scope)
            gc = gspread.authorize(creds)
            worksheet = gc.open_by_key(GOOGLE_SHEET_KEY).worksheet(FEW_SHOT_SHEET_NAME)
            all_records = worksheet.get_all_records()
            examples = []
            for record in all_records:
                user_input = record.pop('회의록', '')
                if '확인사항' in record and isinstance(record['확인사항'], str):
                    record['확인사항'] = [item.strip() for item in record['확인사항'].split('\n') if item.strip()]
                if user_input:
                    examples.append(HumanMessage(content=f"회의록:\n{user_input}"))
                    examples.append(AIMessage(content=json.dumps([record], ensure_ascii=False)))
            st.sidebar.success(f"oogle Sheets 로드 성공!.")
            return examples
        except Exception as e:
            st.sidebar.success(f"Google Sheets 로드 성공!:")
            return []

    def extract_requirements_from_text(text, few_shot_examples):
        system_prompt = """
        You are a requirements engineer that always outputs only a valid JSON array.
        Analyze the provided meeting minutes and extract all requirements.
        Follow the provided JSON schema. Do not include any explanations or text outside the JSON array.
        JSON_SCHEMA:
        [
            {{
                "No.": "INTEGER",
                "요구사항 ID" : "STRING (REQ-001, REQ-002...)",
                "파일명": "STRING (Source file name of the requirement)",
                "구분": "STRING (eg. 사용자, 관리자)",
                "분류": "STRING (eg. PC, mobile)",
                "유형": "STRING (eg. 신규, 개선)",
                "기능 분류 1": "STRING (Top-level function category)",
                "기능 분류 2": "STRING (Sub-level function category)",
                "요구사항 명": "STRING (A concise title for the requirement)",
                "요구사항 상세 내용": "STRING (A detailed description of the requirement)",
                "확인사항": "ARRAY of STRINGS (Specific points to verify)"
            }}
        ]
        """
        prompt = ChatPromptTemplate.from_messages(
            [("system", system_prompt)] + few_shot_examples + [("human", "회의록:\n{text}")]
        )
        chain = prompt | req_llm | req_output_parser
        return chain.invoke({"text": text[:15000]}) # 입력 텍스트 길이 제한

    uploaded_files = st.file_uploader(
        "여기에 회의록 파일을 드래그 앤 드롭하거나 클릭하여 업로드하세요 (txt, docx, pdf, pptx, csv, xlsx, json, xml, hwpx)",
        type=["txt", "docx", "pdf", "pptx", "xlsx", "csv", "json", "xml", "hwpx"],
        accept_multiple_files=True,
        key="minutes_uploader_tab1"
    )
    
    if uploaded_files: st.write(f"**선택된 파일: {len(uploaded_files)}개**")

    if st.button("명세서 생성하기", use_container_width=True, key="generate_req_btn_tab1"):
        if not uploaded_files:
            st.error("⚠️ 파일을 선택해주세요.")
        else:
            with st.spinner("파일 분석 및 요구사항 추출 중... 이 작업은 몇 분 정도 소요될 수 있습니다."):
                try:
                    combined_text = ""
                    for file in uploaded_files:
                        text = extract_text_from_uploaded_file(file)
                        combined_text += f"\n\n--- 문서 시작: [{file.name}] ---\n{text.strip()}\n--- 문서 끝: [{file.name}] ---\n"
                    
                    few_shot_examples = load_req_few_shot_examples()
                    requirements_data = extract_requirements_from_text(combined_text, few_shot_examples)
                    
                    if requirements_data:
                        df = pd.DataFrame(requirements_data)
                        output_buffer = io.BytesIO()
                        with pd.ExcelWriter(output_buffer, engine='openpyxl') as writer:
                            df.to_excel(writer, index=False, sheet_name='요구사항')
                        
                        st.session_state['generated_excel'] = output_buffer.getvalue()
                        st.success("요구사항 명세서 생성 완료! 아래 버튼으로 다운로드하세요.")
                    else:
                        st.warning("분석 결과, 추출된 요구사항이 없습니다.")

                except Exception as e:
                    st.error(f"오류 발생: {e}")
    
    if 'generated_excel' in st.session_state:
        st.download_button(
            label="명세서 다운로드 (.xlsx)", data=st.session_state['generated_excel'],
            file_name="요구사항_명세서.xlsx", mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

# ==================================================================================
# << TAB 2: Side-Effect 예측기 (RAG 포함) >>
# ==================================================================================
with tab2:
    banner("tab2.png", max_height=400)
    spacer()

    section_heading("GitHub PR URL 입력", level=2, bg="#F8D7DA", color="#333")
    pr_url_tab2 = st.text_input("🔗 PR URL", key="pr_url_input_tab2", placeholder="[https://github.com/owner/repo/pull/123](https://github.com/owner/repo/pull/123)")

    if st.button("PR 코드 불러오기", key="fetch_pr_tab2", use_container_width=True):
        if not pr_url_tab2:
            st.warning("PR URL을 입력하세요.")
        else:
            try:
                owner, repo, pr_no = parse_pr_url(pr_url_tab2)
                with st.spinner("GitHub에서 코드 가져오는 중..."):
                    orig, mod = fetch_pr_code_only(owner, repo, pr_no)
                st.session_state.update({"orig_tab2": orig, "mod_tab2": mod})
                st.success("코드 로드 완료!")
            except Exception as e:
                st.error(f"GitHub 불러오기 실패: {e}")

    spacer()

    section_heading("요구사항 명세서 업로드", level=2, bg="#F8D7DA", color="#333")
    uploaded_req_file_tab2 = st.file_uploader("요구사항 엑셀(.xlsx) 파일 업로드", type=["xlsx"], key="req_uploader_tab2")
    if uploaded_req_file_tab2 and (req_text_tab2 := read_excel_to_string(uploaded_req_file_tab2)):
        st.session_state["req_text_tab2"] = req_text_tab2
        st.success("요구사항 파일 분석 완료!")
        with st.expander("업로드된 요구사항 보기"): st.markdown(req_text_tab2)
    
    spacer()

    section_heading("코드 확인 및 수정", level=2, bg="#F8D7DA", color="#333")
    st.text_area("원본 코드", key="orig_tab2", height=180)
    st.text_area("수정된 코드", key="mod_tab2", height=180)

    st.markdown("---")
    if st.button(" RAG 기반 예측 및 DB 저장", use_container_width=True, key="predict_btn_tab2"):
        req_content = st.session_state.get("req_text_tab2", "")
        orig_code = st.session_state.get("orig_tab2", "")
        mod_code = st.session_state.get("mod_tab2", "")

        if not pr_url_tab2 or not req_content or not orig_code:
            st.warning("PR URL, 요구사항, 코드를 모두 준비해주세요.")
        elif not pinecone_index:
            st.error("Pinecone DB가 연결되지 않았습니다. .env 파일을 확인하세요.")
        else:
            try:
                owner, repo, pr_no = parse_pr_url(pr_url_tab2)
                pr_id = f"{owner}/{repo}#{pr_no}"
                code_diff = make_code_diff(orig_code, mod_code)
                
                with st.spinner("유사 사례 검색 → RAG 예측 → DB 저장 중..."):
                    query_text = f"[요구사항]\n{req_content}\n\n[코드 변경]\n{code_diff}"
                    matches = search_similar_prs(query_text)
                    rag_context = "\n".join([f"▶ PR: {m.metadata.get('pr_id', '')} (유사도: {m.score:.2f})\n - 예측 요약: {m.metadata.get('side_effect', '')[:200]}..." for m in matches]) if matches else "과거 유사 PR 없음"
                    
                    chain = RAG_PROMPT_TEMPLATE | se_llm
                    response = chain.invoke({"rag_context": rag_context, "requirements": req_content, "code_diff": code_diff})
                    final_text = getattr(response, "content", "").strip()

                    embedding_text = f"[요구사항]\n{req_content}\n\n[코드 변경]\n{code_diff}\n\n[예측 결과]\n{final_text}"
                    meta = {"pr_id": pr_id, "title": pr_url_tab2, "desc": req_content[:150], "side_effect": final_text[:1000], "url": pr_url_tab2}
                    upsert_to_pinecone(pr_id, embedding_text, meta)
                    
                    st.session_state["final_result_tab2"] = final_text
                    st.success("RAG 기반 예측 및 DB 저장이 완료되었습니다!")
            except Exception as e:
                st.error(f"예측 중 오류 발생: {e}")

    if "final_result_tab2" in st.session_state:
        st.markdown("## RAG 기반 예측 결과")
        st.markdown(st.session_state["final_result_tab2"], unsafe_allow_html=True)


# ==================================================================================
# << TAB 3: Side-Effect 완전예측 >>
# ==================================================================================
with tab3:
    banner("tab3.png", max_height=400)
    spacer()

    section_heading("GitHub PR URL 입력", level=2, bg="#F8D7DA", color="#333")
    pr_url_tab3 = st.text_input("🔗 PR URL", key="pr_url_input_tab3", placeholder="[https://github.com/owner/repo/pull/123](https://github.com/owner/repo/pull/123)")
    
    if st.button("원본 코드 불러오기", key="fetch_orig_tab3", use_container_width=True):
        if not pr_url_tab3:
            st.warning("PR URL을 입력해주세요.")
        else:
            try:
                owner, repo, pr_no = parse_pr_url(pr_url_tab3)
                with st.spinner("GitHub에서 원본 코드 가져오는 중..."):
                    orig, _ = fetch_pr_code_only(owner, repo, pr_no) # 원본 코드만 사용
                st.session_state["orig_tab3"] = orig
                st.success("원본 코드 로드 완료!")
            except Exception as e:
                st.error(f"GitHub 불러오기 실패: {e}")
    
    spacer()

    section_heading("요구사항 명세서 업로드", level=2, bg="#F8D7DA", color="#333")
    uploaded_req_file_tab3 = st.file_uploader("요구사항 엑셀(.xlsx) 파일 업로드", type=["xlsx"], key="req_uploader_tab3")
    
    if uploaded_req_file_tab3 and (req_text_tab3 := read_excel_to_string(uploaded_req_file_tab3)):
        st.session_state["req_text_tab3"] = req_text_tab3
        st.success("요구사항 파일 분석 완료!")
        with st.expander("업로드된 요구사항 보기"):
            st.markdown(req_text_tab3)

    spacer()
    
    section_heading("수정된 코드 생성 및 예측", level=2, bg="#F8D7DA", color="#333")
    st.text_area("원본 코드", key="orig_tab3", height=180)
    
    if st.button("🚀 수정 코드 생성 및 Side-Effect 예측", use_container_width=True, key="generate_predict_btn_tab3"):
        req_content = st.session_state.get("req_text_tab3", "")
        orig_code = st.session_state.get("orig_tab3", "")

        if not pr_url_tab3 or not req_content or not orig_code:
            st.warning("PR URL, 요구사항, 원본 코드를 모두 준비해주세요.")
        elif not pinecone_index:
            st.error("Pinecone DB가 연결되지 않았습니다. .env 파일을 확인하세요.")
        else:
            with st.spinner("1단계: 요구사항 기반으로 코드 수정 중..."):
                try:
                    modified_code = generate_modified_code(req_content, orig_code)
                    st.session_state["modified_code_tab3"] = modified_code
                    st.success("코드 수정 완료!")
                except Exception as e:
                    st.error(f"코드 생성 중 오류 발생: {e}")
                    st.stop()
            
            with st.spinner("2단계: 유사 사례 검색 및 Side-Effect 예측 중..."):
                try:
                    owner, repo, pr_no = parse_pr_url(pr_url_tab3)
                    pr_id = f"{owner}/{repo}#{pr_no}-generated" # 생성된 코드임을 명시
                    code_diff = make_code_diff(orig_code, modified_code)

                    query_text = f"[요구사항]\n{req_content}\n\n[코드 변경]\n{code_diff}"
                    matches = search_similar_prs(query_text)
                    rag_context = "\n".join([f"▶ PR: {m.metadata.get('pr_id', '')} (유사도: {m.score:.2f})\n - 예측 요약: {m.metadata.get('side_effect', '')[:200]}..." for m in matches]) if matches else "과거 유사 PR 없음"
                    
                    chain = RAG_PROMPT_TEMPLATE | se_llm
                    response = chain.invoke({"rag_context": rag_context, "requirements": req_content, "code_diff": code_diff})
                    final_text = getattr(response, "content", "").strip()

                    embedding_text = f"[요구사항]\n{req_content}\n\n[코드 변경]\n{code_diff}\n\n[예측 결과]\n{final_text}"
                    meta = {"pr_id": pr_id, "title": pr_url_tab3, "desc": req_content[:150], "side_effect": final_text[:1000], "url": pr_url_tab3}
                    
                    # Pinecone에 데이터를 저장하는 함수를 호출합니다.
                    upsert_to_pinecone(pr_id, embedding_text, meta)

                    st.session_state["final_result_tab3"] = final_text
                    st.success("예측 및 DB 저장 완료!")
                except Exception as e:
                    st.error(f"예측 중 오류 발생: {e}")

    if "modified_code_tab3" in st.session_state:
        st.markdown("### AI가 생성한 수정 코드")
        st.code(st.session_state["modified_code_tab3"], language="python")

    if "final_result_tab3" in st.session_state:
        st.markdown("## 🤖 RAG 기반 예측 결과")
        st.markdown(st.session_state["final_result_tab3"], unsafe_allow_html=True)
# ==================================================================================

# --- (여기까지 각 탭의 내용들) ---

# 하단 고정 박스
st.markdown("""
<style>
.footer {
    width: 100%;
    background-color: #8C8C8C; /* 어두운 배경 */
    color: #fff;            /* 흰색 글자 */
    text-align: center;
    padding: 12px 0;
    font-size: 14px;
    border-top: 1px solid rgba(255,255,255,0.2);
    margin-top: 30px; /* 위쪽과 여백 */
}
</style>

<div class="footer">
    © 2025 S-Kape. All rights reserved. | SK mySUNI SUNIC Season 4. #19
</div>
""", unsafe_allow_html=True)


