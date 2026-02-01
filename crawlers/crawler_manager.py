"""크롤러 매니저 - 여러 커뮤니티 크롤러를 통합 관리"""
import logging
from typing import List, Dict
from config import CRAWL_CONFIG, DUPLICATE_CHECK, CLEANUP_CONFIG

logger = logging.getLogger(__name__)


class CrawlerManager:
    """크롤러 매니저 - 모든 크롤러를 자동으로 실행"""
    
    def __init__(self, supabase):
        self.supabase = supabase
        self.crawlers = {}
        self._register_crawlers()
    
    def _register_crawlers(self):
        """크롤러 등록"""
        from community.ppomppu import PpomppuCrawler
        from community.clien import ClienCrawler
        from community.ruliweb import RuliwebCrawler
        from community.quasarzone import QuasarzoneCrawler
        
        # 크롤러 등록 (config.py의 키와 매칭)
        self.crawlers = {
            'ppomppu': PpomppuCrawler(),
            'clien': ClienCrawler(),
            'ruliweb' : RuliwebCrawler(),
            'quasarzone': QuasarzoneCrawler(),
            # 새 크롤러 추가 시 여기에만 추가하면 됨
            # 'ruliweb': RuliwebCrawler(),
            # 'quasarzone': QuasarzoneCrawler(),
        }
        
        logger.info(f"총 {len(self.crawlers)}개 크롤러 등록 완료")
    
    def crawl_all(self, filter_duplicates_fn, save_deals_fn, cleanup_fn):
        """
        모든 크롤러 실행
        
        Args:
            filter_duplicates_fn: 중복 필터링 함수
            save_deals_fn: DB 저장 함수
            cleanup_fn: 정리 함수
        """
        total_crawled = 0
        total_saved = 0
        
        for name, crawler in self.crawlers.items():
            # config에 해당 커뮤니티 설정이 없으면 스킵
            if name not in CRAWL_CONFIG:
                logger.warning(f"{name}: config에 설정이 없어 스킵합니다")
                continue
            
            try:
                config = CRAWL_CONFIG[name]
                logger.info(f"{name} 크롤링 시작...")
                
                # 크롤링
                deals = crawler.crawl(max_pages=config['max_pages'])
                
                if not deals:
                    logger.warning(f"{name}: 수집된 딜이 없습니다")
                    continue
                
                total_crawled += len(deals)
                logger.info(f"{name}에서 {len(deals)}개 딜 수집")
                
                # 중복 필터링
                if DUPLICATE_CHECK['enabled']:
                    filtered_deals = filter_duplicates_fn(
                        deals,
                        self.supabase,
                        similarity_threshold=DUPLICATE_CHECK['similarity_threshold']
                    )
                else:
                    filtered_deals = deals
                
                # DB 저장
                saved_count = save_deals_fn(filtered_deals, self.supabase)
                total_saved += saved_count
                logger.info(f"{name}: {saved_count}개 딜 저장 완료")
                
                # 오래된 딜 정리
                if CLEANUP_CONFIG['enabled']:
                    cleanup_fn(
                        self.supabase,
                        community_id=config['community_id'],
                        keep_count=config['keep_count']
                    )
                
            except Exception as e:
                logger.error(f"{name} 크롤링 실패: {str(e)}", exc_info=True)
                # 한 커뮤니티 실패해도 계속 진행
                continue
        
        logger.info(f"전체 크롤링 완료: 수집 {total_crawled}개 / 저장 {total_saved}개")
        return total_crawled, total_saved
    
    def crawl_community(self, community_name: str, filter_duplicates_fn, save_deals_fn, cleanup_fn):
        """
        특정 커뮤니티만 크롤링
        
        Args:
            community_name: 크롤링할 커뮤니티 이름 ('ppomppu', 'clien' 등)
            filter_duplicates_fn: 중복 필터링 함수
            save_deals_fn: DB 저장 함수
            cleanup_fn: 정리 함수
        """
        if community_name not in self.crawlers:
            logger.error(f"{community_name}: 등록되지 않은 크롤러입니다")
            return 0
        
        if community_name not in CRAWL_CONFIG:
            logger.error(f"{community_name}: config에 설정이 없습니다")
            return 0
        
        try:
            crawler = self.crawlers[community_name]
            config = CRAWL_CONFIG[community_name]
            
            logger.info(f"{community_name} 크롤링 시작...")
            
            # 크롤링
            deals = crawler.crawl(max_pages=config['max_pages'])
            
            if not deals:
                logger.warning(f"{community_name}: 수집된 딜이 없습니다")
                return 0
            
            logger.info(f"{community_name}에서 {len(deals)}개 딜 수집")
            
            # 중복 필터링
            if DUPLICATE_CHECK['enabled']:
                filtered_deals = filter_duplicates_fn(
                    deals,
                    self.supabase,
                    similarity_threshold=DUPLICATE_CHECK['similarity_threshold']
                )
            else:
                filtered_deals = deals
            
            # DB 저장
            saved_count = save_deals_fn(filtered_deals, self.supabase)
            logger.info(f"{community_name}: {saved_count}개 딜 저장 완료")
            
            # 오래된 딜 정리
            if CLEANUP_CONFIG['enabled']:
                cleanup_fn(
                    self.supabase,
                    community_id=config['community_id'],
                    keep_count=config['keep_count']
                )
            
            return saved_count
            
        except Exception as e:
            logger.error(f"{community_name} 크롤링 실패: {str(e)}", exc_info=True)
            return 0
