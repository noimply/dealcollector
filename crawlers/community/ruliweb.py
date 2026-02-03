import logging
from datetime import datetime
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re
from baseCrawler import BaseCrawler

logger = logging.getLogger(__name__)

class RuliwebCrawler(BaseCrawler):
    """루리웹 핫딜 게시판 크롤러"""
    
    BASE_URL = "https://bbs.ruliweb.com"
    HOTDEAL_URL = "https://bbs.ruliweb.com/market/board/1020"
    COMMUNITY_ID = 30  # deal_community 테이블의 루리웹 ID
    
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
        루리웹 핫딜 게시판 크롤링
        
        Args:
            max_pages: 크롤링할 최대 페이지 수
            
        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"루리웹 크롤링 시작 (최대 {max_pages}페이지)")
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
        
        logger.info(f"루리웹 크롤링 완료: 총 {len(deals)}개 딜 수집")
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
            # 루리웹은 ?page=1, ?page=2 형식
            url = f"{self.HOTDEAL_URL}?page={page_num + 1}"
        
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
        # 루리웹은 tr.table_body (class="table_body blocktarget")
        articles = soup.select('tr.table_body.blocktarget')
        
        if not articles:
            logger.warning(f"게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            # 디버깅을 위해 HTML 일부 저장
            with open('logs/ruliweb_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:5000])
            logger.info("디버깅용 HTML이 logs/ruliweb_debug.html에 저장되었습니다")
            return deals, should_stop
        
        for article in articles:
            try:
                # 공지사항 제외
                if article.has_attr('class'):
                    classes = article.get('class', [])
                    if any(cls in ['notice', 'notice_eng', 'notice_kor'] for cls in classes):
                        logger.debug("공지사항 제외")
                        continue
                
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
            title_selectors = ['a.subject_link']
            
            for selector in title_selectors:
                title_elem = article.select_one(selector)
                if title_elem:
                    break
            
            if not title_elem:
                return None
            
            title = title_elem.get_text(strip=True)
            title = re.sub(r'\(\d+\)$', '', title)
            
            # 빈 제목이나 너무 짧은 제목 제외
            if not title or len(title) < 3:
                return None
            
            # URL 추출
            href = title_elem.get('href', '')
            if not href:
                return None
            
            if href.startswith('/'):
                url = self.BASE_URL + href
            elif href.startswith('http'):
                url = href
            else:
                url = self.BASE_URL + '/' + href
            
            # 차단된 URL인지 확인
            if url in self.BLACKLISTED_URLS:
                return None

            # 이미지 URL 추출
            image_url = self._extract_image_url(article)
            
            # 작성일 추출 및 형식 변환
            # 26.02.01 11:05:05 → 2026-02-01 11:05:05
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
    
    def _extract_category(self, article, title: str) -> str:
        #"""카테고리 추출 ([] 제거된 순수 값 반환)"""
        try:
            category_selectors = [
                'td.divsn a',
                'span.category',
                'td[class*="category"]',
                '.divsn'
            ]

            for selector in category_selectors:
                category_elem = article.select_one(selector)
                if category_elem:
                    cat_text = category_elem.get_text(strip=True)
                    if cat_text:
                        # [국내] → 국내
                        return re.sub(r'^\[|\]$', '', cat_text).strip()

            # 제목에서 [] 패턴 추출 → [] 제거
            match = re.search(r'\[([^\]]+)\]', title)
            if match:
                return match.group(1).strip()

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
                'td img',
                'span.thumb img'
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
        """HTML에서 작성일 추출 (HH:MM 형식만 허용)"""
        try:
            date_selectors = ['td.time']

            for selector in date_selectors:
                date_elem = article.select_one(selector)
                if not date_elem:
                    continue

                date_text = date_elem.get_text(strip=True)
                if not date_text:
                    continue

                # HH:MM 형식만 허용
                if not re.fullmatch(r'\d{2}:\d{2}', date_text):
                    return None

                now = datetime.now()
                return f"{now.strftime('%Y-%m-%d')} {date_text}:00"

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
    
    crawler = RuliwebCrawler()
    deals = crawler.crawl(max_pages=1)
    
    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")