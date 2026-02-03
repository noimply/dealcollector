"""
크롤러 기본 클래스 - GitHub Actions 환경 대응
"""
import os
import logging
import random
import time
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page, Browser

logger = logging.getLogger(__name__)


class BaseCrawler:
    """모든 크롤러의 기본 클래스 - GitHub Actions 최적화"""
    
    # GitHub Actions 환경 감지
    IS_GITHUB_ACTIONS = os.getenv('GITHUB_ACTIONS') == 'true'
    
    # 환경별 설정
    TIMEOUT = 120000 if IS_GITHUB_ACTIONS else 60000  # GitHub: 2분, 로컬: 1분
    WAIT_TIME = 3000 if IS_GITHUB_ACTIONS else 2000   # GitHub: 3초, 로컬: 2초
    
    # User-Agent 목록 (랜덤 선택으로 차단 방지)
    USER_AGENTS = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    ]
    
    BASE_URL = ""
    HOTDEAL_URL = ""
    COMMUNITY_ID = 0
    BLACKLISTED_URLS = []
    
    def __init__(self):
        self.user_agent = random.choice(self.USER_AGENTS)
        if self.IS_GITHUB_ACTIONS:
            logger.info(f"🔧 GitHub Actions 모드로 실행 (타임아웃: {self.TIMEOUT}ms)")
    
    def _launch_browser(self, playwright) -> Browser:
        """브라우저 실행 - GitHub Actions 최적화"""
        args = [
            '--disable-blink-features=AutomationControlled',
        ]
        
        # GitHub Actions 전용 설정
        if self.IS_GITHUB_ACTIONS:
            args.extend([
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-gpu',
            ])
        
        return playwright.chromium.launch(
            headless=True,
            args=args
        )
    
    def _create_context(self, browser: Browser):
        """브라우저 컨텍스트 생성"""
        return browser.new_context(
            user_agent=self.user_agent,
            viewport={'width': 1920, 'height': 1080},
            extra_http_headers={
                'Accept-Language': 'ko-KR,ko;q=0.9,en-US;q=0.8,en;q=0.7',
            }
        )
    
    def _safe_goto(self, page: Page, url: str, max_retries: int = 3) -> bool:
        """안전한 페이지 이동 (재시도 포함)"""
        for attempt in range(max_retries):
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=self.TIMEOUT)
                page.wait_for_timeout(self.WAIT_TIME)
                return True
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 2  # 2초, 4초, 6초
                    logger.warning(f"페이지 로딩 실패 (시도 {attempt + 1}/{max_retries}): {str(e)}")
                    logger.info(f"{wait_time}초 후 재시도...")
                    time.sleep(wait_time)
                else:
                    logger.error(f"페이지 로딩 최종 실패: {url} - {str(e)}")
                    return False
        return False
    
    def _normalize_url(self, href: str) -> Optional[str]:
        """URL 정규화"""
        if not href:
            return None
        
        if href.startswith('http'):
            return href
        elif href.startswith('//'):
            return 'https:' + href
        elif href.startswith('/'):
            return self.BASE_URL + href
        else:
            return self.BASE_URL + '/' + href
    
    def _random_delay(self, min_sec: float = 1.0, max_sec: float = 3.0):
        """랜덤 지연 (봇 탐지 방지)"""
        if self.IS_GITHUB_ACTIONS:
            # GitHub Actions에서는 더 긴 대기
            delay = random.uniform(min_sec * 1.5, max_sec * 1.5)
        else:
            delay = random.uniform(min_sec, max_sec)
        
        time.sleep(delay)