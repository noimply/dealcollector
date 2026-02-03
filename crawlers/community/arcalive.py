import logging
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re
from baseCrawler import BaseCrawler

logger = logging.getLogger(__name__)


class ArcaliveCrawler(BaseCrawler):
    """아카라이브 핫딜 크롤러"""

    BASE_URL = "https://arca.live"
    HOTDEAL_URL = "https://arca.live/b/hotdeal"
    COMMUNITY_ID = 60

    BLACKLISTED_URLS = []

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def crawl(self, max_pages: int = 1, last_url: str = None) -> List[Dict]:
        """
        아카라이브 핫딜 크롤링

        Args:
            max_pages: 크롤링할 최대 페이지 수
            last_url: 이전 크롤링의 마지막 URL (이 URL을 만나면 중단)

        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"아카라이브 크롤링 시작 (최대 {max_pages}페이지)")
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

        logger.info(f"아카라이브 크롤링 완료: 총 {len(deals)}개 딜 수집")
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
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)  # Next.js 클라이언트 렌더링 대기
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop

        soup = BeautifulSoup(page.content(), 'html.parser')

        # 아카라이브 게시글 목록: a[href*="/b/hotdeal/"] 중 숫자 ID가 포함된 링크
        articles = [
            a for a in soup.select('a[href]')
            if re.search(r'/b/hotdeal/\d+', a.get('href', ''))
        ]

        if not articles:
            logger.warning("게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/arcalive_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:10000])
            logger.info("디버깅용 HTML이 logs/arcalive_debug.html에 저장되었습니다")
            return deals, should_stop

        logger.debug(f"{len(articles)}개 게시글 링크 발견")

        # 중복 URL 제거 (같은 글에 여러 링크가 올 수 있음)
        seen_urls = set()
        unique_articles = []
        for article in articles:
            href = article.get('href', '')
            match = re.search(r'/b/hotdeal/(\d+)', href)
            if match and match.group(1) not in seen_urls:
                seen_urls.add(match.group(1))
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
            href = article.get('href', '')
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

            # 제목 추출 (목록)
            title = article.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # 이미지 URL 추출 (목록)
            image_url = self._extract_image_url(article)

            # 날짜 + 카테고리 추출 (상세 페이지로 진입)
            post_date, category = self._extract_detail(page, url)
            if not post_date:
                return None

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
        """상세 페이지로 진입하여 날짜와 카테고리를 한번에 추출"""
        post_date = None
        category = ''

        try:
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), 'html.parser')

            # 카테고리: class="badge badge-success category-badge"
            category_elem = soup.select_one('.badge.badge-success.category-badge')
            if category_elem:
                cat_text = category_elem.get_text(strip=True)
                if cat_text:
                    # [] 제거 후 다시 감싸기
                    cat_text = cat_text.strip('[]').strip()
                    if cat_text:
                        category = f"{cat_text}"
            else:
                logger.debug(f"카테고리 요소를 찾을 수 없음: {url}")

            # 날짜: <time datetime="2026-02-01T11:49:20.000Z">2026-02-01 20:49:20</time>
            # 텍스트 콘텐츠가 이미 KST로 변환된 값이므로 직접 사용
            time_elem = soup.select_one('time[datetime]')
            if time_elem:
                date_text = time_elem.get_text(strip=True)
                if date_text:
                    post_date = date_text
            else:
                logger.debug(f"날짜 요소를 찾을 수 없음: {url}")

        except Exception as e:
            logger.debug(f"상세 페이지 파싱 실패 ({url}): {str(e)}")

        return post_date, category

    def _extract_image_url(self, article) -> Optional[str]:
        """이미지 URL 추출"""
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


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    crawler = ArcaliveCrawler()
    deals = crawler.crawl(max_pages=1)

    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")