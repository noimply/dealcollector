import os
from supabase import create_client, Client
from typing import Optional
from dotenv import load_dotenv

# .env 파일 로드
load_dotenv()

class SupabaseClient:
    _instance: Optional[Client] = None
    
    @classmethod
    def get_client(cls) -> Client:
        if cls._instance is None:
            url = os.getenv('SUPABASE_URL')
            key = os.getenv('SUPABASE_KEY')
            
            if not url or not key:
                raise ValueError("SUPABASE_URL and SUPABASE_KEY must be set")
            
            cls._instance = create_client(url, key)
        
        return cls._instance