"""크롤러 설정"""

# 크롤링 설정
CRAWL_CONFIG = {
    'clien': {
        'max_pages': 1,
        'keep_count': 200,
        'community_id': 10 # 클리앙
    },
    'ppomppu': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 20
    },
    'ruliweb': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 30  # 루리웹
    },
    'quasarzone': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 40  # 퀘이사존
    },
    'eomisae_rt': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 50  # 어미새 #기타정보
    },
    'eomisae_os': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 51  # 어미새 #패션정보
    },
    'arcalive': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 60  # 아카라이브
    },
    'coolenjoy': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 70  # 쿨앤조이
    },
    'bbassak_korea': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 80  # 빠삭 # 국내핫딜
    },
    'bbassak_overseas': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 81  # 빠삭 # 해외핫딜
    },
    'dealbada_korea': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 90  # 딜바다 # 국내핫딜
    },
    'dealbada_overseas': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 91  # 딜바다 # 해외핫딜
    },
    'etoland': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 100  # 이토랜드 # 핫딜
    }
}

# 중복 체크 설정
DUPLICATE_CHECK = {
    'enabled': True,  # 제목 유사도 기반 중복 체크 활성화
    'similarity_threshold': 0.85,  # 유사도 임계값 (85%)
    'check_days': 7,  # 최근 N일 딜과 비교
}

# 정리(cleanup) 설정
CLEANUP_CONFIG = {
    'enabled': True,  # 오래된 딜 자동 삭제 활성화
}

#핫딜아빠는 뽐뿌, 클리앙, 루리웹, 에펨코리아, 아카라이브, 퀘이사존, 쿨앤조이, 빠삭, 어미새, 시티, 딜바다, 몰테일, 이토랜드 등 40여개 핫딜 커뮤니티의 할인정보를 실시간으로 모아보는 플랫폼입니다.