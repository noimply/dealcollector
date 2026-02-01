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
    """특정 커뮤니티의 오래된 딜 삭제 (최신 N개만 유지)"""
    try:
        result = supabase.table('deals')\
            .select('id', count='exact')\
            .eq('community_id', community_id)\
            .execute()
        
        total_count = result.count
        
        if total_count <= keep_count:
            logger.info(f"커뮤니티 {community_id}: {total_count}개 딜 존재 (정리 불필요)")
            return
        
        delete_count = total_count - keep_count
        logger.info(f"커뮤니티 {community_id}: {total_count}개 중 오래된 {delete_count}개 삭제 예정")
        
        deals = supabase.table('deals')\
            .select('created_at')\
            .eq('community_id', community_id)\
            .order('created_at', desc=True)\
            .limit(keep_count)\
            .execute()
        
        if not deals.data or len(deals.data) < keep_count:
            logger.warning(f"커뮤니티 {community_id}: keep_count({keep_count})보다 딜이 적습니다")
            return
        
        cutoff_time = deals.data[-1]['created_at']
        
        delete_result = supabase.table('deals')\
            .delete()\
            .eq('community_id', community_id)\
            .lt('created_at', cutoff_time)\
            .execute()
        
        deleted_count = len(delete_result.data) if delete_result.data else 0
        logger.info(f"커뮤니티 {community_id}: {deleted_count}개 딜 삭제 완료")
        
    except Exception as e:
        logger.error(f"커뮤니티 {community_id} 정리 실패: {str(e)}", exc_info=True)


def filter_duplicates_by_title(deals: list, supabase, similarity_threshold: float = 0.85) -> list:
    """제목 유사도 기반으로 중복 필터링"""
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
        logger.info(f"최근 {check_days}일간 {len(existing_titles)}개 딜 로드")
        
    except Exception as e:
        logger.warning(f"기존 딜 조회 실패: {str(e)}")
        existing_titles = {}
    
    for deal in deals:
        if deal['url'] in existing_titles:
            logger.debug(f"URL 중복: {deal['title'][:30]}...")
            continue
        
        is_duplicate = False
        for existing_title in existing_titles.values():
            if checker.is_duplicate(deal['title'], existing_title, similarity_threshold):
                logger.debug(f"제목 유사 중복: {deal['title'][:30]}... ≈ {existing_title[:30]}...")
                is_duplicate = True
                break
        
        if not is_duplicate:
            filtered_deals.append(deal)
    
    logger.info(f"중복 필터링: {len(deals)}개 → {len(filtered_deals)}개")
    return filtered_deals


def save_deals_to_supabase(deals: list, supabase):
    """딜 정보를 Supabase에 저장"""
    saved_count = 0
    duplicate_count = 0
    error_count = 0
    
    # date 기준으로 정렬 (오래된 글부터)
    deals_sorted = sorted(deals, key=lambda x: x.get('posted_at', ''))
    logger.info(f"date 기준 정렬 완료 (오래된 글부터 저장)")
    
    for deal in deals_sorted:
        try:
            result = supabase.table('deals').insert(deal).execute()
            saved_count += 1
            logger.debug(f"저장 완료: {deal['title'][:30]}...")
            
        except Exception as e:
            error_msg = str(e)
            if 'duplicate' in error_msg.lower() or 'unique' in error_msg.lower():
                duplicate_count += 1
                logger.debug(f"중복 URL: {deal['url']}")
            else:
                error_count += 1
                logger.warning(f"저장 실패: {deal['title'][:30]}... - {error_msg}")
    
    logger.info(f"저장 완료: {saved_count}개 | 중복: {duplicate_count}개 | 오류: {error_count}개")
    return saved_count


def main():
    logger.info("=" * 50)
    logger.info("크롤링 시작...")
    logger.info(f"실행 시간: {datetime.now()}")
    
    try:
        # Supabase 클라이언트 초기화
        supabase = SupabaseClient.get_client()
        logger.info("Supabase 연결 성공!")
        
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