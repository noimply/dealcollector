import os
import logging
from datetime import datetime, timedelta
from dotenv import load_dotenv
from supabase_client import SupabaseClient
from utils.duplicate_checker import DealDuplicateChecker
from config import DUPLICATE_CHECK
from crawler_manager import CrawlerManager

# .env 파일 로드
load_dotenv()

# 로깅 설정
os.makedirs('logs', exist_ok=True)
root_logger = logging.getLogger()
root_logger.setLevel(logging.INFO)

formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')

file_handler = logging.FileHandler('logs/crawler.log')
file_handler.setLevel(logging.ERROR)
file_handler.setFormatter(formatter)

stream_handler = logging.StreamHandler()
stream_handler.setLevel(logging.INFO)
stream_handler.setFormatter(formatter)

if root_logger.hasHandlers():
    root_logger.handlers.clear()

root_logger.addHandler(file_handler)
root_logger.addHandler(stream_handler)
logger = logging.getLogger(__name__)


def cleanup_old_deals(supabase, community_id: int, keep_count: int = 200):
    try:
        result = supabase.table('deals')\
            .select('id', count='exact')\
            .eq('community_id', community_id)\
            .execute()
        
        total_count = result.count
        
        if total_count <= keep_count:
            return
        
        delete_count = total_count - keep_count
        
        deals = supabase.table('deals')\
            .select('created_at')\
            .eq('community_id', community_id)\
            .order('created_at', desc=True)\
            .limit(keep_count)\
            .execute()
        
        if not deals.data or len(deals.data) < keep_count:
            return
        
        cutoff_time = deals.data[-1]['created_at']
        
        delete_result = supabase.table('deals')\
            .delete()\
            .eq('community_id', community_id)\
            .lt('created_at', cutoff_time)\
            .execute()
        
        deleted_count = len(delete_result.data) if delete_result.data else 0
        
    except Exception as e:
        logger.error(f"커뮤니티 {community_id} 정리 실패: {str(e)}", exc_info=True)


def filter_duplicates_by_title(deals: list, supabase, similarity_threshold: float = 0.85) -> list:
    checker = DealDuplicateChecker()
    filtered_deals = []
    
    try:
        check_days = DUPLICATE_CHECK['check_days']
        days_ago = (datetime.now() - timedelta(days=check_days)).isoformat()
        existing_deals = supabase.table('deals')\
            .select('title, url')\
            .gte('created_at', days_ago)\
            .execute()
        
        existing_titles = {deal['url']: deal['title'] for deal in existing_deals.data}
        
    except Exception as e:
        logger.warning(f"기존 딜 조회 실패: {str(e)}")
        existing_titles = {}
    
    for deal in deals:
        if deal['url'] in existing_titles:
            continue
        
        is_duplicate = False
        for existing_title in existing_titles.values():
            if checker.is_duplicate(deal['title'], existing_title, similarity_threshold):
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_deals.append(deal)
    
    return filtered_deals


def save_deals_to_supabase(deals: list, supabase):
    saved_count = 0
    duplicate_count = 0
    error_count = 0
    
    # date 기준으로 정렬 (오래된 글부터)
    deals_sorted = sorted(deals, key=lambda x: x.get('posted_at', ''))    
    for deal in deals_sorted:
        try:
            result = supabase.table('deals').insert(deal).execute()
            saved_count += 1
            
        except Exception as e:
            error_msg = str(e)
            if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                duplicate_count += 1
            else:
                error_count += 1
    
    logger.info(f"저장 완료: {saved_count}개 | 중복: {duplicate_count}개 | 오류: {error_count}개")
    return saved_count


def main():
    logger.info("=" * 50)
    logger.info("크롤링 시작...")
    logger.info(f"실행 시간: {datetime.now()}")
    
    try:
        # Supabase 클라이언트 초기화
        supabase = SupabaseClient.get_client()
        # 크롤러 매니저 생성 및 모든 크롤러 실행
        manager = CrawlerManager(supabase)
        total_crawled, total_saved = manager.crawl_all(
            filter_duplicates_fn=filter_duplicates_by_title,
            save_deals_fn=save_deals_to_supabase,
            cleanup_fn=cleanup_old_deals
        )
        logger.info("=" * 50)
        logger.info(f"전체 크롤링 완료! 수집: {total_crawled}개 / 저장: {total_saved}개")
        
    except Exception as e:
        logger.error(f"크롤링 실패: {str(e)}", exc_info=True)
        raise


if __name__ == '__main__':
    main()