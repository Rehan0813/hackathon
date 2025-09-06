from supabase import create_client
import os

SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://hksjevwxbvdtchxteiud.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6Imhrc2pldnd4YnZkdGNoeHRlaXVkIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTcxMzY2OTksImV4cCI6MjA3MjcxMjY5OX0.9sdrmVlpB2fj4GsuaAj42aIgkWAiYOtL6vz259qBdXg")

supabase = create_client(SUPABASE_URL, SUPABASE_KEY)
