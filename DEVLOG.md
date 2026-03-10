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
