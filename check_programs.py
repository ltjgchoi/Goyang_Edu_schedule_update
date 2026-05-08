import os
import json
import requests
from bs4 import BeautifulSoup
from datetime import datetime

# ── 설정 ──────────────────────────────────────────────
URL = (
    "https://gong-u.goe.go.kr/goyang/program/studentProgram/list"
    "?semesterTarget=&menuLevel=2&menuNo=1046"
    "&searchCategory=&searchType=&searchRecruitEndType="
    "&searchRecruitTarget=e5&searchDayOfWeek=&searchWord="
)
STATE_FILE = "seen_programs.json"
TELEGRAM_TOKEN = os.environ["TELEGRAM_TOKEN"]
TELEGRAM_CHAT_ID = os.environ["TELEGRAM_CHAT_ID"]

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/124.0.0.0 Safari/537.36"
    )
}

# ── 텔레그램 알림 ────────────────────────────────────
def send_telegram(message: str):
    api_url = f"https://api.telegram.org/bot{TELEGRAM_TOKEN}/sendMessage"
    payload = {
        "chat_id": TELEGRAM_CHAT_ID,
        "text": message,
        "parse_mode": "HTML",
        "disable_web_page_preview": False,
    }
    resp = requests.post(api_url, json=payload, timeout=10)
    resp.raise_for_status()
    print(f"[텔레그램 전송 완료] {message[:50]}...")

# ── 페이지 파싱 ──────────────────────────────────────
def fetch_programs() -> list[dict]:
    resp = requests.get(URL, headers=HEADERS, timeout=15)
    resp.raise_for_status()
    soup = BeautifulSoup(resp.text, "html.parser")

    programs = []
    table = soup.find("table")
    if not table:
        print("테이블을 찾지 못했습니다.")
        return programs

    rows = table.find("tbody").find_all("tr") if table.find("tbody") else table.find_all("tr")[1:]
    for row in rows:
        cols = row.find_all("td")
        if len(cols) < 13:
            continue

        # 컬럼 순서: 유형(0) 개설지역(1) 프로그램명(2) 영역/주제(3) 정원(4)
        #            수강신청기간(5) 수업기간(6) 수업장소(7) 수업요일(8)
        #            모집대상(9) 신청인원(10) 모집상태(11) 상세보기(12)
        name = cols[2].get_text(strip=True)
        status = cols[11].get_text(strip=True)
        recruit_period = cols[5].get_text(strip=True)
        target = cols[9].get_text(strip=True)

        # 상세보기 링크
        link_tag = cols[12].find("a")
        link = ""
        if link_tag and link_tag.get("href"):
            href = link_tag["href"]
            link = href if href.startswith("http") else f"https://gong-u.goe.go.kr{href}"

        programs.append({
            "name": name,
            "status": status,
            "recruit_period": recruit_period,
            "target": target,
            "link": link,
        })

    return programs

# ── 상태 로드/저장 ────────────────────────────────────
def load_seen() -> set[str]:
    if not os.path.exists(STATE_FILE):
        return set()
    with open(STATE_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    return set(data.get("names", []))

def save_seen(names: set[str]):
    with open(STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"names": sorted(names), "updated": datetime.now().isoformat()}, f, ensure_ascii=False, indent=2)

# ── 메인 ─────────────────────────────────────────────
def main():
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M')}] 프로그램 목록 확인 시작")
    programs = fetch_programs()
    print(f"  현재 1페이지 프로그램 수: {len(programs)}개")

    seen = load_seen()
    current_names = {p["name"] for p in programs}

    new_programs = [p for p in programs if p["name"] not in seen]

    if new_programs:
        now_str = datetime.now().strftime("%Y-%m-%d %H:%M")
        for p in new_programs:
            msg = (
                f"🆕 <b>신규 프로그램 등록!</b>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"📌 <b>{p['name']}</b>\n"
                f"📅 모집기간: {p['recruit_period']}\n"
                f"🎯 모집대상: {p['target']}\n"
                f"📊 상태: {p['status']}\n"
                f"🔗 <a href=\"{p['link']}\">바로가기</a>\n"
                f"━━━━━━━━━━━━━━━━\n"
                f"⏰ 확인시각: {now_str}"
            )
            send_telegram(msg)
        print(f"  신규 프로그램 {len(new_programs)}개 알림 전송 완료")
    else:
        print("  신규 프로그램 없음")

    # 상태 업데이트 (현재 목록을 기준으로 저장)
    save_seen(current_names)
    print("  상태 저장 완료")

if __name__ == "__main__":
    main()
