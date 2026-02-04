import logging
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from playwright_stealth import stealth_sync
from bs4 import BeautifulSoup
import re
from baseCrawler import BaseCrawler

logger = logging.getLogger(__name__)

class ArcaliveCrawler(BaseCrawler):
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
        logger.info(f"### 아카라이브 크롤링 시작")
        if last_url:
            logger.info(f"### 아카라이브 중복 체크 URL: {last_url}")
        
        deals = []
        should_stop = False  # 중단 플래그

        with sync_playwright() as p:
            browser = p.chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-blink-features=AutomationControlled',
                    '--disable-dev-shm-usage',
                ]
            )
            context = browser.new_context(
                user_agent=self.user_agent,
                viewport={'width': 1920, 'height': 1080},
                locale='ko-KR',
            )
            # Context Page 생성
            page = context.new_page()
            # Stealth 적용
            stealth_sync(page)

            try:
                for page_num in range(max_pages):
                    if should_stop:
                        logger.info(f"### 아카라이브 이전 크롤링 지점 도달 - 크롤링 중단")
                        break
                    
                    page_deals, stop_flag = self._crawl_page(page, page_num, last_url)
                    deals.extend(page_deals)
                    logger.info(f"### 아카라이브 {len(page_deals)}개 딜 수집")

                    if stop_flag:
                        should_stop = True

            except Exception as e:
                logger.error(f"### 아카라이브 크롤링 중 오류 발생: {str(e)}", exc_info=True)
            finally:
                browser.close()

        logger.info(f"### 아카라이브 크롤링 완료: 총 {len(deals)}개 딜 수집")
        return deals

    def _crawl_page(self, page: Page, page_num: int, last_url: str = None) -> tuple:
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
            logger.error(f"### 아카라이브 페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop

        soup = BeautifulSoup(page.content(), 'html.parser')

        # 아카라이브 게시글 목록: a[href*="/b/hotdeal/"] 중 숫자 ID가 포함된 링크
        articles = [
            a for a in soup.select('a[href]')
            if re.search(r'/b/hotdeal/\d+', a.get('href', ''))
        ]

        if not articles:
            logger.warning("### 아카라이브 게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/arcalive_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:10000])
            return deals, should_stop

        logger.debug(f"### 아카라이브 {len(articles)}개 게시글 링크 발견")

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
                        logger.info(f"### 아카라이브 이전 크롤링 지점 발견: {last_url}")
                        should_stop = True
                        break
                    
                    deals.append(deal)
            except Exception as e:
                logger.warning(f"### 아카라이브 게시글 파싱 실패: {str(e)}")
                continue

        return deals, should_stop

    def _parse_article(self, page: Page, article) -> Optional[Dict]:
        try:
            # URL 추출
            href = article.get('href', '')
            if not href:
                logger.warning(f"### 아카라이브 게시글 URL 추출 실패: {str(e)}")
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
                logger.warning(f"### 아카라이브 제목 추출 실패: {title}")
                return None

            # 이미지 URL 추출 (목록)
            image_url = self._extract_image_url(article)

            # 날짜 + 카테고리 추출 (상세 페이지로 진입)
            post_date, category = self._extract_detail(page, url)
            if not post_date:
                logger.warning(f"### 아카라이브 날짜 추출 실패: {post_date}")
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
            logger.debug(f"### 아카라이브 게시글 파싱 중 오류: {str(e)}")
            return None

    def _extract_detail(self, page: Page, url: str) -> tuple:
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

            # 날짜: <time datetime="2026-02-01T11:49:20.000Z">2026-02-01 20:49:20</time>
            # 텍스트 콘텐츠가 이미 KST로 변환된 값이므로 직접 사용
            time_elem = soup.select_one('time[datetime]')
            if time_elem:
                date_text = time_elem.get_text(strip=True)
                if date_text:
                    post_date = date_text

        except Exception as e:
            logger.debug(f"### 아카라이브 상세 페이지 파싱 실패 ({url}): {str(e)}")

        return post_date, category

    def _extract_image_url(self, article) -> Optional[str]:
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
            return None