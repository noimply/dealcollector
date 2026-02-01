"""딜 중복 체크 유틸리티"""
import re
import hashlib
from typing import Optional
from difflib import SequenceMatcher
import logging

logger = logging.getLogger(__name__)


class DealDuplicateChecker:
    """딜 중복 체크를 위한 유틸리티 클래스"""
    
    @staticmethod
    def normalize_title(title: str) -> str:
        """
        제목 정규화
        - 카테고리 태그 제거 ([가전/가구] 등)
        - 특수문자, 공백 제거
        - 소문자 변환
        """
        # 카테고리 태그 제거
        title = re.sub(r'\[.*?\]', '', title)
        title = re.sub(r'【.*?】', '', title)
        
        # 가격 정보 제거 (선택사항)
        title = re.sub(r'\d+[\,\d]*원', '', title)
        title = re.sub(r'\d+만원', '', title)
        
        # 특수문자, 공백 제거
        title = re.sub(r'[^\w가-힣0-9]', '', title)
        
        # 소문자 변환 및 공백 제거
        return title.lower().strip()
    
    @staticmethod
    def get_title_hash(title: str) -> str:
        """제목 정규화 후 해시 생성"""
        normalized = DealDuplicateChecker.normalize_title(title)
        return hashlib.md5(normalized.encode()).hexdigest()[:16]  # 16자리만 사용
    
    @staticmethod
    def calculate_similarity(title1: str, title2: str) -> float:
        """두 제목의 유사도 계산 (0.0 ~ 1.0)"""
        clean1 = DealDuplicateChecker.normalize_title(title1)
        clean2 = DealDuplicateChecker.normalize_title(title2)
        
        if not clean1 or not clean2:
            return 0.0
        
        return SequenceMatcher(None, clean1, clean2).ratio()
    
    @staticmethod
    def is_duplicate(title1: str, title2: str, threshold: float = 0.85) -> bool:
        """
        두 제목이 중복인지 확인
        
        Args:
            title1: 첫 번째 제목
            title2: 두 번째 제목
            threshold: 유사도 임계값 (0.85 = 85% 유사)
            
        Returns:
            중복 여부
        """
        similarity = DealDuplicateChecker.calculate_similarity(title1, title2)
        return similarity >= threshold
    
    @staticmethod
    def extract_product_keywords(title: str) -> set:
        """
        제목에서 핵심 키워드 추출
        브랜드명, 제품명 등
        """
        normalized = DealDuplicateChecker.normalize_title(title)
        
        # 한글 단어와 영문 단어 추출
        korean_words = re.findall(r'[가-힣]{2,}', normalized)
        english_words = re.findall(r'[a-z0-9]{2,}', normalized)
        
        return set(korean_words + english_words)
    
    @staticmethod
    def is_duplicate_by_keywords(title1: str, title2: str, min_common_keywords: int = 3) -> bool:
        """
        핵심 키워드 기반 중복 체크
        공통 키워드가 min_common_keywords 이상이면 중복으로 판단
        """
        keywords1 = DealDuplicateChecker.extract_product_keywords(title1)
        keywords2 = DealDuplicateChecker.extract_product_keywords(title2)
        
        common_keywords = keywords1 & keywords2
        
        return len(common_keywords) >= min_common_keywords


# 테스트 예제
if __name__ == '__main__':
    checker = DealDuplicateChecker()
    
    # 테스트 케이스
    test_cases = [
        ("[가전/가구] 삼성 에어프라이어 50% 할인", "[디지털] 삼성 에어프라이어 특가"),
        ("아이폰 15 Pro 1,200,000원", "아이폰15프로 120만원 핫딜"),
        ("LG 냉장고 특가", "삼성 냉장고 할인"),
    ]
    
    print("=== 중복 체크 테스트 ===\n")
    
    for title1, title2 in test_cases:
        hash1 = checker.get_title_hash(title1)
        hash2 = checker.get_title_hash(title2)
        similarity = checker.calculate_similarity(title1, title2)
        is_dup = checker.is_duplicate(title1, title2)
        is_dup_kw = checker.is_duplicate_by_keywords(title1, title2)
        
        print(f"제목1: {title1}")
        print(f"제목2: {title2}")
        print(f"해시1: {hash1}")
        print(f"해시2: {hash2}")
        print(f"유사도: {similarity:.2%}")
        print(f"중복(유사도): {is_dup}")
        print(f"중복(키워드): {is_dup_kw}")
        print("-" * 50)
