# Desktop Calendar Widget 개발 로그

이 문서는 개발 과정에서 **왜** 그런 변경을 했고, **어떻게** 구현했는지를 정리한 학습용 문서입니다.

---

## 1. Anaconda 환경에서 Python 실행 지원

### 문제
- `conda --version`은 되지만 `python` 명령이 안 됨
- Anaconda는 자체 환경(base) 안에 python을 넣어두기 때문에, 일반 CMD에서는 `python`이 PATH에 없음

### 해결 (DesktopCalendar.bat)
```bat
call conda activate base 2>nul
```
- `conda activate base`를 먼저 실행해서 Anaconda의 python을 PATH에 올림
- 실패 시 일반적인 Anaconda 설치 경로(`%USERPROFILE%\anaconda3` 등)를 탐색해서 직접 PATH에 추가

### 배운 점
- Anaconda는 가상환경 시스템이라 `conda` 자체는 PATH에 있어도 `python`은 환경 활성화 후에만 접근 가능
- `call` 키워드: BAT 파일 안에서 다른 명령을 호출할 때 사용. `call` 없이 하면 BAT가 거기서 종료됨

---

## 2. CMD 창이 계속 떠있는 문제 해결

### 문제
- BAT 파일로 실행하면 `python main.py`가 포그라운드에서 실행되어 CMD 창이 계속 남아있음

### 해결
```bat
start "" pythonw main.py
```

### 핵심 개념
| 명령 | 설명 |
|------|------|
| `python` | 콘솔 창이 필요한 Python 인터프리터 |
| `pythonw` | 콘솔 창 없이 실행되는 Python (GUI 앱용) |
| `start ""` | 새 프로세스로 분리 실행. BAT는 기다리지 않고 즉시 종료 |

### 배운 점
- GUI 앱은 `pythonw`로 실행해야 불필요한 콘솔 창이 안 뜸
- `start "" 프로그램`으로 실행하면 BAT가 프로그램 종료를 기다리지 않고 바로 끝남

---

## 3. 일정 삭제 기능 추가

### 문제
- 등록한 일정을 앱 안에서 삭제할 수 없었음 (Google Calendar 웹에서만 가능)

### 해결 방법

#### 3-1. Google API 삭제 함수 추가 (`google_service.py`)
```python
def delete_event(event_id: str) -> None:
    service = _calendar_service()
    service.events().delete(calendarId="primary", eventId=event_id).execute()
```
- Google Calendar API의 `events().delete()` 메서드 사용
- Tasks는 어떤 tasklist에 속해있는지 모르므로 모든 tasklist를 순회하며 삭제 시도

#### 3-2. 다이얼로그 개편 (`add_event_dialog.py`)
- **기존**: 추가만 가능한 단순 폼
- **변경**: 기존 일정 목록(스크롤) + 삭제 버튼 + 추가 폼

#### 3-3. 이벤트 데이터 전달 연결
```python
# main.py — 더블클릭 시 해당 날짜의 이벤트를 필터링해서 전달
existing = [e for e in self._calendar.events if e["date"] == iso_date]
dialog = AddEventDialog(iso_date, existing_events=existing, parent=self)
```
- `calendar_widget.py`에 `events` 프로퍼티를 추가하여 현재 이벤트 목록에 접근 가능하게 함

### 배운 점
- **관심사 분리**: API 호출(`google_service`) → UI(`add_event_dialog`) → 연결(`main.py`)로 역할 분리
- **QScrollArea**: 일정이 많을 때 스크롤 가능하도록 감싸는 위젯
- **lambda 클로저**: `lambda _, e=ev, w=widget: self._on_delete(e, w)` — 반복문 안에서 각 버튼에 고유한 이벤트 데이터를 바인딩하기 위해 기본값 매개변수 사용

---

## 4. 시간 선택을 5분 단위 드롭다운으로 변경

### 문제
- 기존: `QLineEdit`에 "HH:MM" 직접 입력 → 오타 가능, 형식 오류 가능

### 해결
```python
def _build_time_options() -> list[str]:
    options = [""]  # 종일
    for h in range(24):
        for m in range(0, 60, 5):
            options.append(f"{h:02d}:{m:02d}")
    return options
```
- "종일" + 00:00 ~ 23:55 (5분 간격, 총 289개 옵션)
- `QComboBox`로 변경하여 선택식으로 전환

### 배운 점
- **UX 개선**: 자유 입력 → 선택식으로 바꾸면 입력 오류가 원천 차단됨
- `f"{h:02d}"`: Python f-string에서 2자리 0-패딩 포맷팅

---

## 5. 직접입력 체크박스 추가

### 문제
- 드롭다운만 있으면 5분 단위가 아닌 시간(예: 14:03)은 입력 불가

### 해결
```python
self._manual_check = QCheckBox("직접입력")
self._manual_check.toggled.connect(self._on_manual_toggled)
```
- 체크 해제: `QComboBox` (드롭다운) 표시
- 체크: `QLineEdit` (자유 입력) 표시
- `_on_manual_toggled`에서 두 위젯의 `setVisible()`을 토글

### 시간 값 읽기 로직
```python
if self._manual_check.isChecked():
    time_text = self._time_edit.text().strip() or None
elif self._time_combo.currentIndex() > 0:
    time_text = self._time_combo.currentText()
```

### 배운 점
- **QCheckBox.toggled 시그널**: 체크 상태가 바뀔 때 발생, `bool` 값 전달
- 같은 위치에 두 위젯을 두고 `setVisible()`로 전환하는 패턴은 UI에서 자주 사용됨

---

## 6. 라벨 왼쪽 정렬

### 문제
- 유형/제목/시간 라벨이 각각 텍스트 길이만큼만 차지해서 오른쪽 입력 필드가 들쭉날쭉

### 해결
```python
lbl_type = QLabel("유형")
lbl_type.setFixedWidth(40)
```
- 모든 라벨에 동일한 고정 너비(40px)를 설정하여 정렬

### 배운 점
- **setFixedWidth**: 위젯의 너비를 고정. 레이아웃 매니저가 이 값을 존중함
- 폼 레이아웃에서 라벨을 정렬하는 가장 간단한 방법

---

## 7. 다중 날짜(야간) 일정 표시 수정

### 문제
- 5/30 17:00 ~ 5/31 10:00 일정이 5/30에만 표시되고 5/31에는 안 나옴
- 원인: `_normalize_calendar_events`가 **시작 날짜 1개만** 기준으로 이벤트를 생성

### 해결
```python
start_date = start_dt.date()
end_date = end_dt.date()
# 자정에 정확히 끝나면 그 날은 차지하지 않음
if end_dt.hour == 0 and end_dt.minute == 0 and end_dt.second == 0:
    end_date -= timedelta(days=1)

current = start_date
while current <= end_date:
    prefix = time_prefix if current == start_date else "[연속] "
    results.append({...})
    current += timedelta(days=1)
```

### 처리 케이스
| 일정 | 표시 결과 |
|------|----------|
| 5/30 17:00 ~ 5/31 10:00 | 5/30: `[17:00] 제목`, 5/31: `[연속] 제목` |
| 5/30 종일 ~ 6/1 종일 | 5/30, 5/31, 6/1 모두: `제목` |
| 5/30 22:00 ~ 5/31 00:00 | 5/30만: `[22:00] 제목` (자정 종료는 그 날 미포함) |

### 배운 점
- **Google Calendar API의 종일 이벤트**: `end.date`가 **exclusive**(미포함). 5/30~5/31 종일이면 end는 6/1
- **datetime.date()**: datetime에서 날짜 부분만 추출
- **timedelta(days=1)**: 하루씩 순회할 때 사용
- 이벤트를 여러 날짜에 **복제**하는 방식으로 캘린더 그리드와 호환성 유지

---

## 프로젝트 구조 요약

```
desktopcal/
├── main.py                  # 메인 윈도우, 동기화, 드래그/리사이즈
├── src/
│   ├── calendar_widget.py   # 월간 달력 그리드 UI
│   ├── add_event_dialog.py  # 일정 추가/삭제 다이얼로그
│   ├── google_service.py    # Google Calendar/Tasks API 호출
│   ├── auth.py              # OAuth 2.0 인증
│   ├── cache.py             # SQLite 오프라인 캐시
│   └── system_tray.py       # 시스템 트레이 아이콘/메뉴
├── DesktopCalendar.bat      # 실행 스크립트 (CMD)
├── DesktopCalendar.vbs      # 실행 스크립트 (창 없이)
└── requirements.txt         # 의존성 목록
```

---

## 8. 월 변경 시 동기화 속도 개선

### 문제
- 월을 바꾸면 일정이 비어있는 빈 화면이 수 초간 보이다가 뒤늦게 채워짐
- 체감 로딩이 매우 느림

### 원인 분석 (4가지)

| 원인 | 설명 |
|------|------|
| `build()` 반복 호출 | 매 API 호출마다 `build("calendar", "v3", ...)` → HTTP discovery 문서를 다시 가져옴 |
| 순차 API 호출 | `fetch_month_events()` 완료 → `fetch_month_tasks()` 시작. 직렬이라 대기 시간이 합산됨 |
| 캐시 미활용 | 이미 SQLite에 캐시가 있는데도, API 응답 올 때까지 빈 화면 |
| 500ms 디바운스 | 월 변경 후 0.5초 대기 후에야 API 호출 시작 |

### 해결 1: 서비스 객체 캐싱 (싱글턴)

```python
_cached_calendar_service = None

def _calendar_service():
    global _cached_calendar_service
    if _cached_calendar_service is None:
        _cached_calendar_service = build("calendar", "v3", credentials=get_credentials())
    return _cached_calendar_service
```

**왜?** `build()`는 내부적으로 Google API의 discovery document를 HTTP로 가져와서 파싱합니다. 이 과정이 수백ms 걸리는데, 서비스 객체는 재사용 가능하므로 최초 1회만 생성하면 됩니다.

**추가**: 401/403 에러 시 `invalidate_services()`로 캐시를 무효화해서 토큰 갱신 후 재생성되게 처리.

### 해결 2: events + tasks 병렬 fetch

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def fetch_all(year, month):
    with ThreadPoolExecutor(max_workers=2) as pool:
        fut_events = pool.submit(fetch_month_events, year, month)
        fut_tasks = pool.submit(fetch_month_tasks, year, month)
        for fut in as_completed([fut_events, fut_tasks]):
            results.extend(fut.result())
```

**왜?** events와 tasks는 서로 독립적인 API 호출입니다. 순차적으로 하면 각각 1초씩 걸릴 때 2초가 되지만, 병렬이면 1초면 됩니다.

**핵심 개념**:
- `ThreadPoolExecutor`: 스레드 풀을 만들어서 작업을 분배
- `pool.submit()`: 작업을 스레드에 제출 (즉시 반환, 백그라운드 실행)
- `as_completed()`: 완료되는 순서대로 결과를 받아옴

### 해결 3: 캐시 우선 표시 (Optimistic UI)

```python
def _on_nav(self) -> None:
    year, month = self._calendar.year, self._calendar.month
    cached = cache.load_events(year, month)
    if cached:
        self._calendar.set_events(cached)  # 즉시 표시!
    self._nav_timer.start(NAV_SYNC_DELAY_MS)  # API는 뒤에서 갱신
```

**왜?** 사용자가 월을 바꾸는 순간, SQLite 캐시에서 읽는 건 ~1ms입니다. 이걸 먼저 보여주고, 백그라운드에서 API 결과가 오면 갱신하면 됩니다.

**패턴 이름**: **Optimistic UI** (낙관적 UI)
- 로컬 데이터를 먼저 보여줘서 즉각적인 반응을 제공
- 서버 데이터가 오면 조용히 업데이트
- 대부분의 경우 캐시 데이터와 서버 데이터가 동일하므로 사용자는 변화를 못 느낌

### 해결 4: 디바운스 감소

```python
NAV_SYNC_DELAY_MS = 100  # 기존 500ms → 100ms
```

**왜?** 캐시를 먼저 보여주므로 사용자 체감은 이미 즉각적입니다. API 호출까지의 대기도 줄여서 최신 데이터로의 갱신도 빨라지게 합니다.

### 개선 효과 요약

| 항목 | Before | After |
|------|--------|-------|
| 서비스 생성 | 매번 ~300ms | 최초 1회만 |
| API 호출 | 순차 (A+B) | 병렬 (max(A,B)) |
| 월 변경 시 화면 | 빈 화면 → 수초 대기 | 캐시 즉시 표시 → API 갱신 |
| 디바운스 | 500ms | 100ms |

### 배운 점
- **싱글턴 패턴**: 비싼 객체는 한 번 만들어서 재사용. `global` 변수 + `None` 체크로 간단 구현
- **ThreadPoolExecutor**: Python 표준 라이브러리로 간단하게 병렬 처리. `with`문으로 자동 정리
- **Optimistic UI**: 로컬 캐시 → 즉시 표시 → 서버 갱신은 모바일/웹에서도 널리 쓰이는 패턴
- **디바운스**: 빠른 연속 입력에서 마지막 입력만 처리. `QTimer.setSingleShot(True)` + `start()`로 구현

---

## 9. 월 변경 시 빈 화면 깜빡임 제거

### 문제
- 월을 바꾸면 빈 달력이 순간적으로 떴다가 사라짐

### 원인
`go_prev()`/`go_next()`에서 `_rebuild(빈 데이터)`가 1번, `_on_nav()`에서 `set_events(캐시)`로 `_rebuild()`가 또 1번 — **이중 빌드**

```
_on_prev() → go_prev() → _rebuild(빈 데이터) ← 여기서 깜빡!
           → nav_clicked.emit() → _on_nav() → set_events(캐시) → _rebuild(캐시 데이터)
```

### 해결
`go_prev()`/`go_next()`에서 `_rebuild()` 호출 제거. 월/년 값만 변경하고, `_on_nav()`에서 캐시와 함께 한 번만 빌드.

### 배운 점
- **이벤트 흐름 추적**: 버그의 원인을 찾으려면 시그널/슬롯 체인을 따라가며 호출 순서를 확인해야 함
- UI 깜빡임은 보통 **불필요한 중간 렌더링** 때문에 발생. 최종 상태만 1회 렌더링하면 해결됨

---

## 10. 한국 공휴일 표시 및 일요일 날짜 빨간색

### 문제
- 달력에 한국 공휴일이 전혀 표시되지 않음
- 일요일 날짜 숫자가 평일과 같은 흰색이라 구분이 안 됨

### 해결 1: 공휴일 데이터 모듈 (`src/holidays.py`)

```python
# 고정 공휴일 (매년 동일)
_FIXED_HOLIDAYS = [
    (1, 1, "신정"), (3, 1, "삼일절"), (5, 5, "어린이날"),
    (6, 6, "현충일"), (8, 15, "광복절"), (10, 3, "개천절"),
    (10, 9, "한글날"), (12, 25, "성탄절"),
]

# 음력 기반 공휴일 (연도별 룩업 테이블)
_LUNAR_HOLIDAYS = {
    2026: [
        (2, 16, "설날 연휴"), (2, 17, "설날"), (2, 18, "설날 연휴"),
        (5, 24, "부처님오신날"), ...
    ],
    ...
}
```

**왜 룩업 테이블?** 음력→양력 변환은 복잡한 계산이 필요하고 외부 라이브러리 의존성이 생김. 2024~2030년 데이터를 미리 계산해두면 외부 의존성 없이 정확하게 동작.

### 해결 2: DayCell에 공휴일/일요일 스타일 적용

```python
class DayCell:
    def __init__(self, ..., is_sunday=False, holiday_name=None):
        is_red = is_sunday or holiday_name is not None

        # 날짜 숫자 색상
        if is_today:
            color = "#4FC3F7"      # 오늘: 파란색 (최우선)
        elif is_red:
            color = "#FF6B6B"      # 일요일/공휴일: 빨간색
        else:
            color = "#E0E0E0"      # 평일: 밝은 회색

        # 공휴일 이름 표시
        if holiday_name:
            h_lbl = QLabel(holiday_name)
            h_lbl.setStyleSheet("color: #FF8A80; ...")
```

### 해결 3: _rebuild에서 공휴일 조회

```python
holidays = get_holidays(self._year, self._month)  # {day: name}

cell = DayCell(
    iso, day, items,
    is_today=is_today,
    is_sunday=(col == 0),         # Sunday-first 레이아웃에서 0번째 열
    holiday_name=holidays.get(day),
)
```

### 배운 점
- **데이터와 표현 분리**: 공휴일 데이터(`holidays.py`)와 UI(`calendar_widget.py`)를 분리
- **룩업 테이블 vs 계산**: 데이터가 제한적이고 변하지 않으면 계산보다 테이블이 간단하고 안전
- **색상 우선순위**: 오늘 > 일요일/공휴일 > 평일 순으로 색상 결정 (if-elif 체인)

---

## 11. 리사이즈 커서가 달력 위에서 유지되는 버그 수정

### 문제
- 윈도우 가장자리에서 마우스를 올리면 리사이즈 커서(↔)가 나타나는데, 달력 위로 이동해도 커서가 돌아오지 않음

### 원인
```
1. 마우스가 가장자리 → MainWindow.setCursor(SizeHorCursor)
2. 마우스가 달력 위로 이동 → 자식 위젯이 mouseMoveEvent를 받아서
   MainWindow의 mouseMoveEvent가 호출되지 않음 → setCursor(ArrowCursor) 실행 안 됨
3. 자식 위젯에 자체 커서 미설정 → 부모의 SizeHorCursor을 상속
```

### 해결
```python
# MonthlyCalendarWidget에 자체 커서를 명시적으로 설정
self.setCursor(Qt.CursorShape.ArrowCursor)
```

### 배운 점
- **Qt 커서 상속**: 자식 위젯에 커서가 없으면 부모 위젯의 커서를 상속함
- 자식에 명시적 커서를 설정하면 부모 커서와 무관하게 자체 커서를 표시

---

## 12. 창 이동을 휠클릭(중간 버튼) 드래그로 변경

### 문제
- 좌클릭 드래그로 창을 이동하면, 달력 셀 클릭/더블클릭과 충돌

### 해결

#### MainWindow 마우스 이벤트 분리
```python
def mousePressEvent(self, event):
    if event.button() == Qt.MouseButton.LeftButton:
        # 가장자리일 때만 리사이즈
        edge = self._edge_at(event.position().toPoint())
        if edge:
            self._resize_edge = edge
            ...
    elif event.button() == Qt.MouseButton.MiddleButton:
        # 휠클릭: 창 드래그
        self._drag_pos = event.globalPosition().toPoint() - self.frameGeometry().topLeft()
```

#### 자식 위젯에서 중간 버튼 이벤트 전달
```python
class DayCell(QFrame):
    def mousePressEvent(self, event):
        if event.button() == Qt.MouseButton.MiddleButton:
            event.ignore()  # 부모(MainWindow)로 전달
            return
        super().mousePressEvent(event)
```

### Qt 이벤트 전파 메커니즘
| 메서드 | 효과 |
|--------|------|
| `event.accept()` | 이벤트를 이 위젯에서 처리함 (기본값). 부모에게 전달 안 됨 |
| `event.ignore()` | 이 위젯이 처리 안 함. Qt가 부모 위젯으로 자동 전파 |

### 배운 점
- **이벤트 버블링**: Qt에서 `ignore()`하면 이벤트가 부모 위젯으로 올라감 (웹의 이벤트 버블링과 유사)
- **마우스 버튼 분리**: 좌클릭/중간클릭/우클릭을 구분해서 다른 동작을 할당할 수 있음
- `Qt.MouseButton.MiddleButton`: 마우스 휠 버튼 클릭

---

## 13. 종일 일정이 리스트에 안 나오는 버그 수정

### 문제
- 종일 이벤트를 추가해도 달력에 표시되지 않음

### 원인
`create_event`에서 종일 이벤트 생성 시 `end.date`를 `start.date`와 **동일하게** 설정:
```python
# 버그 코드
body = {
    "start": {"date": "2026-03-11"},
    "end":   {"date": "2026-03-11"},  # ← 같은 날!
}
```

Google Calendar API에서 종일 이벤트의 `end.date`는 **exclusive(미포함)**:
```
normalizer: end_date = 2026-03-11 - 1일 = 2026-03-10
while(2026-03-11 <= 2026-03-10) → False → 결과 0건!
```

### 해결
```python
end_date = (datetime.fromisoformat(date) + timedelta(days=1)).strftime("%Y-%m-%d")
body = {
    "start": {"date": date},           # "2026-03-11"
    "end":   {"date": end_date},        # "2026-03-12" (exclusive)
}
```

### 배운 점
- **Google Calendar API 규칙**: 종일 이벤트의 `end.date`는 exclusive. 1일짜리 이벤트면 end = start + 1
- 데이터를 **읽을 때**(normalizer)와 **쓸 때**(create)의 규칙이 일치해야 함
- 이 버그는 `_normalize_calendar_events`에서 이미 exclusive를 올바르게 처리하고 있었지만, `create_event`에서 규칙을 안 지킨 것

---

## 14. 동기화 버튼 추가 및 동기화 큐잉

### 문제
- 일정 추가/삭제 후 화면이 갱신 안 됨 (이전 동기화 워커 실행 중이면 새 동기화가 무시됨)
- 수동 동기화 버튼이 없어서 사용자가 최신 데이터를 즉시 가져올 방법이 없음

### 해결 1: 동기화 큐잉 (`_sync_pending`)
```python
def _sync(self):
    if self._sync_worker is not None and self._sync_worker.isRunning():
        self._sync_pending = True  # 나중에 실행하도록 예약
        return
    ...

def _on_sync_done(self, year, month, events):
    ...
    if self._sync_pending:
        self._sync_pending = False
        self._sync()  # 대기 중이던 동기화 실행
```

**왜?** 기존에는 워커 실행 중 `_sync()` 호출을 그냥 무시(`return`)했음. 일정 추가 직후 호출되는 `_sync()`가 씹히면 새 이벤트가 안 보임.

### 해결 2: 동기화 버튼 (⟳)
```python
# calendar_widget.py
sync_clicked = pyqtSignal()

self._btn_sync = QPushButton("⟳")
self._btn_sync.clicked.connect(self.sync_clicked)

# main.py
self._calendar.sync_clicked.connect(self._sync)
```
헤더의 `▶` 버튼과 `✕` 버튼 사이에 `⟳` 버튼 배치.

### 배운 점
- **큐잉 패턴**: "지금 못 하면 나중에 해" — `_sync_pending` 플래그로 간단 구현
- 시그널/슬롯 연결만으로 UI 버튼 → 비즈니스 로직 연결 가능

---

### 데이터 흐름
```
Google Calendar/Tasks API
        ↓ fetch
google_service.py (정규화)
        ↓ events list
calendar_widget.py (그리드 렌더링)
        ↓ double-click signal
add_event_dialog.py (추가/삭제 UI)
        ↓ API 호출
google_service.py → Google API
```

---

## 15. 토요일 날짜 파란색 표시

### 문제
- 일요일은 빨간색으로 표시했지만, 토요일도 평일과 동일한 흰색이라 구분이 안 됨

### 해결
```python
# DayCell 색상 우선순위
if is_today:
    color = "#4FC3F7"       # 오늘: 밝은 파란색
elif is_sunday or holiday_name:
    color = "#FF6B6B"       # 일요일/공휴일: 빨간색
elif is_saturday:
    color = "#5B9BD5"       # 토요일: 파란색
else:
    color = "#E0E0E0"       # 평일: 밝은 회색
```

### 배운 점
- if-elif 체인의 **순서**가 우선순위를 결정. 토요일이면서 공휴일이면 빨간색이 적용됨

---

## 16. 삭제 확인 다이얼로그 스타일 개선

### 문제
- 삭제 확인 팝업의 Yes/No 버튼이 어두운 배경에 검은 글씨라 안 보임
- 영문 Yes/No가 한국어 UI와 어울리지 않음

### 해결
```python
msg = QMessageBox(self)
btn_yes = msg.addButton("네", QMessageBox.ButtonRole.YesRole)
btn_no = msg.addButton("아니요", QMessageBox.ButtonRole.NoRole)
btn_yes.setStyleSheet("background-color: #EF5350; color: #FFFFFF;")
btn_no.setStyleSheet("background-color: #616161; color: #FFFFFF;")
```

### 배운 점
- `QMessageBox.addButton(text, role)`: 기본 버튼 대신 커스텀 텍스트/스타일 버튼 추가 가능
- `ButtonRole.YesRole`/`NoRole`: Qt가 버튼 동작(기본 선택 등)을 결정하는 데 사용하는 역할 값

---

## 17. 일정 수정 기능 추가

### 문제
- 일정 추가/삭제만 가능하고, 기존 일정의 제목이나 시간을 수정할 수 없었음

### 해결

#### 17-1. Google API 업데이트 함수 (`google_service.py`)
```python
@_retry_on_auth_error
def update_event(event_id, summary, date, start_time=None):
    body = {"summary": summary, "start": {...}, "end": {...}}
    service.events().update(calendarId="primary", eventId=event_id, body=body).execute()

@_retry_on_auth_error
def update_task(task_id, title, date):
    # 모든 tasklist를 순회하여 해당 task를 찾아 업데이트
    for tl in tasklists:
        task = service.tasks().get(tasklist=tl["id"], task=task_id).execute()
        task["title"] = title
        service.tasks().update(tasklist=tl["id"], task=task_id, body=task).execute()
```

#### 17-2. 다이얼로그에 수정 모드 추가 (`add_event_dialog.py`)
```python
def _on_edit(self, ev):
    self._editing_event = ev
    self._form_label.setText("일정 수정")
    self._btn_ok.setText("수정")
    title, time_str = self._parse_summary(ev["summary"], ev["source"])
    self._title_edit.setText(title)
    # 시간 드롭다운/입력 필드에도 기존 값 세팅
```

#### 17-3. summary에서 제목/시간 파싱
```python
@staticmethod
def _parse_summary(summary, source):
    if source == "calendar":
        m = re.match(r"^\[(\d{2}:\d{2})\]\s*(.*)$", summary)
        if m:
            return m.group(2), m.group(1)  # (title, time)
    elif source == "tasks":
        m = re.match(r"^\[[ x]\]\s*(.*)$", summary)
        if m:
            return m.group(1), ""
    return summary, ""
```

### 배운 점
- **상태 기반 UI**: `_editing_event`가 `None`이면 추가 모드, 값이 있으면 수정 모드. 같은 폼을 두 모드에서 재활용
- **정규식으로 파싱**: `[HH:MM] 제목` 형태에서 시간과 제목을 분리. `re.match`는 문자열 시작부터 매칭
- Tasks API는 event ID로 직접 접근이 안 되므로, 모든 tasklist를 순회해서 찾아야 함

---

## 18. 종일 체크박스로 UI 개선

### 문제
- 시간 드롭다운에 "종일" 옵션이 포함되어 있어서 직관적이지 않음
- 종일 일정을 만들려면 스크롤해서 빈 항목을 찾아야 함

### 해결
```python
# 시간 행 구성: 시간라벨 | 드롭다운 | 직접입력체크 | (스트레치) | 종일체크
self._allday_check = QCheckBox("종일")
self._allday_check.toggled.connect(self._on_allday_toggled)

def _on_allday_toggled(self, checked):
    self._time_combo.setVisible(not checked and not self._manual_check.isChecked())
    self._time_edit.setVisible(not checked and self._manual_check.isChecked())
    self._manual_check.setVisible(not checked)
```

### 배운 점
- **토글 가시성 매트릭스**: 3개의 체크박스/콤보 상태가 서로 영향을 미칠 때, 각 콜백에서 전체 가시성을 재계산해야 함
- `QLineEdit.setInputMask("99:99")`: 시간 입력 시 콜론이 자동으로 채워져서 형식 오류 방지

---

## 19. OAuth 토큰 만료 대응 및 자동 재인증

### 문제
- 일정 시간이 지나면 "invalid_grant" 오류로 인증 재요구
- API 호출 실패 시 복구 없이 그대로 에러 발생

### 원인
1. Google Cloud Console에서 OAuth 동의 화면이 **"테스트" 모드**이면 refresh token이 **7일 후 만료**
2. Refresh token이 만료/취소되었을 때 복구 로직이 없었음
3. API 쓰기 작업(create, delete, update) 시 401/403 에러 처리 없었음

### 해결 1: auth.py — refresh 실패 시 재인증 fallback
```python
if creds and creds.expired and creds.refresh_token:
    try:
        creds.refresh(Request())
    except Exception:
        creds = None  # refresh 실패 → 전체 재인증으로 fallback

if creds is None or not creds.valid:
    flow = InstalledAppFlow.from_client_secrets_file(...)
    creds = flow.run_local_server(
        port=0,
        access_type="offline",   # 오프라인 접근 요청 → refresh token 발급
        prompt="consent",        # 항상 동의 화면 표시 → 새 refresh token 보장
    )
```

### 해결 2: google_service.py — 쓰기 작업 자동 재시도
```python
def _retry_on_auth_error(fn):
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        try:
            return fn(*args, **kwargs)
        except HttpError as e:
            if e.resp.status in (401, 403):
                invalidate_services()  # 서비스 캐시 무효화
                return fn(*args, **kwargs)  # 새 credentials로 재시도
            raise
    return wrapper
```

### 해결 3: Google Cloud Console 설정 (사용자 조치)
| 설정 | 테스트 모드 | 프로덕션 모드 |
|------|-----------|-------------|
| Refresh token 수명 | 7일 | 무기한 |
| 사용 가능 유저 | 등록된 테스트 유저만 | 모든 Google 계정 |
| 전환 방법 | - | OAuth 동의 화면 → "앱 게시" 클릭 |

### 핵심 개념: OAuth 2.0 토큰 흐름
```
최초 인증 → Authorization Code → Access Token (1시간) + Refresh Token (장기)
                                       ↓ 만료
                                  Refresh Token으로 새 Access Token 발급
                                       ↓ Refresh Token 만료 (테스트 모드: 7일)
                                  전체 재인증 필요 (브라우저 열림)
```

### OAuth 파라미터 설명
| 파라미터 | 값 | 효과 |
|----------|-----|------|
| `access_type` | `"offline"` | Refresh token을 발급받음. 없으면 access token만 받아서 1시간 후 만료 |
| `prompt` | `"consent"` | 항상 동의 화면을 표시하여 새로운 refresh token을 보장. 이전 token이 취소되어도 새로 발급 |

### 배운 점
- **Decorator 패턴**: `_retry_on_auth_error`는 모든 쓰기 함수에 동일한 에러 처리를 적용. 코드 중복 제거
- **OAuth access_type="offline"**: 사용자가 앱을 닫아도 백그라운드에서 토큰 갱신 가능
- **prompt="consent"**: 기존 refresh token이 있어도 새로 발급. 토큰이 오래되어 실효된 경우에 유용
- **테스트 vs 프로덕션**: Google Cloud의 "테스트" 모드는 개발 편의를 위한 것이지만, refresh token 7일 제한이 있음
