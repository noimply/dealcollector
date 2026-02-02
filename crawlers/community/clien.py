import logging
from datetime import datetime
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)

class ClienCrawler:
    """클리앙 알뜰구매 게시판 크롤러"""
    
    BASE_URL = "https://www.clien.net"
    HOTDEAL_URL = "https://www.clien.net/service/board/jirum"
    COMMUNITY_ID = 10  # deal_community 테이블의 클리앙 ID
    
    # 차단할 URL 목록
    BLACKLISTED_URLS = []
    
    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )
    
    def crawl(self, max_pages: int = 1, last_url: str = None) -> List[Dict]:
        """
        클리앙 알뜰구매 게시판 크롤링
        
        Args:
            max_pages: 크롤링할 최대 페이지 수
            last_url: 이전 크롤링의 마지막 URL (이 URL을 만나면 중단)
            
        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"클리앙 크롤링 시작 (최대 {max_pages}페이지)")
        if last_url:
            logger.info(f"중복 체크 URL: {last_url}")
        
        deals = []
        should_stop = False  # 중단 플래그
        
        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()
            
            try:
                for page_num in range(max_pages):
                    if should_stop:
                        logger.info(f"이전 크롤링 지점 도달 - 크롤링 중단")
                        break
                    
                    logger.info(f"페이지 {page_num + 1} 크롤링 중...")
                    page_deals, stop_flag = self._crawl_page(page, page_num, last_url)
                    deals.extend(page_deals)
                    logger.info(f"페이지 {page_num + 1}에서 {len(page_deals)}개 딜 수집")
                    
                    if stop_flag:
                        should_stop = True
                    
            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {str(e)}", exc_info=True)
            finally:
                browser.close()
        
        logger.info(f"클리앙 크롤링 완료: 총 {len(deals)}개 딜 수집")
        return deals
    
    def _crawl_page(self, page: Page, page_num: int, last_url: str = None) -> tuple:
        """
        단일 페이지 크롤링
        
        Args:
            page_num: 페이지 번호
            last_url: 이전 크롤링의 마지막 URL (중단 체크용)
        
        Returns:
            (deals, should_stop): 딜 리스트와 중단 플래그
        """
        deals = []
        should_stop = False
        
        # 페이지 이동
        if page_num == 0:
            url = self.HOTDEAL_URL
        else:
            # 클리앙은 ?po=0, ?po=1 형식으로 페이지 구분
            url = f"{self.HOTDEAL_URL}?po={page_num}"
        
        # 타임아웃 증가 및 wait_until 조건 완화
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            # 추가 대기 (페이지 렌더링 완료까지)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop
        
        # HTML 파싱
        soup = BeautifulSoup(page.content(), 'html.parser')
        
        # 게시글 목록 찾기
        # 클리앙은 div.contents_jirum > div.list_item 형식
        selectors = [
            'div.contents_jirum > div.list_item'
        ]
        
        articles = []
        
        for selector in selectors:
            articles = soup.select(selector)
            if articles:
                logger.debug(f"셀렉터 '{selector}'로 {len(articles)}개 요소 발견")
                break
        
        if not articles:
            logger.warning(f"게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            # 디버깅을 위해 HTML 일부 저장
            with open('logs/clien_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:5000])
            logger.info("디버깅용 HTML이 logs/clien_debug.html에 저장되었습니다")
            return deals, should_stop
        
        for article in articles:
            try:
                deal = self._parse_article(article)
                if deal:
                    # last_url 체크 - 이전 크롤링 지점 발견시 중단
                    if last_url and deal['url'] == last_url:
                        logger.info(f"이전 크롤링 지점 발견: {last_url}")
                        should_stop = True
                        break
                    
                    deals.append(deal)
            except Exception as e:
                logger.warning(f"게시글 파싱 실패: {str(e)}")
                continue
        
        return deals, should_stop
    
    def _parse_article(self, article) -> Optional[Dict]:
        """게시글 파싱"""
        try:
            # 제목 추출
            title_elem = None
            title_selectors = [
                'span.subject_fixed',
                'span.list_subject',
                '.subject a',
                'a.list_subject',
                'a[class*="subject"]'
            ]
            
            for selector in title_selectors:
                title_elem = article.select_one(selector)
                if title_elem:
                    break
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            
            # 빈 제목이나 너무 짧은 제목 제외
            if not title or len(title) < 3:
                return None
            
            # URL 추출
            # 제목 링크 찾기
            link_elem = article.select_one('a[href*="/service/board/jirum/"]')
            if not link_elem:
                link_elem = article.select_one('a')
            
            if not link_elem:
                return None
            
            href = link_elem.get('href', '')
            if not href:
                return None
            
            # URL 정규화
            if href.startswith('http'):
                url = href
            elif href.startswith('//'):
                url = 'https:' + href
            elif href.startswith('/'):
                url = self.BASE_URL + href
            else:
                url = self.BASE_URL + '/' + href
            
            # 차단된 URL인지 확인
            if url in self.BLACKLISTED_URLS:
                return None
            
            # 이미지 URL 추출
            image_url = self._extract_image_url(article)
            
            # 작성일 추출
            post_date = self._extract_date(article)
            if not post_date:
                return None
            
            # 카테고리 추출
            category = self._extract_category(article, title)
            
            deal = {
                'title': title,
                'url': url,
                'image_url': image_url,
                'category': category,
                'posted_at': post_date,
                'community_id': self.COMMUNITY_ID
            }
            
            return deal
            
        except Exception as e:
            logger.debug(f"게시글 파싱 중 오류: {str(e)}")
            return None
    
    def _normalize_category(self, cat: str) -> str:
        if not cat:
            return ''

        # [국내] → 국내
        cat = re.sub(r'^\[|\]$', '', cat)

        # 쉼표 / 공백 제거
        cat = cat.strip().strip(',')

        return cat if cat else ''


    def _extract_category(self, article, title: str) -> str:
        """카테고리 추출"""
        try:
            # 1️⃣ HTML에서 카테고리 태그 찾기
            category_selectors = [
                'span.category',
                '.list_category',
                'span[class*="category"]'
            ]

            for selector in category_selectors:
                category_elem = article.select_one(selector)
                if category_elem:
                    return self._normalize_category(
                        category_elem.get_text(strip=True)
                    )

            # 2️⃣ 제목에서 [카테고리] 패턴 추출
            match = re.search(r'\[([^\]]+)\]', title)
            if match:
                return self._normalize_category(match.group(1))

            return ''

        except Exception as e:
            logger.debug(f"카테고리 추출 실패: {str(e)}")
            return ''
    
    def _extract_image_url(self, article) -> Optional[str]:
        """HTML에서 이미지 URL 추출"""
        try:
            # img 태그에서 이미지 추출
            img_selectors = [
                'img',
                '.list_img img',
                'div[class*="img"] img'
            ]
            
            for selector in img_selectors:
                img_elem = article.select_one(selector)
                if img_elem:
                    src = img_elem.get('src', '')
                    if not src:
                        src = img_elem.get('data-src', '')
                    
                    if src:
                        # 상대 경로를 절대 경로로 변환
                        if src.startswith('//'):
                            return 'https:' + src
                        elif src.startswith('/'):
                            return self.BASE_URL + src
                        elif src.startswith('http'):
                            return src
                        else:
                            return self.BASE_URL + '/' + src
            
            return None
            
        except Exception as e:
            logger.debug(f"이미지 URL 추출 실패: {str(e)}")
            return None
    
    def _extract_date(self, article) -> Optional[str]:
        """HTML에서 작성일 추출"""
        try:
            # 클리앙 날짜 형식 찾기
            date_selectors = [
                'span.timestamp',
                'span.time',
                '.list_time',
                'span[class*="time"]',
                'span[class*="date"]'
            ]
            
            for selector in date_selectors:
                date_elem = article.select_one(selector)
                if date_elem:
                    date_text = date_elem.get_text(strip=True)
                    if date_text:
                        return date_text
            
            return None
            
        except Exception as e:
            logger.debug(f"작성일 추출 실패: {str(e)}")
            return None


if __name__ == '__main__':
    # 테스트 코드
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    crawler = ClienCrawler()
    deals = crawler.crawl(max_pages=1)
    
    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")