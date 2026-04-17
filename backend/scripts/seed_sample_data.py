"""
샘플 데이터 시딩 스크립트

한국 실제 콘텐츠 기반 100개+ 샘플 데이터를 DB에 삽입합니다.
  - 영화 40편 (다양한 장르, 상태)
  - 드라마 시리즈 10개 + 각 시즌 + 에피소드 (약 80개)
  - CP사 이메일 로그 15개
  - 외부 메타 소스 연결
  - AI 처리 결과 (일부 콘텐츠)
  - 이미지, 크레딧

실행:
    cd backend && python3 scripts/seed_sample_data.py
    python3 scripts/seed_sample_data.py --clean  # 기존 데이터 삭제 후 재삽입
"""

import sys
import os
import random
import argparse
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from shared.database import SessionLocal, engine, Base
import api.programming.metadata.models  # noqa — 모든 모델 로드

from api.programming.metadata.models import (
    Content, ContentMetadata, CpEmailLog,
    ContentType, ContentStatus, MetaSource,
    GenreCode, TagCode, ContentGenre, ContentTag,
    PersonMaster, ContentCredit, CreditRole,
    ContentImage, ImageType,
    ExternalMetaSource, ExternalSourceType,
    ContentAIResult, AITaskType,
)

# ─────────────────────────────────────────────
# 원본 데이터 정의
# ─────────────────────────────────────────────

MOVIES = [
    # (title, original_title, year, runtime, country, cp_name, genres, mood_tags, synopsis, tmdb_id, quality)
    ("범죄도시", "The Roundup", 2022, 106, "KR", "에이비오엔터테인먼트",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "마석도 형사가 베트남에서 도망친 악성 범죄 조직을 뒤쫓는 액션 범죄 영화. "
     "실제 2004년 베트남 원정 검거 사건을 바탕으로 제작된 작품으로, 마석도 형사의 압도적인 피지컬과 유머러스한 캐릭터가 인상적이다.",
     985939, 88.5),
    ("헤어질 결심", "Decision to Leave", 2022, 138, "KR", "CJ ENM",
     ["MYS", "ROM"], ["심야감성", "반전있음"],
     "산에서 추락사한 남자의 사건을 수사하는 형사가 용의자인 중국 여인에게 묘한 감정을 느끼게 되는 미스터리 멜로. "
     "박찬욱 감독의 섬세한 연출과 탕웨이, 박해일의 감정 연기가 돋보이는 작품.",
     1016084, 91.2),
    ("오빠생각", "My Annoying Brother", 2016, 109, "KR", "쇼박스",
     ["DRM", "COM"], ["따뜻한", "눈물주의"],
     "시각장애인 유도 선수 두영이 형기 단축을 위해 출소한 가짜 오빠 두식과 함께 살게 되면서 벌어지는 이야기. "
     "조정석과 도경수의 케미가 돋보이는 감동 드라마.",
     399406, 82.0),
    ("극한직업", "Extreme Job", 2019, 111, "KR", "CJ ENM",
     ["COM", "ACT"], ["웃음보장", "액션몰입"],
     "마약반 형사들이 잠복 수사를 위해 치킨집을 인수했다가 뜻밖에 대박이 나면서 벌어지는 코믹 액션. "
     "역대 한국 영화 흥행 2위를 기록한 작품으로 류승룡, 이하늬 등이 출연.",
     614637, 90.5),
    ("기생충", "Parasite", 2019, 132, "KR", "CJ ENM",
     ["DRM", "THR"], ["긴장감", "반전있음", "인간드라마"],
     "전원 백수인 기택 가족이 부유한 박 사장 가족의 집에 하나둘 침투하면서 벌어지는 이야기. "
     "봉준호 감독의 걸작으로 칸 황금종려상, 아카데미 작품상 등 4관왕을 달성한 한국 영화의 역사.",
     496243, 96.0),
    ("부산행", "Train to Busan", 2016, 118, "KR", "넥스트엔터테인먼트월드",
     ["HOR", "ACT"], ["긴장감", "눈물주의"],
     "부산행 KTX에서 좀비 바이러스가 퍼지면서 생존을 위한 사투를 벌이는 사람들의 이야기. "
     "연상호 감독의 첫 실사 영화로 전 세계적으로 큰 인기를 얻었다.",
     396535, 87.0),
    ("신과함께-죄와벌", "Along with the Gods: The Two Worlds", 2017, 139, "KR", "덱스터스튜디오",
     ["FAN", "DRM"], ["따뜻한", "눈물주의"],
     "사후세계에서 7번의 재판을 받게 된 소방관이 세 명의 저승사자와 함께 각 지옥의 재판을 통과하는 이야기.",
     487291, 84.5),
    ("건축학개론", "Architecture 101", 2012, 118, "KR", "롯데엔터테인먼트",
     ["ROM", "DRM"], ["따뜻한", "사랑이야기"],
     "건축학과 1학년 때 사랑했던 여자가 15년 만에 건축 의뢰인으로 나타나면서 시작되는 첫사랑 이야기.",
     93402, 83.0),
    ("택시운전사", "A Taxi Driver", 2017, 137, "KR", "쇼박스",
     ["HIS", "DRM"], ["인간드라마", "실화기반"],
     "1980년 5·18 광주민주화운동 당시 독일 기자를 태우고 광주로 향한 서울 택시운전사의 실화를 바탕으로 한 작품.",
     429455, 88.0),
    ("왕의 남자", "The King and the Clown", 2005, 119, "KR", "시네마서비스",
     ["HIS", "DRM"], ["청춘", "인간드라마"],
     "조선시대 연산군 앞에서 공연을 하게 된 광대 패의 이야기. 역대 한국 영화 관객 수 기록을 갈아치운 작품.",
     23518, 85.0),
    ("써니", "Sunny", 2011, 124, "KR", "CJ ENM",
     ["COM", "DRM"], ["따뜻한", "웃음보장"],
     "중년이 된 나미가 우연히 재회한 옛 친구 춘화가 시한부임을 알게 되자 함께했던 7인조 '써니' 멤버들을 다시 찾아 나서는 이야기.",
     74293, 86.0),
    ("도둑들", "The Thieves", 2012, 135, "KR", "쇼박스",
     ["CRM", "ACT"], ["긴장감", "반전있음"],
     "한국과 홍콩의 도둑들이 마카오에서 다이아몬드를 훔치기 위해 뭉치는 케이퍼 무비.",
     103070, 83.5),
    ("암살", "Assassination", 2015, 139, "KR", "쇼박스",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "1930년대 일제강점기 시대, 대한민국 임시정부의 특무대장이 친일파를 암살하기 위해 특수 작전팀을 꾸리는 이야기.",
     330770, 87.5),
    ("나의 사랑 나의 신부", "My Love, My Bride", 2014, 108, "KR", "CGV아트하우스",
     ["ROM", "COM"], ["웃음보장", "사랑이야기"],
     "결혼 2년차 부부의 현실적이고 유쾌한 일상을 담은 로맨틱 코미디.",
     303791, 75.0),
    ("살인의 추억", "Memories of Murder", 2003, 132, "KR", "CJ ENM",
     ["CRM", "THR"], ["긴장감", "실화기반"],
     "1986년 경기도 화성에서 발생한 한국 최초 연쇄 살인 사건을 수사하는 형사들의 이야기. "
     "봉준호 감독의 초기 걸작.",
     8588, 93.0),
    ("올드보이", "Oldboy", 2003, 120, "KR", "쇼이스트",
     ["THR", "MYS"], ["긴장감", "반전있음"],
     "이유도 모른 채 15년간 감금되었다 풀려난 남자가 자신을 가둔 자를 추적하는 이야기. "
     "박찬욱 감독의 복수 3부작 중 두 번째 작품.",
     5786, 92.0),
    ("밀양", "Secret Sunshine", 2007, 142, "KR", "시네마서비스",
     ["DRM"], ["인간드라마", "눈물주의"],
     "남편이 죽고 아들과 함께 밀양으로 내려온 신애가 겪는 상실과 치유의 이야기.",
     32694, 86.0),
    ("오아시스", "Oasis", 2002, 132, "KR", "유니코리아",
     ["DRM", "ROM"], ["인간드라마", "사랑이야기"],
     "전과자인 종두와 뇌성마비 공주의 순수한 사랑 이야기. 이창동 감독의 역작.",
     16869, 89.0),
    ("아저씨", "The Man from Nowhere", 2010, 119, "KR", "씨제이이엔엠",
     ["ACT", "THR"], ["액션몰입", "긴장감"],
     "이웃 소녀를 구하기 위해 마약 조직에 맞서는 전직 특수요원의 이야기.",
     58587, 86.5),
    ("국제시장", "Ode to My Father", 2014, 126, "KR", "CJ ENM",
     ["DRM", "HIS"], ["눈물주의", "실화기반", "인간드라마"],
     "6·25전쟁과 산업화 시대를 살아온 한 남자의 일생을 통해 그 시대 아버지들의 이야기를 담은 작품.",
     266396, 85.0),
    ("마녀", "The Witch: Part 1. The Subversion", 2018, 125, "KR", "넥스트엔터테인먼트월드",
     ["ACT", "THR"], ["긴장감", "반전있음"],
     "기억을 잃은 채 한 농가에서 자란 소녀 자윤이 TV 오디션 프로그램에 나갔다가 정체불명의 사람들에게 쫓기는 이야기.",
     503977, 82.0),
    ("사냥의 시간", "Time to Hunt", 2020, 135, "KR", "리틀빅픽처스",
     ["THR", "ACT"], ["긴장감", "액션몰입"],
     "근미래 디스토피아 한국을 배경으로 한 탈출 스릴러. 출소한 준석이 친구들과 함께 불법 도박장을 털기로 계획하지만 예상치 못한 킬러에게 쫓기게 된다.",
     713648, 77.5),
    ("잠", "Sleep", 2023, 95, "KR", "루이스픽쳐스",
     ["HOR", "MYS"], ["긴장감", "반전있음"],
     "결혼 후 신혼의 행복을 즐기던 부부에게 남편의 수면 중 이상 행동이 나타나면서 벌어지는 공포.",
     1120894, 80.0),
    ("밀수", "Smugglers", 2023, 129, "KR", "외유내강",
     ["ACT", "CRM"], ["액션몰입", "반전있음"],
     "1970년대를 배경으로 해녀들이 밀수에 가담하면서 벌어지는 이야기. 류승완 감독의 신작.",
     1084191, 83.0),
    ("콘크리트 유토피아", "Concrete Utopia", 2023, 130, "KR", "클라이맥스스튜디오",
     ["DRM", "THR"], ["긴장감", "인간드라마"],
     "대규모 지진으로 서울이 폐허가 된 상황에서 유일하게 살아남은 아파트 주민들의 이야기.",
     1006191, 81.5),
    ("비상선언", "Emergency Declaration", 2022, 140, "KR", "쇼박스",
     ["THR", "ACT"], ["긴장감", "눈물주의"],
     "비행기에서 바이오 테러가 발생하고 착륙이 불가능한 상황에서 벌어지는 긴박한 이야기.",
     882359, 74.0),
    ("한산: 용의 출현", "Hansan: Rising Dragon", 2022, 129, "KR", "빅스톤픽쳐스",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "임진왜란 3대 대첩 중 하나인 한산도 대첩을 배경으로, 이순신 장군이 학익진을 펼쳐 왜군을 격파하는 이야기.",
     837039, 85.5),
    ("외계+인 1부", "Alienoid", 2022, 142, "KR", "CJ ENM",
     ["SCI", "ACT"], ["액션몰입", "반전있음"],
     "고려 시대와 현재를 넘나들며 외계인과 신선, 도사가 뒤엉키는 SF 판타지 액션.",
     782498, 73.5),
    ("킹메이커", "Kingmaker", 2022, 125, "KR", "쇼박스",
     ["DRM", "HIS"], ["인간드라마", "실화기반"],
     "1970년대 정치인과 그를 당선시키기 위한 전략가의 이야기를 담은 정치 드라마.",
     838930, 80.0),
    ("특송", "Special Delivery", 2022, 109, "KR", "오퍼스픽쳐스",
     ["ACT", "THR"], ["액션몰입", "긴장감"],
     "무적의 드라이버 은하가 위험한 화물을 운반하면서 벌어지는 카체이싱 액션.",
     840430, 79.0),
    ("헌트", "Hunt", 2022, 125, "KR", "메가박스중앙플러스엠",
     ["ACT", "THR"], ["긴장감", "반전있음"],
     "1980년대 안기부를 배경으로 내부 스파이를 찾는 두 안기부 요원의 이야기. 이정재 감독 데뷔작.",
     829330, 82.5),
    ("공조 2: 인터내셔날", "Confidential Assignment 2: International", 2022, 121, "KR", "CJ ENM",
     ["ACT", "COM"], ["액션몰입", "웃음보장"],
     "남북 형사 강진태와 임철령이 다시 뭉쳐 미국 FBI와 함께 국제 범죄 조직에 맞서는 이야기.",
     829429, 78.0),
    ("유령", "The Ghost", 2022, 134, "KR", "플러스엠엔터테인먼트",
     ["ACT", "THR"], ["긴장감", "실화기반"],
     "일제강점기 경성을 배경으로 독립운동 밀정을 쫓는 친일파 형사와 독립운동가들의 이야기.",
     838226, 76.5),
    ("육사오", "6/45", 2022, 101, "KR", "넥스트엔터테인먼트월드",
     ["COM"], ["웃음보장"],
     "남북한 병사들이 복권 당첨금 10억 원을 서로 차지하려다 벌어지는 코미디.",
     876969, 77.0),
    ("공조", "Confidential Assignment", 2017, 118, "KR", "CJ ENM",
     ["ACT", "COM"], ["액션몰입", "웃음보장"],
     "탈북한 북한 형사와 한국 형사가 공조 수사를 펼치는 액션 코미디.",
     430826, 82.0),
    ("서울의 봄", "12.12: The Day", 2023, 141, "KR", "플러스엠엔터테인먼트",
     ["HIS", "DRM"], ["긴장감", "실화기반", "인간드라마"],
     "1979년 12월 12일, 군사 반란을 일으킨 전두광과 이를 막으려는 이태신의 9시간을 그린 작품.",
     1165227, 92.5),
    ("30일", "30 Days", 2023, 115, "KR", "CJ ENM",
     ["ROM", "COM"], ["웃음보장", "사랑이야기"],
     "이혼 소송 중인 부부가 사고로 기억을 잃어 서로를 처음 만난 사이로 착각하게 되면서 벌어지는 로맨틱 코미디.",
     1138194, 76.0),
    ("소울메이트", "Soulmate", 2023, 124, "KR", "NEW",
     ["DRM", "ROM"], ["따뜻한", "사랑이야기", "청춘"],
     "제주도에서 만난 두 소녀가 20년을 넘는 우정을 이어가는 과정을 담은 감동적인 드라마.",
     1139433, 84.0),
    ("드림", "Dream", 2023, 120, "KR", "롯데엔터테인먼트",
     ["COM", "SPT"], ["웃음보장", "따뜻한"],
     "노숙인으로 구성된 대한민국 홈리스 월드컵 대표팀이 도전하는 이야기.",
     993440, 73.0),
    # ── 추가 영화 61편 ─────────────────────────────────────
    ("괴물", "The Host", 2006, 119, "KR", "쇼박스",
     ["HOR", "DRM"], ["긴장감", "인간드라마"],
     "한강에 나타난 괴물에게 딸을 빼앗긴 가족이 딸을 구하기 위해 싸우는 이야기. 봉준호 감독의 괴수 영화.",
     8014, 88.0),
    ("좋은 놈, 나쁜 놈, 이상한 놈", "The Good, the Bad, the Weird", 2008, 130, "KR", "씨제이이엔엠",
     ["ACT", "WES"], ["액션몰입", "웃음보장"],
     "1930년대 만주를 배경으로 세 남자가 보물 지도를 차지하기 위해 벌이는 추격전.",
     18785, 84.0),
    ("베테랑", "Veteran", 2015, 123, "KR", "씨제이이엔엠",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "부패한 재벌 3세와 맞서는 광역수사대 형사 서도철의 이야기. 류승완 감독의 흥행작.",
     312174, 87.5),
    ("명량", "The Admiral: Roaring Currents", 2014, 126, "KR", "빅스톤픽쳐스",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "1597년 명량해전에서 13척의 배로 330척의 왜군을 물리친 이순신 장군의 이야기.",
     247399, 85.0),
    ("변호인", "The Attorney", 2013, 127, "KR", "넥스트엔터테인먼트월드",
     ["DRM", "HIS"], ["인간드라마", "실화기반"],
     "1980년대 부림 사건을 배경으로 세금 전문 변호사가 국가 권력에 맞서는 이야기.",
     211778, 89.5),
    ("7번방의 선물", "Miracle in Cell No.7", 2013, 127, "KR", "NEW",
     ["DRM", "COM"], ["눈물주의", "따뜻한"],
     "지적 장애를 가진 아버지가 억울하게 사형수가 되면서 어린 딸과 교도소 동료들이 함께 싸우는 감동 이야기.",
     163966, 84.0),
    ("수상한 그녀", "Miss Granny", 2014, 124, "KR", "CJ ENM",
     ["COM", "DRM"], ["웃음보장", "따뜻한"],
     "74세 할머니가 갑자기 20대 처녀로 변신하면서 벌어지는 유쾌한 이야기.",
     259695, 82.0),
    ("완벽한 타인", "Intimate Strangers", 2018, 101, "KR", "롯데엔터테인먼트",
     ["COM", "DRM"], ["반전있음", "인간드라마"],
     "오랜 친구들이 모인 저녁 식사에서 스마트폰 속 모든 비밀을 공개하자는 게임을 시작하며 벌어지는 이야기.",
     550257, 82.5),
    ("남산의 부장들", "The Man Standing Next", 2020, 114, "KR", "쇼박스",
     ["HIS", "THR"], ["긴장감", "실화기반"],
     "1979년 10·26 사건 직전 40일을 중앙정보부장의 시선으로 재구성한 정치 스릴러.",
     717378, 86.0),
    ("다만 악에서 구하소서", "The Gangster, the Cop, the Devil", 2020, 109, "KR", "씨제이이엔엠",
     ["ACT", "THR"], ["액션몰입", "긴장감"],
     "연쇄 살인마에게 습격당한 조폭 보스가 형사와 손잡고 범인을 추적하는 이야기.",
     665119, 83.5),
    ("모가디슈", "Escape from Mogadishu", 2021, 121, "KR", "롯데엔터테인먼트",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "1991년 소말리아 내전 당시 남북한 외교관들이 함께 탈출하는 실화를 바탕으로 한 작품.",
     836228, 88.5),
    ("자산어보", "The Book of Fish", 2021, 126, "KR", "메가박스중앙플러스엠",
     ["HIS", "DRM"], ["인간드라마", "따뜻한"],
     "조선 후기 유배지 흑산도에서 정약전과 어부 청년 창대의 특별한 우정을 그린 작품. 이준익 감독.",
     830870, 85.5),
    ("1987", "1987: When the Day Comes", 2017, 129, "KR", "CJ ENM",
     ["HIS", "DRM"], ["실화기반", "인간드라마"],
     "1987년 6월 민주항쟁의 도화선이 된 박종철 고문치사 사건과 이한열 최루탄 피격 사건을 다룬 작품.",
     464327, 90.0),
    ("내부자들", "Inside Men", 2015, 130, "KR", "쇼박스",
     ["CRM", "THR"], ["긴장감", "인간드라마"],
     "정치인, 언론인, 재벌 간의 유착 비리를 폭로하는 스릴러. 우민호 감독, 이병헌·조승우 주연.",
     346570, 86.5),
    ("파묘", "Exhuma", 2024, 134, "KR", "쇼박스",
     ["HOR", "MYS"], ["긴장감", "반전있음"],
     "거액의 의뢰를 받은 무당과 장의사가 묫자리를 이장하면서 벌어지는 오컬트 공포.",
     1209290, 84.5),
    ("서울대작전", "Seoul Vibe", 2022, 140, "KR", "넷플릭스",
     ["ACT", "CRM"], ["액션몰입", "웃음보장"],
     "1988 서울 올림픽을 배경으로 강남 정치인의 비자금을 훔치기 위해 뭉친 드라이버 크루의 이야기.",
     940551, 76.0),
    ("엑시트", "Exit", 2019, 103, "KR", "CJ ENM",
     ["ACT", "COM"], ["웃음보장", "액션몰입"],
     "취업 준비생이 결혼식 피로연장에서 발생한 독가스 테러로 가족을 구하기 위해 고군분투하는 이야기.",
     608985, 80.5),
    ("증인", "Innocent Witness", 2019, 129, "KR", "롯데엔터테인먼트",
     ["DRM", "CRM"], ["인간드라마", "따뜻한"],
     "살인 사건의 유일한 목격자인 자폐 소녀와 변호사 사이의 교감을 그린 법정 드라마.",
     596833, 85.0),
    ("달콤한 인생", "A Bittersweet Life", 2005, 120, "KR", "씨제이이엔엠",
     ["ACT", "CRM"], ["긴장감", "액션몰입"],
     "보스의 명령을 어기면서 조직에 배신당한 킬러의 복수를 그린 느와르 액션.",
     20372, 87.0),
    ("장화, 홍련", "A Tale of Two Sisters", 2003, 115, "KR", "봄픽처스",
     ["HOR", "MYS"], ["긴장감", "반전있음"],
     "정신병원을 퇴원한 두 자매가 새어머니와 함께 살면서 벌어지는 심리 공포 스릴러.",
     10532, 86.0),
    ("친구", "Friend", 2001, 113, "KR", "씨제이이엔엠",
     ["DRM", "CRM"], ["인간드라마", "눈물주의"],
     "1970~80년대 부산을 배경으로 어릴 때부터 함께한 네 친구의 우정과 엇갈린 삶을 그린 작품.",
     13462, 84.5),
    ("엽기적인 그녀", "My Sassy Girl", 2001, 137, "KR", "씨네2000",
     ["ROM", "COM"], ["웃음보장", "사랑이야기"],
     "지하철에서 만난 괴짜 여자와 평범한 남자의 사랑 이야기. 한류 열풍의 시작을 알린 대표작.",
     14535, 85.0),
    ("클래식", "The Classic", 2003, 127, "KR", "싸이더스",
     ["ROM", "DRM"], ["사랑이야기", "따뜻한"],
     "30년 전 어머니의 첫사랑 편지를 발견한 딸이 자신도 같은 사랑에 빠지는 두 세대에 걸친 로맨스.",
     27018, 82.0),
    ("공공의 적", "Public Enemy", 2002, 138, "KR", "씨제이이엔엠",
     ["CRM", "ACT"], ["긴장감", "액션몰입"],
     "부동산 사기꾼을 쫓는 무뚝뚝한 형사 강철중의 이야기. 설경구의 대표작.",
     30148, 83.5),
    ("봄날은 간다", "One Fine Spring Day", 2001, 106, "KR", "씨네2000",
     ["ROM", "DRM"], ["따뜻한", "사랑이야기"],
     "라디오 음향감독과 방송작가의 계절을 따라 피어나고 지는 사랑 이야기.",
     27052, 80.0),
    ("사도", "The Throne", 2015, 125, "KR", "쇼박스",
     ["HIS", "DRM"], ["인간드라마", "눈물주의"],
     "영조가 뒤주에 가두어 죽인 사도세자의 비극적인 이야기. 이준익 감독.",
     327387, 84.0),
    ("군함도", "The Battleship Island", 2017, 132, "KR", "CJ ENM",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "일제강점기 강제 징용으로 군함도에 끌려간 조선인들의 탈출 작전을 그린 작품.",
     436968, 77.5),
    ("남한산성", "The Fortress", 2017, 139, "KR", "CJ ENM",
     ["HIS", "DRM"], ["인간드라마", "실화기반"],
     "병자호란 당시 남한산성에 고립된 인조와 신하들의 47일간의 이야기.",
     459320, 83.5),
    ("안시성", "The Great Battle", 2018, 136, "KR", "빅스톤픽쳐스",
     ["ACT", "HIS"], ["액션몰입", "실화기반"],
     "645년 당나라 20만 대군의 침략에 맞서 88일간 안시성을 지켜낸 양만춘 장군의 이야기.",
     568620, 82.5),
    ("PMC: 더 벙커", "PMC: The Bunker", 2018, 110, "KR", "NEW",
     ["ACT", "SCI"], ["액션몰입", "긴장감"],
     "비밀 작전으로 지하 벙커에 갇힌 용병 팀의 탈출 작전을 그린 밀리터리 액션.",
     576006, 73.0),
    ("생일", "Birthday", 2019, 120, "KR", "NEW",
     ["DRM"], ["눈물주의", "인간드라마"],
     "세월호 참사로 아들을 잃은 부부가 아들의 친구들과 함께하는 생일 파티를 준비하는 이야기.",
     605488, 84.5),
    ("82년생 김지영", "Kim Ji-young: Born 1982", 2019, 118, "KR", "롯데엔터테인먼트",
     ["DRM"], ["인간드라마", "눈물주의"],
     "1982년생 평범한 여성 김지영의 삶을 통해 한국 사회의 여성 차별을 조명한 작품.",
     644736, 81.0),
    ("시동", "Start-Up", 2019, 122, "KR", "롯데엔터테인먼트",
     ["DRM", "COM"], ["따뜻한", "인간드라마"],
     "학교를 그만두고 자신만의 꿈을 찾아가는 청년과 열혈 요리사의 이야기.",
     745258, 76.5),
    ("반도", "Peninsula", 2020, 116, "KR", "넥스트엔터테인먼트월드",
     ["ACT", "HOR"], ["액션몰입", "긴장감"],
     "부산행 4년 후, 좀비로 폐허가 된 한반도에서 잔류한 생존자들의 이야기.",
     672845, 73.5),
    ("#살아있다", "#Alive", 2020, 99, "KR", "롯데엔터테인먼트",
     ["HOR", "THR"], ["긴장감", "액션몰입"],
     "갑자기 발생한 좀비 사태에 혼자 아파트에 고립된 청년이 살아남기 위해 고군분투하는 이야기.",
     718789, 74.5),
    ("발신제한", "Hard Hit", 2021, 95, "KR", "쇼박스",
     ["THR", "ACT"], ["긴장감", "액션몰입"],
     "폭탄이 설치된 차에 갇힌 은행 지점장이 자리를 벗어날 수 없는 긴박한 상황.",
     833365, 78.5),
    ("보이스", "Voice of Silence", 2021, 105, "KR", "플러스엠엔터테인먼트",
     ["CRM", "THR"], ["긴장감", "반전있음"],
     "범죄 조직의 뒤처리 담당자가 뜻하지 않게 어린 소녀를 보호하게 되면서 벌어지는 이야기.",
     842967, 80.0),
    ("킬링 로맨스", "Killing Romance", 2023, 122, "KR", "씨제이이엔엠",
     ["COM", "CRM"], ["웃음보장", "반전있음"],
     "억만장자 남편에게 살인을 의뢰받은 여배우의 기상천외한 탈출기.",
     1094556, 75.5),
    ("시민덕희", "Citizen of a Kind", 2023, 115, "KR", "CJ ENM",
     ["CRM", "DRM"], ["인간드라마", "실화기반"],
     "보이스피싱 조직에 속아 전 재산을 잃은 평범한 여성이 직접 범인을 잡기 위해 나서는 이야기.",
     1148271, 82.5),
    ("탈주", "Escape", 2024, 98, "KR", "메가박스중앙플러스엠",
     ["ACT", "THR"], ["액션몰입", "긴장감"],
     "탈영한 북한 군인과 이를 뒤쫓는 보위부 장교의 추격전을 그린 스릴러.",
     1371335, 79.0),
    ("파일럿", "Pilot", 2024, 115, "KR", "CJ ENM",
     ["COM"], ["웃음보장"],
     "항공사에서 해고된 기장이 승무원으로 위장 취업해 벌어지는 코미디.",
     1358628, 74.5),
    ("범죄도시3", "The Roundup: No Way Out", 2023, 105, "KR", "에이비오엔터테인먼트",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "마석도 형사가 일본 야쿠자와 손잡은 신종 마약 조직을 소탕하는 이야기.",
     1074413, 85.5),
    ("범죄도시4", "The Roundup: Punishment", 2024, 109, "KR", "에이비오엔터테인먼트",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "마석도 형사가 온라인 도박 조직과 테러범들을 상대로 활약하는 이야기.",
     1171032, 84.0),
    ("베테랑2", "Veteran 2", 2024, 117, "KR", "씨제이이엔엠",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "서도철 형사팀이 이번엔 디지털 성범죄 조직과 맞서는 이야기.",
     1178816, 82.0),
    ("히말라야", "The Himalayas", 2015, 125, "KR", "CJ ENM",
     ["DRM", "SPT"], ["인간드라마", "눈물주의"],
     "엄홍길 대장이 히말라야에서 실종된 후배 대원의 시신을 찾아 나서는 실화 이야기.",
     348888, 83.0),
    ("덕혜옹주", "The Last Princess", 2016, 127, "KR", "롯데엔터테인먼트",
     ["HIS", "DRM"], ["실화기반", "눈물주의"],
     "조선의 마지막 공주 덕혜옹주의 비극적인 일생을 다룬 역사 드라마.",
     427440, 78.0),
    ("귀향", "Spirits' Homecoming", 2016, 127, "KR", "리틀빅픽처스",
     ["HIS", "DRM"], ["눈물주의", "실화기반"],
     "일제강점기 강제로 위안부로 끌려간 소녀들의 이야기.",
     399367, 82.0),
    ("럭키", "Lucky", 2016, 106, "KR", "넥스트엔터테인먼트월드",
     ["ACT", "COM"], ["웃음보장", "반전있음"],
     "우연히 청부 살인업자와 얼굴이 바뀐 평범한 남자가 암살자로 오인받으면서 벌어지는 이야기.",
     430756, 78.5),
    ("성난황소", "Rampant", 2018, 122, "KR", "넥스트엔터테인먼트월드",
     ["HIS", "ACT"], ["액션몰입", "긴장감"],
     "조선 시대를 배경으로 외세와 역병에 맞서는 왕세자의 이야기.",
     568620, 72.0),
    ("악인전", "The Gangster, the Cop, the Devil", 2019, 110, "KR", "씨제이이엔엠",
     ["ACT", "CRM"], ["액션몰입", "긴장감"],
     "연쇄 살인범에게 습격당한 조폭 대부가 형사와 협력해 범인을 쫓는 이야기.",
     665119, 84.0),
    ("반창꼬", "Bandage", 2012, 116, "KR", "롯데엔터테인먼트",
     ["ROM", "COM"], ["사랑이야기", "웃음보장"],
     "사랑받는 법을 모르는 상처받은 두 남녀가 티격태격하며 사랑에 빠지는 로맨틱 코미디.",
     118452, 76.0),
    ("사랑하기 때문에", "Because I Love You", 2017, 119, "KR", "쇼박스",
     ["ROM", "DRM"], ["사랑이야기", "따뜻한"],
     "음악을 통해 연결된 세 사람의 엇갈린 사랑과 인연을 그린 로맨스 드라마.",
     474565, 74.5),
    ("걷기왕", "The Queen of Walking", 2016, 95, "KR", "NEW",
     ["COM", "SPT"], ["웃음보장", "따뜻한"],
     "걸어다니기를 좋아하는 여고생이 경보 선수로 거듭나는 유쾌한 이야기.",
     409965, 72.5),
    ("무뢰한", "The Shameless", 2015, 112, "KR", "씨제이이엔엠",
     ["CRM", "ROM"], ["긴장감", "심야감성"],
     "살인 사건을 조사하던 형사가 용의자의 여자에게 빠져드는 느와르 로맨스.",
     358880, 79.5),
    ("더 테러 라이브", "The Terror Live", 2013, 98, "KR", "쇼박스",
     ["THR", "ACT"], ["긴장감", "반전있음"],
     "라디오 진행자가 생방송 중 폭탄 테러를 예고한 시민과 독단적으로 협상하는 이야기.",
     221444, 84.0),
    ("숨바꼭질", "Hide and Seek", 2013, 107, "KR", "씨제이이엔엠",
     ["HOR", "THR"], ["긴장감", "반전있음"],
     "실종된 형을 찾아 이사 온 아파트에서 괴인을 만나게 되는 공포 스릴러.",
     196940, 76.0),
    ("써니", "Sunny", 2011, 124, "KR", "CJ ENM",  # duplicate – handled by dedup
     ["COM", "DRM"], ["따뜻한", "웃음보장"],
     "80년대 학창시절을 공유한 일곱 친구들의 우정과 재회를 그린 감동 코미디.",
     74293, 86.0),
    ("동주", "Dongju; The Portrait of a Poet", 2016, 110, "KR", "인디스토리",
     ["HIS", "DRM"], ["인간드라마", "실화기반"],
     "일제강점기 젊은 시인 윤동주와 그의 사촌 송몽규의 우정과 독립 운동을 그린 흑백 영화.",
     373584, 87.5),
    ("고산자, 대동여지도", "Jiseul", 2016, 113, "KR", "넥스트엔터테인먼트월드",
     ["HIS", "DRM"], ["인간드라마", "실화기반"],
     "조선 시대 지도학자 김정호가 대동여지도를 완성해 나가는 여정을 그린 작품.",
     415242, 75.5),
    ("마스터", "Master", 2016, 143, "KR", "씨제이이엔엠",
     ["CRM", "ACT"], ["긴장감", "반전있음"],
     "수백만 명을 상대로 다단계 사기를 친 거대 금융그룹과 이를 쫓는 경찰의 이야기.",
     399419, 80.5),
    ("대호", "The Tiger: An Old Hunter's Tale", 2015, 139, "KR", "씨제이이엔엠",
     ["DRM", "HIS"], ["인간드라마", "실화기반"],
     "일제강점기 마지막 호랑이와 늙은 사냥꾼의 마지막 대결을 그린 작품.",
     380355, 81.0),
    ("프리즌", "The Prison", 2017, 125, "KR", "쇼박스",
     ["CRM", "ACT"], ["긴장감", "반전있음"],
     "세상에서 가장 은밀한 범죄 조직이 운영되는 감옥에 위장 잠입한 형사의 이야기.",
     464369, 78.5),
    ("꾼", "The Con Artists", 2015, 114, "KR", "NEW",
     ["CRM", "ACT"], ["반전있음", "긴장감"],
     "최고의 금고털이 전문가들이 뭉쳐 인터폴 수배 중인 전설의 사기꾼을 노리는 케이퍼 무비.",
     368340, 77.0),
    ("소년들", "The Boys", 2023, 110, "KR", "플러스엠엔터테인먼트",
     ["DRM", "CRM"], ["실화기반", "인간드라마"],
     "1999년 화성에서 발생한 실제 소년 강도 사건을 재수사하며 진실을 밝혀나가는 형사들의 이야기.",
     1138767, 84.0),
    ("오늘의 웹툰", "Today's Webtoon", 2022, 102, "KR", "스튜디오드래곤",
     ["COM", "DRM"], ["따뜻한", "청춘"],
     "유도 선수 출신 신입 웹툰 편집자가 웹툰 업계에서 성장해 나가는 이야기.",
     1058951, 73.0),
    ("주먹왕 랄프2", "Ralph Breaks the Internet", 2018, 112, "US", "월트디즈니코리아",
     ["ANI", "COM"], ["웃음보장", "따뜻한"],
     "아케이드 게임 캐릭터 랄프와 바넬로피가 인터넷 세계를 탐험하는 애니메이션.",
     404368, 77.0),
    ("스파이더맨: 홈커밍", "Spider-Man: Homecoming", 2017, 133, "US", "소니픽쳐스코리아",
     ["ACT", "SCI"], ["액션몰입", "청춘"],
     "어벤저스 합류 후 일상으로 돌아온 피터 파커가 새로운 악당 벌처에 맞서는 이야기.",
     315635, 83.0),
    ("인터스텔라", "Interstellar", 2014, 169, "US", "워너브라더스코리아",
     ["SCI", "DRM"], ["인간드라마", "반전있음"],
     "인류의 새로운 터전을 찾아 우주로 떠난 탐험대의 이야기. 크리스토퍼 놀란 감독.",
     157336, 92.0),
    ("어벤져스: 엔드게임", "Avengers: Endgame", 2019, 181, "US", "월트디즈니코리아",
     ["ACT", "SCI"], ["액션몰입", "눈물주의"],
     "타노스에게 패배한 어벤져스가 과거로 돌아가 인피니티 스톤을 모아 반전을 꾀하는 이야기.",
     299534, 88.0),
    ("보헤미안 랩소디", "Bohemian Rhapsody", 2018, 134, "UK", "이십세기폭스코리아",
     ["MUS", "HIS"], ["인간드라마", "실화기반"],
     "전설적인 록밴드 퀸과 보컬 프레디 머큐리의 삶과 음악을 그린 전기 영화.",
     424694, 86.5),
]

SERIES = [
    # (title, year, cp_name, genres, synopsis, num_seasons, eps_per_season)
    ("이상한 변호사 우영우", 2022, "에이스토리",
     ["DRM", "COM"],
     "자폐 스펙트럼 장애를 가진 천재 변호사 우영우가 대형 로펌에 취직하면서 겪는 성장 이야기. "
     "박은빈의 열연으로 전 세계적인 인기를 얻었다.",
     1, 16),
    ("오징어 게임", 2021, "넷플릭스",
     ["THR", "DRM"],
     "456명의 참가자들이 생존을 건 데스게임에 참여하는 서바이벌 스릴러. "
     "전 세계 넷플릭스 1위를 기록한 한국 드라마의 아이콘.",
     2, 9),
    ("킹덤", 2019, "넷플릭스",
     ["HOR", "HIS"],
     "조선 시대를 배경으로 왕위를 둘러싼 음모와 기이한 역병에 맞서는 왕세자의 이야기.",
     2, 6),
    ("미스터 션샤인", 2018, "화앤담픽쳐스",
     ["HIS", "ROM"],
     "구한말 격동의 시대, 미국 군인이 된 조선인과 양반가 규수의 사랑 이야기.",
     1, 24),
    ("사랑의 불시착", 2019, "스튜디오드래곤",
     ["ROM", "DRM"],
     "패러글라이딩 사고로 북한에 불시착한 재벌 상속녀와 북한 장교의 로맨스.",
     1, 16),
    ("도깨비", 2016, "화앤담픽쳐스",
     ["FAN", "ROM"],
     "불멸의 삶을 사는 도깨비와 죽음의 사자, 그리고 신부로 태어난 소녀의 이야기.",
     1, 16),
    ("스물다섯 스물하나", 2022, "스튜디오드래곤",
     ["ROM", "DRM"],
     "1998년 외환위기 시대를 배경으로 꿈을 향해 나아가는 두 청춘의 성장과 사랑.",
     1, 16),
    ("나의 해방일지", 2022, "JTBC스튜디오",
     ["DRM"],
     "경기도 산포시에서 서울로 출퇴근하는 염씨 삼남매와 미스터리한 이웃 구씨의 이야기.",
     1, 16),
    ("비밀의 숲", 2017, "화앤담픽쳐스",
     ["CRM", "THR"],
     "감정을 느끼지 못하는 검사와 열혈 형사가 거대한 비리를 파헤치는 법정 스릴러.",
     2, 16),
    ("무빙", 2023, "스튜디오드래곤",
     ["ACT", "FAN"],
     "초능력을 숨긴 채 평범하게 살아가는 부모들과 그 자녀들이 과거의 비밀과 마주하는 이야기.",
     1, 20),
    # ── 추가 시리즈 10개 ───────────────────────────────────
    ("눈물의 여왕", 2024, "스튜디오드래곤",
     ["ROM", "DRM"],
     "재벌가 상속녀와 그녀의 남편이 이혼 위기에서 다시 사랑을 찾아가는 이야기. 김수현·김지원 주연.",
     2, 16),
    ("선재 업고 튀어", 2024, "스튜디오드래곤",
     ["ROM", "FAN"],
     "팬이 타임리프를 통해 스타가 되기 전의 선재를 구하러 과거로 돌아가면서 벌어지는 판타지 로맨스.",
     1, 16),
    ("닥터 슬럼프", 2024, "스튜디오드래곤",
     ["ROM", "COM"],
     "탑 성형외과 의사와 최고 학원 강사 출신 두 사람이 슬럼프 속에서 사랑을 찾는 이야기.",
     1, 16),
    ("마당이 있는 집", 2023, "JTBC스튜디오",
     ["THR", "MYS"],
     "아파트를 탈출해 마당 있는 집에서 살고 싶은 여자와 집주인이 서로의 비밀을 알게 되는 미스터리 스릴러.",
     1, 12),
    ("더 글로리", 2022, "넷플릭스",
     ["THR", "DRM"],
     "학교 폭력 피해자 문동은이 가해자들에게 치밀하게 복수하는 이야기. 송혜교 주연.",
     2, 8),
    ("지금 거신 전화는", 2023, "스튜디오드래곤",
     ["ROM", "FAN"],
     "2024년의 형사와 1999년의 여자가 우연히 전화로 연결되어 서로의 운명을 바꾸는 이야기.",
     1, 16),
    ("낮과 밤이 다른 그녀", 2023, "NEW",
     ["ROM", "FAN"],
     "낮에는 평범한 회사원, 밤에는 완전히 다른 성격이 되는 여자의 로맨틱 판타지 코미디.",
     1, 16),
    ("내 남편과 결혼해줘", 2024, "스튜디오드래곤",
     ["ROM", "FAN"],
     "남편과 친구에게 배신당해 죽은 여자가 10년 전으로 돌아가 복수하는 타임리프 로맨스.",
     1, 16),
    ("별들에게 물어봐", 2023, "JTBC스튜디오",
     ["ROM", "DRM"],
     "제주도를 배경으로 스타와 평범한 여자의 로맨스. 이민호·한효주 주연.",
     1, 16),
    ("구미호뎐 1938", 2023, "스튜디오드래곤",
     ["FAN", "ROM"],
     "1938년 경성 시대를 배경으로 한 구미호 이랑의 이야기. 구미호뎐 스핀오프.",
     1, 12),
]

CP_COMPANIES = [
    ("에이비오엔터테인먼트", "supply@abo-ent.co.kr"),
    ("CJ ENM", "contents@cjenm.com"),
    ("쇼박스", "content@showbox.co.kr"),
    ("넥스트엔터테인먼트월드", "meta@new.co.kr"),
    ("스튜디오드래곤", "vod@studio-dragon.com"),
    ("JTBC스튜디오", "contents@jtbcstudios.com"),
    ("화앤담픽쳐스", "supply@hwa-dam.co.kr"),
    ("에이스토리", "vod@astory.co.kr"),
    ("롯데엔터테인먼트", "content@lotte-ent.co.kr"),
    ("외유내강", "meta@oynk.co.kr"),
]

DIRECTORS = [
    ("봉준호", "Bong Joon-ho", 1969, "KR", 21879),
    ("박찬욱", "Park Chan-wook", 1963, "KR", 10099),
    ("이창동", "Lee Chang-dong", 1954, "KR", 40472),
    ("류승완", "Ryoo Seung-wan", 1973, "KR", 51379),
    ("연상호", "Yeon Sang-ho", 1978, "KR", 1178162),
    ("최동훈", "Choi Dong-hun", 1971, "KR", 57328),
    ("김성수", "Kim Sung-su", 1976, "KR", 184496),
    ("이정재", "Lee Jung-jae", 1972, "KR", 1136406),
    ("장재현", "Jang Jae-hyun", 1980, "KR", 1381025),
    ("황동혁", "Hwang Dong-hyuk", 1971, "KR", 2266649),
]

ACTORS = [
    ("마동석", "Don Lee", 1971, "KR", 1506980),
    ("탕웨이", "Tang Wei", 1979, "CN", 23181),
    ("박해일", "Park Hae-il", 1977, "KR", 1017656),
    ("조정석", "Jo Jung-suk", 1980, "KR", 1379580),
    ("송강호", "Song Kang-ho", 1967, "KR", 14292),
    ("최우식", "Choi Woo-shik", 1990, "KR", 1596804),
    ("박소담", "Park So-dam", 1991, "KR", 1734839),
    ("이병헌", "Lee Byung-hun", 1970, "KR", 43941),
    ("전지현", "Jun Ji-hyun", 1981, "KR", 216893),
    ("류승룡", "Ryu Seung-ryong", 1970, "KR", 1018560),
    ("이하늬", "Lee Ha-nee", 1985, "KR", 1303580),
    ("박은빈", "Park Eun-bin", 1992, "KR", 2259538),
    ("이준기", "Lee Joon-gi", 1982, "KR", 43457),
    ("김혜수", "Kim Hye-soo", 1970, "KR", 155441),
    ("엄정화", "Uhm Jung-hwa", 1969, "KR", 1091048),
    ("현빈", "Hyun Bin", 1982, "KR", 1023883),
    ("손예진", "Son Ye-jin", 1982, "KR", 1023905),
    ("공유", "Gong Yoo", 1979, "KR", 1029950),
    ("이성경", "Lee Sung-kyung", 1990, "KR", 1726903),
    ("김고은", "Kim Go-eun", 1991, "KR", 1440025),
    ("황정민", "Hwang Jung-min", 1970, "KR", 85576),
    ("하정우", "Ha Jung-woo", 1978, "KR", 152822),
    ("이정재", "Lee Jung-jae", 1972, "KR", 56724),
    ("공효진", "Gong Hyo-jin", 1980, "KR", 1025340),
    ("전도연", "Jeon Do-yeon", 1973, "KR", 85427),
]

TMDB_POSTER_BASE = "https://image.tmdb.org/t/p/w500"
TMDB_POSTER_IDS = {
    "기생충": "/7IiTTgloJzvGI1TAYymCfbfl3vT.jpg",
    "부산행": "/hABCyC8sFVEEMkWDkVoZNFRGAWx.jpg",
    "헤어질 결심": "/lhFbTXV1WqLHcE8jbR6ZHtlxNAV.jpg",
    "범죄도시": "/e6VnXsP1mT4pGBaYyEVjNJYmLDI.jpg",
    "오징어 게임": "/dDlEmu3EZ0Pgg93K2SVNLCjCSvE.jpg",
    "이상한 변호사 우영우": "/8Ovm3mz8BgclsOGQMeYtrxMbJGg.jpg",
}


def random_date(start_days_ago: int, end_days_ago: int) -> datetime:
    delta = random.randint(end_days_ago, start_days_ago)
    return datetime.utcnow() - timedelta(days=delta)


def pick_status(quality: float) -> ContentStatus:
    if quality >= 90:
        return ContentStatus.approved
    elif quality >= 70:
        return random.choice([ContentStatus.review, ContentStatus.approved])
    elif quality >= 50:
        return random.choice([ContentStatus.review, ContentStatus.waiting])
    else:
        return random.choice([ContentStatus.waiting, ContentStatus.rejected])


def get_genre_id(db, code: str) -> int | None:
    g = db.query(GenreCode).filter(GenreCode.code == code).first()
    return g.id if g else None


def get_tag_ids(db, names: list[str]) -> list[int]:
    tags = db.query(TagCode).filter(TagCode.name.in_(names)).all()
    return [t.id for t in tags]


def seed(db):
    print("=== 샘플 데이터 시딩 시작 ===\n")

    # ── 1. 인물 마스터 ───────────────────────────────────
    print("1. 인물 마스터 삽입...")
    director_objs = {}
    for name_ko, name_en, birth_year, nationality, tmdb_id in DIRECTORS:
        p = PersonMaster(
            name_ko=name_ko, name_en=name_en,
            birth_year=birth_year, nationality=nationality,
            tmdb_person_id=tmdb_id,
        )
        db.add(p)
        db.flush()
        director_objs[name_ko] = p

    actor_objs = {}
    for name_ko, name_en, birth_year, nationality, tmdb_id in ACTORS:
        p = PersonMaster(
            name_ko=name_ko, name_en=name_en,
            birth_year=birth_year, nationality=nationality,
            tmdb_person_id=tmdb_id,
        )
        db.add(p)
        db.flush()
        actor_objs[name_ko] = p

    db.commit()
    print(f"   감독 {len(director_objs)}명, 배우 {len(actor_objs)}명 삽입 완료")

    # ── 2. CP 이메일 로그 ────────────────────────────────
    print("2. CP 이메일 로그 삽입...")
    email_objs = []
    for i, (cp_name, email) in enumerate(CP_COMPANIES):
        log = CpEmailLog(
            message_id=f"<{i+1}@{email.split('@')[1]}>",
            subject=f"[{cp_name}] VOD 콘텐츠 메타데이터 제공 - {i+1}차",
            sender=f"content-team@{email.split('@')[1]}",
            cp_name=cp_name,
            received_at=random_date(30, 1),
            extracted_titles=[f"샘플콘텐츠{i+1}", f"작품{i+1}"],
            extracted_year=random.choice([2021, 2022, 2023]),
            extracted_quantity=random.randint(2, 8),
            raw_body=f"{cp_name}에서 제공하는 VOD 콘텐츠 목록입니다.\n총 {random.randint(2,8)}편 첨부.",
            extraction_confidence=round(random.uniform(0.75, 0.97), 2),
            processed=True,
        )
        db.add(log)
        db.flush()
        email_objs.append(log)
    db.commit()
    print(f"   이메일 로그 {len(email_objs)}개 삽입 완료")

    # ── 3. 영화 콘텐츠 ───────────────────────────────────
    print("3. 영화 콘텐츠 삽입...")
    movie_objs = []

    # 중복 제거
    seen_titles = set()
    unique_movies = []
    for m in MOVIES:
        if m[0] not in seen_titles:
            seen_titles.add(m[0])
            unique_movies.append(m)

    for idx, (title, orig_title, year, runtime, country, cp_name,
               genre_codes, mood_tags, synopsis, tmdb_id, quality) in enumerate(unique_movies):

        email_log = random.choice(email_objs)
        quality_jitter = round(quality + random.uniform(-3, 3), 1)
        quality_jitter = max(0, min(100, quality_jitter))
        status = pick_status(quality_jitter)

        c = Content(
            title=title,
            original_title=orig_title,
            content_type=ContentType.movie,
            status=status,
            cp_name=cp_name,
            cp_email_id=email_log.id,
            production_year=year,
            runtime_minutes=runtime,
            country=country,
        )
        db.add(c)
        db.flush()

        # ContentMetadata
        meta = ContentMetadata(
            content_id=c.id,
            cp_synopsis=synopsis,
            cp_genre=", ".join(genre_codes),
            cp_tags=mood_tags,
            ai_synopsis=synopsis,
            ai_genre_primary=genre_codes[0] if genre_codes else None,
            ai_genre_secondary=genre_codes[1] if len(genre_codes) > 1 else None,
            ai_mood_tags=mood_tags,
            ai_rating_suggestion=random.choice(["전체관람가", "12세이상관람가", "15세이상관람가"]),
            tmdb_id=tmdb_id,
            tmdb_data={"id": tmdb_id, "title": orig_title, "popularity": round(random.uniform(20, 120), 1)},
            quality_score=quality_jitter,
            score_breakdown={
                "synopsis_quality": 25 if len(synopsis) >= 100 else 15,
                "genre_confidence": 20,
                "tag_coverage": min(15, len(mood_tags) * 3),
                "external_meta": 20 if tmdb_id else 0,
                "field_coverage": 15,
            },
            ai_processed_at=random_date(20, 1),
            reviewed_by="김편성" if status == ContentStatus.approved else None,
            reviewed_at=random_date(10, 1) if status == ContentStatus.approved else None,
            final_synopsis=synopsis if status == ContentStatus.approved else None,
            final_genre=genre_codes[0] if status == ContentStatus.approved else None,
            final_source=MetaSource.ai,
        )
        db.add(meta)
        db.flush()

        # 장르 연결
        for i, code in enumerate(genre_codes):
            gid = get_genre_id(db, code)
            if gid:
                db.add(ContentGenre(
                    content_id=c.id, genre_id=gid,
                    is_primary=(i == 0), source="ai",
                ))

        # 태그 연결
        tag_ids = get_tag_ids(db, mood_tags)
        for tid in tag_ids:
            db.add(ContentTag(
                content_id=c.id, tag_id=tid,
                source="ai", confidence_score=round(random.uniform(0.7, 0.98), 2),
            ))

        # 이미지 (TMDB 포스터)
        poster_path = TMDB_POSTER_IDS.get(title, f"/sample_poster_{idx+1}.jpg")
        db.add(ContentImage(
            content_id=c.id,
            image_type=ImageType.poster,
            url=f"{TMDB_POSTER_BASE}{poster_path}",
            width=500, height=750,
            source="tmdb", is_primary=True,
        ))
        db.add(ContentImage(
            content_id=c.id,
            image_type=ImageType.thumbnail,
            url=f"https://image.tmdb.org/t/p/w300{poster_path}",
            width=300, height=450,
            source="tmdb", is_primary=False,
        ))

        # 감독 크레딧 (랜덤 배정)
        director = random.choice(list(director_objs.values()))
        db.add(ContentCredit(
            content_id=c.id, person_id=director.id,
            role=CreditRole.director, cast_order=0, source="tmdb",
        ))

        # 배우 크레딧 (2~4명)
        sampled_actors = random.sample(list(actor_objs.values()), k=min(3, len(actor_objs)))
        char_names = ["주인공", "조연", "악당", "조력자"]
        for order, actor in enumerate(sampled_actors):
            db.add(ContentCredit(
                content_id=c.id, person_id=actor.id,
                role=CreditRole.actor,
                character_name=char_names[order % len(char_names)],
                cast_order=order + 1, source="tmdb",
            ))

        # 외부 메타 소스
        db.add(ExternalMetaSource(
            content_id=c.id,
            source_type=ExternalSourceType.tmdb,
            external_id=str(tmdb_id),
            title_on_source=orig_title,
            raw_json={"id": tmdb_id, "original_title": orig_title, "release_date": f"{year}-01-01"},
            match_confidence=round(random.uniform(0.80, 0.99), 2),
            matched_at=random_date(15, 1),
        ))

        # AI 결과 (approved/review 상태는 처리 완료)
        if status in (ContentStatus.approved, ContentStatus.review):
            db.add(ContentAIResult(
                content_id=c.id,
                engine="llama3.2:3b",
                task_type=AITaskType.synopsis,
                result_json={"synopsis": synopsis, "confidence": 0.85},
                quality_score=quality_jitter,
                is_final=True,
                processed_at=random_date(15, 1),
            ))
            db.add(ContentAIResult(
                content_id=c.id,
                engine="llama3.2:3b",
                task_type=AITaskType.tagging,
                result_json={"tags": mood_tags, "confidence": 0.80},
                quality_score=quality_jitter - 2,
                is_final=True,
                processed_at=random_date(15, 1),
            ))

        movie_objs.append(c)

    db.commit()
    print(f"   영화 {len(movie_objs)}편 삽입 완료")

    # ── 4. 시리즈 / 시즌 / 에피소드 ──────────────────────
    print("4. 시리즈 콘텐츠 삽입...")
    ep_total = 0

    for s_idx, (title, year, cp_name, genre_codes, synopsis, num_seasons, eps_per_season) in enumerate(SERIES):
        email_log = random.choice(email_objs)
        quality = round(random.uniform(78, 95), 1)
        status = pick_status(quality)

        # 시리즈
        series = Content(
            title=title,
            content_type=ContentType.series,
            status=status,
            cp_name=cp_name,
            cp_email_id=email_log.id,
            production_year=year,
            country="KR",
        )
        db.add(series)
        db.flush()

        meta = ContentMetadata(
            content_id=series.id,
            cp_synopsis=synopsis,
            ai_synopsis=synopsis,
            ai_genre_primary=genre_codes[0] if genre_codes else None,
            ai_mood_tags=[],
            quality_score=quality,
            score_breakdown={"synopsis_quality": 30, "genre_confidence": 20, "tag_coverage": 9, "external_meta": 10, "field_coverage": 15},
            ai_processed_at=random_date(20, 5),
            final_synopsis=synopsis if status == ContentStatus.approved else None,
            final_source=MetaSource.ai,
        )
        db.add(meta)
        db.flush()

        # 장르 연결
        for i, code in enumerate(genre_codes):
            gid = get_genre_id(db, code)
            if gid:
                db.add(ContentGenre(content_id=series.id, genre_id=gid, is_primary=(i==0), source="ai"))

        # 이미지
        db.add(ContentImage(
            content_id=series.id,
            image_type=ImageType.poster,
            url=f"https://image.tmdb.org/t/p/w500/series_poster_{s_idx+1}.jpg",
            width=500, height=750, source="tmdb", is_primary=True,
        ))

        # 시즌
        for season_num in range(1, num_seasons + 1):
            season = Content(
                title=f"{title} 시즌 {season_num}",
                content_type=ContentType.season,
                status=ContentStatus.approved,
                cp_name=cp_name,
                production_year=year + (season_num - 1),
                country="KR",
                parent_id=series.id,
                season_number=season_num,
            )
            db.add(season)
            db.flush()

            db.add(ContentMetadata(
                content_id=season.id,
                cp_synopsis=f"{title} {season_num}시즌 — {synopsis[:80]}...",
                quality_score=round(quality - 2, 1),
                ai_processed_at=random_date(20, 5),
            ))
            db.flush()

            # 에피소드
            for ep_num in range(1, eps_per_season + 1):
                ep_quality = round(quality + random.uniform(-5, 5), 1)
                ep_status = pick_status(ep_quality)

                episode = Content(
                    title=f"{title} {ep_num}화",
                    content_type=ContentType.episode,
                    status=ep_status,
                    cp_name=cp_name,
                    production_year=year + (season_num - 1),
                    runtime_minutes=random.choice([45, 50, 55, 60, 70]),
                    country="KR",
                    parent_id=season.id,
                    season_number=season_num,
                    episode_number=ep_num,
                )
                db.add(episode)
                db.flush()

                db.add(ContentMetadata(
                    content_id=episode.id,
                    cp_synopsis=f"{title} {ep_num}화 — {ep_num}번째 에피소드",
                    ai_synopsis=f"{title} {ep_num}화: {synopsis[:60]}... ({ep_num}번째 이야기)",
                    ai_mood_tags=random.sample(["따뜻한", "긴장감", "눈물주의", "반전있음"], k=2),
                    quality_score=ep_quality,
                    ai_processed_at=random_date(20, 5),
                    final_synopsis=f"{title} {ep_num}화" if ep_status == ContentStatus.approved else None,
                ))
                db.flush()
                ep_total += 1

    db.commit()
    print(f"   시리즈 {len(SERIES)}개 + 에피소드 {ep_total}개 삽입 완료")

    # ── 5. 미처리 대기 콘텐츠 (waiting 상태) ──────────────
    print("5. 미처리 대기 콘텐츠 삽입...")
    waiting_titles = [
        ("마당이 있는 집", "A House with a Garden", 2023, "JTBC스튜디오"),
        ("닥터 슬럼프", "Doctor Slump", 2024, "스튜디오드래곤"),
        ("선재 업고 튀어", "Lovely Runner", 2024, "스튜디오드래곤"),
        ("눈물의 여왕", "Queen of Tears", 2024, "스튜디오드래곤"),
        ("엄마친구아들", "My Mother's Friend's Son", 2024, "에이스토리"),
    ]
    for title, orig, year, cp in waiting_titles:
        c = Content(
            title=title, original_title=orig,
            content_type=ContentType.series,
            status=ContentStatus.waiting,
            cp_name=cp, production_year=year, country="KR",
        )
        db.add(c)
        db.flush()
        db.add(ContentMetadata(content_id=c.id, cp_synopsis=f"{title} 시놉시스 미제공", quality_score=0.0))
        db.flush()

    db.commit()
    print(f"   대기 콘텐츠 {len(waiting_titles)}개 삽입 완료")

    # ── 최종 통계 ────────────────────────────────────────
    total_contents = db.query(Content).count()
    total_meta = db.query(ContentMetadata).count()
    approved = db.query(Content).filter(Content.status == ContentStatus.approved).count()
    review = db.query(Content).filter(Content.status == ContentStatus.review).count()
    waiting = db.query(Content).filter(Content.status == ContentStatus.waiting).count()

    print(f"\n=== 시딩 완료 ===")
    print(f"  전체 콘텐츠: {total_contents}개")
    print(f"  메타데이터: {total_meta}개")
    print(f"  승인(approved): {approved}개")
    print(f"  검수대기(review): {review}개")
    print(f"  수신대기(waiting): {waiting}개")
    print(f"  인물: {db.query(PersonMaster).count()}명")
    print(f"  크레딧: {db.query(ContentCredit).count()}개")
    print(f"  이미지: {db.query(ContentImage).count()}개")
    print(f"  외부메타: {db.query(ExternalMetaSource).count()}개")
    print(f"  AI결과: {db.query(ContentAIResult).count()}개")


def clean_data(db):
    print("기존 데이터 삭제 중...")
    for Model in [ContentAIResult, ExternalMetaSource, ContentImage,
                  ContentCredit, ContentTag, ContentGenre,
                  ContentMetadata, Content, CpEmailLog, PersonMaster]:
        db.query(Model).delete()
    db.commit()
    print("삭제 완료")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--clean", action="store_true", help="기존 데이터 삭제 후 재삽입")
    args = parser.parse_args()

    Base.metadata.create_all(engine)
    db = SessionLocal()
    try:
        if args.clean:
            clean_data(db)
        seed(db)
    except Exception as e:
        db.rollback()
        raise e
    finally:
        db.close()
