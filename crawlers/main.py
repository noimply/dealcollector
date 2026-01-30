import os
import logging
from datetime import datetime
from dotenv import load_dotenv
from supabase_client import SupabaseClient

# .env 파일 로드
load_dotenv()

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('logs/crawler.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

def main():
    logger.info("=" * 50)
    logger.info("크롤링 시작...")
    logger.info(f"실행 시간: {datetime.now()}")
    
    try:
        # Supabase 클라이언트 테스트
        supabase = SupabaseClient.get_client()
        logger.info("Supabase 연결 성공!")
        
        # TODO: 크롤링 로직 추가
        
        logger.info("크롤링 완료!")
        
    except Exception as e:
        logger.error(f"크롤링 실패: {str(e)}", exc_info=True)
        raise

if __name__ == '__main__':
    main()