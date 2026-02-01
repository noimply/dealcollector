"""크롤러 설정"""

# 크롤링 설정
CRAWL_CONFIG = {
    'clien': {
        'max_pages': 1,
        'keep_count': 200,
        'community_id': 1
    },
    'ppomppu': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 2
    },
    'ruliweb': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 3  # 루리웹
    },
    'quasarzone': {
        'max_pages': 1,  # 1페이지만 크롤링
        'keep_count': 200,  # DB에 유지할 최대 딜 개수
        'community_id': 4  # 퀘이사존
    },
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