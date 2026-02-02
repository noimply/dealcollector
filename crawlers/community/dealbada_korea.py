import logging
from typing import List, Dict, Optional
from playwright.sync_api import sync_playwright, Page
from bs4 import BeautifulSoup
import re

logger = logging.getLogger(__name__)


class DealbadaKoreaCrawler:
    """딜바다 국내 핫딜 크롤러"""

    BASE_URL = "https://www.dealbada.com"
    HOTDEAL_URL = "https://www.dealbada.com/bbs/board.php?bo_table=deal_domestic"
    COMMUNITY_ID = 90

    BLACKLISTED_URLS = []

    def __init__(self):
        self.user_agent = (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) '
            'Chrome/120.0.0.0 Safari/537.36'
        )

    def crawl(self, max_pages: int = 1, last_url: str = None) -> List[Dict]:
        """
        딜바다 국내 핫딜 크롤링

        Args:
            max_pages: 크롤링할 최대 페이지 수

        Returns:
            크롤링된 딜 정보 리스트
        """
        logger.info(f"딜바다 국내 크롤링 시작 (최대 {max_pages}페이지)")
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

        logger.info(f"딜바다 국내 크롤링 완료: 총 {len(deals)}개 딜 수집")
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
            page.goto(url, wait_until="networkidle", timeout=60000)
            page.wait_for_timeout(3000)
        except Exception as e:
            logger.error(f"페이지 로딩 실패: {url} - {str(e)}")
            return deals, should_stop

        soup = BeautifulSoup(page.content(), 'html.parser')

        # 딜바다 국내 게시글 목록: div > table > tbody > tr:not(.bo_notice):not(.best_article)
        articles = soup.select('div > table > tbody > tr:not(.bo_notice):not(.best_article)')

        if not articles:
            logger.warning("게시글을 찾을 수 없습니다. HTML 구조 확인 필요")
            with open('logs/dealbada_korea_debug.html', 'w', encoding='utf-8') as f:
                f.write(soup.prettify()[:10000])
            logger.info("디버깅용 HTML이 logs/dealbada_korea_debug.html에 저장되었습니다")
            return deals, should_stop

        logger.debug(f"{len(articles)}개 게시글 발견")

        # 중복 URL 제거
        seen_urls = set()
        unique_articles = []
        for article in articles:
            link = article.select_one('td.td_subject > a')
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
            link = article.select_one('td.td_subject a')
            if not link:
                return None

            href = link.get('href', '')
            if not href:
                return None

            logger.debug(f"원본 href: {href}")

            # URL 정규화 (중복 방지)
            if href.startswith('http'):
                # 이미 절대 URL
                url = href
            elif href.startswith('//'):
                # 프로토콜 없는 절대 URL
                url = 'https:' + href
            elif href.startswith('/'):
                # 상대 경로
                url = self.BASE_URL + href
            else:
                # 기타 (상대 경로)
                url = self.BASE_URL + '/' + href

            logger.debug(f"최종 url: {url}")

            if url in self.BLACKLISTED_URLS:
                return None

            # 제목 추출 (목록)
            title_elem = article.select_one('td.td_subject')
            if not title_elem:
                return None

            title = title_elem.get_text(strip=True)
            if not title or len(title) < 3:
                return None

            # 이미지 URL 추출 (목록)
            image_url = self._extract_image_url(article)

            # 카테고리
            category = self._extract_category(article)

            # 날짜 + 카테고리 추출 (상세 페이지로 진입)
            post_date = self._extract_detail(page, url)

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

    

    def _extract_detail(self, page: Page, url: str) -> str:
        """상세 페이지로 진입하여 날짜와 카테고리를 한번에 추출"""
        post_date = None

        try:
            page.goto(url, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(2000)

            soup = BeautifulSoup(page.content(), 'html.parser')

            # 디버그: 전체 HTML 저장 (첫 번째 게시글만)
            import os
            debug_file = 'logs/dealbada_detail_debug.html'
            if not os.path.exists(debug_file):
                with open(debug_file, 'w', encoding='utf-8') as f:
                    f.write(soup.prettify())
                logger.info(f"디버그용 상세 HTML 저장: {debug_file}")

            # #bo_v_info 전체 출력
            bo_v_info = soup.select_one('#bo_v_info')
            if bo_v_info:
                logger.debug(f"#bo_v_info 발견")
                all_spans = bo_v_info.select('span')
                logger.debug(f"#bo_v_info 내부 span 개수: {len(all_spans)}")
                for i, span in enumerate(all_spans, 1):
                    logger.debug(f"  span[{i}]: class={span.get('class')} | text={span.get_text(strip=True)}")
            else:
                logger.warning("#bo_v_info를 찾을 수 없음")

            # 날짜: span 텍스트에서 "2026-02-02 10:44:44" 형식 추출
            if bo_v_info:
                all_spans = bo_v_info.select('span')
                for span in all_spans:
                    text = span.get_text(strip=True)
                    # YYYY-MM-DD HH:MM:SS 패턴 찾기
                    date_match = re.search(r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})', text)
                    if date_match:
                        post_date = date_match.group(1)
                        break

            if not post_date:
                logger.warning(f"날짜를 찾을 수 없음: {url}")

        except Exception as e:
            logger.error(f"상세 페이지 파싱 실패 ({url}): {str(e)}", exc_info=True)

        return post_date

    def _extract_image_url(self, article) -> Optional[str]:
        """이미지 URL 추출"""
        try:
            # td.td_img 내부의 img 태그 또는 style 속성의 background-image
            img_td = article.select_one('td.td_img')
            if not img_td:
                return None

            # img 태그 우선
            img_elem = img_td.select_one('img')
            if img_elem:
                src = img_elem.get('src', '') or img_elem.get('data-src', '')
                if src:
                    if src.startswith('//'):
                        return 'https:' + src
                    elif src.startswith('/'):
                        return self.BASE_URL + src
                    elif src.startswith('http'):
                        return src
                    else:
                        return self.BASE_URL + '/' + src

            # style 속性의 background-image 확인
            style = img_td.get('style', '')
            if 'background-image' in style:
                match = re.search(r'url\(["\']?([^"\']+)["\']?\)', style)
                if match:
                    src = match.group(1)
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


    def _extract_category(self, article) -> str:
        """카테고리 추출"""
        try:
            category = article.select_one('td.td_cate').get_text(strip=True)
            if category:
                return category

            return None

        except Exception as e:
            logger.debug(f"카테고리 추출 실패: {str(e)}")
            return ''


if __name__ == '__main__':
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    crawler = DealbadaKoreaCrawler()
    deals = crawler.crawl(max_pages=1)

    print(f"\n총 {len(deals)}개 딜 수집")
    for i, deal in enumerate(deals[:5], 1):
        print(f"\n{i}. {deal['title']}")
        print(f"   카테고리: {deal['category']}")
        print(f"   작성일: {deal.get('posted_at', 'None')}")
        print(f"   이미지: {deal.get('image_url', 'None')}")
        print(f"   URL: {deal['url']}")