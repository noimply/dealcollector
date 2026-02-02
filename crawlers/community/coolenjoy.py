import logging
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re
from datetime import datetime

logger = logging.getLogger(__name__)


class CoolenjoyCrawler:
    """쿨앤조이 핫딜 크롤러"""

    BASE_URL = "https://coolenjoy.net"
    HOTDEAL_URL = "https://coolenjoy.net/bbs/jirum"
    COMMUNITY_ID = 70

    BLACKLISTED_URLS = []

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def crawl(self, max_pages: int = 1, last_url: str = None) -> List[Dict]:
        """
        쿨앤조이 핫딜 크롤링

        Args:
            max_pages: 크롤링할 최대 페이지 수
            last_url: 이전 크롤링의 마지막 URL (이 URL을 만나면 중단)

        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"쿨앤조이 크롤링 시작 (최대 {max_pages}페이지)")
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

        logger.info(f"쿨앤조이 크롤링 완료: 총 {len(deals)}개 딜 수집")
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

        if page_num == 0:
            url = self.HOTDEAL_URL
        else:
            url = f"{self.HOTDEAL_URL}?page={page_num + 1}"

        try:
            # networkidle 대신 domcontentloaded 사용 (타임아웃 방지)
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop

        soup = BeautifulSoup(page.content(), 'html.parser')

        # 쿨앤조이 게시글 목록
        # #bo_list > ul > li:not(.bg-light)
        articles = soup.select('#bo_list > ul > li:not(.bg-light)')

        if not articles:
            logger.warning("게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/coolenjoy_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:10000])
            logger.info("디버깅용 HTML이 logs/coolenjoy_debug.html에 저장되었습니다")
            return deals, should_stop

        logger.debug(f"{len(articles)}개 게시글 발견")

        # 중복 URL 제거
        seen_urls = set()
        unique_articles = []
        for article in articles:
            link = article.select_one('a.na-subject')
            if not link:
                continue
            href = link.get('href', '')
            if href and href not in seen_urls:
                seen_urls.add(href)
                unique_articles.append(article)

        for article in unique_articles:
            try:
                deal = self._parse_article(page, article)
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

    def _parse_article(self, page: Page, article) -> Optional[Dict]:
        """게시글 파싱"""
        try:
            # URL 추출
            link = article.select_one('a.na-subject')
            if not link:
                return None

            href = link.get('href', '')
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

            if url in self.BLACKLISTED_URLS:
                return None

            # 제목 추출 (목록)
            title_elem = article.select_one('a.na-subject')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            category = self._extract_category(article)

            # 날짜 + 이미지 주소 (상세 페이지로 진입)
            post_date, image_url = self._extract_detail(page, url)

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

    def _extract_detail(self, page: Page, url: str) -> tuple:
        """상세 페이지로 진입하여 날짜와 이미지를 한번에 추출"""
        post_date = None
        image_url = None

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), 'html.parser')

            # 이미지: a.view_image > img
            img_elem = soup.select_one('a.view_image > img')
            if img_elem:
                src = img_elem.get('src', '')
                if src:
                    if src.startswith('//'):
                        image_url = 'https:' + src
                    elif src.startswith('/'):
                        image_url = self.BASE_URL + src
                    elif src.startswith('http'):
                        image_url = src
                    else:
                        image_url = self.BASE_URL + '/' + src

            # 날짜: time 태그
            # 형식: 2026.02.01 08:44
            time_elem = soup.select_one('time')
            if time_elem:
                date_text = time_elem.get_text(strip=True)
                if date_text:
                    try:
                        # 2026.02.01 08:44 → 2026-02-01 08:44:00
                        dt = datetime.strptime(date_text, '%Y.%m.%d %H:%M')
                        post_date = dt.strftime('%Y-%m-%d %H:%M:%S')
                        logger.debug(f"날짜 추출 성공: {post_date}")
                    except ValueError as e:
                        logger.debug(f"날짜 파싱 실패: {date_text} / {e}")
            else:
                logger.debug(f"날짜 요소를 찾을 수 없음: {url}")

        except Exception as e:
            logger.debug(f"상세 페이지 파싱 실패 ({url}): {str(e)}")

        return post_date, image_url

    def _extract_category(self, article) -> Optional[str]:
        """카테고리 추출"""
        try:
            elem = article.select_one('#abcd')
            if not elem:
                return None

            category = elem.get_text(strip=True)
            if not category:
                return None

            return category

        except Exception as e:
            logger.debug(f"카테고리 추출 실패: {str(e)}")
            return None

if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    crawler = CoolenjoyCrawler()
    deals = crawler.crawl(max_pages=1)

    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")