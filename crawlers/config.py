"""크롤링 설정"""
import os

# GitHub Actions 환경 감지
IS_GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'

# 환경별 설정
if IS_GITHUB_ACTIONS:
    # GitHub Actions: 안정성 우선, 적은 페이지
    CRAWL_CONFIG = {
        'clien': {'max_pages': 1, 'keep_count': 100, 'community_id': 10},
        'ppomppu': {'max_pages': 1, 'keep_count': 100, 'community_id': 20},
        'ruliweb': {'max_pages': 1, 'keep_count': 100, 'community_id': 30},
        'quasarzone': {'max_pages': 1, 'keep_count': 100, 'community_id': 40},
        'eomisae_rt': {'max_pages': 1, 'keep_count': 100, 'community_id': 50},
        'eomisae_os': {'max_pages': 1, 'keep_count': 100, 'community_id': 51},
        'arcalive': {'max_pages': 1, 'keep_count': 100, 'community_id': 60},
        'coolenjoy': {'max_pages': 1, 'keep_count': 100, 'community_id': 70},
        'bbassak_korea': {'max_pages': 1, 'keep_count': 100, 'community_id': 80},
        'bbassak_overseas': {'max_pages': 1, 'keep_count': 100, 'community_id': 81},
        'dealbada_korea': {'max_pages': 1, 'keep_count': 100, 'community_id': 90},
        'dealbada_overseas': {'max_pages': 1, 'keep_count': 100, 'community_id': 91},
        'etoland': {'max_pages': 1, 'keep_count': 100, 'community_id': 100},
    }
    TIMEOUT = 120000  # 2분
    print("🔧 GitHub Actions 환경 설정 적용")
else:
    # 로컬: 더 많은 페이지, 더 많은 데이터
    CRAWL_CONFIG = {
        'clien': {'max_pages': 1, 'keep_count': 200, 'community_id': 10},
        'ppomppu': {'max_pages': 1, 'keep_count': 200, 'community_id': 20},
        'ruliweb': {'max_pages': 1, 'keep_count': 200, 'community_id': 30},
        'quasarzone': {'max_pages': 1, 'keep_count': 200, 'community_id': 40},
        'eomisae_rt': {'max_pages': 1, 'keep_count': 200, 'community_id': 50},
        'eomisae_os': {'max_pages': 1, 'keep_count': 200, 'community_id': 51},
        'arcalive': {'max_pages': 1, 'keep_count': 200, 'community_id': 60},
        'coolenjoy': {'max_pages': 1, 'keep_count': 200, 'community_id': 70},
        'bbassak_korea': {'max_pages': 1, 'keep_count': 200, 'community_id': 80},
        'bbassak_overseas': {'max_pages': 1, 'keep_count': 200, 'community_id': 81},
        'dealbada_korea': {'max_pages': 1, 'keep_count': 200, 'community_id': 90},
        'dealbada_overseas': {'max_pages': 1, 'keep_count': 200, 'community_id': 91},
        'etoland': {'max_pages': 1, 'keep_count': 200, 'community_id': 100},
    }
    TIMEOUT = 60000  # 1분
    print("💻 로컬 환경 설정 적용")

# 중복 체크 설정
DUPLICATE_CHECK = {
    'enabled': True,
    'similarity_threshold': 0.85
}

# 정리 설정
CLEANUP_CONFIG = {
    'enabled': True
}

# 로깅 설정
LOGGING_CONFIG = {
    'level': 'INFO' if IS_GITHUB_ACTIONS else 'DEBUG',
    'format': '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    'file': 'logs/crawler.log'
}