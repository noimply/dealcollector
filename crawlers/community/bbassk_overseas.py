import logging
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class BbssakOverseasCrawler:
    """빠삭 핫딜 크롤러"""

    BASE_URL = "https://bbasak.com"
    HOTDEAL_URL = "https://bbasak.com/bbs/board.php?bo_table=bbasak2"
    COMMUNITY_ID = 81

    BLACKLISTED_URLS = []

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def crawl(self, max_pages: int = 1, last_url: str = None) -> List[Dict]:
        """
        빠삭 국내 핫딜 크롤링

        Args:
            max_pages: 크롤링할 최대 페이지 수
            last_url: 이전 크롤링의 마지막 URL (이 URL을 만나면 중단)

        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"빠삭 크롤링 시작 (최대 {max_pages}페이지)")
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

        logger.info(f"빠삭 국내 크롤링 완료: 총 {len(deals)}개 딜 수집")
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
            url = f"{self.HOTDEAL_URL}&page={page_num + 1}"

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop

        soup = BeautifulSoup(page.content(), 'html.parser')

        # table.t1 기준으로 목록 선택
        articles = soup.select('table.t1 tbody tr')

        if not articles:
            logger.warning("게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/bbassak_korea_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:10000])
            logger.info("디버깅용 HTML이 logs/bbassak_korea_debug.html에 저장되었습니다")
            return deals, should_stop

        logger.debug(f"{len(articles)}개 table.t1 발견")

        for article in articles:
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
            # 제목 및 URL 추출
            title_elem = article.select_one('td.tit')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # URL 추출
            link = title_elem.select_one('a')
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

            # 블랙리스트
            if url in self.BLACKLISTED_URLS:
                return None

            # 이미지 URL 추출
            image_url = self._extract_image_url(article)

            # 카테고리 추출 (목록 페이지)
            category = self._extract_category(article)

            # 작성일 추출 (개별 게시글 페이지로 진입)
            post_date = self._extract_date(page, url)

            # deal 생성
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

    def _extract_category(self, article) -> str:
        """목록 페이지에서 카테고리 추출"""
        try:
            category_elem = article.select_one('td:nth-child(2)')
            if not category_elem:
                return ''

            cat_text = category_elem.get_text(strip=True)
            if not cat_text:
                return ''
        
            # 정규화
            cat_text = cat_text.strip().strip(',')

            return f"{cat_text}"

        except Exception as e:
            logger.debug(f"카테고리 추출 실패: {str(e)}")
            return ''

    def _extract_date(self, page: Page, url: str) -> Optional[str]:
        """개별 게시글 페이지로 진입하여 작성일 추출"""
        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(1500)

            soup = BeautifulSoup(page.content(), 'html.parser')

            # div.view_title.s_title > div > p.info > span:nth-child(2) > span:nth-child(1)
            date_elem = soup.select_one(
                'div.view_title.s_title > div > p.info > span:nth-child(2) > span:nth-child(1)'
            )

            if not date_elem:
                logger.debug(f"날짜 요소를 찾을 수 없음: {url}")
                return None

            raw_date = date_elem.get_text(strip=True)
            if not raw_date:
                return None

            # 형식 변환: 26-02-01 11:05 → 2026-02-01 11:05:00
            if re.match(r'\d{2}-\d{2}-\d{2}', raw_date):
                parts = raw_date.split(' ')
                date_part = parts[0].split('-')  # 하이픈으로 split
                time_part = parts[1] if len(parts) > 1 else '00:00'
                # 초가 없으면 추가
                if len(time_part.split(':')) == 2:
                    time_part += ':00'

                return f"20{date_part[0]}-{date_part[1]}-{date_part[2]} {time_part}"

            return raw_date

        except Exception as e:
            logger.debug(f"작성일 추출 실패 ({url}): {str(e)}")
            return None

    def _extract_image_url(self, article) -> Optional[str]:
        """이미지 URL 추출"""
        try:
            img_elem = article.select_one('td:nth-child(4) > a > img')

            if not img_elem:
                return None

            src = img_elem.get('src', '')
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    crawler = BbssakOverseasCrawler()
    deals = crawler.crawl(max_pages=1)

    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")