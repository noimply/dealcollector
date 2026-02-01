import logging
from typing import List, Dict, Optional
from datetime import datetime, timedelta
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class QuasarzoneCrawler:
    """퀘이사존 핫딜 게시판 크롤러"""

    BASE_URL = "https://www.quasarzone.com"
    HOTDEAL_URL = "https://quasarzone.com/bbs/qb_saleinfo"
    COMMUNITY_ID = 4

    BLACKLISTED_URLS = []

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def crawl(self, max_pages: int = 1) -> List[Dict]:
        """
        퀘이사존 핫딜 게시판 크롤링

        Args:
            max_pages: 크롤링할 최대 페이지 수

        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"퀘이사존 크롤링 시작 (최대 {max_pages}페이지)")
        deals = []

        with sync_playwright() as p:
            browser = p.chromium.launch(headless=True)
            context = browser.new_context(user_agent=self.user_agent)
            page = context.new_page()

            try:
                for page_num in range(max_pages):
                    logger.info(f"페이지 {page_num + 1} 크롤링 중...")
                    page_deals = self._crawl_page(page, page_num)
                    deals.extend(page_deals)
                    logger.info(f"페이지 {page_num + 1}에서 {len(page_deals)}개 딜 수집")

            except Exception as e:
                logger.error(f"크롤링 중 오류 발생: {str(e)}", exc_info=True)
            finally:
                browser.close()

        logger.info(f"퀘이사존 크롤링 완료: 총 {len(deals)}개 딜 수집")
        return deals

    def _crawl_page(self, page: Page, page_num: int) -> List[Dict]:
        """단일 페이지 크롤링"""
        deals = []

        # 페이지 이동
        if page_num == 0:
            url = self.HOTDEAL_URL
        else:
            url = f"{self.HOTDEAL_URL}?page={page_num + 1}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals

        # HTML 파싱
        soup = BeautifulSoup(page.content(), 'html.parser')

        # div.market-type-list.market-info-type-list 하위 테이블의 tr
        container = soup.select_one('div.market-type-list.market-info-type-list')
        if not container:
            logger.warning("게시글 컨테이너를 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/quasarzone_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:5000])
            logger.info("디버깅용 HTML이 logs/quasarzone_debug.html에 저장되었습니다")
            return deals

        articles = container.select('table tbody tr')

        if not articles:
            logger.warning("테이블 tr 요소를 찾을 수 없습니다")            
            return deals

        logger.debug(f"{len(articles)}개 요소 발견")

        for article in articles:
            try:
                deal = self._parse_article(article)
                if deal:
                    deals.append(deal)
            except Exception as e:
                logger.warning(f"게시글 파싱 실패: {str(e)}")
                continue

        return deals

    def _parse_article(self, article) -> Optional[Dict]:
        """게시글 파싱"""
        try:
            # 제목 및 URL 추출
            title_elem = article.select_one('p.tit a')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
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

            if url in self.BLACKLISTED_URLS:
                return None

            # 이미지 URL 추출
            image_url = self._extract_image_url(article)

            # 작성일 추출 및 형식 변환
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
        """카테고리 추출"""
        try:
            category_selectors = [
                'td.category a',
                'td.category',
                'span.category',
                '.category'
            ]

            for selector in category_selectors:
                elem = article.select_one(selector)
                if elem:
                    cat_text = elem.get_text(strip=True)
                    if cat_text:
                        return f"[{cat_text}]"

            # 제목에서 [] 패턴 추출
            match = re.search(r'(\[[^\]]+\])', title)
            if match:
                return match.group(1)

            return ''

        except Exception as e:
            logger.debug(f"카테고리 추출 실패: {str(e)}")
            return ''

    def _extract_image_url(self, article) -> Optional[str]:
        """HTML에서 이미지 URL 추출"""
        try:
            img_elem = article.select_one('img')
            if not img_elem:
                return None

            src = img_elem.get('src', '') or img_elem.get('data-src', '')
            if not src:
                return None

            if src.startswith('//'):
                return 'https:' + src
            elif src.startswith('/'):
                return self.BASE_URL + src
            elif src.startswith('http'):
                return src
            else:
                return self.BASE_URL + '/' + src

        except Exception as e:
            logger.debug(f"이미지 URL 추출 실패: {str(e)}")
            return None

    def _extract_date(self, article) -> Optional[str]:
        """HTML에서 작성일 추출 및 형식 변환"""
        try:
            date_selectors = [
                'td.date',
                'td.time',
                'span.date',
                'td[class*="date"]',
                'td[class*="time"]'
            ]

            raw_date = None
            for selector in date_selectors:
                elem = article.select_one(selector)
                if elem:
                    if elem.get('title'):
                        raw_date = elem.get('title').strip()
                        break
                    text = elem.get_text(strip=True)
                    if text:
                        raw_date = text
                        break

            if not raw_date:
                return None

            now = datetime.now()

            # 1️⃣ "n시간 전"
            match = re.match(r'(\d+)\s*시간\s*전', raw_date)
            if match:
                hours = int(match.group(1))
                return (now - timedelta(hours=hours)).strftime('%Y-%m-%d %H:%M:%S')

            # 2️⃣ "n분 전"
            match = re.match(r'(\d+)\s*분\s*전', raw_date)
            if match:
                minutes = int(match.group(1))
                return (now - timedelta(minutes=minutes)).strftime('%Y-%m-%d %H:%M:%S')

            # 3️⃣ "방금 전"
            if raw_date in ('방금', '방금 전'):
                return now.strftime('%Y-%m-%d %H:%M:%S')

            # 그 외는 실패로
            return None

        except Exception as e:
            logger.debug(f"작성일 추출 실패: {str(e)}")
            print(f"작성일 추출 실패: {str(e)}")
            return None


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    crawler = QuasarzoneCrawler()
    deals = crawler.crawl(max_pages=1)

    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")